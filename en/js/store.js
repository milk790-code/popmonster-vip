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

  /* 海外模式（/en/、/zh-hans/ 的 products.js 會設 intl:true）：不走 LINE 宅配結帳，改到下單頁用 WhatsApp；
     運費依國家另報，不顯示台灣滿額免運 */
  var INTL = !!CFG.intl;
  var EN = /^en\b/i.test(document.documentElement.getAttribute('lang') || '');
  var ORDER_URL = CFG.orderUrl || ((CFG.base || '') + 'order.html');
  var LS_CART = 'pm_cart_v1';
  var LS_ORDERS = 'pm_orders_v1';

  /* ── 工具 ── */
  function $(s, r) { return (r || document).querySelector(s); }
  function $all(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function nt(n) { return 'NT$' + Number(n).toLocaleString('zh-Hant-TW'); }
  function track(ev, params) { try { if (typeof gtag === 'function') gtag('event', ev, params || {}); } catch (e) {} }

  /* ── 購物車狀態 ──
     pm_cart_v1 下單頁（order.html）也在讀寫：它多放一欄 v（首頁沒有的規格，例：天使塗層 30ml）。
     這支不認得的欄位一律原樣留著；每次改之前先重讀一次，別的分頁剛改的數量才不會被這頁手上的舊資料蓋掉。 */
  function load() {
    try {
      var c = JSON.parse(localStorage.getItem(LS_CART));
      if (c && typeof c === 'object' && c.items && typeof c.items === 'object') return c;
    } catch (e) {}
    return { items: {} };
  }
  function save(cart) {
    cart.updated = Date.now();
    try { localStorage.setItem(LS_CART, JSON.stringify(cart)); } catch (e) {}
  }
  var cart = load();
  function sync() { cart = load(); }

  /* 下單頁另選的規格（cart.v，key 像 'a001|0'；規格名稱在 cart.vn，下單頁存的）：
     這支沒有規格價格表，只列名稱、規格、件數，請客人回下單頁確認、送出。舊資料沒有 vn 就寫「規格在下單頁」 */
  function extras() {
    /* 英文頁讀 vne（下單頁存的英文規格名）；舊資料沒有 vne 就不秀中文規格名，改寫「規格在下單頁」 */
    var names = EN ? cart.vne : cart.vn;
    var v = cart.v, vn = names && typeof names === 'object' ? names : {}, rows = {}, order = [];
    if (!v || typeof v !== 'object') return [];
    Object.keys(v).forEach(function (k) {
      var q = parseInt(v[k], 10) || 0, S = String(k).split('|')[0].toUpperCase();
      if (!(q > 0) || !BYSKU[S]) return;
      var spec = typeof vn[k] === 'string' ? vn[k].trim() : '', id = S + '|' + spec;
      if (!rows[id]) { rows[id] = { sku: S, qty: 0, p: BYSKU[S], spec: spec }; order.push(id); }
      rows[id].qty += q;
    });
    return order.map(function (id) { return rows[id]; });
  }
  function extraCount() { return extras().reduce(function (a, e) { return a + e.qty; }, 0); }
  /* 規格名稱照逗號切段、每段不拆開（「1入 體驗裝（不划算），20倍稀釋最高可稀釋65倍」不會剩一個「倍」掉到下一行） */
  function specHtml(s) {
    var parts = String(s).split(/\s*,\s*/).filter(Boolean);
    return parts.map(function (t, i) { return '<span class="c">' + esc(t) + (i < parts.length - 1 ? (EN ? ', ' : '，') : '') + '</span>'; }).join('');
  }
  /* only＝這裡的購物車沒有別的商品：下單頁那幾件就是全部，按鈕改成主要按鈕「到下單頁送出」 */
  function extrasHtml(only) {
    var xs = extras();
    if (!xs.length) return '';
    return '<div class="pm-extra' + (only ? ' only' : '') + '"><div class="pm-extra-h">Spec selected on order page · ' + extraCount() + ' pcs</div><ul>' +
      xs.map(function (e) {
        return '<li><span class="nm">' + esc(e.p.name) + '</span><span class="sp">' + (e.spec ? specHtml(e.spec) : 'Spec on order page') + '</span><span class="q">×' + e.qty + '</span></li>';
      }).join('') + '</ul>' +
      (only ? '<p>These items need to be submitted on the order page. The spec and price are confirmed there too.</p>'
            : '<p>These items won\'t be submitted with this cart. Go back to the order page to confirm the spec and price, then <span class="nw">submit there.</span></p>') +
      '<a class="btn ' + (only ? 'btn-gold' : 'btn-outline') + '" href="' + ORDER_URL + '">' + (only ? 'Go to order page to submit →' : 'Go to order page to view →') + '</a></div>';
  }

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
    sync();
    cart.items[sku] = Math.min(99, (cart.items[sku] || 0) + qty);
    save(cart); refresh();
    var p = BYSKU[sku];
    toast('<span class="ck">✓</span> Added:' + esc(p.name) + ' <a href="#" data-pm-open-cart>View cart</a>');
    track('add_to_cart', { currency: 'TWD', value: p.price || 0, items: [{ item_id: sku, item_name: p.name, quantity: qty || 1 }] });
  }
  function setQty(sku, qty) {
    sync();
    if (qty <= 0) delete cart.items[sku]; else cart.items[sku] = Math.min(99, qty);
    save(cart); refresh();
  }
  function bump(sku, d) { sync(); setQty(sku, (cart.items[sku] || 0) + d); }
  /* 清空＝清掉這裡的購物車（items）；下單頁另選的規格（v）沒進這張單，留著 */
  function clearCart() { sync(); cart.items = {}; save(cart); refresh(); }
  /* 送單後只扣掉這張單送出的品項與件數 */
  function removeOrdered(list) {
    sync();
    list.forEach(function (e) {
      var left = (cart.items[e.sku] || 0) - e.qty;
      if (left > 0) cart.items[e.sku] = left; else delete cart.items[e.sku];
    });
    save(cart); refresh();
  }

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
      b.setAttribute('aria-label', 'CART');
      b.innerHTML = '<span class="t">Cart</span><span class="nav-cart-badge" aria-hidden="true"></span>';
      var menuBtn = $('.nav-menu-btn', inner);
      inner.insertBefore(b, menuBtn || null);
      b.addEventListener('click', function () { openDrawer(); });
    }
    if (!$('.pm-fab')) {
      var f = document.createElement('button');
      f.className = 'pm-fab';
      f.setAttribute('aria-label', 'Cart');
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
      d.setAttribute('aria-label', 'Cart');
      d.innerHTML =
        '<div class="pm-dw-head"><h3>Cart<span class="ct" data-pm-count></span></h3><button class="pm-dw-close" aria-label="Close">✕</button></div>' +
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
      : '<div class="pm-item-price tbd">Price quoted on WhatsApp</div>';
    var thumb = e.p.img
      ? '<img class="pm-item-img" src="' + esc(e.p.img) + '" alt="' + esc(e.p.name) + '" loading="lazy" onerror="this.style.visibility=\'hidden\'">'
      : '<span class="pm-item-img pm-item-ph" aria-hidden="true">' + esc(e.p.name.charAt(0)) + '</span>';
    return '<div class="pm-item" data-sku="' + e.sku + '">' + thumb +
      '<div class="pm-item-info"><div class="pm-item-sku">' + e.sku + ' · ' + esc(e.p.cat) + '</div>' +
      '<div class="pm-item-name">' + esc(e.p.name) + '</div>' + priceHtml + '</div>' +
      '<div class="pm-item-right"><div class="pm-qty">' +
      '<button data-pm-dec aria-label="Decrease">−</button><span>' + e.qty + '</span><button data-pm-inc aria-label="Increase">+</button>' +
      '</div><button class="pm-item-rm" data-pm-rm>Remove</button></div></div>';
  }

  function totalsHtml(sub, fee) {
    var un = hasUnpriced();
    if (INTL) {
      return '<div class="pm-row"><span>Subtotal</span><b>' + (sub ? nt(sub) : 'Price on request') + (un && sub ? '+ Price on request' : '') + '</b></div>' +
        '<div class="pm-row"><span>Shipping</span><b>Quoted by destination</b></div>' +
        '<div class="pm-note">We confirm on WhatsApp whether each item can ship to your country and what shipping costs, before you pay.</div>';
    }
    var h = '<div class="pm-row"><span>Subtotal</span><b>' + (sub ? nt(sub) : (un ? 'Price on request' : nt(0))) + (un && sub ? '+ Price on request' : '') + '</b></div>';
    h += '<div class="pm-row"><span>Shipping (' + esc(CFG.shipLabel || 'Home delivery') + '）</span><b>' + (fee === 0 && sub >= (CFG.freeShipAt || 2000) ? 'Free' : (un && !sub ? 'Calculated at checkout' : nt(fee))) + '</b></div>';
    h += '<div class="pm-row total"><span>Total</span><b>' + (un ? (sub ? nt(sub + fee) + '＋' : '') + 'Price on request' : nt(sub + fee)) + '</b></div>';
    if (un) h += '<div class="pm-note">Some items are priced on request. After you submit your order, we\'ll <span class="nw">reply with the total on WhatsApp.</span></div>';
    return h;
  }

  function shipBarHtml() {
    var sub = pricedSubtotal(), goal = CFG.freeShipAt || 2000;
    var txtEl = $('[data-pm-shiptxt]'), fillEl = $('[data-pm-shipfill]');
    if (!txtEl) return;
    if (INTL) { var bar = $('[data-pm-shipbar]'); if (bar) bar.style.display = 'none'; return; }
    if (!entries().length) { txtEl.innerHTML = 'Free shipping in Taiwan over <b>' + nt(goal) + '</b>'; fillEl.style.width = '0%'; return; }
    if (sub >= goal) { txtEl.innerHTML = '<b>You qualify for free shipping in Taiwan ✓</b>'; fillEl.style.width = '100%'; }
    else { txtEl.innerHTML = 'Spend <b>' + nt(goal - sub) + '</b> more for free shipping in Taiwan'; fillEl.style.width = Math.min(100, sub / goal * 100) + '%'; }
  }

  /* ── 抽屜渲染 ── */
  function renderDrawer() {
    var es = entries();
    var itemsEl = $('[data-pm-items]'), footEl = $('[data-pm-foot]'), ctEl = $('[data-pm-count]');
    if (!itemsEl) return;
    var all = count() + extraCount(); // 跟購物車鈕上的數字一致（含下單頁另選的規格）
    ctEl.textContent = all ? '· ' + all + ' pcs' : '';
    if (!es.length) {
      itemsEl.innerHTML = extras().length ? extrasHtml(true) : '<div class="pm-empty"><div class="big">🛒</div><p>Your cart is empty<br>Add the items you like</p></div>';
      footEl.innerHTML = '<a class="btn btn-outline" href="' + (CFG.base || '') + 'index.html#products" style="width:100%">Browse all products</a>';
    } else {
      itemsEl.innerHTML = es.map(itemRow).join('') + extrasHtml();
      var sub = pricedSubtotal(), fee = shipFee(sub);
      footEl.innerHTML = totalsHtml(sub, fee) +
        '<a class="btn btn-gold" href="' + (INTL ? ORDER_URL : (CFG.base || '') + 'cart.html') + '">Checkout →</a>' +
        '<button class="btn btn-outline" data-pm-continue style="width:100%">Continue shopping</button>';
      $('[data-pm-continue]', footEl).addEventListener('click', closeDrawer);
    }
    shipBarHtml();
  }

  /* ── 徽章 ── */
  function refreshBadges() {
    var c = count() + extraCount(); // 下單頁另選的規格也算進數字，客人才不會以為購物車是空的
    $all('.nav-cart-badge').forEach(function (b) { b.textContent = c > 0 ? c : ''; b.classList.toggle('on', c > 0); });
    $all('.nav-cart-btn').forEach(function (b) { b.setAttribute('aria-label', 'Cart, ' + c + ' item(s)'); });
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
    L.push('🛒 POP MONSTER website order');
    L.push('Order number:' + oid);
    L.push('────────────');
    es.forEach(function (e, i) {
      var line = (i + 1) + '. ' + e.p.name + '（' + e.sku + '）× ' + e.qty;
      if (e.p.price) line += '＝' + nt(e.p.price * e.qty); else line += '(Price on request)';
      L.push(line);
    });
    L.push('────────────');
    L.push('Subtotal:' + (un ? (sub ? nt(sub) + '+ Price on request' : 'Price on request') : nt(sub)));
    L.push('Shipping:' + (fee === 0 && sub >= (CFG.freeShipAt || 2000) ? 'Free shipping (over ' + nt(CFG.freeShipAt || 2000) + '）' : (un && !sub ? 'To be quoted on WhatsApp (' + (CFG.shipLabel || 'Home delivery') + '）' : nt(fee) + '（' + (CFG.shipLabel || 'Home delivery') + '）')));
    L.push('Total:' + (un ? 'Pending quote confirmation on WhatsApp' : nt(sub + fee)));
    L.push('────────────');
    L.push('Recipient:' + form.name);
    L.push('Phone:' + form.phone);
    L.push('Shipping address:' + form.addr);
    if (form.note) L.push('Notes:' + form.note);
    L.push('Payment method:' + (CFG.payment || 'Bank transfer (we confirm the total and shipping on WhatsApp before you pay)'));
    L.push('────────────');
    L.push('Please confirm stock and the total, thanks 🙏');
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
    if (root.dataset.done) return;
    /* 重畫前先記下已填的收件資訊（別的分頁改購物車時也會重畫，不能把客人打到一半的字清掉） */
    var kept = {}, focused = document.activeElement && root.contains(document.activeElement) ? document.activeElement.name : '';
    $all('input[name],textarea[name]', root).forEach(function (i) { kept[i.name] = i.value; });
    if (!es.length) {
      /* 只有下單頁另選的規格：不寫「購物車是空的」（右上角數字明明是 1），把那幾件放最上面，逛商品改成次要連結 */
      root.innerHTML = extras().length
        ? '<div class="pm-cart-extra">' + extrasHtml(true) +
          '<p class="pm-cart-more">Want to add something else? <a href="index.html#products">Browse all products →</a></p></div>'
        : '<div class="pm-empty" style="padding:80px 20px"><div class="big">🛒</div>' +
          '<p>Your cart is empty</p><a class="btn btn-gold" href="index.html#products" style="margin-top:20px">Browse all products</a></div>';
      return;
    }
    var sub = pricedSubtotal(), fee = shipFee(sub);
    root.innerHTML =
      '<div class="pm-cart-grid">' +
      '<div class="pm-panel"><div class="pm-panel-h">Order details · ' + count() + ' pcs</div><div class="pm-panel-b" data-pm-items>' +
      es.map(itemRow).join('') + '</div>' +
      '<div style="padding:0 20px 20px">' + totalsHtml(sub, fee) + extrasHtml() + '</div></div>' +
      '<div class="pm-panel"><div class="pm-panel-h">Recipient info</div><div class="pm-panel-b" style="padding-bottom:24px">' +
      '<div class="pm-field"><label>Recipient name <span class="req">*</span></label><input type="text" name="name" autocomplete="name" placeholder="Full name"></div>' +
      '<div class="pm-field"><label>Phone number <span class="req">*</span></label><input type="tel" name="phone" autocomplete="tel" inputmode="tel" placeholder="0912 345 678"></div>' +
      '<div class="pm-field"><label>Shipping address <span class="req">*</span></label><input type="text" name="addr" autocomplete="street-address" placeholder="Street address, city, postal code"></div>' +
      '<div class="pm-field"><label>Order notes</label><textarea name="note" placeholder="Preferred delivery time, invoice details, etc. (optional)"></textarea></div>' +
      '<div class="pm-info-strip"><span class="ic">ℹ</span><span>Payment method:<b style="color:var(--txt)">' + esc(CFG.payment || 'Bank transfer') + '</b>. Tapping the button below opens WhatsApp with your order details filled in. <b style="color:var(--txt)">Tap Send</b> to complete your order. We\'ll confirm the total and shipping to your country on WhatsApp and send payment details before you pay.</span></div>' +
      '<button class="btn btn-line pm-submit" data-pm-send>● Send your order on WhatsApp</button>' +
      '<div class="pm-err-msg" data-pm-err></div>' +
      '</div></div></div>' +
      '<div class="pm-done" data-pm-done></div>';
    $('[data-pm-send]', root).addEventListener('click', submitOrder);
    $all('input[name],textarea[name]', root).forEach(function (i) { if (kept[i.name] != null) i.value = kept[i.name]; });
    if (focused) { var f = $('[name="' + focused + '"]', root); if (f) f.focus(); }
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
    if (!form.name) { err.push('Name'); $('input[name=name]', root).classList.add('err'); }
    if (!/^09\d{8}$|^0\d{1,2}[\s-]?\d{6,8}$/.test(form.phone.replace(/[\s-]/g, '')) || !form.phone) { err.push('Phone (e.g. 0912345678)'); $('input[name=phone]', root).classList.add('err'); }
    if (form.addr.length < 6) { err.push('Full shipping address'); $('input[name=addr]', root).classList.add('err'); }
    var errEl = $('[data-pm-err]', root);
    if (err.length) { errEl.textContent = 'Please check:' + err.join('、'); errEl.classList.add('on'); return; }
    errEl.classList.remove('on');

    var oid = orderId();
    var ordered = entries();
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
      '<div class="oid">' + oid + '</div><h2>Order created</h2>' +
      '<p>WhatsApp should have opened automatically with your order info filled in — <b style="color:var(--txt)">tap Send in WhatsApp</b> to complete your order. If it didn\'t open, copy the order text below and paste it to us on WhatsApp.</p>' +
      '<a class="btn btn-line" href="' + url + '" target="_blank" rel="noopener">● Open WhatsApp again</a>' +
      '<button class="btn btn-outline" data-pm-copy>Copy order text</button>' +
      '<textarea class="pm-order-txt" readonly>' + esc(text) + '</textarea>' +
      '<a class="btn btn-outline" href="index.html">Continue shopping</a>';
    done.classList.add('on');
    $('[data-pm-copy]', done).addEventListener('click', function () {
      var ta = $('.pm-order-txt', done); ta.select();
      try { navigator.clipboard.writeText(text); } catch (e) { document.execCommand('copy'); }
      toast('<span class="ck">✓</span> Order text copied');
    });
    removeOrdered(ordered);
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
      addBtn.innerHTML = '✓ Added';
      setTimeout(function () { addBtn.classList.remove('added'); addBtn.innerHTML = old; }, 1600);
      return;
    }
    if (ev.target.closest('[data-pm-open-cart]')) { ev.preventDefault(); openDrawer(); return; }
    var row = ev.target.closest('.pm-item');
    if (row) {
      var sku = row.getAttribute('data-sku');
      if (ev.target.closest('[data-pm-inc]')) bump(sku, 1);
      else if (ev.target.closest('[data-pm-dec]')) bump(sku, -1);
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
      else { el.classList.add('tbd'); el.textContent = 'Ask for price on WhatsApp'; }
    });
    $all('[data-pm-price-note]').forEach(function (el) {
      var p = BYSKU[el.getAttribute('data-pm-price-note')];
      if (!p) return;
      if (INTL) { el.textContent = ''; return; }
      el.textContent = p.price ? 'Over ' + nt(CFG.freeShipAt || 2000) + ' Free' : 'You can add it to your cart now, and we\'ll reply with a price on WhatsApp after you send your order.';
    });
  }

  /* ── 啟動 ── */
  function init() { injectUI(); refreshBadges(); hydratePrices(); renderCartPage(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  /* 別的分頁（含下單頁）改了購物車、或按上一頁從瀏覽器快取還原這頁：重讀一次再畫 */
  window.addEventListener('storage', function (e) { if (e.key === LS_CART || e.key === null) { sync(); refresh(); } });
  window.addEventListener('pageshow', function (e) { if (e.persisted) { sync(); refresh(); } });

  window.PMStore = { add: add, setQty: setQty, clear: clearCart, open: openDrawer, count: count, hydratePrices: hydratePrices };
})();
