"""把英文翻譯庫（i18n/en.json）缺的句子，用 Claude API 補齊。

  python3 scripts/i18n/translate.py              補齊所有缺的、以及原文改過的句子
  python3 scripts/i18n/translate.py --dry-run    只算要翻幾句、分幾批，不呼叫 API
  python3 scripts/i18n/translate.py --limit 50   最多翻 50 句（試跑用）

需要環境變數 ANTHROPIC_API_KEY（GitHub Actions 用 repo secret）。
翻譯守則在 i18n/glossary.md，整份放在 system prompt 並開快取，所以每一批只付一次全價。
人工改過的句子（en.json 裡 "manual": true）永遠不會被覆蓋。
"""
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(__file__))
import config  # noqa: E402
import seg  # noqa: E402
from extract import collect, load_tm, save_tm  # noqa: E402

MODEL = os.environ.get('I18N_MODEL', 'claude-sonnet-5')
BATCH_SEGS = 40          # 一批最多幾句
BATCH_CHARS = 6000       # 一批原文最多幾個字
WORKERS = 4
RETRIES = 2              # 驗證沒過的句子，單獨再翻幾次

FORMAT_RULES = """
## Input and output format

You will receive a JSON object {"segments": [{"id", "kind", "page", "text"}]}.
- kind "html": visible page text. "attr": an alt/title/aria-label/meta value. "jsonld": structured
  data for search engines. "js": a string inside JavaScript that the page shows to users.
- page: where the text appears (helps you pick the right register; a*.html are product pages,
  guide/* are how-to guides).
Return {"items": [{"id", "en"}]} with exactly one item per input id, same ids, nothing else.
If a segment is only a brand name, number or symbol that needs no translation, return it as is
with Chinese brand names replaced by their English names from the table.
The English must not contain any Chinese characters or full-width punctuation (use | : , ( ) + ~).
"""

SCHEMA = {
    'type': 'object',
    'properties': {
        'items': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {'id': {'type': 'string'}, 'en': {'type': 'string'}},
                'required': ['id', 'en'],
                'additionalProperties': False,
            },
        },
    },
    'required': ['items'],
    'additionalProperties': False,
}


def system_prompt():
    with open(os.path.join(config.I18N_DIR, 'glossary.md'), encoding='utf-8') as f:
        return f.read().strip() + '\n' + FORMAT_RULES


def validate(src, en):
    """回傳錯誤訊息；空字串＝可以收"""
    if not en or not en.strip():
        return 'empty translation'
    err = seg.check_tokens(src, en)
    if err:
        return err
    if seg.CJK.search(seg.TOKEN_RE.sub('', en)):
        return 'Chinese characters left in the English'
    return ''


FULLWIDTH = {'｜': ' | ', '：': ': ', '，': ', ', '（': ' (', '）': ') ', '＋': '+', '～': '~', '；': '; '}


def ascii_punct(en):
    """模型偶爾把全形標點照抄過來，英文版換成半形"""
    for a, b in FULLWIDTH.items():
        en = en.replace(a, b)
    return re.sub(r' {2,}', ' ', en).replace(' )', ')').replace('( ', '(')


def keep_edges(src, en):
    """JS 片段前後的空白是拿來接數字的，照原文補回去"""
    lead = src[:len(src) - len(src.lstrip())]
    tail = src[len(src.rstrip()):]
    core = en.strip()
    return (' ' if lead else '') + core + (' ' if tail else '')


def batches(items):
    cur, size = [], 0
    for it in items:
        if cur and (len(cur) >= BATCH_SEGS or size + len(it['text']) > BATCH_CHARS):
            yield cur
            cur, size = [], 0
        cur.append(it)
        size += len(it['text'])
    if cur:
        yield cur


