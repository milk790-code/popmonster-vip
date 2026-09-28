"""把一頁 HTML（或一支 JS）切成「要翻的句子」，翻完再原位換回去。

做法：不重排、不格式化原檔，只記住每句話在原檔的起訖位置，翻完照位置替換，
所以沒翻到的地方一個字元都不會動。

一句話（segment）的四種來源：
  html   區塊元素裡連續的一段文字＋行內標籤（<b>、<a>、<br> …），標籤換成 <g0>…</g0>、<x1/> 佔位
  attr   alt／title／aria-label／placeholder／meta 描述這類屬性值
  jsonld JSON-LD 裡的字串值（網址、SKU、價格這些不翻）
  js     JS 字串常值（內嵌 <script> 與 js/*.js）
  jsattr JS 字串裡 HTML 標籤的 alt／aria-label／placeholder 這類屬性值（跟著所屬的 js 句一起換）
"""
import hashlib
import html as htmllib
import json
import re
from html.parser import HTMLParser

CJK = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
        'param', 'source', 'track', 'wbr'}
BLOCK = {'html', 'head', 'body', 'title', 'div', 'p', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4',
         'h5', 'h6', 'section', 'article', 'main', 'nav', 'header', 'footer', 'aside', 'table',
         'thead', 'tbody', 'tfoot', 'tr', 'td', 'th', 'caption', 'dl', 'dt', 'dd', 'form',
         'fieldset', 'legend', 'figure', 'figcaption', 'blockquote', 'details', 'summary',
         'pre', 'option', 'optgroup', 'select', 'textarea', 'noscript', 'template', 'svg',
         'text', 'desc', 'address', 'canvas', 'video', 'audio', 'iframe', 'picture', 'label',
         'dialog', 'menu', 'hgroup', 'ruby'}
RAW = {'script', 'style'}
# 這幾類是裝飾字（墨紙占位的大字、印章），各語言都留原字
SKIP_CLASSES = {'ink-ph-char', 'ink-ph-seal', 'lang-switch'}

TRANSLATABLE_ATTRS = {'alt', 'title', 'aria-label', 'placeholder', 'data-cta-a', 'data-cta-b',
                      'aria-description', 'aria-roledescription'}
META_CONTENT_KEYS = {'description', 'keywords', 'og:title', 'og:description', 'og:site_name',
                     'og:image:alt', 'twitter:title', 'twitter:description', 'twitter:image:alt',
                     'apple-mobile-web-app-title', 'application-name'}
JSONLD_SKIP_KEYS = {'@context', '@type', '@id', 'url', 'item', 'sku', 'gtin', 'gtin13', 'mpn',
                    'priceCurrency', 'price', 'availability', 'image', 'logo', 'sameAs',
                    'telephone', 'email', 'inLanguage', 'datePublished', 'dateModified',
                    'priceValidUntil', 'contentUrl', 'thumbnailUrl', 'target', 'urlTemplate'}

ATTR_RE = re.compile(r'''([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?''')
TOKEN_RE = re.compile(r'<(/?)([gx])(\d+)(/?)>')


def has_cjk(s):
    return bool(CJK.search(s or ''))


def norm(s):
    return re.sub(r'\s+', ' ', s).strip()


def key_of(text):
    return hashlib.sha1(norm(text).encode('utf-8')).hexdigest()[:12]


# ───────────────────────── HTML 解析（保留原檔位置） ─────────────────────────

class Node:
    __slots__ = ('tag', 'start', 'stag_end', 'etag_start', 'end', 'children', 'parent', 'attrs')

    def __init__(self, tag, start, stag_end, parent):
        self.tag = tag
        self.start = start          # '<' 的位置
        self.stag_end = stag_end    # 開始標籤結束後的位置
        self.etag_start = None      # 結束標籤 '<' 的位置（沒有結束標籤＝內容結尾）
        self.end = None             # 整個元素結束後的位置
        self.children = []
        self.parent = parent
        self.attrs = {}


class Text:
    __slots__ = ('start', 'end', 'parent')
    tag = '#text'

    def __init__(self, start, end, parent):
        self.start, self.end, self.parent = start, end, parent


