(function (global) {
  'use strict';

  var EVENT_PARAMETERS = {
    hero_cta: ['target'],
    home_intent_select: ['intent', 'result_count'],
    catalog_filter: ['category', 'result_count'],
    catalog_search: ['category', 'query_length', 'result_count'],
    product_select: ['sku', 'category', 'source'],
    support_click: ['channel', 'placement']
  };

  function hasAnalyticsConsent() {
    try {
      return global.localStorage.getItem('ck_consent') === 'granted';
    } catch (error) {
      return false;
    }
  }

  function cleanValue(value) {
    if (typeof value === 'string') {
      var trimmed = value.trim();
      return trimmed ? trimmed.slice(0, 64) : undefined;
    }
    if (typeof value === 'number') {
      return isFinite(value) ? value : undefined;
    }
    if (typeof value === 'boolean') return value;
    return undefined;
  }

  function allowedParameters(eventName, parameters) {
    var clean = {};
    var source = parameters || {};
    EVENT_PARAMETERS[eventName].forEach(function (key) {
      var value = cleanValue(source[key]);
      if (value !== undefined) clean[key] = value;
    });
    return clean;
  }

  function track(eventName, parameters) {
    if (!Object.prototype.hasOwnProperty.call(EVENT_PARAMETERS, eventName)) return false;
    if (!hasAnalyticsConsent() || typeof global.gtag !== 'function') return false;
    try {
      global.gtag('event', eventName, allowedParameters(eventName, parameters));
      return true;
    } catch (error) {
      return false;
    }
  }

  global.PopMonsterAnalytics = {
    track: track
  };
})(window);
