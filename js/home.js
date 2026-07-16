(function () {
  'use strict';

  var cards = Array.prototype.slice.call(document.querySelectorAll('#product-grid .card[data-cat]'));
  var filterButtons = Array.prototype.slice.call(document.querySelectorAll('.filter-btn[data-cat]'));
  var intentButtons = Array.prototype.slice.call(document.querySelectorAll('[data-home-intent]'));
  var searchInput = document.getElementById('product-search');
  var clearButton = document.getElementById('product-search-clear');
  var resultStatus = document.getElementById('product-results');
  var emptyState = document.getElementById('product-empty');
  var catalog = document.getElementById('products');
  var activeCategory = 'all';
  var normalizedQuery = '';

  function track(eventName, parameters) {
    try {
      if (!window.PopMonsterAnalytics) return false;
      return window.PopMonsterAnalytics.track(eventName, parameters);
    } catch (error) {
      return false;
    }
  }

  function normalizeText(value) {
    return String(value || '')
      .normalize('NFKC')
      .toLocaleLowerCase('zh-Hant-TW')
      .replace(/[\s\-_/（）()]+/g, ' ')
      .trim();
  }

  cards.forEach(function (card) {
    card.dataset.homeSearch = normalizeText(card.textContent);
  });

  function matchesCard(card) {
    var categoryMatches = activeCategory === 'all' || card.dataset.cat === activeCategory;
    var queryMatches = !normalizedQuery || card.dataset.homeSearch.indexOf(normalizedQuery) !== -1;
    return categoryMatches && queryMatches;
  }

  function updatePressedState() {
    filterButtons.forEach(function (button) {
      var selected = button.dataset.cat === activeCategory;
      button.classList.toggle('active', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
    intentButtons.forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.homeIntent === activeCategory));
    });
  }

  function applyFilters() {
    var visibleCount = 0;
    cards.forEach(function (card) {
      card.style.removeProperty('display');
      var visible = matchesCard(card);
      card.hidden = !visible;
      if (visible) visibleCount += 1;
    });
    if (resultStatus) {
      var context = activeCategory === 'all' ? '' : '（已套用分類）';
      resultStatus.textContent = visibleCount + ' 款商品' + context;
    }
    if (emptyState) emptyState.hidden = visibleCount !== 0;
    if (clearButton) clearButton.hidden = !normalizedQuery;
    updatePressedState();
    return visibleCount;
  }

  function setCategory(category) {
    activeCategory = category || 'all';
    return applyFilters();
  }

  function scrollToCatalog() {
    if (!catalog) return;
    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var top = catalog.getBoundingClientRect().top + window.scrollY - 76;
    window.scrollTo({ top: Math.max(0, top), behavior: reduced ? 'auto' : 'smooth' });
  }

  filterButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      var visibleCount = setCategory(button.dataset.cat);
      track('catalog_filter', {
        category: activeCategory,
        result_count: visibleCount
      });
    });
  });

  intentButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      var visibleCount = setCategory(button.dataset.homeIntent);
      track('home_intent_select', {
        intent: activeCategory,
        result_count: visibleCount
      });
      window.requestAnimationFrame(scrollToCatalog);
    });
  });

  if (searchInput) {
    searchInput.addEventListener('input', function () {
      normalizedQuery = normalizeText(searchInput.value);
      applyFilters();
    });
    searchInput.addEventListener('change', function () {
      track('catalog_search', {
        category: activeCategory,
        query_length: normalizedQuery.length,
        result_count: cards.filter(function (card) { return !card.hidden; }).length
      });
    });
    searchInput.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && searchInput.value) {
        searchInput.value = '';
        normalizedQuery = '';
        applyFilters();
      }
    });
  }

  if (clearButton) {
    clearButton.addEventListener('click', function () {
      if (!searchInput) return;
      searchInput.value = '';
      normalizedQuery = '';
      applyFilters();
      searchInput.focus();
    });
  }

  document.addEventListener('click', function (event) {
    var target = event.target;
    if (!target || typeof target.closest !== 'function') return;

    var heroCta = target.closest('[data-home-cta]');
    if (heroCta) {
      track('hero_cta', { target: heroCta.dataset.homeCta });
    }

    var productCard = target.closest('#product-grid .card[data-cat]');
    if (productCard && !target.closest('[data-pm-add]')) {
      var sku = productCard.querySelector('.card-sku');
      track('product_select', {
        sku: sku ? sku.textContent.trim() : '',
        category: productCard.dataset.cat,
        source: 'catalog'
      });
    }

    var supportLink = target.closest('a[href*="line.me"], a[href*="wa.me"]');
    if (supportLink) {
      var href = supportLink.getAttribute('href') || '';
      var placement = 'content';
      if (supportLink.closest('.nav')) placement = 'navigation';
      else if (supportLink.closest('#product-empty')) placement = 'empty_state';
      else if (supportLink.closest('.footer')) placement = 'footer';
      track('support_click', {
        channel: href.indexOf('wa.me') !== -1 ? 'whatsapp' : 'line',
        placement: placement
      });
    }
  });

  function initMobileMenu() {
    var button = document.querySelector('.nav-menu-btn');
    var menu = document.getElementById('mobile-menu');
    if (!button || !menu) return;

    function setOpen(open) {
      button.setAttribute('aria-expanded', String(open));
      button.setAttribute('aria-label', open ? 'MENU 關閉選單' : 'MENU 開啟選單');
      menu.setAttribute('aria-hidden', String(!open));
      menu.classList.toggle('show', open);
      document.body.classList.toggle('menu-open', open);
    }

    button.addEventListener('click', function () {
      setOpen(button.getAttribute('aria-expanded') !== 'true');
    });
    menu.addEventListener('click', function (event) {
      if (event.target.closest('a')) setOpen(false);
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') {
        setOpen(false);
        button.focus();
      }
    });
    window.addEventListener('resize', function () {
      if (window.innerWidth > 920) setOpen(false);
    }, { passive: true });
  }

  initMobileMenu();
  applyFilters();

  window.PMHome = {
    applyFilters: applyFilters,
    normalizeText: normalizeText,
    setCategory: setCategory,
    state: function () {
      return {
        activeCategory: activeCategory,
        normalizedQuery: normalizedQuery,
        visibleCount: cards.filter(function (card) { return !card.hidden; }).length
      };
    }
  };
})();