class Comment:
    __slots__ = ('start', 'end', 'parent')
    tag = '#comment'

    def __init__(self, start, end, parent):
        self.start, self.end, self.parent = start, end, parent


class _Events(HTMLParser):
    def __init__(self, src):
        super().__init__(convert_charrefs=False)
        self.src = src
        self.ls = [0]
        for m in re.finditer('\n', src):
            self.ls.append(m.end())
        self.ev = []

    def off(self):
        ln, col = self.getpos()
        return self.ls[ln - 1] + col

    def handle_starttag(self, tag, attrs):
        self.ev.append(('start', tag, self.off(), self.get_starttag_text()))

    def handle_startendtag(self, tag, attrs):
        self.ev.append(('void', tag, self.off(), self.get_starttag_text()))

    def handle_endtag(self, tag):
        self.ev.append(('end', tag, self.off(), None))

    def handle_data(self, d):
        self.ev.append(('text', None, self.off(), None))

    def handle_entityref(self, n):
        self.ev.append(('text', None, self.off(), None))

    def handle_charref(self, n):
        self.ev.append(('text', None, self.off(), None))

    def handle_comment(self, d):
        self.ev.append(('comment', None, self.off(), None))

    def handle_decl(self, d):
        self.ev.append(('comment', None, self.off(), None))

    def handle_pi(self, d):
        self.ev.append(('comment', None, self.off(), None))

    def unknown_decl(self, d):
        self.ev.append(('comment', None, self.off(), None))


def parse_attrs(stag):
    """開始標籤字串 → {屬性名: (值, 值在標籤內的起, 訖, 引號)}"""
    out = {}
    m = re.match(r'<[^\s/>]+', stag)
    pos = m.end() if m else 0
    for a in ATTR_RE.finditer(stag, pos):
        name = a.group(1).lower()
        if name in ('/', '>'):
            continue
        for gi, q in ((2, '"'), (3, "'"), (4, '')):
            if a.group(gi) is not None:
                out.setdefault(name, (a.group(gi), a.start(gi), a.end(gi), q))
                break
        else:
            out.setdefault(name, ('', None, None, None))
    return out


IMPLIED_CLOSE = {'li': {'li'}, 'dt': {'dt', 'dd'}, 'dd': {'dt', 'dd'}, 'option': {'option'},
                 'tr': {'tr'}, 'td': {'td', 'th'}, 'th': {'td', 'th'}}
P_CLOSERS = BLOCK - {'label', 'text', 'desc', 'option', 'optgroup', 'select', 'textarea',
                     'canvas', 'video', 'audio', 'iframe', 'picture', 'ruby', 'title'}


def parse(src):
    p = _Events(src)
    p.feed(src)
    p.close()
    ev = p.ev
    root = Node('#root', 0, 0, None)
    stack = [root]
    for i, (kind, tag, off, stag) in enumerate(ev):
        nxt = ev[i + 1][2] if i + 1 < len(ev) else len(src)
        cur = stack[-1]
        if kind == 'text':
            if cur.children and isinstance(cur.children[-1], Text) and cur.children[-1].end == off:
                cur.children[-1].end = nxt
            else:
                cur.children.append(Text(off, nxt, cur))
        elif kind == 'comment':
            cur.children.append(Comment(off, nxt, cur))
        elif kind in ('start', 'void'):
            # 沒寫結束標籤的 <li>、<p> 這類，照瀏覽器規則先收掉
            closers = IMPLIED_CLOSE.get(tag, set())
            if stack[-1].tag in closers:
                _close(stack, stack[-1].tag, off)
            if tag in P_CLOSERS and stack[-1].tag == 'p':
                _close(stack, 'p', off)
            n = Node(tag, off, off + len(stag), stack[-1])
            n.attrs = parse_attrs(stag)
            stack[-1].children.append(n)
            if kind == 'void' or tag in VOID:
                n.etag_start = n.end = n.stag_end
            else:
                stack.append(n)
        elif kind == 'end':
            end = src.find('>', off) + 1 or len(src)
            if any(s.tag == tag for s in stack[1:]):
                while stack[-1].tag != tag:
                    _close(stack, stack[-1].tag, off)
                n = stack.pop()
                n.etag_start, n.end = off, end
    while len(stack) > 1:
        _close(stack, stack[-1].tag, len(src))
    root.end = len(src)
    return root


