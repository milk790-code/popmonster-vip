/* ═══════════════════════════════════════════════════════
   POP MONSTER 官网购物车引擎 · js/store.js
   纯前端（无后端）：localStorage 购物车 → LINE 官方帐号下单
   依赖：js/products.js（PM_CONFIG / PM_PRODUCTS）、css/store.css
   ═══════════════════════════════════════════════════════ */
(function () {
  'use strict';
  var CFG = window.PM_CONFIG || {};
  var LIST = window.PM_PRODUCTS || [];
  var BYSKU = {};
  LIST.forEach(function (p) { BYSKU[p.sku] = p; });

  /* 海外模式（/en/、/zh-hans/ 的 products.js 会设 intl:true）：不走 LINE 宅配结帐，改到下单页用 WhatsApp；
     运费依国家另报，不显示台湾满额免运 */
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

  /* ── 购物车状态 ──
     pm_cart_v1 下单页（order.html）也在读写：它多放一栏 v（首页没有的规格，例：天使涂层 30ml）。
     这支不认得的字段一律原样留着；每次改之前先重读一次，别的分页刚改的数量才不会被这页手上的旧数据盖掉。 */
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

  /* 下单页另选的规格（cart.v，key 像 'a001|0'；规格名称在 cart.vn，下单页存的）：
     这支没有规格价格表，只列名称、规格、件数，请客人回下单页确认、送出。旧数据没有 vn 就写「规格在下单页」 */
  function extras() {
    /* 英文页读 vne（下单页存的英文规格名）；旧数据没有 vne 就不秀中文规格名，改写「规格在下单页」 */
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
  /* 规格名称照逗号切段、每段不拆开（「1入 体验装（不划算），20倍稀释最高可稀释65倍」不会剩一个「倍」掉到下一行） */
  function specHtml(s) {
    var parts = String(s).split(/\s*,\s*/).filter(Boolean);
    // 英文逗号后的空白放在 span 外面：span 是 inline-block，里面的尾端空白会被吃掉
    return parts.map(function (t, i) { var more = i < parts.length - 1; return '<span class="c">' + esc(t) + (more ? (EN ? ',' : '，') : '') + '</span>' + (more && EN ? ' ' : ''); }).join('');
  }
  /* only＝这里的购物车没有别的商品：下单页那几件就是全部，按钮改成主要按钮「到下单页送出」 */
  function extrasHtml(only) {
    var xs = extras();
    if (!xs.length) return '';
    return '<div class="pm-extra' + (only ? ' only' : '') + '"><div class="pm-extra-h">在下单页选的规格 · ' + extraCount() + ' 件</div><ul>' +
      xs.map(function (e) {
        return '<li><span class="nm">' + esc(e.p.name) + '</span><span class="sp">' + (e.spec ? specHtml(e.spec) : '规格在下单页') + '</span><span class="q">×' + e.qty + '</span></li>';
      }).join('') + '</ul>' +
      (only ? '<p>这几件要在下单页送出，规格和价格也在那里确认。</p>'
            : '<p>这几件不会跟这里的购物车一起送出，规格和价格请回下单页确认、<span class="nw">送出。</span></p>') +
      '<a class="btn ' + (only ? 'btn-gold' : 'btn-outline') + '" href="' + ORDER_URL + '">' + (only ? '到下单页送出 →' : '到下单页查看 →') + '</a></div>';
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
    toast('<span class="ck">✓</span> 已加入：' + esc(p.name) + ' <a href="#" data-pm-open-cart>查看购物车</a>');
    track('add_to_cart', { currency: 'TWD', value: p.price || 0, items: [{ item_id: sku, item_name: p.name, quantity: qty || 1 }] });
  }
  function setQty(sku, qty) {
    sync();
    if (qty <= 0) delete cart.items[sku]; else cart.items[sku] = Math.min(99, qty);
    save(cart); refresh();
  }
  function bump(sku, d) { sync(); setQty(sku, (cart.items[sku] || 0) + d); }
  /* 清空＝清掉这里的购物车（items）；下单页另选的规格（v）没进这张单，留着 */
  function clearCart() { sync(); cart.items = {}; save(cart); refresh(); }
  /* 送单后只扣掉这张单送出的品项与件数 */
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

  /* ── Nav 按钮 / FAB / 抽屉 DOM 注入 ── */
  function injectUI() {
    var inner = $('.nav-inner');
    if (inner && !$('.nav-cart-btn')) {
      var b = document.createElement('button');
      b.className = 'nav-cart-btn';
      b.setAttribute('aria-label', 'CART 购物车');
      b.innerHTML = '<span class="t">购物车</span><span class="nav-cart-badge" aria-hidden="true"></span>';
      var menuBtn = $('.nav-menu-btn', inner);
      inner.insertBefore(b, menuBtn || null);
      b.addEventListener('click', function () { openDrawer(); });
    }
    if (!$('.pm-fab')) {
      var f = document.createElement('button');
      f.className = 'pm-fab';
      f.setAttribute('aria-label', '购物车');
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
      d.setAttribute('aria-label', '购物车');
      d.innerHTML =
        '<div class="pm-dw-head"><h3>购物车<span class="ct" data-pm-count></span></h3><button class="pm-dw-close" aria-label="关闭">✕</button></div>' +
        '<div class="pm-ship-bar" data-pm-shipbar><div class="t" data-pm-shiptxt></div><div class="pm-ship-track"><div class="pm-ship-fill" data-pm-shipfill></div></div></div>' +
        '<div class="pm-dw-items" data-pm-items></div>' +
        '<div class="pm-dw-foot" data-pm-foot></div>';
      document.body.appendChild(d);
      $('.pm-dw-close', d).addEventListener('click', closeDrawer);
    }
  }
  function openDrawer() { renderDrawer(); $('.pm-overlay').classList.add('on'); $('.pm-drawer').classList.add('on'); document.body.style.overflow = 'hidden'; track('view_cart'); }
  function closeDrawer() { $('.pm-overlay').classList.remove('on'); $('.pm-drawer').classList.remove('on'); document.body.style.overflow = ''; }

  /* ── 品项 HTML（抽屉与结帐页共用） ── */
  function itemRow(e) {
    var priceHtml = e.p.price
      ? '<div class="pm-item-price">' + nt(e.p.price) + (e.qty > 1 ? ' ×' + e.qty : '') + '</div>'
      : '<div class="pm-item-price tbd">价格由 WhatsApp 报价</div>';
    var thumb = e.p.img
      ? '<img class="pm-item-img" src="' + esc(e.p.img) + '" alt="' + esc(e.p.name) + '" loading="lazy" onerror="this.style.visibility=\'hidden\'">'
      : '<span class="pm-item-img pm-item-ph" aria-hidden="true">' + esc(e.p.name.charAt(0)) + '</span>';
    return '<div class="pm-item" data-sku="' + e.sku + '">' + thumb +
      '<div class="pm-item-info"><div class="pm-item-sku">' + e.sku + ' · ' + esc(e.p.cat) + '</div>' +
      '<div class="pm-item-name">' + esc(e.p.name) + '</div>' + priceHtml + '</div>' +
      '<div class="pm-item-right"><div class="pm-qty">' +
      '<button data-pm-dec aria-label="减少">−</button><span>' + e.qty + '</span><button data-pm-inc aria-label="增加">＋</button>' +
      '</div><button class="pm-item-rm" data-pm-rm>移除</button></div></div>';
  }

  function totalsHtml(sub, fee) {
    var un = hasUnpriced();
    if (INTL) {
      return '<div class="pm-row"><span>商品小计</span><b>' + (sub ? nt(sub) : '待报价') + (un && sub ? '＋待报价' : '') + '</b></div>' +
        '<div class="pm-row"><span>运费</span><b>依寄送国家报价</b></div>' +
        '<div class="pm-note">每款能不能寄到你的国家、运费多少，会先在 WhatsApp 确认，再请你付款。</div>';
    }
    var h = '<div class="pm-row"><span>商品小计</span><b>' + (sub ? nt(sub) : (un ? '待报价' : nt(0))) + (un && sub ? '＋待报价' : '') + '</b></div>';
    h += '<div class="pm-row"><span>运费（' + esc(CFG.shipLabel || '宅配到府') + '）</span><b>' + (fee === 0 && sub >= (CFG.freeShipAt || 2000) ? '免运' : (un && !sub ? '结账时计算' : nt(fee))) + '</b></div>';
    h += '<div class="pm-row total"><span>合计</span><b>' + (un ? (sub ? nt(sub + fee) + '＋' : '') + '待报价' : nt(sub + fee)) + '</b></div>';
    if (un) h += '<div class="pm-note">部分商品价格待补，送出订单后由小编通过 LINE <span class="nw">回复总金额。</span></div>';
    return h;
  }

  function shipBarHtml() {
    var sub = pricedSubtotal(), goal = CFG.freeShipAt || 2000;
    var txtEl = $('[data-pm-shiptxt]'), fillEl = $('[data-pm-shipfill]');
    if (!txtEl) return;
    if (INTL) { var bar = $('[data-pm-shipbar]'); if (bar) bar.style.display = 'none'; return; }
    if (!entries().length) { txtEl.innerHTML = '满 <b>' + nt(goal) + '</b> 免运费'; fillEl.style.width = '0%'; return; }
    if (sub >= goal) { txtEl.innerHTML = '<b>已达免运门槛 ✓</b>'; fillEl.style.width = '100%'; }
    else { txtEl.innerHTML = '再买 <b>' + nt(goal - sub) + '</b> 即享免运'; fillEl.style.width = Math.min(100, sub / goal * 100) + '%'; }
  }

  /* ── 抽屉渲染 ── */
  function renderDrawer() {
    var es = entries();
    var itemsEl = $('[data-pm-items]'), footEl = $('[data-pm-foot]'), ctEl = $('[data-pm-count]');
    if (!itemsEl) return;
    var all = count() + extraCount(); // 跟购物车钮上的数字一致（含下单页另选的规格）
    ctEl.textContent = all ? '· ' + all + ' 件' : '';
    if (!es.length) {
      itemsEl.innerHTML = extras().length ? extrasHtml(true) : '<div class="pm-empty"><div class="big">🛒</div><p>购物车还是空的<br>把喜欢的商品加进来吧</p></div>';
      footEl.innerHTML = '<a class="btn btn-outline" href="' + (CFG.base || '') + 'index.html#products" style="width:100%">去逛全部商品</a>';
    } else {
      itemsEl.innerHTML = es.map(itemRow).join('') + extrasHtml();
      var sub = pricedSubtotal(), fee = shipFee(sub);
      footEl.innerHTML = totalsHtml(sub, fee) +
        '<a class="btn btn-gold" href="' + (INTL ? ORDER_URL : (CFG.base || '') + 'cart.html') + '">前往结账 →</a>' +
        '<button class="btn btn-outline" data-pm-continue style="width:100%">继续选购</button>';
      $('[data-pm-continue]', footEl).addEventListener('click', closeDrawer);
    }
    shipBarHtml();
  }

  /* ── 徽章 ── */
  function refreshBadges() {
    var c = count() + extraCount(); // 下单页另选的规格也算进数字，客人才不会以为购物车是空的
    $all('.nav-cart-badge').forEach(function (b) { b.textContent = c > 0 ? c : ''; b.classList.toggle('on', c > 0); });
    $all('.nav-cart-btn').forEach(function (b) { b.setAttribute('aria-label', 'CART 购物车，' + c + ' 件商品'); });
    var fab = $('.pm-fab');
    if (fab) { fab.classList.toggle('has', c > 0); $('.pm-fab-badge', fab).textContent = c; }
  }

  function refresh() {
    refreshBadges();
    if ($('.pm-drawer.on')) renderDrawer();
    if ($('#pm-cart-root')) renderCartPage();
  }

  /* ── 订单编号与订单文本 ── */
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
    L.push('🛒 泡泡怪兽官网订单');
    L.push('订单编号：' + oid);
    L.push('────────────');
    es.forEach(function (e, i) {
      var line = (i + 1) + '. ' + e.p.name + '（' + e.sku + '）× ' + e.qty;
      if (e.p.price) line += '＝' + nt(e.p.price * e.qty); else line += '（请报价）';
      L.push(line);
    });
    L.push('────────────');
    L.push('商品小计：' + (un ? (sub ? nt(sub) + '＋待报价' : '待报价') : nt(sub)));
    L.push('运费：' + (fee === 0 && sub >= (CFG.freeShipAt || 2000) ? '免运（满' + nt(CFG.freeShipAt || 2000) + '）' : (un && !sub ? '依 WhatsApp 报价确认（' + (CFG.shipLabel || '宅配到府') + '）' : nt(fee) + '（' + (CFG.shipLabel || '宅配到府') + '）')));
    L.push('合计：' + (un ? '待 WhatsApp 报价确认' : nt(sub + fee)));
    L.push('────────────');
    L.push('收件人：' + form.name);
    L.push('电话：' + form.phone);
    L.push('宅配地址：' + form.addr);
    if (form.note) L.push('备注：' + form.note);
    L.push('付款方式：' + (CFG.payment || '银行转账（LINE 对账后出货）'));
    L.push('────────────');
    L.push('请小编确认库存与金额，谢谢 🙏');
    return L.join('\n');
  }
  function lineUrl(text) {
    var id = (CFG.lineId || '@150tiznd').replace('@', '%40');
    return 'https://line.me/R/oaMessage/' + id + '/?' + encodeURIComponent(text);
  }

  /* ── 结帐页 ── */
  function renderCartPage() {
    var root = $('#pm-cart-root');
    if (!root) return;
    var es = entries();
    if (root.dataset.done) return;
    /* 重画前先记下已填的收件信息（别的分页改购物车时也会重画，不能把客人打到一半的字清掉） */
    var kept = {}, focused = document.activeElement && root.contains(document.activeElement) ? document.activeElement.name : '';
    $all('input[name],textarea[name]', root).forEach(function (i) { kept[i.name] = i.value; });
    if (!es.length) {
      /* 只有下单页另选的规格：不写「购物车是空的」（右上角数字明明是 1），把那几件放最上面，逛商品改成次要链接 */
      root.innerHTML = extras().length
        ? '<div class="pm-cart-extra">' + extrasHtml(true) +
          '<p class="pm-cart-more">还想加别的？<a href="index.html#products">去逛全部商品 →</a></p></div>'
        : '<div class="pm-empty" style="padding:80px 20px"><div class="big">🛒</div>' +
          '<p>购物车是空的</p><a class="btn btn-gold" href="index.html#products" style="margin-top:20px">去逛全部商品</a></div>';
      return;
    }
    var sub = pricedSubtotal(), fee = shipFee(sub);
    root.innerHTML =
      '<div class="pm-cart-grid">' +
      '<div class="pm-panel"><div class="pm-panel-h">订单内容 · ' + count() + ' 件</div><div class="pm-panel-b" data-pm-items>' +
      es.map(itemRow).join('') + '</div>' +
      '<div style="padding:0 20px 20px">' + totalsHtml(sub, fee) + extrasHtml() + '</div></div>' +
      '<div class="pm-panel"><div class="pm-panel-h">收件信息</div><div class="pm-panel-b" style="padding-bottom:24px">' +
      '<div class="pm-field"><label>收件人姓名 <span class="req">＊</span></label><input type="text" name="name" autocomplete="name" placeholder="王小明"></div>' +
      '<div class="pm-field"><label>联系电话 <span class="req">＊</span></label><input type="tel" name="phone" autocomplete="tel" inputmode="tel" placeholder="0912 345 678"></div>' +
      '<div class="pm-field"><label>宅配地址 <span class="req">＊</span></label><input type="text" name="addr" autocomplete="street-address" placeholder="县市＋区＋路街巷弄号楼"></div>' +
      '<div class="pm-field"><label>订单备注</label><textarea name="note" placeholder="指定到货时段、发票需求等（选填）"></textarea></div>' +
      '<div class="pm-info-strip"><span class="ic">ℹ</span><span>付款方式：<b style="color:var(--txt)">' + esc(CFG.payment || '银行转账') + '</b>。按下方按钮会打开 LINE 并自动带入订单内容，<b style="color:var(--txt)">按下发送</b>即完成下单，小编将回复转账信息与总金额。</span></div>' +
      '<button class="btn btn-line pm-submit" data-pm-send>● 通过 LINE 送出订单</button>' +
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
    if (!form.name) { err.push('姓名'); $('input[name=name]', root).classList.add('err'); }
    if (!/^09\d{8}$|^0\d{1,2}[\s-]?\d{6,8}$/.test(form.phone.replace(/[\s-]/g, '')) || !form.phone) { err.push('电话（例：0912345678）'); $('input[name=phone]', root).classList.add('err'); }
    if (form.addr.length < 6) { err.push('完整宅配地址'); $('input[name=addr]', root).classList.add('err'); }
    var errEl = $('[data-pm-err]', root);
    if (err.length) { errEl.textContent = '请确认：' + err.join('、'); errEl.classList.add('on'); return; }
    errEl.classList.remove('on');

    var oid = orderId();
    var ordered = entries();
    var text = buildOrderText(oid, form);
    var url = lineUrl(text);

    /* 保存订单纪录 */
    try {
      var hist = JSON.parse(localStorage.getItem(LS_ORDERS) || '[]');
      hist.unshift({ id: oid, at: Date.now(), text: text });
      localStorage.setItem(LS_ORDERS, JSON.stringify(hist.slice(0, 10)));
    } catch (e) {}
    track('begin_checkout', { currency: 'TWD', value: pricedSubtotal() });
    track('generate_lead', { order_id: oid });

    /* 完成画面（LINE 于新分页/APP 打开） */
    var done = $('[data-pm-done]', root);
    root.dataset.done = '1';
    $('.pm-cart-grid', root).style.display = 'none';
    done.innerHTML =
      '<div style="font-size:40px;color:var(--gold)">✓</div>' +
      '<div class="oid">' + oid + '</div><h2>订单已产生</h2>' +
      '<p>LINE 应已自动打开并带入订单内容——<b style="color:var(--txt)">请在 LINE 按下「发送」</b>才算完成下单。若没有打开，请复制下方订单文本，贴到我们的 LINE 官方账号。</p>' +
      '<a class="btn btn-line" href="' + url + '" target="_blank" rel="noopener">● 再次打开 LINE</a>' +
      '<button class="btn btn-outline" data-pm-copy>复制订单文本</button>' +
      '<textarea class="pm-order-txt" readonly>' + esc(text) + '</textarea>' +
      '<a class="btn btn-outline" href="index.html">回首页继续逛</a>';
    done.classList.add('on');
    $('[data-pm-copy]', done).addEventListener('click', function () {
      var ta = $('.pm-order-txt', done); ta.select();
      try { navigator.clipboard.writeText(text); } catch (e) { document.execCommand('copy'); }
      toast('<span class="ck">✓</span> 已复制订单文本');
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
      addBtn.innerHTML = '✓ 已加入';
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
    /* 商品页数量步进器 */
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

  /* ── 价格植水（全站 data-pm-price 由 PM_PRICES 单一来源同步） ── */
  function hydratePrices() {
    $all('[data-pm-price]').forEach(function (el) {
      var p = BYSKU[el.getAttribute('data-pm-price')];
      if (!p) return;
      if (p.price) { el.classList.remove('tbd'); el.innerHTML = '<span class="cur">NT$</span>' + Number(p.price).toLocaleString('zh-Hant-TW'); }
      else { el.classList.add('tbd'); el.textContent = '价格请洽 WhatsApp'; }
    });
    $all('[data-pm-price-note]').forEach(function (el) {
      var p = BYSKU[el.getAttribute('data-pm-price-note')];
      if (!p) return;
      if (INTL) { el.textContent = ''; return; }
      el.textContent = p.price ? '满 ' + nt(CFG.freeShipAt || 2000) + ' 免运' : '可先加入购物车，送单后由 LINE 回复报价';
    });
  }

  /* ── 启动 ── */
  function init() { injectUI(); refreshBadges(); hydratePrices(); renderCartPage(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  /* 别的分页（含下单页）改了购物车、或按上一页从浏览器缓存还原这页：重读一次再画 */
  window.addEventListener('storage', function (e) { if (e.key === LS_CART || e.key === null) { sync(); refresh(); } });
  window.addEventListener('pageshow', function (e) { if (e.persisted) { sync(); refresh(); } });

  window.PMStore = { add: add, setQty: setQty, clear: clearCart, open: openDrawer, count: count, hydratePrices: hydratePrices };
})();
