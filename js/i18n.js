/* 語言切換：記住客人選的語言；瀏覽器語言跟頁面不同時在上方提示一次（不自動跳轉）。
   build.py 會把這支放進每一頁；/en/、/zh-hans/ 共用。 */
(function () {
  var KEY = 'pm_lang_pref';
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  var sw = document.querySelector('.lang-switch');
  var here = (document.documentElement.lang || '').toLowerCase();
  var cur = here.indexOf('en') === 0 ? 'en' : (here === 'zh-hans' ? 'zh-Hans' : 'zh-Hant');

  function remember(l) {
    set(KEY, l);
    set('pm_lang', l === 'en' ? 'en' : 'zh');   // 下單頁的中／英模式跟著走
  }

  var row = document.querySelector('.lang-row');
  if (row) {
    row.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a[data-lang]');
      if (a) remember(a.getAttribute('data-lang'));
    });
  }

  if (sw) {
    sw.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a[data-lang]');
      if (!a) return;
      remember(a.getAttribute('data-lang'));
      if (location.hash && a.getAttribute('href').indexOf('#') < 0) {
        e.preventDefault();
        location.href = a.getAttribute('href') + location.hash;
      }
    });
    document.addEventListener('click', function (e) {
      if (sw.open && !sw.contains(e.target)) sw.open = false;
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && sw.open) { sw.open = false; sw.querySelector('summary').focus(); }
    });
  }

  // 提示：只在客人沒選過語言、也沒關過提示時出現
  if (!sw || get(KEY)) return;
  var langs = navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ''];
  var want = null;
  for (var i = 0; i < langs.length && !want; i++) {
    var l = String(langs[i]).toLowerCase();
    if (/^zh-(hant|tw|hk|mo)/.test(l)) want = 'zh-Hant';
    else if (/^zh/.test(l)) want = 'zh-Hans';
    else if (/^en/.test(l)) want = 'en';
  }
  if (!want) {
    var first = String(langs[0] || '').toLowerCase();
    if (first && first.indexOf('zh') !== 0) want = 'en';   // 其他語系的客人，英文比中文好讀
  }
  if (!want || want === cur) return;
  var link = sw.querySelector('a[data-lang="' + want + '"]');
  if (!link) return;
  var TXT = {
    'en': ['This page is also available in English.', 'English', 'Close'],
    'zh-Hans': ['本页有简体中文版。', '看简体', '关闭'],
    'zh-Hant': ['本頁有繁體中文版。', '看繁體', '關閉']
  }[want];
  var bar = document.createElement('div');
  bar.className = 'lang-hint';
  bar.setAttribute('role', 'region');
  bar.setAttribute('lang', link.getAttribute('lang'));
  bar.setAttribute('aria-label', TXT[1]);
  bar.innerHTML = '<p></p><a></a><button type="button">×</button>';
  bar.querySelector('p').textContent = TXT[0];
  var go = bar.querySelector('a');
  go.href = link.getAttribute('href');
  go.textContent = TXT[1];
  go.addEventListener('click', function () { remember(want); });
  var x = bar.querySelector('button');
  x.setAttribute('aria-label', TXT[2]);
  x.addEventListener('click', function () { remember(cur); bar.remove(); });
  document.body.appendChild(bar);
})();