def _close(stack, tag, off):
    n = stack.pop()
    n.etag_start = n.end = off


def walk(node):
    yield node
    for c in getattr(node, 'children', []):
        yield from walk(c)


def classes(n):
    return set((n.attrs.get('class', ('',))[0] or '').split()) if isinstance(n, Node) else set()


def is_skip(n):
    if not isinstance(n, Node):
        return False
    if 'translate' in n.attrs and n.attrs['translate'][0] == 'no':
        return True
    if 'data-i18n-skip' in n.attrs:
        return True
    return bool(classes(n) & SKIP_CLASSES)


_inline_cache = {}


def inline_only(n):
    if isinstance(n, (Text,)):
        return True
    if isinstance(n, Comment):
        return False
    k = id(n)
    if k in _inline_cache:
        return _inline_cache[k]
    r = n.tag not in BLOCK and n.tag not in RAW and all(inline_only(c) for c in n.children)
    _inline_cache[k] = r
    return r


# ───────────────────────── 切句 ─────────────────────────

class Seg:
    __slots__ = ('kind', 'start', 'end', 'text', 'tokens', 'quote', 'where', 'extra')

    def __init__(self, kind, start, end, text, tokens=None, quote=None, where='', extra=None):
        self.kind, self.start, self.end, self.text = kind, start, end, text
        self.tokens = tokens or {}   # 'g0' → (開始標籤 起,訖, 結束標籤 起,訖)；'x1' → (起,訖)
        self.quote = quote
        self.where = where
        self.extra = extra

    @property
    def key(self):
        return key_of(self.text)


def _run_text(nodes, src, tokens, counter, raw_mode=False):
    out = []
    for n in nodes:
        if isinstance(n, Text):
            t = src[n.start:n.end]
            out.append(t if raw_mode else htmllib.unescape(t))
        elif isinstance(n, Comment):
            i = counter[0]; counter[0] += 1
            tokens['x%d' % i] = (n.start, n.end)
            out.append('<x%d/>' % i)
        elif is_skip(n) or n.tag in VOID or n.tag in RAW:
            i = counter[0]; counter[0] += 1
            tokens['x%d' % i] = (n.start, n.end)
            out.append('<x%d/>' % i)
        else:
            i = counter[0]; counter[0] += 1
            tokens['g%d' % i] = (n.start, n.stag_end, n.etag_start, n.end)
            out.append('<g%d>' % i)
            out.append(_run_text(n.children, src, tokens, counter, raw_mode))
            out.append('</g%d>' % i)
    return ''.join(out)


def _content_text(nodes, src):
    out = []
    for n in nodes:
        if isinstance(n, Text):
            out.append(htmllib.unescape(src[n.start:n.end]))
        elif isinstance(n, Node) and not is_skip(n) and n.tag not in RAW:
            out.append(_content_text(n.children, src))
    return ''.join(out)


def _process_run(nodes, src, segs, where):
    while nodes and isinstance(nodes[0], Text) and not src[nodes[0].start:nodes[0].end].strip():
        nodes = nodes[1:]
    while nodes and isinstance(nodes[-1], Text) and not src[nodes[-1].start:nodes[-1].end].strip():
        nodes = nodes[:-1]
    if not nodes:
        return
    if not has_cjk(_content_text(nodes, src)):
        return
    elems = [n for n in nodes if isinstance(n, Node)]
    texts = [n for n in nodes if isinstance(n, Text)]
    if len(nodes) == 1 and isinstance(nodes[0], Node):
        n = nodes[0]
        if is_skip(n) or n.tag in VOID or n.tag in RAW:
            return
        _process_run(list(n.children), src, segs, where)   # 拆掉外層包裝（<a>、<button>、<span>）
        return
    if len(elems) >= 2 and all(not src[t.start:t.end].strip() for t in texts):
        for e in elems:                                     # 並排的連結、按鈕：一顆一句
            _process_run([e], src, segs, where)
        return
    tokens, counter = {}, [0]
    text = _run_text(nodes, src, tokens, counter)
    segs.append(Seg('html', nodes[0].start, nodes[-1].end, text, tokens, where=where))


