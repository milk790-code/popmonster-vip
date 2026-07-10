/* ═══════════════════════════════════════════════════════
   POP MONSTER 品牌圖騰 · js/totem.js
   飛白書法「泡」＋朱砂印（參無 Cānwú DS feibai 技法移植）
   純前端 canvas 一次性渲染；固定種子，圖騰恆定。
   ═══════════════════════════════════════════════════════ */
(function () {
  'use strict';
  var cv = document.getElementById('pm-totem');
  if (!cv || !cv.getContext) return;

  var W = 720, H = 920;
  var INK = '#1b1712', PAPER = '#faf6ec', SEAL = '#9e3a2b';
  var SEED = 8848;            // 固定種子：品牌圖騰不隨機
  var DENSITY = 0.42;
  var ctx = cv.getContext('2d');

  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function drawPaper() {
    ctx.fillStyle = PAPER;
    ctx.fillRect(0, 0, W, H);
    var g = ctx.createRadialGradient(W / 2, H * 0.42, 140, W / 2, H * 0.5, H * 0.7);
    g.addColorStop(0, 'rgba(244,239,227,0)');
    g.addColorStop(1, 'rgba(202,191,164,0.20)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    var rnd = mulberry32(12345);
    ctx.globalAlpha = 0.04;
    for (var i = 0; i < 4200; i++) {
      var x = rnd() * W, y = rnd() * H, s = rnd() * 1.4;
      ctx.fillStyle = rnd() > 0.5 ? INK : '#ffffff';
      ctx.fillRect(x, y, s, s);
    }
    ctx.globalAlpha = 1;
    ctx.strokeStyle = 'rgba(27,23,18,0.10)';
    ctx.lineWidth = 1;
    ctx.strokeRect(30, 30, W - 60, H - 60);
  }

  function drawFeibaiChar(char, cx, cy, size, rnd) {
    var pad = size * 0.25;
    var bw = Math.ceil(size + pad * 2), bh = Math.ceil(size * 1.25 + pad * 2);

    var buf = document.createElement('canvas');
    buf.width = bw; buf.height = bh;
    var b = buf.getContext('2d');
    b.font = size + 'px "Ma Shan Zheng", "Noto Serif TC", serif';
    b.textAlign = 'center';
    b.textBaseline = 'middle';
    b.fillStyle = INK;
    b.filter = 'blur(0.6px)';
    b.fillText(char, bw / 2, bh / 2);
    b.filter = 'none';

    /* 墨色濃淡：入筆濃、收筆枯 */
    b.globalCompositeOperation = 'source-atop';
    var grad = b.createLinearGradient(0, 0, bw * 0.5, bh);
    grad.addColorStop(0.00, 'rgba(180,170,150,0)');
    grad.addColorStop(0.50, 'rgba(150,140,122,0.05)');
    grad.addColorStop(0.78, 'rgba(176,166,148,0.30)');
    grad.addColorStop(1.00, 'rgba(205,196,176,0.52)');
    b.fillStyle = grad;
    b.fillRect(0, 0, bw, bh);
    var blots = 34 + Math.floor(DENSITY * 30);
    for (var i = 0; i < blots; i++) {
      var x = rnd() * bw, y = rnd() * bh, r = 20 + rnd() * 74;
      var t = 150 + Math.floor(rnd() * 80);
      var a = 0.04 + rnd() * 0.13;
      var rg = b.createRadialGradient(x, y, 0, x, y, r);
      rg.addColorStop(0, 'rgba(' + t + ',' + (t - 8) + ',' + (t - 22) + ',' + a + ')');
      rg.addColorStop(1, 'rgba(0,0,0,0)');
      b.fillStyle = rg;
      b.beginPath(); b.arc(x, y, r, 0, Math.PI * 2); b.fill();
    }
    b.globalCompositeOperation = 'source-over';

    /* 飛白絲：短段為主、聚成乾帶 */
    var streak = document.createElement('canvas');
    streak.width = bw; streak.height = bh;
    var s = streak.getContext('2d');
    s.lineCap = 'round';
    var tilt = (rnd() - 0.5) * 0.18;
    var count = Math.floor(bw * (0.16 + DENSITY * 0.58));
    for (var i2 = 0; i2 < count; i2++) {
      var band = Math.floor(rnd() * 5);
      var sx = (band + rnd()) / 5 * bw + (rnd() - 0.5) * bw * 0.16;
      sx = Math.max(0, Math.min(bw, sx));
      var segStart = rnd() * bh;
      var segLen = bh * (0.05 + rnd() * rnd() * (0.5 + DENSITY * 0.4));
      var yTop = segStart, yBot = Math.min(bh, segStart + segLen);
      var span = yBot - yTop;
      var wob = (rnd() - 0.5) * 7;
      s.strokeStyle = 'rgba(255,255,255,' + (0.4 + rnd() * 0.55) + ')';
      s.lineWidth = 0.5 + rnd() * (1.3 + DENSITY * 2.4);
      s.beginPath();
      s.moveTo(sx, yTop);
      s.bezierCurveTo(
        sx + wob + tilt * span * 0.3, yTop + span * 0.33,
        sx - wob + tilt * span * 0.6, yTop + span * 0.66,
        sx + tilt * span, yBot
      );
      s.stroke();
    }
    var flecks = Math.floor(90 * DENSITY);
    for (var i3 = 0; i3 < flecks; i3++) {
      var fx = rnd() * bw, fy = rnd() * bh, len = 4 + rnd() * 22;
      s.strokeStyle = 'rgba(255,255,255,' + (0.3 + rnd() * 0.55) + ')';
      s.lineWidth = 0.5 + rnd() * 1.3;
      s.beginPath(); s.moveTo(fx, fy); s.lineTo(fx + tilt * len, fy + len); s.stroke();
    }
    /* 斷墨 */
    s.filter = 'blur(1.6px)';
    var nBreaks = Math.floor(3 + DENSITY * 11);
    for (var i4 = 0; i4 < nBreaks; i4++) {
      var cxr = rnd() * bw, cyr = rnd() * bh;
      var blobs = 3 + Math.floor(rnd() * 5);
      s.fillStyle = 'rgba(255,255,255,' + (0.65 + rnd() * 0.35) + ')';
      for (var j = 0; j < blobs; j++) {
        var ox = cxr + (rnd() - 0.5) * 46;
        var oy = cyr + (rnd() - 0.5) * 52;
        var r2 = 3 + rnd() * (10 + DENSITY * 12);
        s.beginPath(); s.arc(ox, oy, r2, 0, Math.PI * 2); s.fill();
      }
    }
    s.filter = 'none';

    b.globalCompositeOperation = 'destination-out';
    b.drawImage(streak, 0, 0);
    b.globalCompositeOperation = 'source-over';

    var ox0 = cx - bw / 2, oy0 = cy - bh / 2;

    /* 墨暈 */
    ctx.save();
    ctx.globalAlpha = 0.10;
    ctx.filter = 'blur(5px)';
    ctx.drawImage(buf, ox0, oy0);
    ctx.filter = 'none';
    ctx.restore();

    ctx.drawImage(buf, ox0, oy0);
    drawSplatter(buf, bw, bh, ox0, oy0, rnd);
  }

  /* 撒墨：貼著筆畫聚集，偶有甩點 */
  function drawSplatter(buf, bw, bh, ox0, oy0, rnd) {
    var data;
    try { data = buf.getContext('2d').getImageData(0, 0, bw, bh).data; }
    catch (e) { return; }
    var pts = [];
    for (var y = 0; y < bh; y += 4) {
      for (var x = 0; x < bw; x += 4) {
        if (data[(y * bw + x) * 4 + 3] > 90) pts.push(x, y);
      }
    }
    if (!pts.length) return;
    var n = Math.floor(70 + DENSITY * 200);
    for (var i = 0; i < n; i++) {
      var k = (Math.floor(rnd() * (pts.length / 2))) * 2;
      var fling = rnd() < 0.16;
      var spread = fling ? 20 + rnd() * 60 : rnd() * 10;
      var ang = rnd() * Math.PI * 2;
      var sx = ox0 + pts[k] + Math.cos(ang) * spread;
      var sy = oy0 + pts[k + 1] + Math.sin(ang) * spread;
      var r = Math.pow(rnd(), 2.7) * (2.0 + DENSITY * 3.0) + 0.28;
      var a = 0.16 + rnd() * 0.6;
      ctx.fillStyle = 'rgba(27,23,18,' + a + ')';
      ctx.beginPath(); ctx.arc(sx, sy, r, 0, Math.PI * 2); ctx.fill();
      if (fling && rnd() < 0.5) {
        ctx.strokeStyle = 'rgba(27,23,18,' + (a * 0.6) + ')';
        ctx.lineWidth = r * 0.7;
        ctx.beginPath(); ctx.moveTo(sx, sy);
        ctx.lineTo(sx + (rnd() - 0.5) * 10, sy + (rnd() - 0.2) * 16);
        ctx.stroke();
      }
    }
  }

  /* 朱砂印：泡／怪 直式二字 */
  function drawSeal(cx, cy, sz) {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(-2.5 * Math.PI / 180);
    ctx.fillStyle = SEAL;
    roundRect(-sz / 2, -sz / 2, sz, sz, 5);
    ctx.fill();
    ctx.strokeStyle = 'rgba(124,44,32,0.4)';
    ctx.lineWidth = 2;
    roundRect(-sz / 2 + 1.5, -sz / 2 + 1.5, sz - 3, sz - 3, 4);
    ctx.stroke();
    ctx.fillStyle = '#f4efe3';
    ctx.font = (sz * 0.38) + 'px "Ma Shan Zheng", "Noto Serif TC", serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('泡', 0, -sz * 0.21);
    ctx.fillText('怪', 0, sz * 0.23);
    ctx.restore();
  }
  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function render() {
    var rnd = mulberry32(SEED);
    drawPaper();
    drawFeibaiChar('泡', W / 2, H * 0.44, 430, rnd);
    /* 側題：小字直排 */
    ctx.save();
    ctx.fillStyle = 'rgba(27,23,18,0.55)';
    ctx.font = '20px "Noto Serif TC", serif';
    ctx.textAlign = 'center';
    var motto = '安全永遠第一';
    for (var i = 0; i < motto.length; i++) {
      ctx.fillText(motto[i], W - 92, H * 0.20 + i * 30);
    }
    ctx.restore();
    drawSeal(W - 92, H * 0.74, 76);
  }

  var done = false;
  function renderOnce() { if (done) return; done = true; render(); }
  function boot() {
    if (document.fonts && document.fonts.load) {
      Promise.all([
        document.fonts.load('430px "Ma Shan Zheng"', '泡'),
        document.fonts.load('29px "Ma Shan Zheng"', '怪')
      ]).then(renderOnce, renderOnce);
      /* 字體逾時保底 */
      setTimeout(renderOnce, 2500);
    } else {
      renderOnce();
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
