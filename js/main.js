/* ═══ POP MONSTER 共用行為 · js/main.js ═══ */
(function () {
  'use strict';

  /* View Transitions：跳過轉場時的良性 rejection 靜音 */
  window.addEventListener('unhandledrejection', function (e) {
    var m = e.reason && (e.reason.message || String(e.reason));
    if (m && m.indexOf('Transition was skipped') !== -1) e.preventDefault();
  });

  /* 手機選單（覆蓋舊 inline onclick，避免雙重觸發） */
  document.querySelectorAll('.nav-menu-btn').forEach(function (btn) {
    btn.onclick = null;
    btn.addEventListener('click', function () {
      var m = btn.nextElementSibling;
      if (!m || !m.classList.contains('mobile-menu')) m = document.querySelector('.mobile-menu');
      if (!m) return;
      var open = m.classList.toggle('show');
      m.setAttribute('aria-hidden', String(!open));
    });
  });

  /* FAQ 手風琴（事件委派，全站通用） */
  document.addEventListener('click', function (ev) {
    var q = ev.target.closest('.faq-q');
    if (!q) return;
    var item = q.closest('.faq-item');
    var wasOpen = item.classList.contains('open');
    document.querySelectorAll('.faq-item.open').forEach(function (i) { i.classList.remove('open'); });
    if (!wasOpen) item.classList.add('open');
  });

  /* 進場動畫 */
  var els = document.querySelectorAll('.fi,.fade-up');
  if ('IntersectionObserver' in window) {
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); obs.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    els.forEach(function (el) { obs.observe(el); });
  } else {
    els.forEach(function (el) { el.classList.add('in'); });
  }

  /* 商品即時搜尋（首頁） */
  var searchInput = document.getElementById('pm-search');
  if (searchInput) {
    var ctEl = document.getElementById('pm-search-ct');
    searchInput.addEventListener('input', function () {
      var q = searchInput.value.trim().toLowerCase();
      var shown = 0;
      document.querySelectorAll('#products .p-card').forEach(function (card) {
        var hit = !q || card.textContent.toLowerCase().indexOf(q) !== -1;
        card.style.display = hit ? '' : 'none';
        if (hit) shown++;
      });
      document.querySelectorAll('#products .cat-block').forEach(function (blk) {
        var any = Array.prototype.some.call(blk.querySelectorAll('.p-card'), function (c) { return c.style.display !== 'none'; });
        blk.style.display = any ? '' : 'none';
      });
      var strip = document.querySelector('.flow-strip');
      if (strip) strip.style.display = q ? 'none' : '';
      if (ctEl) ctEl.textContent = q ? '找到 ' + shown + ' 款' : '';
    });
  }

  /* Cookie 同意列 */
  var bar = document.querySelector('.cookie-bar');
  if (bar) {
    var choice = null;
    try { choice = localStorage.getItem('pm_cookie'); } catch (e) {}
    if (!choice) bar.classList.add('show');
    function decide(v) {
      try { localStorage.setItem('pm_cookie', v); } catch (e) {}
      bar.classList.remove('show');
      if (v === 'y' && typeof gtag === 'function') {
        gtag('consent', 'update', { analytics_storage: 'granted' });
      }
    }
    var acc = document.getElementById('ck-accept');
    var dec = document.getElementById('ck-decline');
    if (acc) acc.addEventListener('click', function () { decide('y'); });
    if (dec) dec.addEventListener('click', function () { decide('n'); });
    if (choice === 'y' && typeof gtag === 'function') {
      gtag('consent', 'update', { analytics_storage: 'granted' });
    }
  }

  /* 商品圖載入失敗 → 優雅占位（金色 SKU 字樣） */
  function imgFallback(img) {
    if (!(img instanceof HTMLImageElement) || img.dataset.fbDone) return;
    img.dataset.fbDone = '1';
    var label = (img.getAttribute('data-sku') || img.alt || 'POP MONSTER').slice(0, 12);
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800">' +
      '<rect width="800" height="800" fill="#f4efe3"/>' +
      '<rect x="1" y="1" width="798" height="798" fill="none" stroke="rgba(27,23,18,.25)" stroke-width="2"/>' +
      '<text x="400" y="380" font-family="Space Mono, monospace" font-size="34" font-weight="700" letter-spacing="8" fill="#9e3a2b" text-anchor="middle">POP MONSTER</text>' +
      '<text x="400" y="440" font-family="Space Mono, monospace" font-size="22" letter-spacing="6" fill="#938a78" text-anchor="middle">' + label.replace(/[<>&]/g, '') + '</text></svg>';
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }
  document.addEventListener('error', function (ev) { imgFallback(ev.target); }, true);
  /* 掃描在本腳本執行前就已載入失敗的圖 */
  Array.prototype.forEach.call(document.images, function (img) {
    if (img.complete && img.naturalWidth === 0 && img.src) imgFallback(img);
  });
})();
