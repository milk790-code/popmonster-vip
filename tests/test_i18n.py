"""多語版（/en/、/zh-hans/）的基本保證：切句不漏字、佔位符對得上、互相指得到、連結不斷。"""
import difflib
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'i18n'))
import build  # noqa: E402
import config  # noqa: E402
import seg  # noqa: E402

PAGES = config.pages()
GEN = {'en': 'en', 'zh-Hans': 'zh-hans'}


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def generated(lang):
    d = GEN[lang]
    out = [d + '/' + p for p in PAGES]
    if lang == 'zh-Hans':
        out.append(d + '/' + config.ORDER_PAGE)
    return out


# ── 切句與還原 ──

def test_token_check_catches_missing_and_reordered():
    assert seg.check_tokens('<g0>怎麼買</g0>加入', '<g0>How</g0> add') == ''
    assert seg.check_tokens('<g0>怎麼買</g0>加入', 'How add')
    assert seg.check_tokens('<g0>a</g0>', '</g0>a<g0>')
    assert seg.check_tokens('a<x1/>b', 'a b')


@pytest.mark.parametrize('page', PAGES)
def test_identity_render_keeps_every_segment(page):
    """譯文＝原文時，重新切句要得到同一組句子（證明還原沒有吃掉或多出字）"""
    src = read(page)
    _, segs = seg.html_segments(src, page)
    out, missing = seg.render(src, segs, lambda t, k: t)
    assert not missing
    _, again = seg.html_segments(out, page)
    assert sorted(s.key for s in segs) == sorted(s.key for s in again)


@pytest.mark.parametrize('f', config.JS_FILES)
def test_js_identity_render(f):
    src = read(f)
    segs = seg.js_segments(src, where=f)
    out, _ = seg.render(src, segs, lambda t, k: t)
    assert out == src


def test_js_html_attrs_are_translated():
    """JS 字串裡 HTML 標籤的 aria-label／placeholder 要跟著翻，其他字元不動"""
    src = "var a = '<button class=\"x\" aria-label=\"關閉\">✕</button>';"
    segs = seg.js_segments(src)
    assert sorted(s.kind for s in segs) == ['js', 'jsattr']
    out, missing = seg.render(src, segs, lambda t, k: {'關閉': 'Close'}.get(t, t))
    assert not missing
    assert out == "var a = '<button class=\"x\" aria-label=\"Close\">✕</button>';"


def test_unquoted_attr_gets_quotes():
    """原本沒加引號的屬性值，換成有空白的譯文時要補引號，不然瀏覽器只讀到第一個字"""
    src = '<p><img alt=圖片 src=a.png>看這裡</p>'
    _, segs = seg.html_segments(src, 't')

    def look(t, k):
        return t.replace('圖片', 'A photo').replace('看這裡', 'Look here')
    out, missing = seg.render(src, segs, look)
    assert not missing
    assert '<img alt="A photo" src=a.png>Look here' in out
    js = "var a = '<img alt=圖片 src=a.png>';"
    out, _ = seg.render(js, seg.js_segments(js), look)
    assert out == "var a = '<img alt=\"A photo\" src=a.png>';"


def test_js_button_value_is_translated():
    """JS 字串裡 <input type=button value=…> 跟頁面上的一樣要翻（共用同一套判斷）"""
    src = "var a = '<input type=\"submit\" value=\"送出\"><input type=\"text\" value=\"王小明\">';"
    segs = seg.js_segments(src)
    assert [s.text for s in segs if s.kind == 'jsattr'] == ['送出']
    out, _ = seg.render(src, segs, lambda t, k: {'送出': 'Send'}.get(t, t))
    assert 'value="Send"' in out and 'value="王小明"' in out


def test_hans_not_converted_twice():
    """簡中譯文已是簡體，整頁繁轉簡時不能再轉一次（么→幺、显著→显着）"""
    for p in generated('zh-Hans') + ['zh-hans/' + f for f in config.JS_FILES + config.JS_HANS_ONLY]:
        html = read(p)
        assert '幺' not in html and '显着' not in html, p
        assert build.DONE_A not in html and build.DONE_B not in html, p


