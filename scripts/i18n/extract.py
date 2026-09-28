"""掃過所有要出多語版的頁與 JS，列出每一句要翻的話 → i18n/source.json。

  python3 scripts/i18n/extract.py            更新 source.json
  python3 scripts/i18n/extract.py --missing  只列出英文翻譯庫（i18n/en.json）還沒有的句子
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import config  # noqa: E402
import seg  # noqa: E402


def collect():
    """回傳 [(key, text, kind, where)]，照第一次出現的順序、同一句只留一筆。"""
    seen, out = {}, []

    def add(s, where):
        k = s.key
        if k in seen:
            seen[k]['pages'].append(where)
            return
        seen[k] = {'key': k, 'text': seg.norm(s.text), 'kind': 'attr' if s.kind == 'jsattr' else s.kind,
                   'pages': [where]}
        out.append(seen[k])

    for p in config.pages():
        src = open(os.path.join(config.ROOT, p), encoding='utf-8').read()
        _, segs = seg.html_segments(src, p)
        for s in segs:
            add(s, p)
    for f in config.JS_FILES:
        src = open(os.path.join(config.ROOT, f), encoding='utf-8').read()
        for s in seg.js_segments(src, where=f):
            add(s, f)
    for item in out:
        item['pages'] = sorted(set(item['pages']))
    return out


def load_tm(lang='en'):
    p = os.path.join(config.I18N_DIR, lang + '.json')
    if not os.path.exists(p):
        return {}
    return json.load(open(p, encoding='utf-8'))


def save_tm(tm, lang='en'):
    p = os.path.join(config.I18N_DIR, lang + '.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(dict(sorted(tm.items())), f, ensure_ascii=False, indent=1)
        f.write('\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--missing', action='store_true')
    a = ap.parse_args()
    items = collect()
    os.makedirs(config.I18N_DIR, exist_ok=True)
    with open(os.path.join(config.I18N_DIR, 'source.json'), 'w', encoding='utf-8') as f:
        json.dump({'segments': items}, f, ensure_ascii=False, indent=1)
        f.write('\n')
    tm = load_tm('en')
    miss = [i for i in items if i['key'] not in tm]
    if a.missing:
        for i in miss:
            print(i['key'], i['text'][:80])
    print('segments: %d · 英文已有: %d · 缺: %d' % (len(items), len(items) - len(miss), len(miss)),
          file=sys.stderr)


if __name__ == '__main__':
    main()
