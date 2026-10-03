"""多語系設定：哪些頁、哪些 JS、有哪些語言。

原文（繁中）一律放在根目錄，是唯一正本；/en/、/zh-hans/ 全部由 build.py 產生，不要手改。
"""
import glob
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DOMAIN = 'https://popmonster.vip'
I18N_DIR = os.path.join(ROOT, 'i18n')

# code：網址資料夾；hreflang：搜尋引擎用；html_lang：<html lang>；og：og:locale
LANGS = {
    'zh-Hant': {'dir': '', 'hreflang': 'zh-Hant-TW', 'html_lang': 'zh-Hant-TW', 'og': 'zh_TW',
                'label': '繁中', 'name': '繁體中文'},
    'zh-Hans': {'dir': 'zh-hans', 'hreflang': 'zh-Hans', 'html_lang': 'zh-Hans', 'og': 'zh_CN',
                'label': '简中', 'name': '简体中文'},
    'en': {'dir': 'en', 'hreflang': 'en', 'html_lang': 'en', 'og': 'en_US',
           'label': 'EN', 'name': 'English'},
}
TARGETS = ['en', 'zh-Hans']

# 對外公開、要出多語版的頁（tools/、share/、go 接線台、下單頁另有處理）
PAGES_FIXED = ['index.html', 'about.html', 'brand.html', 'brand-deck.html', 'brand-totem.html',
               'members.html', 'systems.html', 'privacy.html', 'terms.html',
               'ai-encyclopedia.html', 'free-guide.html']
# thanks.html 是台灣匯款訂單的確認頁，海外流程（WhatsApp）不會走到，不出多語版
# 下單頁：英文沿用它自己的 ?lang=en 模式；簡中另出一份（見 build.py）
ORDER_PAGE = 'order.html'
# 這幾支 JS 有給客人看的中文字，各語言各出一份放在 /<lang>/js/
JS_FILES = ['js/products.js', 'js/store.js', 'js/main.js', 'js/home.js']
# 只轉簡體、不翻英文的 JS（下單頁用）
JS_HANS_ONLY = ['products_catalog.js']

# 各語言的頁面換路：原本連到這些頁的，改連到哪裡（相對網站根目錄）
REDIRECT_LINKS = {
    'en': {'cart.html': 'order.html?lang=en', 'order.html': 'order.html?lang=en',
           'go.html': 'go-en', 'go': 'go-en'},
    'zh-Hans': {'cart.html': 'zh-hans/order.html', 'order.html': 'zh-hans/order.html',
                'go.html': 'go-en', 'go': 'go-en'},   # 繁中接線台只有 LINE；海外一律 WhatsApp
}

WHATSAPP = 'https://wa.me/886970527037'


def pages():
    ps = list(PAGES_FIXED)
    ps += sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, 'a[0-9][0-9][0-9].html')))
    ps += sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, 'guide', '*.html')))
    return [p for p in ps if os.path.exists(os.path.join(ROOT, p))]
