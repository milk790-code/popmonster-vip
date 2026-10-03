"""產生 /en/ 與 /zh-hans/ 全站，並在繁中原頁補上語言切換與 hreflang。

  python3 scripts/i18n/build.py           產生（英文缺譯的句子先留中文，列出清單）
  python3 scripts/i18n/build.py --strict  英文有任何一句缺譯就失敗（CI 用）
  python3 scripts/i18n/build.py --check   只檢查產出是不是最新的，不寫檔（CI 用）

英文：i18n/en.json（翻譯庫，key＝原句雜湊）逐句替換。
簡中：OpenCC tw2sp 整頁轉換；i18n/zh-hans.json 放人工改寫的句子（結帳、聯絡方式這類海外流程不同的地方）。
"""
import argparse
import json
import os
import posixpath
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import config  # noqa: E402
import seg  # noqa: E402
from extract import load_tm  # noqa: E402

ROOT = config.ROOT
DOMAIN = config.DOMAIN

try:
    import opencc
    try:
        _CC = opencc.OpenCC('tw2sp')
    except Exception:  # 官方 OpenCC 套件的設定檔名要帶 .json
        _CC = opencc.OpenCC('tw2sp.json')
except ImportError:  # pragma: no cover
    _CC = None


def to_hans(s):
    if _CC is None:
        raise SystemExit('需要 OpenCC：pip install opencc-python-reimplemented')
    return _CC.convert(s)


# 簡中：譯文（查表、OpenCC、覆寫都已是簡體）先用這兩個私用字元包起來，
# 整頁繁轉簡時跳過，不然已經是簡體的字會再被轉一次（么→幺、显著→显着）
DONE_A, DONE_B = '\ue000', '\ue001'
_DONE_RE = re.compile(DONE_A + '(.*?)' + DONE_B, re.S)


def mark_done(s):
    return DONE_A + s + DONE_B


def hans_rest(s):
    """把沒標記的部分（原頁搬來的標籤、id、註解、裝飾字）轉簡體，標記過的原樣保留"""
    parts = _DONE_RE.split(s)
    out = ''.join(x if i % 2 else to_hans(x) for i, x in enumerate(parts))
    if DONE_A in out or DONE_B in out:
        raise SystemExit('簡中標記沒配對，檢查 seg.render 的 wrap')
    return out


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def write(p, s, check, changed):
    fp = os.path.join(ROOT, p)
    old = None
    if os.path.exists(fp):
        with open(fp, encoding='utf-8') as f:
            old = f.read()
    if old == s:
        return
    changed.append(p)
    if check:
        return
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(s)


# ───────────────────────── 網址 ─────────────────────────

def page_url(p, lang):
    """頁面的正式網址：index.html → /；guide/index.html → /guide/"""
    d = config.LANGS[lang]['dir']
    path = p
    if path == 'index.html':
        path = ''
    elif path.endswith('/index.html'):
        path = path[:-len('index.html')]
    return DOMAIN + '/' + (d + '/' if d else '') + path


def root_url(p, lang):
    return page_url(p, lang)[len(DOMAIN):]


def resolve(target):
    """把連結目標正規化成檔案路徑：'' → index.html、'guide/' → guide/index.html、'go' → go.html"""
    if target in ('', '.', './'):
        return 'index.html'
    if target.endswith('/'):
        return target + 'index.html'
    if '.' not in posixpath.basename(target):
        if os.path.exists(os.path.join(ROOT, target + '.html')):
            return target + '.html'
        if os.path.isdir(os.path.join(ROOT, target)):
            return target + '/index.html'
    return target


