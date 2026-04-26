// W4P Background Service Worker — proxies fetch calls for MAIN world content script
// MAIN world scripts can't use host_permissions; the service worker can.

const API_BASE = 'https://potlimitomaha.xyz/api';
const SITE_BASE = 'https://potlimitomaha.xyz';

chrome.runtime.onMessage.addListener(function(msg, sender, sendResponse) {
  if (msg.type === 'W4P_FETCH') {
    // rawPath: use SITE_BASE (no /api prefix), otherwise use API_BASE
    var url = msg.rawPath ? (SITE_BASE + msg.path) : (API_BASE + msg.path);
    var opts = { method: msg.method || 'GET', headers: {} };

    if (msg.body) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(msg.body);
    }
    if (msg.apiKey) {
      opts.headers['X-API-Key'] = msg.apiKey;
    }

    fetch(url, opts)
      .then(function(r) { return r.json(); })
      .then(function(data) { sendResponse({ ok: true, data: data }); })
      .catch(function(e) { sendResponse({ ok: false, error: e.message }); });

    return true; // keep sendResponse channel open for async
  }
});