def test_translation_memory_placeholders_valid():
    tm = json.load(open(os.path.join(config.I18N_DIR, 'en.json'), encoding='utf-8')) \
        if os.path.exists(os.path.join(config.I18N_DIR, 'en.json')) else {}
    bad = {k: seg.check_tokens(v['src'], v['en']) for k, v in tm.items() if v.get('en')}
    bad = {k: v for k, v in bad.items() if v}
    assert not bad, list(bad.items())[:5]
    han = [k for k, v in tm.items() if v.get('en') and not v.get('allow_cjk') and seg.CJK.search(seg.TOKEN_RE.sub('', v['en']))]
    assert not han, han[:5]


def test_hans_overrides_placeholders_valid():
    data = json.load(open(os.path.join(config.I18N_DIR, 'zh-hans.json'), encoding='utf-8'))
    for k, v in data.items():
        if not isinstance(v, dict):
            continue
        assert seg.key_of(v['src']) == k
        assert seg.check_tokens(v['src'], v['zh-Hans']) == '', k


# ── 產出的頁 ──

ALT = re.compile(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">')


@pytest.mark.parametrize('lang', ['zh-Hant', 'en', 'zh-Hans'])
def test_hreflang_reciprocal_and_canonical(lang):
    pages = PAGES if lang == 'zh-Hant' else [p.split('/', 1)[1] for p in generated(lang)]
    for p in pages:
        if lang != 'zh-Hant' and p == config.ORDER_PAGE:
            continue
        path = p if lang == 'zh-Hant' else GEN[lang] + '/' + p
        html = read(path)
        alts = dict(ALT.findall(html))
        assert set(alts) == {'zh-Hant-TW', 'zh-Hans', 'en', 'x-default'}, path
        canon = re.search(r'<link rel="canonical" href="([^"]+)"', html).group(1)
        assert alts[config.LANGS[lang]['hreflang']] == canon, path
        assert alts['x-default'] == alts['zh-Hant-TW']


@pytest.mark.parametrize('lang', ['zh-Hant', 'en', 'zh-Hans'])
def test_one_switch_per_page_with_current_language(lang):
    pages = PAGES if lang == 'zh-Hant' else generated(lang)
    for p in pages:
        if p.endswith(config.ORDER_PAGE):
            continue
        html = read(p)
        assert html.count('class="lang-switch') == 1, p
        cur = re.search(r'<a [^>]*data-lang="([^"]+)" aria-current="true"', html)
        assert cur and cur.group(1) == lang, p
        m = re.search(r'<html lang="([^"]+)"', html)
        assert m.group(1) == config.LANGS[lang]['html_lang'], p


LINK = re.compile(r'\s(?:href|src)="([^"#?]*)(?:[?#][^"]*)?"')


@pytest.mark.parametrize('lang', ['en', 'zh-Hans'])
def test_relative_links_resolve(lang):
    broken = []
    for p in generated(lang):
        html = read(p)
        base = os.path.dirname(p)
        for u in LINK.findall(html):
            if not u or re.match(r'[a-z]+:|//|\{|\$', u) or "'" in u:   # '+src+' 這類是 JS 組出來的
                continue
            target = u[1:] if u.startswith('/') else os.path.normpath(os.path.join(base, u))
            target = build.resolve(target.replace(os.sep, '/'))
            if u.endswith('/') and not target.endswith('index.html'):
                target += '/index.html'
            if not os.path.exists(os.path.join(ROOT, target)):
                broken.append((p, u))
    assert not broken, broken[:10]


@pytest.mark.parametrize('lang', ['en', 'zh-Hans'])
def test_whatsapp_text_goes_to_whatsapp(lang):
    for p in generated(lang):
        root = seg.parse(read(p))
        html = read(p)
        for n in seg.walk(root):
            if isinstance(n, seg.Node) and n.tag == 'a' and 'href' in n.attrs:
                txt = re.sub(r'<[^>]+>', '', html[n.stag_end:n.etag_start])
                href = n.attrs['href'][0]
                if 'WhatsApp' in txt and ('line.me' in href or 'shopee.tw' in href):
                    pytest.fail('%s: 「%s」 still links to %s' % (p, txt.strip(), href))


def test_no_shopee_in_international_nav():
    for lang in GEN:
        for p in generated(lang):
            html = read(p)
            nav = re.search(r'<div class="nav-links">[\s\S]*?</div>', html)
            if nav:
                assert 'shopee.tw' not in nav.group(0), p


def test_no_shopee_links_on_international_pages():
    """海外版一律 WhatsApp：頁面上不能有可點的蝦皮連結（JSON-LD 的 sameAs 是品牌身分，不算）"""
    for lang in GEN:
        for p in generated(lang):
            html = re.sub(r'<script type="application/ld\+json">[\s\S]*?</script>', '', read(p))
            assert not re.search(r'href="[^"]*shopee', html), p


def test_hans_shopee_sentences_not_mangled():
    """簡中「前往蝦皮賣場 → WhatsApp 下單」的替換不能留下蝦皮網址（例：請WhatsApp 下单（shopee.tw/…））"""
    for p in generated('zh-Hans'):
        assert not re.search(r'WhatsApp ?下单（shopee', read(p)), p


def test_en_js_has_no_chinese_strings():
    for f in config.JS_FILES:
        src = read('en/' + f)
        left = [src[a:b] for a, b, q in seg.js_literals(src) if seg.has_cjk(src[a:b])]
        assert not left, (f, left[:5])


SIMPLIFIED_OK = {'么', '著'}


def test_hans_pages_fully_converted():
    if build._CC is None:
        pytest.skip('OpenCC not installed')
    for p in generated('zh-Hans'):
        text = re.sub(r'<details class="lang-switch[\s\S]*?</details>|<!--i18n:menu-->[\s\S]*?<!--/i18n:menu-->',
                      ' ', read(p))  # 語言名稱各用自己的寫法
        text = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>', ' ', text)
        again = build.to_hans(text)
        if again == text:
            continue
        # 再轉一次只准動到「本來就是簡體、OpenCC 卻當繁體再轉」的字（怎么→怎幺、显著→显着）
        sm = difflib.SequenceMatcher(None, text, again, autojunk=False)
        moved = {text[a:b] for op, a, b, c, d in sm.get_opcodes() if op != 'equal'}
        assert moved <= SIMPLIFIED_OK, (p, moved - SIMPLIFIED_OK)


def test_intl_config_in_localized_products_js():
    assert "orderUrl = '../order.html?lang=en'" in read('en/js/products.js')
    assert "orderUrl = 'order.html'" in read('zh-hans/js/products.js')
    assert 'data-intl="1"' in read('zh-hans/order.html')


@pytest.mark.skipif(not shutil.which('node'), reason='node not installed')
def test_generated_js_parses():
    for lang in GEN:
        for f in config.JS_FILES + (config.JS_HANS_ONLY if lang == 'zh-Hans' else []):
            p = os.path.join(ROOT, GEN[lang], f)
            r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
            assert r.returncode == 0, (p, r.stderr[:300])


def test_sitemap_lists_all_languages():
    xml = read('sitemap.xml')
    for lang in GEN:
        assert 'https://popmonster.vip/%s/' % GEN[lang] in xml
    assert 'xmlns:xhtml=' in xml
    assert xml.count('hreflang="x-default"') >= len(PAGES)


def test_whatsapp_links_do_not_show_line_account():
    """海外版改成 WhatsApp 的連結，裡面不能還寫 LINE 帳號；寫 WhatsApp 的按鈕不能連到 LINE"""
    for lang in GEN:
        for p in generated(lang):
            html = read(p)
            for m in re.finditer(r'<a\b[^>]*href="([^"]*)"[^>]*>([\s\S]*?)</a>', html):
                href, txt = m.group(1), re.sub(r'<[^>]+>', '', m.group(2))
                if 'wa.me' in href:
                    assert not re.search(r'LINE|150tiznd', txt), (p, txt.strip()[:80])
                if 'line.me' in href:
                    assert 'WhatsApp' not in txt, (p, txt.strip()[:80])


def test_about_contact_cards_have_no_shopee():
    for lang in GEN:
        html = read(GEN[lang] + '/about.html')
        grid = re.search(r'<div class="ct-grid">([\s\S]*?)</section>', html).group(1)
        assert grid.count('class="ct-card"') == 4
        assert 'Shopee' not in grid and '虾皮' not in grid and '1,657' not in grid