def _walk_blocks(n, src, segs, where):
    if isinstance(n, (Text, Comment)) or is_skip(n) or n.tag in RAW:
        return
    run = []
    for c in n.children:
        if isinstance(c, Text) or (isinstance(c, Node) and inline_only(c)):
            run.append(c)
        else:
            _process_run(run, src, segs, where)
            run = []
            if isinstance(c, Node):
                _walk_blocks(c, src, segs, where)
    _process_run(run, src, segs, where)


def attr_translatable(tag, attrs, name):
    """這個標籤的這個屬性要不要翻（頁面 HTML 與 JS 字串裡的標籤共用同一套判斷）"""
    if tag == 'meta' and name == 'content':
        k = (attrs.get('name') or attrs.get('property') or ('',))[0].lower()
        return k in META_CONTENT_KEYS
    if tag == 'input' and name == 'value':
        return attrs.get('type', ('',))[0].lower() in ('button', 'submit', 'reset')
    return name in TRANSLATABLE_ATTRS


def _attr_segs(root, src, segs, where):
    def skipped(n):
        p = n
        while p is not None and p.tag != '#root':
            if is_skip(p):
                return True
            p = p.parent
        return False

    for n in walk(root):
        if not isinstance(n, Node) or n.tag == '#root' or skipped(n):
            continue
        for name, (val, vs, ve, q) in n.attrs.items():
            if vs is None or not has_cjk(val):
                continue
            if attr_translatable(n.tag, n.attrs, name):
                segs.append(Seg('attr', n.start + vs, n.start + ve, htmllib.unescape(val),
                                quote=q, where=where + ' @' + name))


def _jsonld_segs(root, src, segs, where):
    for n in walk(root):
        if isinstance(n, Node) and n.tag == 'script' and \
                (n.attrs.get('type', ('',))[0] or '').lower() == 'application/ld+json':
            body = src[n.stag_end:n.etag_start]
            try:
                data = json.loads(body)
            except ValueError:
                continue
            strings = []

            def visit(o, k=None):
                if isinstance(o, dict):
                    for kk, vv in o.items():
                        visit(vv, kk)
                elif isinstance(o, list):
                    for vv in o:
                        visit(vv, k)
                elif isinstance(o, str) and k not in JSONLD_SKIP_KEYS and has_cjk(o):
                    strings.append(o)
            visit(data)
            for s in strings:
                segs.append(Seg('jsonld', n.stag_end, n.etag_start, s, where=where + ' ld+json'))


def html_segments(src, where=''):
    _inline_cache.clear()
    root = parse(src)
    segs = []
    _walk_blocks(root, src, segs, where)
    _attr_segs(root, src, segs, where)
    _jsonld_segs(root, src, segs, where)
    for n in walk(root):
        if isinstance(n, Node) and n.tag == 'script' and 'src' not in n.attrs and \
                (n.attrs.get('type', ('',))[0] or 'text/javascript').lower() in \
                ('text/javascript', 'module', 'application/javascript', ''):
            for s in js_segments(src, n.stag_end, n.etag_start, where + ' <script>'):
                segs.append(s)
    return root, segs


# ───────────────────────── JS 字串常值 ─────────────────────────

REGEX_PREV = set('(,=:[!&|?{};+-*%<>~^')
REGEX_KW = ('return', 'typeof', 'case', 'do', 'else', 'in', 'of', 'new', 'delete', 'void', 'throw')