def call(client, system, items, note=''):
    import anthropic
    payload = {'segments': [{'id': it['key'], 'kind': it['kind'], 'page': it['pages'][0],
                             'text': it['text']} for it in items]}
    user = json.dumps(payload, ensure_ascii=False)
    if note:
        user += '\n\n' + note
    for attempt in range(4):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=[{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}],
                messages=[{'role': 'user', 'content': user}],
                output_config={'effort': 'medium', 'format': {'type': 'json_schema', 'schema': SCHEMA}},
            )
        except anthropic.RateLimitError as e:
            wait = int(e.response.headers.get('retry-after', '30'))
            time.sleep(min(wait, 120))
            continue
        except anthropic.APIStatusError as e:
            if e.status_code >= 500 and attempt < 3:
                time.sleep(10 * (attempt + 1))
                continue
            raise
        except anthropic.APIConnectionError:
            if attempt < 3:
                time.sleep(10 * (attempt + 1))
                continue
            raise
        if resp.stop_reason == 'refusal':
            return {}, resp.usage
        if resp.stop_reason == 'max_tokens':
            if len(items) > 1:   # 太長：拆兩半再翻
                h = len(items) // 2
                a, ua = call(client, system, items[:h], note)
                b, _ = call(client, system, items[h:], note)
                a.update(b)
                return a, ua
            return {}, resp.usage
        text = next((b.text for b in resp.content if b.type == 'text'), '{}')
        try:
            out = json.loads(text)
        except ValueError:
            return {}, resp.usage
        return {i['id']: i['en'] for i in out.get('items', []) if isinstance(i, dict)}, resp.usage
    return {}, None


def todo_items(tm):
    items = collect()
    todo = []
    for it in items:
        e = tm.get(it['key'])
        if e and e.get('manual'):
            continue
        if e and e.get('en') and e.get('src') == it['text']:
            continue
        todo.append(it)
    return items, todo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    tm = load_tm('en')
    items, todo = todo_items(tm)
    if a.limit:
        todo = todo[:a.limit]
    groups = list(batches(todo))
    print('要翻 %d 句（共 %d 句），分 %d 批，模型 %s' % (len(todo), len(items), len(groups), MODEL),
          file=sys.stderr)
    if a.dry_run or not todo:
        return 0
    if not os.environ.get('ANTHROPIC_API_KEY') and not os.environ.get('ANTHROPIC_AUTH_TOKEN'):
        print('沒有 ANTHROPIC_API_KEY，跳過翻譯', file=sys.stderr)
        return 2

    import anthropic
    client = anthropic.Anthropic()
    system = system_prompt()
    by_key = {it['key']: it for it in todo}
    done, failed = {}, {}
    stats = {'in': 0, 'cache_read': 0, 'cache_write': 0, 'out': 0}

    def account(u):
        if u is None:
            return
        stats['in'] += u.input_tokens or 0
        stats['out'] += u.output_tokens or 0
        stats['cache_read'] += getattr(u, 'cache_read_input_tokens', 0) or 0
        stats['cache_write'] += getattr(u, 'cache_creation_input_tokens', 0) or 0

    def accept(res):
        for k, en in res.items():
            if k not in by_key:
                continue
            src = by_key[k]['text']
            en = ascii_punct(en)
            if by_key[k]['kind'] == 'js':
                en = keep_edges(src, en)
            err = validate(src, en)
            if err:
                failed[k] = err
            else:
                done[k] = en
                failed.pop(k, None)

    # 第一批先單獨跑，讓 system prompt 寫進快取，後面平行的批次才讀得到
    res, u = call(client, system, groups[0])
    account(u)
    accept(res)
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = [ex.submit(call, client, system, g) for g in groups[1:]]
        for n, f in enumerate(as_completed(futs), 2):
            res, u = f.result()
            account(u)
            accept(res)
            print('  批次 %d/%d 完成，已收 %d 句' % (n, len(groups), len(done)), file=sys.stderr)

    for r in range(RETRIES):
        left = [by_key[k] for k in by_key if k not in done]
        if not left:
            break
        print('第 %d 輪重翻 %d 句' % (r + 1, len(left)), file=sys.stderr)
        for it in left:
            why = failed.get(it['key'], 'missing from your previous answer')
            note = ('Your previous translation of this segment was rejected: %s. Keep every placeholder '
                    'exactly once and write no Chinese characters.' % why)
            res, u = call(client, system, [it], note)
            account(u)
            accept(res)

    for k, en in done.items():
        tm[k] = {'src': by_key[k]['text'], 'en': en, 'model': MODEL}
    save_tm(tm, 'en')
    miss = [k for k in by_key if k not in done]
    print('完成：新增 %d 句，失敗 %d 句｜tokens 輸入 %d、快取讀 %d、快取寫 %d、輸出 %d' % (
        len(done), len(miss), stats['in'], stats['cache_read'], stats['cache_write'], stats['out']),
        file=sys.stderr)
    for k in miss[:30]:
        print('  失敗 %s %s ← %s' % (k, by_key[k]['text'][:60], failed.get(k, 'no answer')), file=sys.stderr)
    return 1 if miss else 0


if __name__ == '__main__':
    sys.exit(main())
