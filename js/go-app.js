/* go-app.js — /go 宇宙 App 層：加入主畫面引導＋App 殼。
 * 原則：只加不改。不碰 go.js 的事件、同意閘與分流邏輯。
 * 情境矩陣：
 *   1. 已是 App（standalone）→ 全部安裝 UI 隱藏，顯示底部導覽。
 *   2. LINE / FB / IG / Threads 站內瀏覽器 → 引導跳外部瀏覽器（LINE 用 openExternalBrowser=1）。
 *   3. Android Chrome/Edge → 攔 beforeinstallprompt，一鍵跳原生安裝框（最像下載 App）。
 *   4. iOS Safari → 兩步教學：分享 → 加入主畫面。
 *   5. 桌面 → 有 beforeinstallprompt 才顯示，安靜不打擾。
 */
(function () {
  "use strict";

  var DISMISS_KEY = "pm_app_install_dismissed_at";
  var DISMISS_DAYS = 7;
  var ua = navigator.userAgent || "";

  var env = {
    standalone:
      (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) ||
      window.navigator.standalone === true,
    ios: /iPhone|iPad|iPod/i.test(ua) || (/Macintosh/i.test(ua) && "ontouchend" in document),
    android: /Android/i.test(ua),
    inAppLine: /Line\//i.test(ua),
    inAppMeta: /FBAN|FBAV|FB_IAB|Instagram|Barcelona/i.test(ua),
    safari: /Safari/i.test(ua) && !/CriOS|FxiOS|EdgiOS|Chrome|Android/i.test(ua)
  };
  env.inApp = env.inAppLine || env.inAppMeta;

  var deferredPrompt = null;
  var bar, sheet;

  function dismissedRecently() {
    try {
      var at = Number(localStorage.getItem(DISMISS_KEY) || 0);
      return at && Date.now() - at < DISMISS_DAYS * 864e5;
    } catch (_e) {
      return false;
    }
  }

  function markDismissed() {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch (_e) {}
  }

  function externalBrowserUrl() {
    var url = new URL(window.location.href);
    url.searchParams.set("openExternalBrowser", "1");
    return url.toString();
  }

  function el(id) {
    return document.getElementById(id);
  }

  function showBar() {
    if (!bar || env.standalone || dismissedRecently()) return;
    bar.hidden = false;
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        bar.classList.add("is-visible");
      });
    });
  }

  function hideBar() {
    if (!bar) return;
    bar.classList.remove("is-visible");
    window.setTimeout(function () {
      bar.hidden = true;
    }, 380);
  }

  function openSheet(kind) {
    if (!sheet) return;
    var steps = el("app-sheet-steps");
    var title = el("app-sheet-title");
    var lede = el("app-sheet-lede");
    var extAction = el("app-sheet-external");
    if (!steps || !title || !lede || !extAction) return;

    extAction.hidden = true;

    if (kind === "line") {
      title.textContent = "先用外部瀏覽器開啟";
      lede.textContent = "LINE 裡面沒辦法加到主畫面。點下面的按鈕用瀏覽器打開，再照兩步安裝。";
      steps.innerHTML =
        '<li><span class="step-no">1</span><span>點「<b>用瀏覽器開啟</b>」跳到 Safari／Chrome</span></li>' +
        '<li><span class="step-no">2</span><span>回到這頁，照畫面提示<b>加入主畫面</b>就完成</span></li>';
      extAction.href = externalBrowserUrl();
      extAction.hidden = false;
    } else if (kind === "meta") {
      title.textContent = "先用外部瀏覽器開啟";
      lede.textContent = "FB／IG 裡面沒辦法加到主畫面。照下面兩步跳出來再安裝。";
      steps.innerHTML =
        '<li><span class="step-no">1</span><span>點右上角「<b>⋯</b>」→ 選「<b>以外部瀏覽器開啟</b>」</span></li>' +
        '<li><span class="step-no">2</span><span>回到這頁，照畫面提示<b>加入主畫面</b>就完成</span></li>';
    } else if (kind === "ios") {
      title.textContent = "兩步，把 POP 宇宙裝進手機";
      lede.textContent = "不用下載、不佔空間，裝好跟 App 一樣從主畫面點開。";
      steps.innerHTML =
        '<li><span class="step-no">1</span><span>點下方工具列的「<b>分享</b>」按鈕（□↑）</span></li>' +
        '<li><span class="step-no">2</span><span>往下滑，選「<b>加入主畫面</b>」→ 點「<b>新增</b>」</span></li>';
    } else {
      title.textContent = "把 POP 宇宙裝進手機";
      lede.textContent = "在瀏覽器選單裡找「加入主畫面」或「安裝應用程式」就完成。";
      steps.innerHTML =
        '<li><span class="step-no">1</span><span>打開瀏覽器「<b>⋮</b>」選單</span></li>' +
        '<li><span class="step-no">2</span><span>選「<b>加入主畫面</b>」／「<b>安裝應用程式</b>」</span></li>';
    }
    sheet.hidden = false;
  }

  function closeSheet() {
    if (sheet) sheet.hidden = true;
  }

  function onInstallClick() {
    if (env.inAppLine) return openSheet("line");
    if (env.inAppMeta) return openSheet("meta");
    if (deferredPrompt) {
      var p = deferredPrompt;
      deferredPrompt = null;
      p.prompt();
      p.userChoice
        .then(function (choice) {
          if (choice && choice.outcome === "accepted") hideBar();
        })
        .catch(function () {});
      return;
    }
    if (env.ios) return openSheet("ios");
    openSheet("generic");
  }

  function markActiveTab() {
    var links = document.querySelectorAll(".app-tabbar a");
    var path = window.location.pathname.replace(/\/+$/, "") || "/";
    links.forEach(function (link) {
      var target = (link.getAttribute("data-path") || "").replace(/\/+$/, "") || "/";
      if (target === path) link.classList.add("is-active");
    });
  }

  function init() {
    bar = el("app-install-bar");
    sheet = el("app-install-sheet");

    if (env.standalone) {
      document.body.classList.add("is-standalone");
      markActiveTab();
      return; // 已在 App 內，不需要任何安裝 UI
    }
    markActiveTab();

    var cta = el("app-install-cta");
    var dismiss = el("app-install-dismiss");
    var sheetClose = el("app-sheet-close");
    if (cta) cta.addEventListener("click", onInstallClick);
    if (dismiss)
      dismiss.addEventListener("click", function () {
        markDismissed();
        hideBar();
      });
    if (sheetClose) sheetClose.addEventListener("click", closeSheet);
    if (sheet)
      sheet.addEventListener("click", function (event) {
        if (event.target === sheet) closeSheet();
      });

    window.addEventListener("beforeinstallprompt", function (event) {
      event.preventDefault();
      deferredPrompt = event;
      showBar();
    });

    window.addEventListener("appinstalled", function () {
      hideBar();
      closeSheet();
    });

    // 沒有 beforeinstallprompt 的環境（iOS／站內瀏覽器）：延遲幾秒再輕聲出現
    if (env.ios || env.inApp) {
      window.setTimeout(showBar, 2600);
    }

    // Service worker：離線殼＋回訪加速。註冊失敗不影響頁面。
    if ("serviceWorker" in navigator && window.location.protocol === "https:") {
      window.addEventListener("load", function () {
        navigator.serviceWorker.register("/go-sw.js").catch(function () {});
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