def js_literals(src, a=0, b=None):
    """找出 src[a:b] 裡的字串常值 → [(內容起, 內容訖, 引號)]；樣板字串只取沒有 ${} 的。"""
    b = len(src) if b is None else b
    i, out = a, []
    last = ''     # 上一個有意義的字元（判斷 / 是除號還是正規式）
    lastword = ''
    while i < b:
        c = src[i]
        if c in ' \t\r\n':
            i += 1
            continue
        if src.startswith('//', i):
            j = src.find('\n', i)
            i = b if j < 0 or j > b else j
            continue
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            i = b if j < 0 else j + 2
            continue
        if src.startswith('<!--', i) or src.startswith('-->', i):
            i += 3 if src.startswith('-->', i) else 4
            continue
        if c in '\'"`':
            j = i + 1
            interp = False
            while j < b and src[j] != c:
                if src[j] == '\\':
                    j += 2
                    continue
                if c == '`' and src.startswith('${', j):
                    interp = True
                    depth = 0
                    while j < b:
                        if src[j] == '{':
                            depth += 1
                        elif src[j] == '}':
                            depth -= 1
                            if depth == 0:
                                break
                        j += 1
                if c != '`' and src[j] == '\n':
                    break
                j += 1
            if not interp:
                out.append((i + 1, j, c))
            i = j + 1
            last, lastword = 'str', ''
            continue
        if c == '/':
            if last in REGEX_PREV or last == '' or lastword in REGEX_KW:
                j = i + 1
                cls = False
                while j < b:
                    if src[j] == '\\':
                        j += 2
                        continue
                    if src[j] == '[':
                        cls = True
                    elif src[j] == ']':
                        cls = False
                    elif src[j] == '/' and not cls:
                        break
                    elif src[j] == '\n':
                        break
                    j += 1
                j += 1
                while j < b and (src[j].isalpha()):
                    j += 1
                i = j
                last, lastword = 'regex', ''
                continue
            last, lastword = '/', ''
            i += 1
            continue
        m = re.match(r'[A-Za-z_$][\w$]*', src[i:i + 64])
        if m:
            lastword = m.group(0)
            last = 'id'
            i += len(lastword)
            continue
        if c.isdigit():
            m = re.match(r'[0-9.xXa-fA-F_eEn]+', src[i:i + 64])
            i += len(m.group(0))
            last, lastword = 'num', ''
            continue
        last, lastword = c, ''
        i += 1
    return out


_JS_ESC = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}


def js_unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            d = s[i + 1]
            if d == 'u' and s[i + 2:i + 3] == '{':
                j = s.index('}', i)
                out.append(chr(int(s[i + 3:j], 16)))
                i = j + 1
                continue
            if d == 'u':
                out.append(chr(int(s[i + 2:i + 6], 16)))
                i += 6
                continue
            if d == 'x':
                out.append(chr(int(s[i + 2:i + 4], 16)))
                i += 4
                continue
            if d == '\n':
                i += 2
                continue
            out.append(_JS_ESC.get(d, d))
            i += 2
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def js_escape(s, q):
    s = s.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r')
    if q in ('"', "'"):
        s = s.replace(q, '\\' + q)
    elif q == '`':
        s = s.replace('`', '\\`').replace('${', '\\${')
    return s.replace('</script', '<\\/script')


def _frag_tokens(text):
    """JS 字串裡的完整標籤換成佔位：成對的 <gN>…</gN>，其他（半截、單獨的）<xN/>。"""
    parts = re.split(r'(<[A-Za-z/][^<>]*>)', text)
    tokens, out, stack, n = {}, [], [], 0
    for p in parts:
        m = re.match(r'<(/?)([A-Za-z][\w-]*)[^<>]*?(/?)>$', p)
        if not m:
            out.append(p)
            continue
        closing, name, selfclose = m.group(1), m.group(2).lower(), m.group(3)
        if closing:
            for k in range(len(stack) - 1, -1, -1):
                if stack[k][0] == name:
                    idx = stack[k][1]
                    del stack[k:]
                    tokens['g%d' % idx] = (tokens['g%d' % idx][0], p)
                    out.append('</g%d>' % idx)
                    break
            else:
                tokens['x%d' % n] = (p,)
                out.append('<x%d/>' % n)
                n += 1
        elif selfclose or name in VOID:
            tokens['x%d' % n] = (p,)
            out.append('<x%d/>' % n)
            n += 1
        else:
            tokens['g%d' % n] = (p, None)
            stack.append((name, n))
            out.append('<g%d>' % n)
            n += 1
    # 沒配對到結束標籤的開始標籤改成單獨佔位
    text = ''.join(out)
    for name, idx in stack:
        tokens['x%d' % idx] = (tokens.pop('g%d' % idx)[0],)
        text = text.replace('<g%d>' % idx, '<x%d/>' % idx)
    return text, tokens