class Linker:
    def __init__(self, lang, localized):
        self.lang = lang
        self.dir = config.LANGS[lang]['dir']
        self.localized = localized      # 這個語言有自己版本的檔案（頁與 JS）
        self.redirect = config.REDIRECT_LINKS.get(lang, {})

    def map(self, u, page):
        if not u or u.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:', 'blob:', '{', '$')):
            return u
        m = re.match(r'https?://popmonster\.vip(/[^?#]*)?(.*)$', u)
        absdom = bool(m)
        if m:
            path, rest = m.group(1) or '/', m.group(2)
        elif re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:|//', u):
            return u
        else:
            mm = re.match(r'([^?#]*)(.*)$', u)
            path, rest = mm.group(1), mm.group(2)
        rooted = path.startswith('/')
        if rooted:
            target = path[1:]
        else:
            if path == '':
                return u    # 只有 ?query 或 #hash
            target = posixpath.normpath(posixpath.join(posixpath.dirname(page), path))
            if target.startswith('..'):
                return u
            if path.endswith('/'):
                target += '/'
        t = resolve(target)
        depth = page.count('/') + 1
        if t in self.redirect:
            r = self.redirect[t]
            extra = '' if '?' in r and rest.startswith('?') else rest
            if absdom:
                return DOMAIN + '/' + r + extra
            return '../' * depth + r + extra
        if t in self.localized:
            if absdom:
                return DOMAIN + '/' + self.dir + path + rest
            if rooted:
                return '/' + self.dir + path + rest
            return u
        if absdom or rooted:
            return u
        return '../' + u

    def srcset(self, v, page):
        parts = []
        for item in v.split(','):
            bits = item.strip().split()
            if bits:
                bits[0] = self.map(bits[0], page)
            parts.append(' '.join(bits))
        return ', '.join(parts)

    def css(self, v, page):
        return re.sub(r'url\((["\']?)([^"\')]+)\1\)',
                      lambda m: 'url(%s%s%s)' % (m.group(1), self.map(m.group(2), page), m.group(1)), v)


ASSET_LIT = re.compile(r'^(img|css|js|assets|vendor|fonts|share)/')


def js_asset_paths(src):
    """在地化 JS 裡的相對素材路徑（img/…）多退一層，因為頁面搬進了 /en/、/zh-hans/"""
    edits = []
    for s, e, q in seg.js_literals(src):
        v = src[s:e]
        if ASSET_LIT.match(v):
            edits.append((s, e, '../' + v))
    return seg.apply_edits(src, edits)


# ───────────────────────── 語言切換與 hreflang ─────────────────────────

ALT_RE = re.compile(r'<!--i18n:alt-->[\s\S]*?<!--/i18n:alt-->\n?')
SW_RE = re.compile(r'([ \t]*)<!--i18n:switch-->[\s\S]*?<!--/i18n:switch-->(\n?)')
MENU_RE = re.compile(r'([ \t]*)<!--i18n:menu-->[\s\S]*?<!--/i18n:menu-->(\n?)')
OLD_ALT_RE = re.compile(r'[ \t]*<link\s+rel="alternate"\s+hreflang="[^"]*"\s+href="[^"]*"\s*/?>\n?')
SW_ARIA = {'zh-Hant': '切換語言', 'zh-Hans': '切换语言', 'en': 'Change language'}


def alt_urls(p):
    """各語言版本的網址。下單頁的英文版是 ?lang=en（它自己有中英模式）"""
    if p == config.ORDER_PAGE:
        return {'zh-Hant': DOMAIN + '/order.html', 'en': DOMAIN + '/order.html?lang=en',
                'zh-Hans': DOMAIN + '/zh-hans/order.html'}
    return {l: page_url(p, l) for l in config.LANGS}


def alt_block(p):
    urls = alt_urls(p)
    lines = ['<!--i18n:alt-->']
    for l in ('zh-Hant', 'zh-Hans', 'en'):
        lines.append('<link rel="alternate" hreflang="%s" href="%s">' % (config.LANGS[l]['hreflang'], urls[l]))
    lines.append('<link rel="alternate" hreflang="x-default" href="%s">' % urls['zh-Hant'])
    lines.append('<link rel="stylesheet" href="/css/i18n.css">')
    lines.append('<script src="/js/i18n.js" defer></script>')
    lines.append('<!--/i18n:alt-->')
    return '\n'.join(lines) + '\n'


GLOBE = ('<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">'
         '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.6"/>'
         '<path d="M3 12h18M12 3c2.6 2.8 3.9 5.8 3.9 9s-1.3 6.2-3.9 9c-2.6-2.8-3.9-5.8-3.9-9S9.4 5.8 12 3z" '
         'fill="none" stroke="currentColor" stroke-width="1.6"/></svg>')


def switch_block(p, lang, floating):
    urls = alt_urls(p)
    cur = config.LANGS[lang]
    items = []
    for l in ('zh-Hant', 'zh-Hans', 'en'):
        L = config.LANGS[l]
        u = urls[l][len(DOMAIN):] or '/'
        items.append('<a href="%s" hreflang="%s" lang="%s" data-lang="%s"%s>%s<small>%s</small></a>' % (
            u, L['hreflang'], L['html_lang'], l, ' aria-current="true"' if l == lang else '',
            L['label'], L['name']))
    cls = 'lang-switch' + (' lang-float' if floating else '')
    return ('<!--i18n:switch--><details class="%s" data-i18n-skip><summary aria-label="%s">%s<span>%s</span></summary>'
            '<div class="lang-menu">%s</div></details><!--/i18n:switch-->' % (
                cls, SW_ARIA[lang], GLOBE, cur['label'], ''.join(items)))


def menu_block(p, lang):
    """手機版：語言選項放進 ☰ 選單最下面（導覽列放不下第四顆按鈕）"""
    urls = alt_urls(p)
    items = []
    for l in ('zh-Hant', 'zh-Hans', 'en'):
        L = config.LANGS[l]
        u = urls[l][len(DOMAIN):] or '/'
        items.append('<a href="%s" hreflang="%s" lang="%s" data-lang="%s"%s>%s</a>' % (
            u, L['hreflang'], L['html_lang'], l, ' aria-current="true"' if l == lang else '', L['name']))
    return ('<!--i18n:menu--><div class="lang-row" data-i18n-skip role="group" aria-label="%s">%s</div>'
            '<!--/i18n:menu-->' % (SW_ARIA[lang], ''.join(items)))


def inject(src, p, lang):
    """放 hreflang 區塊與語言切換鈕（重跑會先拿掉舊的再放，結果一樣）"""
    s = ALT_RE.sub('', src)
    s = SW_RE.sub('', s)
    s = MENU_RE.sub('', s)
    s = OLD_ALT_RE.sub('', s)
    block = alt_block(p)
    m = re.search(r'<link\s+rel="canonical"[^>]*>\n?', s)
    if m:
        at = m.end()
        if not s[m.start():m.end()].endswith('\n'):
            block = '\n' + block
    else:
        at = s.find('</head>')
    s = s[:at] + block + s[at:]
    if p == config.ORDER_PAGE:
        return s    # 下單頁自己有「中文／EN」切換列
    m = re.search(r'<button[^>]*class="nav-menu-btn"', s)
    if m and '<div class="nav-inner"' in s[:m.start()]:
        ls = s.rfind('\n', 0, m.start()) + 1
        indent = s[ls:m.start()] if not s[ls:m.start()].strip() else ''
        at = ls if indent or ls == m.start() else m.start()
        s = s[:at] + indent + switch_block(p, lang, False) + '\n' + s[at:]
        mm = re.search(r'<div class="mobile-menu"[^>]*>[\s\S]*?(\n?)([ \t]*)</div>', s)
        if mm:
            at = mm.start(2)
            s = s[:at] + mm.group(2) + '  ' + menu_block(p, lang) + '\n' + s[at:]
    else:
        m = re.search(r'<body[^>]*>\n?', s)
        s = s[:m.end()] + switch_block(p, lang, True) + '\n' + s[m.end():]
    return s


# ───────────────────────── 一頁在地化 ─────────────────────────

PAGE_TYPES = {'WebPage', 'Article', 'BlogPosting', 'WebSite', 'FAQPage', 'CollectionPage', 'AboutPage',
              'HowTo', 'ItemPage', 'ContactPage'}


def set_in_language(body, code):
    """JSON-LD 的頁面類節點標上 inLanguage（已有的改成這個語言）"""
    try:
        d = json.loads(body)
    except ValueError:
        return body

    def fix(o):
        if isinstance(o, dict):
            t = o.get('@type')
            ts = set(t) if isinstance(t, list) else {t}
            if 'inLanguage' in o or ts & PAGE_TYPES:
                o['inLanguage'] = code
            for v in o.values():
                fix(v)
        elif isinstance(o, list):
            for v in o:
                fix(v)
    fix(d)
    return json.dumps(d, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

WHATSAPP = config.WHATSAPP
LINE_CHAT = 'line.me/R/ti/p/@150tiznd'
# 改成 WhatsApp 的連結裡，卡片角落還寫著 LINE 帳號的字一起換掉
WA_TEXT = [
    (re.compile(r'(?:打开|开启|打開|開啟) ?LINE ?@150tiznd'), '打开 WhatsApp'),
    (re.compile(r'Open LINE ?@150tiznd', re.I), 'Open WhatsApp'),
    (re.compile(r'LINE (?:Official Account|OA)'), 'WhatsApp'),
    (re.compile(r'LINE ?官方(?:帐号|账号|帳號)'), 'WhatsApp'),
    (re.compile(r'@150tiznd'), '+886-970-527-037'),
]


def localize_page(html, p, lang, linker):
    root = seg.parse(html)
    edits = []
    cur = config.LANGS[lang]

    def attr_edit(n, name, newval):
        val, vs, ve, q = n.attrs[name]
        if vs is None or newval == val:
            return
        edits.append((n.start + vs, n.start + ve, seg.attr_value(newval, q)))

    def text_of(n):
        return re.sub(r'<[^>]+>', '', html[n.stag_end:n.etag_start]).strip()

    def ancestor(n, cls):
        x = n.parent
        while x is not None and x.tag != '#root':
            if cls in seg.classes(x):
                return x
            x = x.parent
        return None

    def in_class(n, cls):
        return ancestor(n, cls) is not None

    def wa_text(n):
        for t in seg.walk(n):
            if isinstance(t, seg.Text):
                old = new = html[t.start:t.end]
                for rx, to in WA_TEXT:
                    new = rx.sub(to, new)
                if new != old:
                    edits.append((t.start, t.end, new))

    def drop(x):
        # 整個元素拿掉；它那一行只剩空白的話，連行首縮排和換行一起拿掉
        a, b = x.start, x.end
        ls = html.rfind('\n', 0, a) + 1
        if not html[ls:a].strip() and html[b:b + 1] == '\n':
            a, b = ls, b + 1
        edits[:] = [e for e in edits if not (a <= e[0] and e[1] <= b)]
        edits.append((a, b, ''))
        dropped.append((a, b))

    dropped = []
    for n in seg.walk(root):
        if not isinstance(n, seg.Node) or n.tag == '#root':
            continue
        if any(a0 <= n.start < b0 for a0, b0 in dropped):
            continue
        a = n.attrs
        if n.tag == 'html' and 'lang' in a:
            attr_edit(n, 'lang', cur['html_lang'])
            continue
        if n.tag == 'link' and 'href' in a:
            rel = a.get('rel', ('',))[0].lower()
            if rel == 'canonical':
                attr_edit(n, 'href', page_url(p, lang) if p != config.ORDER_PAGE else DOMAIN + '/zh-hans/order.html')
                continue
            if rel == 'alternate':
                continue
        if n.tag == 'meta' and 'content' in a:
            k = (a.get('property') or a.get('name') or ('',))[0].lower()
            if k == 'og:url':
                attr_edit(n, 'content', page_url(p, lang) if p != config.ORDER_PAGE else DOMAIN + '/zh-hans/order.html')
            elif k == 'og:locale':
                attr_edit(n, 'content', cur['og'])
            elif (a.get('http-equiv') or ('',))[0].lower() == 'refresh':
                v = a['content'][0]
                mm = re.match(r'(\s*\d+\s*;\s*url=)(.*)$', v, re.I)
                if mm:
                    attr_edit(n, 'content', mm.group(1) + linker.map(mm.group(2), p))
            continue
        # 聯絡與購買管道：海外版改 WhatsApp（翻譯後文字已經寫 WhatsApp 的才換，文字仍是 LINE／Shopee 的照舊）
        if n.tag == 'a' and 'href' in a:
            href = a['href'][0]
            txt = text_of(n)
            if 'shopee.tw' in href and any(in_class(n, c) for c in ('footer-links', 'nav-links', 'mobile-menu')):
                drop(n)
                continue
            if 'shopee.tw' in href and in_class(n, 'c-row'):   # 品牌簡報聯絡頁：蝦皮那一列整列拿掉
                drop(ancestor(n, 'c-row'))
                continue
            if 'shopee.tw' in href and 'ct-card' in seg.classes(n):   # 關於頁聯絡卡：蝦皮那張拿掉
                drop(n)
                continue
            if LINE_CHAT in href and not re.search(r'(?<![A-Za-z])(?:LINE|Line)(?![A-Za-z])|WhatsApp', txt) and \
                    'WhatsApp' in text_of(n.parent):
                txt = 'WhatsApp'   # 按鈕只寫「立即前往」，旁邊那句說的是 WhatsApp
            if ('shopee.tw' in href or LINE_CHAT in href) and 'WhatsApp' in txt:
                attr_edit(n, 'href', WHATSAPP)
                if 'rel' in a:
                    attr_edit(n, 'rel', 'noopener')
                wa_text(n)
                continue
        for name in ('href', 'src', 'action', 'poster', 'data-src', 'data-href'):
            if name in a and a[name][1] is not None:
                attr_edit(n, name, linker.map(a[name][0], p))
        for name in ('srcset', 'data-srcset'):
            if name in a and a[name][1] is not None:
                attr_edit(n, name, linker.srcset(a[name][0], p))
        if 'style' in a and 'url(' in a['style'][0]:
            attr_edit(n, 'style', linker.css(a['style'][0], p))
        if n.tag == 'style' and n.etag_start:
            body = html[n.stag_end:n.etag_start]
            if 'url(' in body:
                edits.append((n.stag_end, n.etag_start, linker.css(body, p)))
        if n.tag == 'script' and n.etag_start and 'src' not in a:
            body = html[n.stag_end:n.etag_start]
            typ = (a.get('type', ('',))[0] or '').lower()
            if typ == 'application/ld+json':
                nb = re.sub(r'https?://popmonster\.vip/[^"\s\\]*', lambda m: linker.map(m.group(0), p), body)
                nb = set_in_language(nb, cur['hreflang'])
                if nb != body:
                    edits.append((n.stag_end, n.etag_start, nb))
            elif typ in ('', 'text/javascript', 'module'):
                nb = js_asset_paths(body)
                if nb != body:
                    edits.append((n.stag_end, n.etag_start, nb))
    out = seg.apply_edits(html, edits)
    out = ALT_RE.sub(lambda m: alt_block(p), out)
    out = SW_RE.sub(lambda m: m.group(1) + switch_block(p, lang, 'lang-float' in m.group(0)) + m.group(2), out)
    out = MENU_RE.sub(lambda m: m.group(1) + menu_block(p, lang) + m.group(2), out)
    if lang == 'en':   # 沒有中文字所以沒被切成句子的標籤（例：<li>LINE：），全形冒號換半形
        out = re.sub(r'(>[A-Za-z][\w .&-]{0,30})：', r'\1: ', out)
    return out


# ───────────────────────── 主流程 ─────────────────────────

def load_hans_overrides():
    fp = os.path.join(config.I18N_DIR, 'zh-hans.json')
    if not os.path.exists(fp):
        return {}
    return {k: v['zh-Hans'] for k, v in json.load(open(fp, encoding='utf-8')).items()
            if isinstance(v, dict) and seg.key_of(v.get('src', '')) == k}


def load_hans_phrases():
    fp = os.path.join(config.I18N_DIR, 'zh-hans.phrases.json')
    if not os.path.exists(fp):
        return []
    return [(re.compile(a), b) for a, b in json.load(open(fp, encoding='utf-8'))['rules']]


def load_hans_keep():
    """OpenCC tw2sp 會換錯的詞（核心→内核、堆疊→堆栈…）：[(繁體, 要的簡體)]，長的先換"""
    fp = os.path.join(config.I18N_DIR, 'zh-hans.phrases.json')
    if not os.path.exists(fp):
        return []
    keep = json.load(open(fp, encoding='utf-8')).get('keep', [])
    return sorted(((a, b) for a, b in keep), key=lambda x: -len(x[0]))


def to_hans_keep(s, keep):
    """繁轉簡，但 keep 裡的詞先換成私用字元躲過 OpenCC，轉完再換成指定的簡體"""
    for i, (a, b) in enumerate(keep):
        s = s.replace(a, chr(0xE100 + i))
    s = to_hans(s)
    for i, (a, b) in enumerate(keep):
        s = s.replace(chr(0xE100 + i), b)
    return s


def en_lookup(tm, missing_log, where):
    def look(text, kind):
        e = tm.get(seg.key_of(text))
        if e and e.get('en'):
            return e['en']
        missing_log.append((where, seg.norm(text)))
        return None
    return look


def hans_lookup(over, phrases, keep=()):
    def look(text, kind):
        k = seg.key_of(text)
        if k in over:
            return over[k]
        t = to_hans_keep(text, keep)
        for rx, rep in phrases:
            t = rx.sub(rep, t)
        return t
    return look


def intl_config(lang):
    order = config.REDIRECT_LINKS[lang]['order.html']
    if order.startswith(config.LANGS[lang]['dir'] + '/'):
        order = order[len(config.LANGS[lang]['dir']) + 1:]
    else:
        order = '../' + order
    return ("\n/* 海外版（build.py 產生）：購物車改到下單頁用 WhatsApp，運費依國家報價 */\n"
            "window.PM_CONFIG.intl = true;\nwindow.PM_CONFIG.orderUrl = '%s';\n" % order)


def build(strict=False, check=False):
    tm = load_tm('en')
    over = load_hans_overrides()
    phrases = load_hans_phrases()
    keep = load_hans_keep()
    pages = config.pages()
    changed, missing = [], []

    # 1. 繁中原頁：補 hreflang 與切換鈕
    for p in pages + [config.ORDER_PAGE]:
        src = read(p)
        write(p, inject(src, p, 'zh-Hant'), check, changed)
    src_of = {p: inject(read(p), p, 'zh-Hant') for p in pages + [config.ORDER_PAGE]}

    for lang in config.TARGETS:
        d = config.LANGS[lang]['dir']
        localized = set(pages) | set(config.JS_FILES)
        if lang == 'zh-Hans':
            localized |= {config.ORDER_PAGE} | set(config.JS_HANS_ONLY)
        linker = Linker(lang, localized)
        todo = list(pages) + ([config.ORDER_PAGE] if lang == 'zh-Hans' else [])
        for p in todo:
            src = src_of[p]
            _, segs = seg.html_segments(src, p)
            if lang == 'en':
                out, _ = seg.render(src, segs, en_lookup(tm, missing, p), strict=False)
            else:
                out, _ = seg.render(src, segs, hans_lookup(over, phrases, keep), strict=False, wrap=mark_done)
                out = hans_rest(out)
            out = localize_page(out, p, lang, linker)
            if lang == 'zh-Hans' and p == config.ORDER_PAGE:
                out = out.replace('<html lang="zh-Hans"', '<html lang="zh-Hans" data-intl="1"', 1)
            write(d + '/' + p, out, check, changed)
        for f in config.JS_FILES + (config.JS_HANS_ONLY if lang == 'zh-Hans' else []):
            src = read(f)
            segs = seg.js_segments(src, where=f)
            if lang == 'en':
                out, _ = seg.render(src, segs, en_lookup(tm, missing, f), strict=False)
            else:
                out, _ = seg.render(src, segs, hans_lookup(over, phrases, keep), strict=False, wrap=mark_done)
                out = hans_rest(out)
            out = js_asset_paths(out)
            if f == 'js/products.js':
                out += intl_config(lang)
            write(d + '/' + f, out, check, changed)

    write('sitemap.xml', sitemap(read('sitemap.xml'), pages), check, changed)

    miss = sorted(set(missing))
    if miss:
        print('英文缺譯 %d 句（先留中文）：' % len(miss), file=sys.stderr)
        for w, t in miss[:40]:
            print('  %s  %s' % (w, t[:70]), file=sys.stderr)
    if check and changed:
        print('產出不是最新的，請跑 python3 scripts/i18n/build.py：', file=sys.stderr)
        for c in changed[:30]:
            print('  ' + c, file=sys.stderr)
        return 1
    if strict and miss:
        return 1
    print('完成：%d 個檔案有變動，英文缺譯 %d 句' % (len(changed), len(miss)), file=sys.stderr)
    return 0


def sitemap(xml, pages):
    """每個有多語版的網址補上 xhtml:link 互指，並加入 /en/、/zh-hans/ 的網址"""
    xml = re.sub(r'\s*<url>\s*<loc>https://popmonster\.vip/(?:en|zh-hans)/[\s\S]*?</url>', '', xml)
    xml = re.sub(r'\s*<xhtml:link [^>]*/>', '', xml)
    if 'xmlns:xhtml' not in xml:
        xml = xml.replace('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
                          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                          'xmlns:xhtml="http://www.w3.org/1999/xhtml"', 1)
    by_url = {page_url(p, 'zh-Hant'): p for p in pages}
    by_url[DOMAIN + '/order.html'] = config.ORDER_PAGE
    blocks = list(re.finditer(r'<url>([\s\S]*?)</url>', xml))
    out, pos, extra = [], 0, []
    for b in blocks:
        loc = re.search(r'<loc>([^<]+)</loc>', b.group(1)).group(1).strip()
        p = by_url.get(loc)
        out.append(xml[pos:b.start()])
        if not p:
            out.append(b.group(0))
            pos = b.end()
            continue
        urls = alt_urls(p)
        links = ''.join('\n    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>' % (
            config.LANGS[l]['hreflang'], urls[l].replace('&', '&amp;')) for l in ('zh-Hant', 'zh-Hans', 'en'))
        links += '\n    <xhtml:link rel="alternate" hreflang="x-default" href="%s"/>' % urls['zh-Hant']
        inner = b.group(1).rstrip()
        out.append('<url>' + inner + links + '\n  </url>')
        pos = b.end()
        lastmod = re.search(r'<lastmod>[^<]+</lastmod>', inner)
        for l in ('zh-Hans', 'en'):
            if '?' in urls[l]:
                continue
            extra.append('  <url>\n    <loc>%s</loc>%s%s\n  </url>' % (
                urls[l], ('\n    ' + lastmod.group(0)) if lastmod else '', links))
    out.append(xml[pos:])
    xml = ''.join(out)
    return xml.replace('</urlset>', '\n'.join(extra) + '\n</urlset>', 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    sys.exit(build(strict=a.strict, check=a.check))


if __name__ == '__main__':
    main()
