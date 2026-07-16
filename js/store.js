/* ═══════════════════════════════════════════════════════
   POP MONSTER 官網購物車引擎 · js/store.js
   純前端（無後端）：localStorage 購物車 → LINE 官方帳號下單
   依賴：js/products.js（PM_CONFIG / PM_PRODUCTS）、css/store.css
   ═══════════════════════════════════════════════════════ */
(function () {
  'use strict';
  var CFG = window.PM_CONFIG || {};
  var LIST = window.PM_PRODUCTS || [];
  var BYSKU = {};
  LIST.forEach(function (p) { BYSKU[p.sku] = p; });

  var LS_CART = 'pm_cart_v1';
  var LS_ORDERS = 'pm_orders_v1';

  /* ── 工具 ── */
  function $(s, r) { return (r || document).querySelector(s); }
  function $all(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function nt(n) { return 'NT$' + Number(n).toLocaleString('zh-Hant-TW'); }
  function track(ev, params) { try { if (typeof gtag === 'function') gtag('event', ev, params || {}); } catch (e) {} }

  /* ── 購物車狀態 ── */
  function load() {
    try { var c = JSON.parse(localStorage.getItem(LS_CART)); if (c && c.items) return c; } catch (e) {}
    return { items: {} };
  }
  function save(cart) {
    cart.updated = Date.now();
    try { localStorage.setItem(LS_CART, JSON.stringify(cart)); } catch (e) {}
  }
  var cart = load();

  function entries() {
    return Object.keys(cart.items).filter(function (k) { return BYSKU[k] && cart.items[k] > 0; })
      .map(function (k) { return { sku: k, qty: cart.items[k], p: BYSKU[k] }; });
  }
  function count() { return entries().reduce(function (a, e) { return a + e.qty; }, 0); }
  function pricedSubtotal() {
    return entries().reduce(function (a, e) { return a + (e.p.price ? e.p.price * e.qty : 0); }, 0);
  }
  function hasUnpriced() { return entries().some(function (e) { return !e.p.price; }); }
  function shipFee(sub) {
    if (!entries().length) return 0;
    return sub >= (CFG.freeShipAt || 2000) ? 0 : (CFG.shipFee || 0);
  }

  /* ── API ── */
  function add(sku, qty) {
    sku = String(sku).toUpperCase();
    if (!BYSKU[sku]) return;
    qty = Math.max(1, parseInt(qty, 10) || 1);
    cart.items[sku] = Math.min(99, (cart.items[sku] || 0) + qty);
    save(cart); refresh();
    var p = BYSKU[sku];
    toast('<span class="ck">✓</span> 已加入：' + esc(p.name) + ' <a href="#" data-pm-open-cart>查看購物車</a>');
    track('add_to_cart', { currency: 'TWD', value: p.price || 0, items: [{ item_id: sku, item_name: p.name, quantity: qty || 1 }] });
  }
  function setQty(sku, qty) {
    if (qty <= 0) delete cart.items[sku]; else cart.items[sku] = Math.min(99, qty);
    save(cart); refresh();
  }
  function clearCart() { cart = { items: {} }; save(cart); refresh(); }

  /* ── Toast ── */
  var toastEl, toastTimer;
  function toast(html) {
    if (!toastEl) { toastEl = document.createElement('div'); toastEl.className = 'pm-toast'; toastEl.setAttribute('role', 'status'); toastEl.setAttribute('aria-live', 'polite'); document.body.appendChild(toastEl); }
    toastEl.innerHTML = html;
    toastEl.classList.add('on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('on'); }, 3400);
  }

  /* ── Nav 按鈕 / FAB / 抽屜 DOM 注入 ── */
  function injectUI() {
    var inner = $('.nav-inner');
    if (inner && !$('.nav-cart-btn')) {
      var b = document.createElement('button');
      b.className = 'nav-cart-btn';
      b.setAttribute('aria-label', 'CART 購物車');
      b.innerHTML = '<span class="t">購物車</span><span class="nav-cart-badge" aria-hidden="true"></span>';
      var menuBtn = $('.nav-menu-btn', inner);
      inner.insertBefore(b, menuBtn || null);
      b.addEventListener('click', function () { openDrawer(); });
    }
    if (!$('.pm-fab')) {
      var f = document.createElement('button');
      f.className = 'pm-fab';
      f.setAttribute('aria-label', '購物車');
      f.innerHTML = '🛒<span class="pm-fab-badge">0</span>';
      f.addEventListener('click', openDrawer);
      document.body.appendChild(f);
    }
    if (!$('.pm-overlay')) {
      var o = document.createElement('div');
      o.className = 'pm-overlay';
      o.addEventListener('click', closeDrawer);
      document.body.appendChild(o);
      var d = document.createElement('aside');
      d.className = 'pm-drawer';
      d.setAttribute('aria-label', '購物車');
      d.innerHTML =
        '<div class="pm-dw-head"><h3>購物車<span class="ct" data-pm-count></span></h3><button class="pm-dw-close" aria-label="關閉">✕</button></div>' +
        '<div class="pm-ship-bar" data-pm-shipbar><div class="t" data-pm-shiptxt></div><div class="pm-ship-track"><div class="pm-ship-fill" data-pm-shipfill></div></div></div>' +
        '<div class="pm-dw-items" data-pm-items></div>' +
        '<div class="pm-dw-foot" data-pm-foot></div>';
      document.body.appendChild(d);
      $('.pm-dw-close', d).addEventListener('click', closeDrawer);
    }
  }
  function openDrawer() { renderDrawer(); $('.pm-overlay').classList.add('on'); $('.pm-drawer').classList.add('on'); document.body.style.overflow = 'hidden'; track('view_cart'); }
  function closeDrawer() { $('.pm-overlay').classList.remove('on'); $('.pm-drawer').classList.remove('on'); document.body.style.overflow = ''; }

  /* ── 品項 HTML（抽屜與結帳頁共用） ── */
  function itemRow(e) {
    var priceHtml = e.p.price
      ? '<div class="pm-item-price">' + nt(e.p.price) + (e.qty > 1 ? ' ×' + e.qty : '') + '</div>'
      : '<div class="pm-item-price tbd">價格由 LINE 報價</div>';
    var thumb = e.p.img
      ? '<img class="pm-item-img" src="' + esc(e.p.img) + '" alt="' + esc(e.p.name) + '" loading="lazy" onerror="this.style.visibility=\'hidden\'">'
      : '<span class="pm-item-img pm-item-ph" aria-hidden="true">' + esc(e.p.name.charAt(0)) + '</span>';
    return '<div class="pm-item" data-sku="' + e.sku + '">' + thumb +
      '<div class="pm-item-info"><div class="pm-item-sku">' + e.sku + ' · ' + esc(e.p.cat) + '</div>' +
      '<div class="pm-item-name">' + esc(e.p.name) + '</div>' + priceHtml + '</div>' +
      '<div class="pm-item-right"><div class="pm-qty">' +
      '<button data-pm-dec aria-label="減少">−</button><span>' + e.qty + '</span><button data-pm-inc aria-label="增加">＋</button>' +
      '</div><button class="pm-item-rm" data-pm-rm>移除</button></div></div>';
  }

  function totalsHtml(sub, fee) {
    var un = hasUnpriced();
    var h = '<div class="pm-row"><span>商品小計</span><b>' + (sub ? nt(sub) : (un ? '待報價' : nt(0))) + (un && sub ? '＋待報價' : '') + '</b></div>';
    h += '<div class="pm-row"><span>運費（' + esc(CFG.shipLabel || '宅配到府') + '）</span><b>' + (fee === 0 && sub >= (CFG.freeShipAt || 2000) ? '免運' : (un && !sub ? '結帳時計算' : nt(fee))) + '</b></div>';
    h += '<div class="pm-row total"><span>合計</span><b>' + (un ? (sub ? nt(sub + fee) + '＋' : '') + '待報價' : nt(sub + fee)) + '</b></div>';
    if (un) h += '<div class="pm-note">部分商品價格待補，送出訂單後由小編透過 LINE 回覆總金額。</div>';
    return h;
  }

  function shipBarHtml() {
    var sub = pricedSubtotal(), goal = CFG.freeShipAt || 2000;
    var txtEl = $('[data-pm-shiptxt]'), fillEl = $('[data-pm-shipfill]');
    if (!txtEl) return;
    if (!entries().length) { txtEl.innerHTML = '滿 <b>' + nt(goal) + '</b> 免運費'; fillEl.style.width = '0%'; return; }
    if (sub >= goal) { txtEl.innerHTML = '<b>已達免運門檻 ✓</b>'; fillEl.style.width = '100%'; }
    else { txtEl.innerHTML = '再買 <b>' + nt(goal - sub) + '</b> 即享免運'; fillEl.style.width = Math.min(100, sub / goal * 100) + '%'; }
  }

  /* ── 抽屜渲染 ── */
  function renderDrawer() {
    var es = entries();
    var itemsEl = $('[data-pm-items]'), footEl = $('[data-pm-foot]'), ctEl = $('[data-pm-count]');
    if (!itemsEl) return;
    ctEl.textContent = es.length ? '· ' + count() + ' 件' : '';
    if (!es.length) {
      itemsEl.innerHTML = '<div class="pm-empty"><div class="big">🛒</div><p>購物車還是空的<br>把喜歡的商品加進來吧</p></div>';
      footEl.innerHTML = '<a class="btn btn-outline" href="' + (CFG.base || '') + 'index.html#products" style="width:100%">去逛全部商品</a>';
    } else {
      itemsEl.innerHTML = es.map(itemRow).join('');
      var sub = pricedSubtotal(), fee = shipFee(sub);
      footEl.innerHTML = totalsHtml(sub, fee) +
        '<a class="btn btn-gold" href="' + (CFG.base || '') + 'cart.html">前往結帳 →</a>' +
        '<button class="btn btn-outline" data-pm-continue style="width:100%">繼續選購</button>';
      $('[data-pm-continue]', footEl).addEventListener('click', closeDrawer);
    }
    shipBarHtml();
  }

  /* ── 徽章 ── */
  function refreshBadges() {
    var c = count();
    $all('.nav-cart-badge').forEach(function (b) { b.textContent = c > 0 ? c : ''; b.classList.toggle('on', c > 0); });
    $all('.nav-cart-btn').forEach(function (b) { b.setAttribute('aria-label', 'CART 購物車，' + c + ' 件商品'); });
    var fab = $('.pm-fab');
    if (fab) { fab.classList.toggle('has', c > 0); $('.pm-fab-badge', fab).textContent = c; }
  }

  function refresh() {
    refreshBadges();
    if ($('.pm-drawer.on')) renderDrawer();
    if ($('#pm-cart-root')) renderCartPage();
  }

  /* ── 訂單編號與訂單文字 ── */
  function orderId() {
    var d = new Date();
    var ymd = String(d.getFullYear()).slice(2) + String(d.getMonth() + 1).padStart(2, '0') + String(d.getDate()).padStart(2, '0');
    var r = Math.random().toString(36).slice(2, 6).toUpperCase();
    return 'PM-' + ymd + '-' + r;
  }
  function buildOrderText(oid, form) {
    var es = entries();
    var sub = pricedSubtotal(), fee = shipFee(sub), un = hasUnpriced();
    var L = [];
    L.push('🛒 泡泡怪獸官網訂單');
    L.push('訂單編號：' + oid);
    L.push('────────────');
    es.forEach(function (e, i) {
      var line = (i + 1) + '. ' + e.p.name + '（' + e.sku + '）× ' + e.qty;
      if (e.p.price) line += '＝' + nt(e.p.price * e.qty); else line += '（請報價）';
      L.push(line);
    });
    L.push('────────────');
    L.push('商品小計：' + (un ? (sub ? nt(sub) + '＋待報價' : '待報價') : nt(sub)));
    L.push('運費：' + (fee === 0 && sub >= (CFG.freeShipAt || 2000) ? '免運（滿' + nt(CFG.freeShipAt || 2000) + '）' : (un && !sub ? '依 LINE 報價確認（' + (CFG.shipLabel || '宅配到府') + '）' : nt(fee) + '（' + (CFG.shipLabel || '宅配到府') + '）')));
    L.push('合計：' + (un ? '待 LINE 報價確認' : nt(sub + fee)));
    L.push('────────────');
    L.push('收件人：' + form.name);
    L.push('電話：' + form.phone);
    L.push('宅配地址：' + form.addr);
    if (form.note) L.push('備註：' + form.note);
    L.push('付款方式：' + (CFG.payment || '銀行轉帳（LINE 對帳後出貨）'));
    L.push('────────────');
    L.push('請小編確認庫存與金額，謝謝 🙏');
    return L.join('\n');
  }
  function lineUrl(text) {
    var id = (CFG.lineId || '@150tiznd').replace('@', '%40');
    return 'https://line.me/R/oaMessage/' + id + '/?' + encodeURIComponent(text);
  }

  /* ── 結帳頁 ── */
  function renderCartPage() {
    var root = $('#pm-cart-root');
    if (!root) return;
    var es = entries();
    if (!es.length && !root.dataset.done) {
      root.innerHTML = '<div class="pm-empty" style="padding:80px 20px"><div class="big">🛒</div>' +
        '<p>購物車是空的</p><a class="btn btn-gold" href="index.html#products" style="margin-top:20px">去逛全部商品</a></div>';
      return;
    }
    if (root.dataset.done) return;
    var sub = pricedSubtotal(), fee = shipFee(sub);
    root.innerHTML =
      '<div class="pm-cart-grid">' +
      '<div class="pm-panel"><div class="pm-panel-h">訂單內容 · ' + count() + ' 件</div><div class="pm-panel-b" data-pm-items>' +
      es.map(itemRow).join('') + '</div>' +
      '<div style="padding:0 20px 20px">' + totalsHtml(sub, fee) + '</div></div>' +
      '<div class="pm-panel"><div class="pm-panel-h">收件資訊</div><div class="pm-panel-b" style="padding-bottom:24px">' +
      '<div class="pm-field"><label>收件人姓名 <span class="req">＊</span></label><input type="text" name="name" autocomplete="name" placeholder="王小明"></div>' +
      '<div class="pm-field"><label>聯絡電話 <span class="req">＊</span></label><input type="tel" name="phone" autocomplete="tel" inputmode="tel" placeholder="0912 345 678"></div>' +
      '<div class="pm-field"><label>宅配地址 <span class="req">＊</span></label><input type="text" name="addr" autocomplete="street-address" placeholder="縣市＋區＋路街巷弄號樓"></div>' +
      '<div class="pm-field"><label>訂單備註</label><textarea name="note" placeholder="指定到貨時段、發票需求等（選填）"></textarea></div>' +
      '<div class="pm-info-strip"><span class="ic">ℹ</span><span>付款方式：<b style="color:var(--txt)">' + esc(CFG.payment || '銀行轉帳') + '</b>。按下方按鈕會開啟 LINE 並自動帶入訂單內容，<b style="color:var(--txt)">按下傳送</b>即完成下單，小編將回覆轉帳資訊與總金額。</span></div>' +
      '<button class="btn btn-line pm-submit" data-pm-send>● 透過 LINE 送出訂單</button>' +
      '<div class="pm-err-msg" data-pm-err></div>' +
      '</div></div></div>' +
      '<div class="pm-done" data-pm-done></div>';
    $('[data-pm-send]', root).addEventListener('click', submitOrder);
  }

  function submitOrder() {
    var root = $('#pm-cart-root');
    var form = {
      name: ($('input[name=name]', root).value || '').trim(),
      phone: ($('input[name=phone]', root).value || '').trim(),
      addr: ($('input[name=addr]', root).value || '').trim(),
      note: ($('textarea[name=note]', root).value || '').trim()
    };
    var err = [];
    $all('input,textarea', root).forEach(function (i) { i.classList.remove('err'); });
    if (!form.name) { err.push('姓名'); $('input[name=name]', root).classList.add('err'); }
    if (!/^09\d{8}$|^0\d{1,2}[\s-]?\d{6,8}$/.test(form.phone.replace(/[\s-]/g, '')) || !form.phone) { err.push('電話（例：0912345678）'); $('input[name=phone]', root).classList.add('err'); }
    if (form.addr.length < 6) { err.push('完整宅配地址'); $('input[name=addr]', root).classList.add('err'); }
    var errEl = $('[data-pm-err]', root);
    if (err.length) { errEl.textContent = '請確認：' + err.join('、'); errEl.classList.add('on'); return; }
    errEl.classList.remove('on');

    var oid = orderId();
    var text = buildOrderText(oid, form);
    var url = lineUrl(text);

    /* 保存訂單紀錄 */
    try {
      var hist = JSON.parse(localStorage.getItem(LS_ORDERS) || '[]');
      hist.unshift({ id: oid, at: Date.now(), text: text });
      localStorage.setItem(LS_ORDERS, JSON.stringify(hist.slice(0, 10)));
    } catch (e) {}
    track('begin_checkout', { currency: 'TWD', value: pricedSubtotal() });
    track('generate_lead', { order_id: oid });

    /* 完成畫面（LINE 於新分頁/APP 開啟） */
    var done = $('[data-pm-done]', root);
    root.dataset.done = '1';
    $('.pm-cart-grid', root).style.display = 'none';
    done.innerHTML =
      '<div style="font-size:40px;color:var(--gold)">✓</div>' +
      '<div class="oid">' + oid + '</div><h2>訂單已產生</h2>' +
      '<p>LINE 應已自動開啟並帶入訂單內容——<b style="color:var(--txt)">請在 LINE 按下「傳送」</b>才算完成下單。若沒有開啟，請複製下方訂單文字，貼到我們的 LINE 官方帳號。</p>' +
      '<a class="btn btn-line" href="' + url + '" target="_blank" rel="noopener">● 再次開啟 LINE</a>' +
      '<button class="btn btn-outline" data-pm-copy>複製訂單文字</button>' +
      '<textarea class="pm-order-txt" readonly>' + esc(text) + '</textarea>' +
      '<a class="btn btn-outline" href="index.html">回首頁繼續逛</a>';
    done.classList.add('on');
    $('[data-pm-copy]', done).addEventListener('click', function () {
      var ta = $('.pm-order-txt', done); ta.select();
      try { navigator.clipboard.writeText(text); } catch (e) { document.execCommand('copy'); }
      toast('<span class="ck">✓</span> 已複製訂單文字');
    });
    clearCart();
    window.open(url, '_blank', 'noopener');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  /* ── 事件委派 ── */
  document.addEventListener('click', function (ev) {
    var t = ev.target.closest ? ev.target : null;
    if (!t) return;
    var addBtn = ev.target.closest('[data-pm-add]');
    if (addBtn) {
      ev.preventDefault();
      var qtyInput = document.querySelector('[data-pm-qty-input]');
      var qty = addBtn.hasAttribute('data-pm-with-qty') && qtyInput ? (parseInt(qtyInput.value, 10) || 1) : 1;
      add(addBtn.getAttribute('data-pm-add'), qty);
      addBtn.classList.add('added');
      var old = addBtn.dataset.orig || addBtn.innerHTML;
      addBtn.dataset.orig = old;
      addBtn.innerHTML = '✓ 已加入';
      setTimeout(function () { addBtn.classList.remove('added'); addBtn.innerHTML = old; }, 1600);
      return;
    }
    if (ev.target.closest('[data-pm-open-cart]')) { ev.preventDefault(); openDrawer(); return; }
    var row = ev.target.closest('.pm-item');
    if (row) {
      var sku = row.getAttribute('data-sku');
      if (ev.target.closest('[data-pm-inc]')) setQty(sku, (cart.items[sku] || 0) + 1);
      else if (ev.target.closest('[data-pm-dec]')) setQty(sku, (cart.items[sku] || 0) - 1);
      else if (ev.target.closest('[data-pm-rm]')) setQty(sku, 0);
    }
    /* 商品頁數量步進器 */
    var qbox = ev.target.closest('.qty-box');
    if (qbox) {
      var input = $('input', qbox);
      if (ev.target.closest('[data-q-inc]')) input.value = Math.min(99, (parseInt(input.value, 10) || 1) + 1);
      if (ev.target.closest('[data-q-dec]')) input.value = Math.max(1, (parseInt(input.value, 10) || 1) - 1);
    }
  });
  document.addEventListener('keydown', function (ev) {
    if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.closest && ev.target.closest('[data-pm-add][role="button"]')) {
      ev.preventDefault(); ev.target.closest('[data-pm-add][role="button"]').click(); return;
    }
    if (ev.key === 'Escape' && $('.pm-drawer.on')) closeDrawer();
  });

  /* ── 價格植水（全站 data-pm-price 由 PM_PRICES 單一來源同步） ── */
  function hydratePrices() {
    $all('[data-pm-price]').forEach(function (el) {
      var p = BYSKU[el.getAttribute('data-pm-price')];
      if (!p) return;
      if (p.price) { el.classList.remove('tbd'); el.innerHTML = '<span class="cur">NT$</span>' + Number(p.price).toLocaleString('zh-Hant-TW'); }
      else { el.classList.add('tbd'); el.textContent = '價格請洽 LINE'; }
    });
    $all('[data-pm-price-note]').forEach(function (el) {
      var p = BYSKU[el.getAttribute('data-pm-price-note')];
      if (!p) return;
      el.textContent = p.price ? '滿 ' + nt(CFG.freeShipAt || 2000) + ' 免運' : '可先加入購物車，送單後由 LINE 回覆報價';
    });
  }

  /* ── 啟動 ── */
  function init() { injectUI(); refreshBadges(); hydratePrices(); renderCartPage(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  window.PMStore = { add: add, setQty: setQty, clear: clearCart, open: openDrawer, count: count, hydratePrices: hydratePrices };
})();