def js_segments(src, a=0, b=None, where=''):
    segs = []
    for s, e, q in js_literals(src, a, b):
        raw = src[s:e]
        if not has_cjk(raw):
            continue
        val = js_unescape(raw)
        lead, core, tail = split_code_edges(val)
        text, tokens = _frag_tokens(core)
        segs.append(Seg('js', s, e, text, tokens, quote=q, where=where, extra=(lead, tail)))
        for t in tokens.values():
            for name, v in _tag_attr_texts(t[0]):
                segs.append(Seg('jsattr', s, e, v, quote=q, where=where))
    return segs


def _tag_attr_texts(tag):
    """一個開始標籤裡要翻的屬性 → [(屬性名, 值)]（值已解 HTML 實體）"""
    out, attrs = [], parse_attrs(tag)
    for name, (val, vs, ve, q) in attrs.items():
        if vs is not None and has_cjk(val) and attr_translatable(_tag_name(tag), attrs, name):
            out.append((name, htmllib.unescape(val)))
    return out


def _tag_name(tag):
    m = re.match(r'<([^\s/>]+)', tag)
    return m.group(1).lower() if m else ''


def _tr_tag_attrs(tag, table):
    """把開始標籤裡的屬性值照 table（原文 → (譯文, wrap)）換掉，其他字元不動"""
    if not table:
        return tag
    edits, attrs = [], parse_attrs(tag)
    for name, (val, vs, ve, q) in attrs.items():
        if vs is not None and attr_translatable(_tag_name(tag), attrs, name):
            hit = table.get(htmllib.unescape(val))
            if hit is not None:
                tr, wrap = hit
                edits.append((vs, ve, wrap(attr_value(tr, q))))
    return apply_edits(tag, edits)


def split_code_edges(val):
    """JS 字串常把半截標籤接在文字前後（'" style="x">去逛全部商品</a>'、'說明<a href="'）。
    把頭尾那段程式碼切出來原樣保留，只翻中間。"""
    m = CJK.search(val)
    first = m.start() if m else 0
    lead = ''
    gt = val.find('>')
    lt = val.find('<')
    if 0 <= gt < first and (lt < 0 or lt > gt):
        lead = val[:gt + 1]
    last = max(i for i, ch in enumerate(val) if CJK.match(ch)) if m else len(val)
    tail = ''
    lt = val.rfind('<')
    if lt > last and val.find('>', lt) < 0:
        tail = val[lt:]
    return lead, val[len(lead):len(val) - len(tail)], tail


# ───────────────────────── 套回翻譯 ─────────────────────────

class MissingTranslation(Exception):
    pass


def check_tokens(src_text, tr_text):
    """佔位符要一個不少、一個不多；成對的要先開後關。回傳錯誤訊息（空字串＝沒問題）"""
    want = sorted(m.group(0) for m in TOKEN_RE.finditer(src_text))
    got = sorted(m.group(0) for m in TOKEN_RE.finditer(tr_text))
    if want != got:
        return 'placeholders differ: want %s got %s' % (want, got)
    for m in TOKEN_RE.finditer(src_text):
        if m.group(2) == 'g' and not m.group(1):
            a = tr_text.find('<g%s>' % m.group(3))
            b = tr_text.find('</g%s>' % m.group(3))
            if b < a:
                return 'g%s closes before it opens' % m.group(3)
    return ''


def esc_text(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def esc_attr(s, q):
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if q == "'":
        return s.replace("'", '&#39;')
    return s.replace('"', '&quot;')


def attr_value(tr, q):
    """換掉屬性值（只換值、不含外面的引號）。原本沒加引號的值，譯文多半有空白，要補上引號。"""
    if not q:
        return '"' + esc_attr(tr, '"') + '"'
    return esc_attr(tr, q)


def _fill(tr, tokens_fn, text_fn):
    out, pos = [], 0
    for m in TOKEN_RE.finditer(tr):
        out.append(text_fn(tr[pos:m.start()]))
        out.append(tokens_fn(m))
        pos = m.end()
    out.append(text_fn(tr[pos:]))
    return ''.join(out)


def apply_edits(src, edits):
    edits = sorted(edits, key=lambda e: (e[0], e[1]))
    out, pos = [], 0
    for s, e, rep in edits:
        if s < pos:
            raise ValueError('overlapping edits at %d' % s)
        out.append(src[pos:s])
        out.append(rep)
        pos = e
    out.append(src[pos:])
    return ''.join(out)


def render(src, segs, lookup, strict=True, jsonld_fix=None, wrap=None):
    """lookup(text, kind) → 譯文或 None。strict 時缺譯文就丟 MissingTranslation。
    wrap：把每段譯文包起來（簡中用來標記「已經轉好」的字，整頁繁轉簡時跳過，免得轉兩次）。
    只包譯文本身，原頁搬過來的標籤與內容不包。"""
    missing = []
    wrap = wrap or (lambda x: x)

    def get(seg):
        tr = lookup(seg.text, seg.kind)
        if tr is None:
            missing.append(seg)
            return None
        return tr

    attr_edits = []
    for s in segs:
        if s.kind == 'attr':
            tr = get(s)
            if tr is not None:
                attr_edits.append((s.start, s.end, wrap(attr_value(tr, s.quote))))

    js_attr = {}   # (字串起, 訖) → {屬性原文: (譯文, wrap)}
    for s in segs:
        if s.kind == 'jsattr':
            tr = get(s)
            if tr is not None and tr != s.text:
                js_attr.setdefault((s.start, s.end), {})[s.text] = (tr, wrap)

    def span(a, b):
        inner = [e for e in attr_edits if a <= e[0] and e[1] <= b]
        return apply_edits(src[a:b], [(x - a, y - a, r) for x, y, r in inner])

    edits, covered = [], []
    for s in segs:
        if s.kind == 'html':
            tr = get(s)
            if tr is None:
                continue
            toks = s.tokens

            def tok(m, toks=toks):
                k = m.group(2) + m.group(3)
                t = toks[k]
                if k[0] == 'x':
                    return span(t[0], t[1])
                return span(t[0], t[1]) if not m.group(1) else src[t[2]:t[3]]
            edits.append((s.start, s.end, _fill(tr, tok, lambda x: wrap(esc_text(x)) if x else x)))
            covered.append((s.start, s.end))
        elif s.kind == 'js':
            tr = get(s)
            if tr is None:
                continue
            toks, table = s.tokens, js_attr.get((s.start, s.end))

            def jtok(m, toks=toks, table=table):
                k = m.group(2) + m.group(3)
                t = toks[k]
                if k[0] == 'x':
                    return _tr_tag_attrs(t[0], table)
                return _tr_tag_attrs(t[0], table) if not m.group(1) else t[1]
            # 翻譯庫存的是去掉頭尾空白的句子；原字串頭尾的空白是拿來接數字的，要補回去
            if s.text[:1].isspace() and not tr[:1].isspace():
                tr = ' ' + tr
            if s.text[-1:].isspace() and not tr[-1:].isspace():
                tr = tr + ' '
            val = _fill(tr, jtok, lambda x: wrap(x) if x else x)
            lead, tail = s.extra or ('', '')
            edits.append((s.start, s.end, js_escape(lead + val + tail, s.quote)))
    for e in attr_edits:
        if not any(a <= e[0] and e[1] <= b for a, b in covered):
            edits.append(e)
    # JSON-LD：同一支 script 裡所有字串一起換，重寫整段
    by_block = {}
    for s in segs:
        if s.kind == 'jsonld':
            by_block.setdefault((s.start, s.end), []).append(s)
    for (a, b), ss in by_block.items():
        data = json.loads(src[a:b])
        table = {}
        for s in ss:
            tr = get(s)
            if tr is not None:
                table[s.text] = wrap(tr)

        def sub(o, k=None):
            if isinstance(o, dict):
                return {kk: sub(vv, kk) for kk, vv in o.items()}
            if isinstance(o, list):
                return [sub(vv, k) for vv in o]
            if isinstance(o, str) and k not in JSONLD_SKIP_KEYS and o in table:
                return table[o]
            return o
        data = sub(data)
        if jsonld_fix:
            data = jsonld_fix(data)
        body = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
        edits.append((a, b, body))
    if missing and strict:
        raise MissingTranslation(missing)
    return apply_edits(src, edits), missing
