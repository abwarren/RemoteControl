// W4P Injectable v21 - PLO Remote Table Control (hero-only: .self-player class ONLY, no fallbacks)
// v19: remove .active gate — self-player + visible buttons = available_actions
// v19.1-3: fix MAX flow, diagnostics, getBoundingClientRect consistency
// v20: unified direct fetch — same file works as extension AND standalone (no bridge.js needed)
// v20.1: MAX fix — skip preset clicks (isTrusted=false), use slider.max + setSliderValue + confirmRaise
// v21: Preset-first model — click preset <li>, wait for <i> amount change, THEN click BET/RAISE
//      No openRaiseSlider. No slider input[range] manipulation. No all-in logic.
//      Hard rule: never execute BET/RAISE unless <i> amount changed or was already correct.
// Extension runtime: deployed to Windows Chrome instances via SSM
// Paste into skillgames iframe console, or: fetch('https://potlimitomaha.xyz/w4p.js').then(r=>r.text()).then(eval)
// Scrapes ALL seats, sends structured snapshots with button detection, polls commands, clicks buttons
// No chrome.runtime deps — pure fetch-based

(function(){
  'use strict';

  // ── Cleanup prior instances ──────────────────────────────────
  if (window._w4p_timer) { clearTimeout(window._w4p_timer); window._w4p_timer = null; }
  if (window._w4p_cmdTimer) { clearTimeout(window._w4p_cmdTimer); window._w4p_cmdTimer = null; }
  if (window._w4p_bbTimer) { clearInterval(window._w4p_bbTimer); window._w4p_bbTimer = null; }
  if (window._w4p) { clearInterval(window._w4p); window._w4p = null; }
  window._w4p_injected = false;

  // ── Config ───────────────────────────────────────────────────
  var API_BASE = 'https://potlimitomaha.xyz/api';
  var API_KEY  = 'trk_prod_1774368827';

  // ── Direct fetch (CORS enabled on Flask — works standalone and in extension) ──
  var SITE_BASE = 'https://potlimitomaha.xyz';
  function bridgeFetch(path, method, body, callback) {
    var opts = { method: method || 'GET', headers: { 'X-API-Key': API_KEY } };
    if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    fetch(API_BASE + path, opts)
      .then(function(r) { return r.json(); })
      .then(function(data) { if (callback) callback({ ok: true, data: data }); })
      .catch(function(e) { console.warn('[W4P] fetch error:', path, e.message); if (callback) callback({ ok: false, error: e.message }); });
  }
  function bridgeFetchRaw(path, method, body, callback) {
    var opts = { method: method || 'GET', headers: { 'X-API-Key': API_KEY } };
    if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    fetch(SITE_BASE + path, opts)
      .then(function(r) { return r.json(); })
      .then(function(data) { if (callback) callback({ ok: true, data: data }); })
      .catch(function(e) { console.warn('[W4P] fetchRaw error:', path, e.message); if (callback) callback({ ok: false, error: e.message }); });
  }

  // v15: tightened polling — faster detection, faster commands
  var POLL_MS = { HERO_TURN: 300, HAND_ACTIVE: 300, IDLE: 300, NO_TABLE: 2000 };
  var CMD_MS  = { HERO_TURN: 150, HAND_ACTIVE: 150, IDLE: 150 };
  var HEARTBEAT_MS = 8000;
  var CASHOUT_POLL_MS = 75;  // hyper-poll interval when cashout preselected

  var _mode = 'IDLE';
  var _seatToken = null;
  var _preAction = null;    // 'check_fold' | 'check_call' | null
  var _lastHash = null;
  var _lastSendTime = 0;
  var _n = 0;
  var _sessionId = 'w4p_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
  var _lastButtons = null;
  var _cashoutPre = false;   // when true, hyper-poll for cashout DOM element
  var _cashoutTimer = null;
  var _lastBoardLen = 0;     // track board cards for new hand detection

  var RANK_MAP = { 'a':'A', 'k':'K', 'q':'Q', 'j':'J', 't':'T', '10':'T' };

  // ── Action button selectors (PokerBet / BetConstruct DOM) ───
  var BTN_SEL = {
    fold:         '.control-b-view-p.fold-c',
    check:        '.control-b-view-p.check-c',
    call:         '.control-b-view-p.call-c',
    raise:        '.control-b-view-p.raise-c',
    bet:          '.control-b-view-p.bet-c',
    cashout:      '.control-b-view-p.cash_out-c',
    allin:        '.control-b-view-p.all_in-c',
    show:         '.control-b-view-p.show-c',
    run_it_twice: '.control-b-view-p.run_it_twice-c',
    resume_hand:  '.control-b-view-p.resume_hand-c',
    back_to_game: '.control-b-view-p.back_to_game-c'
  };

  // ── Detected buttons cache (populated each getAvailableActions call) ──
  var _detectedBtns = {};

  // ── Native click: mousedown → mouseup → click (PokerBet Angular/Zone.js) ──
  function nativeClick(el) {
    if (!el) return false;
    var rect = el.getBoundingClientRect();
    var cx = rect.left + rect.width / 2;
    var cy = rect.top + rect.height / 2;
    var opts = {bubbles: true, cancelable: true, view: window, button: 0, clientX: cx, clientY: cy};
    el.dispatchEvent(new MouseEvent('mousedown', opts));
    el.dispatchEvent(new MouseEvent('mouseup', opts));
    el.dispatchEvent(new MouseEvent('click', opts));
    return true;
  }

  function buildCssPath(el) {
    if (!el) return '';
    var parts = [];
    var cur = el;
    while (cur && cur !== document.body && parts.length < 5) {
      var tag = cur.tagName.toLowerCase();
      if (cur.id) { parts.unshift('#' + cur.id); break; }
      var cls = '';
      if (cur.className && typeof cur.className === 'string') {
        var cc = cur.className.trim().split(/\s+/).filter(function(c) {
          return c && c.indexOf('ng-') !== 0 && c !== 'active' && c !== 'hover';
        }).slice(0, 4);
        if (cc.length) cls = '.' + cc.join('.');
      }
      parts.unshift(tag + cls);
      cur = cur.parentElement;
    }
    return parts.join(' > ');
  }

  function detectSliderPresets() {
    var presetItems = document.querySelectorAll(
      'sg-poker-betting-slider .limits-buttons-v-p li, ' +
      'sg-poker-betting-slider li, .limits-buttons-v-p li, ' +
      '[class*="limit"] li'
    );
    for (var i = 0; i < presetItems.length; i++) {
      var el = presetItems[i];
      var elR = el.getBoundingClientRect(); if (elR.width === 0 && elR.height === 0) continue;
      var txt = (el.textContent || '').trim().toLowerCase();
      var pName = null;
      if (/\bmax\b|all[\s-]*in/i.test(txt)) pName = 'preset_max';
      else if (/\bmin\b/i.test(txt)) pName = 'preset_min';
      else if (/\bpot\b/i.test(txt) && !/half/i.test(txt) && !/1\/2/i.test(txt)) pName = 'preset_pot';
      else if (/half|1\/2/i.test(txt)) pName = 'preset_half';
      if (pName && !_detectedBtns[pName]) {
        var rect = el.getBoundingClientRect();
        _detectedBtns[pName] = {
          el: el, selector: buildCssPath(el),
          text: txt.substring(0, 30),
          x: Math.round(rect.x + rect.width / 2),
          y: Math.round(rect.y + rect.height / 2)
        };
      }
    }
  }

  // ── Card parser ──────────────────────────────────────────────
  function parseCard(cls) {
    if (!cls) return null;
    var m = cls.match(/icon-layer2_([shdc])(10|[akqjt2-9])_p-c-d/i);
    if (!m) return null;
    var suit = m[1].toLowerCase();
    var rank = m[2].toLowerCase();
    rank = RANK_MAP[rank] || rank;
    return rank + suit;
  }

  // ── Table ID from URL ────────────────────────────────────────
  function getTableId() {
    var url = location.href;
    var m = url.match(/\/tbl\/(\d+)/);
    if (m) return 'pb_' + m[1];
    m = url.match(/\/poker\/(\d+)/);
    if (m) return 'pb_' + m[1];
    m = url.match(/openGames=(\d+)/);
    if (m) return 'pb_' + m[1];
    m = url.match(/game[_-]?id[=\/](\d+)/i);
    if (m) return 'pb_' + m[1];
    if (url.indexOf('skillgames') !== -1 || url.indexOf('18751019') !== -1) {
      var idm = url.match(/(\d{4,})/);
      return 'pb_' + (idm ? idm[1] : 'sg');
    }
    if (document.querySelector('.player-mini-container-p') || document.querySelector('sg-poker-table-seat')) {
      var idm2 = url.match(/(\d{3,})/);
      return 'pb_' + (idm2 ? idm2[1] : '0');
    }
    return null;
  }

  // ── Player bet (chips near seat) ──────────────────────────────
  function getPlayerBet(seatNum) {
    var chipEl = document.querySelector('sg-chips-view.player-' + seatNum + '-chips .chip-container-view-p p i');
    if (chipEl) {
      var val = (chipEl.innerText || chipEl.textContent || '').trim();
      if (val) {
        var n = parseFloat(val.replace(/[^0-9.]/g, ''));
        return isNaN(n) ? 0 : n;
      }
    }
    return 0;
  }

  // ── DOM Scanner — inventory what elements exist for remote debugging ──
  function domScan() {
    var scan = { url: location.href.substring(0, 120), inIframe: window !== window.top };
    // Check each BTN_SEL selector
    var selHits = {};
    for (var k in BTN_SEL) {
      var el = document.querySelector(BTN_SEL[k]);
      if (el) {
        var r = el.getBoundingClientRect();
        selHits[k] = { found: true, vis: r.width > 0 && r.height > 0, w: Math.round(r.width), h: Math.round(r.height), cls: el.className.substring(0, 60), text: (el.textContent || '').trim().substring(0, 20) };
      }
    }
    scan.btnSelHits = selHits;
    // All elements with "control" in class name
    var ctrls = document.querySelectorAll('[class*="control"]');
    var ctrlDump = [];
    for (var i = 0; i < Math.min(ctrls.length, 10); i++) {
      var ce = ctrls[i]; var cr = ce.getBoundingClientRect();
      ctrlDump.push({ cls: ce.className.substring(0, 60), tag: ce.tagName, text: (ce.textContent || '').trim().substring(0, 20), vis: cr.width > 0 && cr.height > 0 });
    }
    scan.controls = ctrlDump;
    scan.controlCount = ctrls.length;
    // All elements with "fold" "check" "call" "raise" "bet" in class name
    var actionEls = document.querySelectorAll('[class*="fold"], [class*="check"], [class*="call"], [class*="raise"], [class*="bet-"], [class*="action"]');
    var actDump = [];
    for (var j = 0; j < Math.min(actionEls.length, 15); j++) {
      var ae = actionEls[j]; var ar = ae.getBoundingClientRect();
      actDump.push({ cls: ae.className.substring(0, 80), tag: ae.tagName, text: (ae.textContent || '').trim().substring(0, 30), vis: ar.width > 0 && ar.height > 0 });
    }
    scan.actionElements = actDump;
    scan.actionCount = actionEls.length;
    // All buttons on the page
    var allBtns = document.querySelectorAll('button');
    var btnDump = [];
    for (var b = 0; b < Math.min(allBtns.length, 10); b++) {
      var be = allBtns[b]; var br2 = be.getBoundingClientRect();
      btnDump.push({ cls: be.className.substring(0, 60), text: (be.textContent || '').trim().substring(0, 30), vis: br2.width > 0 && br2.height > 0 });
    }
    scan.buttons = btnDump;
    scan.buttonCount = allBtns.length;
    return scan;
  }

  // ── Available actions (hero only — visible buttons = hero's turn) ────
  function getAvailableActions() {
    var heroSeat = document.querySelector('sg-poker-table-seat.self-player') || document.querySelector('.player-mini-container-p.self-player');
    if (!heroSeat) { _detectedBtns = {}; return []; }
    _detectedBtns = {};
    var avail = [];

    // Primary: scan ALL known selectors (including allin) + cache element refs
    for (var name in BTN_SEL) {
      var btn = document.querySelector(BTN_SEL[name]);
      var rect = btn ? btn.getBoundingClientRect() : null;
      if (btn && rect && rect.width > 0 && rect.height > 0) {
        avail.push(name);
        _detectedBtns[name] = {
          el: btn, selector: BTN_SEL[name],
          text: (btn.textContent || '').trim().substring(0, 30),
          x: Math.round(rect.x + rect.width / 2),
          y: Math.round(rect.y + rect.height / 2)
        };
      }
    }

    // Also detect slider presets if slider is open
    detectSliderPresets();

    // Fallback: scan ALL visible control elements by class
    if (avail.length === 0) {
      var actionMap = {fold:'fold', check:'check', call:'call', raise:'raise', bet:'bet',
                       cashout:'cashout', show:'show', allin:'all_in'};
      var candidates = document.querySelectorAll('[class*="fold"], [class*="check"], [class*="call"], [class*="raise"], [class*="bet-c"], [class*="cash_out"], [class*="all_in"]');
      for (var i = 0; i < candidates.length; i++) {
        var el = candidates[i];
        if (el.offsetParent === null && el.offsetWidth === 0) continue;
        var cls = el.className.toLowerCase();
        for (var key in actionMap) {
          var searchTerm = actionMap[key] || key;
          if (cls.indexOf(searchTerm) !== -1 && avail.indexOf(key) === -1) {
            avail.push(key);
            var frect = el.getBoundingClientRect();
            _detectedBtns[key] = {
              el: el, selector: buildCssPath(el),
              text: (el.textContent || '').trim().substring(0, 30),
              x: Math.round(frect.x + frect.width / 2),
              y: Math.round(frect.y + frect.height / 2)
            };
          }
        }
      }
      if (avail.length > 0 && _n <= 5) {
        console.log('[W4P] actions via fallback:', avail.join(','));
      }
    }

    // Log detected buttons on first few ticks for debugging
    if (avail.length > 0 && _n <= 3) {
      var btnList = [];
      for (var bk in _detectedBtns) {
        btnList.push(bk + '=' + _detectedBtns[bk].selector);
      }
      console.log('[W4P] detected buttons: ' + btnList.join(' | '));
    }

    return avail;
  }

  // ── Button detection (exact selectors + state for remote) ───
  function detectButtons() {
    var result = { actions: [], presets: [], slider: null };

    // ── FULL SELECTOR VALIDATION (runs every tick) ──
    // Context check: are we in the right document?
    if (_n <= 3 || _n % 30 === 0) {
      var _iframes = document.querySelectorAll('iframe');
      var _iframeInfo = [];
      for (var fi = 0; fi < _iframes.length; fi++) {
        var _if = _iframes[fi];
        _iframeInfo.push({src: (_if.src||'').substring(0, 80), id: _if.id||'', vis: _if.offsetWidth > 0});
      }
      console.log('[W4P][CTX] url=' + location.href.substring(0, 100) +
        ' | doc.title=' + document.title.substring(0, 40) +
        ' | inIframe=' + (window !== window.top) +
        ' | iframes=' + _iframes.length + (_iframeInfo.length > 0 ? ' ' + JSON.stringify(_iframeInfo) : ''));
    }
    var heroSeat = document.querySelector('sg-poker-table-seat.self-player') || document.querySelector('.player-mini-container-p.self-player');
    // heroActive = self-player exists AND visible action buttons present (no .active class needed)
    var _heroActive = false;
    if (heroSeat) {
      var _visSels = ['.control-b-view-p.fold-c', '.control-b-view-p.check-c', '.control-b-view-p.call-c', '.control-b-view-p.raise-c', '.control-b-view-p.bet-c'];
      for (var _vi = 0; _vi < _visSels.length; _vi++) {
        var _vel = document.querySelector(_visSels[_vi]);
        if (_vel) { var _vr = _vel.getBoundingClientRect(); if (_vr.width > 0 && _vr.height > 0) { _heroActive = true; break; } }
      }
    }

    // Build full validation report — ALWAYS, regardless of turn state
    var _validation = [];
    for (var vname in BTN_SEL) {
      var vel = document.querySelector(BTN_SEL[vname]);
      var vr = vel ? vel.getBoundingClientRect() : null;
      _validation.push({
        name: vname,
        sel: BTN_SEL[vname],
        found: !!vel,
        visible: !!vel && vr && vr.width > 0 && vr.height > 0,
        text: vel ? (vel.innerText || '').trim().substring(0, 30) : null,
        className: vel ? vel.className : null,
        disabled: vel ? (vel.disabled || vel.classList.contains('disabled')) : false,
        rect: vr ? {x:Math.round(vr.x),y:Math.round(vr.y),w:Math.round(vr.width),h:Math.round(vr.height)} : null
      });
    }
    // Also count all .control-b-view-p elements (raw DOM truth)
    var _allCtrl = document.querySelectorAll('.control-b-view-p');
    var _ctrlDump = [];
    for (var cci = 0; cci < Math.min(_allCtrl.length, 12); cci++) {
      var _ce = _allCtrl[cci];
      var _cr = _ce.getBoundingClientRect();
      _ctrlDump.push({
        cls: _ce.className,
        text: (_ce.innerText||'').trim().substring(0, 20),
        vis: _cr.width > 0 && _cr.height > 0,
        disabled: _ce.disabled || _ce.classList.contains('disabled')
      });
    }

    // Log every tick (compact)
    var _foundNames = _validation.filter(function(v){return v.found;}).map(function(v){return v.name+(v.visible?'[V]':'[H]')+(v.disabled?'[D]':'');});
    console.log('[W4P][VALID] hero=' + (heroSeat?'Y':'N') + ' active=' + _heroActive +
      ' | selectors: ' + (_foundNames.length > 0 ? _foundNames.join(',') : 'NONE') +
      ' | .control-b-view-p=' + _allCtrl.length);

    // Full dump every 10 ticks (or when any selector found)
    if (_n % 10 === 1 || _foundNames.length > 0) {
      console.log('[W4P][VALID-FULL]', JSON.stringify({
        tick: _n, heroSeat: !!heroSeat, heroActive: _heroActive,
        heroClasses: heroSeat ? heroSeat.className.substring(0, 100) : null,
        selectors: _validation,
        rawControls: _ctrlDump
      }));
    }

    // Store on window for console inspection: _w4p_lastValidation
    window._w4p_lastValidation = {
      tick: _n, heroSeat: !!heroSeat, heroActive: _heroActive,
      selectors: _validation, rawControls: _ctrlDump
    };

    // No gate on .active — if hero seated but no visible buttons, actions will just be empty

    // 1. Known action buttons — scan BTN_SEL for visible ones
    for (var name in BTN_SEL) {
      if (name === 'allin') continue;
      var el = document.querySelector(BTN_SEL[name]);
      var elr = el ? el.getBoundingClientRect() : null;
      if (el && elr && elr.width > 0 && elr.height > 0) {
        var text = (el.innerText || el.textContent || '').trim();
        var amtMatch = text.match(/([\d,]+\.?\d*)/);
        result.actions.push({
          action: name,
          text: text,
          amount: amtMatch ? parseFloat(amtMatch[1].replace(/,/g, '')) : null,
          selector: BTN_SEL[name]
        });
      }
    }
    // Check native all-in button separately
    var allinEl = document.querySelector(BTN_SEL.allin);
    var allinR = allinEl ? allinEl.getBoundingClientRect() : null;
    if (allinEl && allinR && allinR.width > 0 && allinR.height > 0) {
      var allinText = (allinEl.innerText || allinEl.textContent || '').trim();
      var allinAmt = allinText.match(/([\d,]+\.?\d*)/);
      result.actions.push({
        action: 'allin',
        text: allinText,
        amount: allinAmt ? parseFloat(allinAmt[1].replace(/,/g, '')) : null,
        selector: BTN_SEL.allin
      });
    }

    // 2. Presets (min/half/pot/max) from slider panel
    var PRPAT = { min: /\bmin\b/i, half: /\bhalf\b|1\/2/i, pot: /\bpot\b/i, max: /\bmax\b|all[\s-]?in/i };
    var presetEls = document.querySelectorAll(
      'sg-poker-betting-slider li, .limits-buttons-v-p li, [class*="limit"] li, [class*="preset"] li');
    for (var p = 0; p < presetEls.length; p++) {
      var pel = presetEls[p];
      if (pel.offsetParent === null && pel.offsetWidth === 0) continue;
      var ptext = (pel.innerText || pel.textContent || '').trim();
      if (!ptext) continue;
      var label = 'custom';
      for (var pk in PRPAT) {
        if (PRPAT[pk].test(ptext)) { label = pk; break; }
      }
      var pamtMatch = ptext.match(/([\d,]+\.?\d*)/);
      result.presets.push({
        label: label, text: ptext,
        amount: pamtMatch ? parseFloat(pamtMatch[1].replace(/,/g, '')) : null,
        index: p
      });
    }

    // 3. Slider state (range + text/number input)
    var rangeEl = document.querySelector('sg-poker-betting-slider input[type="range"]') || document.querySelector('input[type="range"]');
    var amtEl = document.querySelector('sg-poker-betting-slider input[type="number"]') || document.querySelector('sg-poker-betting-slider input[type="text"]');
    if (!amtEl) {
      var ins = document.querySelectorAll('input[type="number"], input[type="text"]');
      for (var ii = 0; ii < ins.length; ii++) {
        if ((ins[ii].offsetParent !== null || ins[ii].offsetWidth > 0) && !ins[ii].closest('sg-buy-in-modal')) {
          amtEl = ins[ii]; break;
        }
      }
    }
    if (rangeEl || amtEl) {
      result.slider = {
        visible: (rangeEl && rangeEl.offsetParent !== null) || (amtEl && amtEl.offsetParent !== null),
        current: amtEl ? parseFloat(amtEl.value) || 0 : (rangeEl ? parseFloat(rangeEl.value) || 0 : 0),
        min: rangeEl ? parseFloat(rangeEl.min) || 0 : null,
        max: rangeEl ? parseFloat(rangeEl.max) || 0 : null,
        step: rangeEl ? parseFloat(rangeEl.step) || 1 : null
      };
    }

    // ── DIAGNOSTIC: log when we actually detect buttons ──
    if (result.actions.length > 0) {
      console.log('[W4P][DIAG] DETECTED BUTTONS:', JSON.stringify(result.actions.map(function(a) { return a.action + '(' + (a.amount || '-') + ')'; })));
    }

    // Pipe diagnostics through API (can't see Chrome console remotely)
    // Only send full scan periodically to keep payload small
    if (_n <= 5 || _n % 30 === 0) {
      result._dom_scan = domScan();
    }
    result._debug = {
      tick: _n,
      heroSeat: !!heroSeat,
      heroActive: _heroActive,
      selectorHits: _foundNames,
      rawControlCount: _allCtrl.length,
      url: location.href.substring(0, 120),
      v: 'v21'
    };

    _lastButtons = result;
    return result;
  }

  // ── Build full snapshot — ALL seats ──────────────────────────
  function buildSnapshot() {
    var tableId = getTableId();
    if (!tableId) {
      if (_n <= 5 || _n % 30 === 0)
        console.log('[W4P] no tableId');
      return null;
    }

    var containers = document.querySelectorAll('sg-poker-table-seat');
    if (!containers.length) containers = document.querySelectorAll('.player-mini-container-p');
    if (!containers.length) {
      if (_n <= 5 || _n % 30 === 0)
        console.log('[W4P] no seat containers');
      return null;
    }

    // Dealer position
    var dealerEl = document.querySelector('.dealer-icon-view');
    var dMatch = dealerEl ? dealerEl.className.match(/position-(\d+)/) : null;
    var dealerSeat = dMatch ? parseInt(dMatch[1]) : null;

    // Pot amount
    var potEl = document.querySelector('.pot-w-view-p') || document.querySelector('.pot-amount') || document.querySelector('.total-pot');
    var potText = potEl ? (potEl.innerText || potEl.textContent || '') : '';
    var pMatch = potText.match(/([\d.,]+)/);
    var potZar = pMatch ? parseFloat(pMatch[1].replace(',', '')) : 0;

    // Board cards (community cards only)
    var boardCards = [];
    var boardEl = document.querySelector('sg-poker-board');
    if (boardEl) {
      var bcEls = boardEl.querySelectorAll('.single-cart-view-p');
      for (var i = 0; i < bcEls.length; i++) {
        if (bcEls[i].closest('sg-poker-table-seat') || bcEls[i].closest('.player-mini-container-p')) continue;
        var c = parseCard(bcEls[i].className);
        if (c) boardCards.push(c);
      }
    }
    if (boardCards.length < 3) {
      var allCardEls = document.querySelectorAll('.single-cart-view-p');
      boardCards = [];
      for (var i = 0; i < allCardEls.length; i++) {
        if (allCardEls[i].closest('.player-mini-container-p') || allCardEls[i].closest('sg-poker-table-seat')) continue;
        var c2 = parseCard(allCardEls[i].className);
        if (c2) boardCards.push(c2);
      }
    }

    var street = 'PREFLOP';
    if (boardCards.length >= 5) street = 'RIVER';
    else if (boardCards.length >= 4) street = 'TURN';
    else if (boardCards.length >= 3) street = 'FLOP';

    var buttons = detectButtons();
    var avail = buttons.actions.map(function(a) { return a.action; });

    // ── STEP 2 DIAG: Log detected buttons EVERY tick ──
    console.log('[W4P][DIAG] DETECTED BUTTONS:', JSON.stringify(buttons.actions.map(function(a){return a.action;})));
    console.log('[W4P][DIAG] available_actions:', JSON.stringify(avail));

    // ── Detect active seat (whose turn to act) from PokerBet DOM ──
    // self-player with visible action buttons = hero's turn (primary signal)
    // .active class is checked as secondary hint only
    var activePlayerName = null;
    for (var ai = 0; ai < containers.length; ai++) {
      var act = containers[ai];
      var isActSelf = act.classList.contains('self-player');
      var hasActClass = act.classList.contains('active') || !!act.querySelector('.active-turn');
      if (hasActClass || (isActSelf && avail.length > 0)) {
        var anEl = act.querySelector('p.single-win-item-sizes') || act.querySelector('.player-name');
        activePlayerName = anEl ? (anEl.innerText || anEl.textContent || '').trim() : null;
        if (!activePlayerName) activePlayerName = null;
        break;
      }
    }

    // ── Scrape ALL seats ────────────────────────────────────────
    var seats = [];
    var heroName = null;

    for (var i = 0; i < containers.length; i++) {
      var ct = containers[i];
      var isHero = ct.classList.contains('self-player') || !!ct.querySelector('.self-player');

      var posMatch = ct.className.match(/position-(\d+)/);
      var seatIdx = posMatch ? parseInt(posMatch[1]) : i;

      // Player name
      var nameEl = ct.querySelector('p.single-win-item-sizes') || ct.querySelector('.player-name');
      var name = nameEl ? (nameEl.innerText || nameEl.textContent || '').trim() : null;
      if (!name || name === '') name = null;

      // Stack
      var stackEl = ct.querySelector('.player-text-info-p span b') || ct.querySelector('.player-text-info-p b') || ct.querySelector('.player-stack');
      var stackText = stackEl ? (stackEl.innerText || stackEl.textContent || '') : '';
      var sMatch = stackText.match(/([\d.,]+)/);
      var stackZar = sMatch ? parseFloat(sMatch[1].replace(',', '')) : 0;

      // Hole cards — try to parse for ALL seats (fallback hero detection)
      var holeCards = [];
      var cardsContainer = ct.querySelector('.carts-container-p');
      var hcEls = (cardsContainer || ct).querySelectorAll('.single-cart-view-p');
      for (var j = 0; j < hcEls.length; j++) {
        var hc = parseCard(hcEls[j].className);
        if (hc) holeCards.push(hc);
      }

      // REMOVED: hole-cards fallback was marking villains as hero during showdown
      // when all players' cards are revealed face-up. The .self-player class is
      // the ONLY reliable hero signal — it's set by the poker client on the
      // player's own seat and never appears on villains even at showdown.

      if (isHero) heroName = name;

      // HERO-ONLY: skip all non-hero seats. Each bot sends only itself.
      // Other bots at the same table send their own snapshots.
      if (!isHero) continue;

      // Status detection
      var sittingOut = ct.classList.contains('seat-out-v') || !!ct.querySelector('.seat-out-v');
      var isFolded = ct.classList.contains('folded') || !!ct.querySelector('.folded');
      var isActive = avail.length > 0;  // visible buttons = active turn (no .active class needed)

      var status = 'playing';
      if (sittingOut) status = 'sitting_out';
      else if (isFolded) status = 'folded';
      else if (holeCards.length === 0 && street !== 'PREFLOP') status = 'folded';

      seats.push({
        seat_index:        seatIdx,
        name:              name,
        stack_zar:         stackZar,
        hole_cards:        holeCards,
        is_hero:           true,
        is_self_player:    true,
        is_dealer:         seatIdx === dealerSeat,
        status:            status,
        sitting_out:       sittingOut,
        is_active:         isActive,
        available_actions: avail,
        bet:               getPlayerBet(seatIdx)
      });
    }

    // Must have found hero
    if (!heroName) {
      if (_n <= 5 || _n % 30 === 0) {
        var seatClasses = [];
        for (var d = 0; d < containers.length; d++) {
          var dct = containers[d];
          var dname = dct.querySelector('p.single-win-item-sizes') || dct.querySelector('.player-name');
          var dnameText = dname ? dname.textContent.trim() : 'EMPTY';
          seatClasses.push(dnameText + ':' + dct.className.replace(/\s+/g, '.'));
        }
        console.log('[W4P] no hero | ' + containers.length + ' seats | ' + seatClasses.join(' | '));
      }
      return null;
    }

    return {
      table_id:      tableId,
      bot_id:        heroName,
      session_id:    _sessionId,
      seats:         seats,
      board: {
        flop:  boardCards.slice(0, 3),
        turn:  boardCards[3] || null,
        river: boardCards[4] || null
      },
      pot_zar:       potZar,
      dealer_seat:   dealerSeat,
      street:        street,
      variant:       'plo',
      buttons:       buttons,
      available_actions: avail,
      active_player: activePlayerName,
      ts:            new Date().toISOString(),
      source_key:    'w4p_inject'
    };
  }

  // ── State hash for dedup ─────────────────────────────────────
  function stateHash(snap) {
    var hero = null;
    for (var i = 0; i < snap.seats.length; i++) {
      if (snap.seats[i].is_hero) { hero = snap.seats[i]; break; }
    }
    if (!hero) return '';
    return JSON.stringify({
      si: hero.seat_index, n: hero.name, st: hero.stack_zar,
      hc: hero.hole_cards.join(''), stat: hero.status,
      act: hero.is_active, aa: hero.available_actions.join(','),
      btn: snap.buttons ? snap.buttons.actions.map(function(a) { return a.action + ':' + (a.amount || ''); }).join(',') : '',
      b: snap.board, p: snap.pot_zar, str: snap.street, d: snap.dealer_seat
    });
  }

  // ── Snapshot response handler ────────────────────────────────
  function handleSnapshotResponse(data) {
    if (data.ok) {
      if (data.seat_token) {
        if (!_seatToken) {
          console.log('[W4P] Connected! seat_no=' + data.seat_no + ' token=' + data.seat_token.substr(0, 8) + '...');
          _seatToken = data.seat_token;
          pollCommands();
        } else {
          _seatToken = data.seat_token;
        }
      }
    } else {
      console.log('[W4P] API error:', data.error);
    }
  }

  // ── Send hand data to collector (for engine textarea) ────────
  var _lastCollectorPayload = '';
  function sendToCollector(snap) {
    if (!snap || !snap.seats || snap.seats.length === 0) return;
    // Build collector text: hero hand + BOARD: tag
    var hero = null;
    for (var i = 0; i < snap.seats.length; i++) {
      if (snap.seats[i].is_hero && snap.seats[i].hole_cards && snap.seats[i].hole_cards.length > 0) {
        hero = snap.seats[i]; break;
      }
    }
    if (!hero) return;
    var lines = [hero.hole_cards.join('')];
    // Build board string
    var b = snap.board || {};
    var boardCards = [];
    if (Array.isArray(b.flop)) boardCards = boardCards.concat(b.flop);
    if (b.turn) boardCards.push(b.turn);
    if (b.river) boardCards.push(b.river);
    if (boardCards.length >= 3) lines.push('BOARD:' + boardCards.join(''));
    var payload = lines.join('\n');
    // Dedup: only send if changed
    if (payload === _lastCollectorPayload) return;
    _lastCollectorPayload = payload;
    bridgeFetchRaw('/collector/save', 'POST', { text: payload, source: 'w4p' });
  }

  // ── Send snapshot (via bridge → service worker) ──────────────
  function sendSnapshot(snap) {
    bridgeFetch('/snapshot', 'POST', snap, function(resp) {
      if (resp && resp.ok) handleSnapshotResponse(resp.data);
      else console.log('[W4P] bridge error:', resp ? resp.error : 'no response');
    });
  }

  // ── Set raise slider amount ──────────────────────────────────
  function setRaiseAmount(amount) {
    if (!amount || amount <= 0) return false;
    var slider = document.querySelector('sg-poker-betting-slider input[type="range"]');
    if (!slider) slider = document.querySelector('input[type="range"]');
    if (slider) {
      var nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      nativeSet.call(slider, String(amount));
      slider.dispatchEvent(new Event('input', {bubbles: true}));
      slider.dispatchEvent(new Event('change', {bubbles: true}));
      return true;
    }
    var inputs = document.querySelectorAll('input[type="number"], input[type="text"]');
    for (var i = 0; i < inputs.length; i++) {
      var iR = inputs[i].getBoundingClientRect();
      if (iR.width > 0 && iR.height > 0 && !inputs[i].closest('sg-buy-in-modal')) {
        var nativeSet2 = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSet2.call(inputs[i], String(amount));
        inputs[i].dispatchEvent(new Event('input', {bubbles: true}));
        inputs[i].dispatchEvent(new Event('change', {bubbles: true}));
        return true;
      }
    }
    return false;
  }

  // ── Click a DOM button by selector ───────────────────────────
  function clickSel(sel) {
    var btn = document.querySelector(sel);
    var br = btn ? btn.getBoundingClientRect() : null;
    if (btn && br && br.width > 0 && br.height > 0) {
      nativeClick(btn);
      return true;
    }
    return false;
  }

  // ── v21: CONFIRMED POKERBET CONTROL MODEL ────────────────────
  // Presets (MAX/POT/MIN/%) select the size → BET/RAISE button text updates → click BET/RAISE executes.
  // BET/RAISE always EXECUTES. It is NOT a slider opener.
  // There is no input[type="range"]. The slider is a custom Angular component.
  // The authoritative amount is in the <i> tag inside the BET/RAISE button.

  // ── Find the BET or RAISE execute button ──
  function findExecuteButton() {
    function _vis(el) { if (!el) return false; var r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }
    var raiseBtn = document.querySelector(BTN_SEL.raise);
    if (_vis(raiseBtn)) return { el: raiseBtn, type: 'raise', sel: BTN_SEL.raise };
    var betBtn = document.querySelector(BTN_SEL.bet);
    if (_vis(betBtn)) return { el: betBtn, type: 'bet', sel: BTN_SEL.bet };
    return null;
  }

  // ── Read amount from BET/RAISE button's <i> tag ──
  function readButtonAmount(btnEl) {
    if (!btnEl) return null;
    var iTag = btnEl.querySelector('i');
    if (!iTag) return null;
    var text = (iTag.textContent || '').replace(/[^\d.]/g, '');
    var val = parseFloat(text);
    return isNaN(val) ? null : val;
  }

  // ── Find preset <li> elements ──
  function findPresets() {
    return document.querySelectorAll(
      'sg-poker-betting-slider .limits-buttons-v-p li, sg-poker-betting-slider li, ' +
      '.limits-buttons-v-p li, [class*="limit"] li, [class*="preset"] li');
  }

  // ── Click a preset element with full event propagation ──
  function clickPreset(presetEl) {
    // Click the <li> itself
    nativeClick(presetEl);
    // Also click all children — Angular may bind on inner <span>, <a>, etc.
    var kids = presetEl.querySelectorAll('*');
    for (var i = 0; i < kids.length; i++) nativeClick(kids[i]);
  }

  // ── CORE: Click preset → wait for amount change → execute BET/RAISE ──
  // This is the ONLY way to size and execute a raise/bet in PokerBet.
  // Hard rule: never execute unless the <i> amount changed or was already correct.
  function presetThenExecute(presetRegex, actionName) {
    var execBtn = findExecuteButton();
    if (!execBtn) {
      console.log('[W4P][' + actionName + '] ABORT: no BET/RAISE button visible');
      return;
    }

    var amountBefore = readButtonAmount(execBtn.el);
    console.log('[W4P][' + actionName + '] button=' + execBtn.type + ' amount_before=' + amountBefore);

    // Find and click the matching preset
    var presets = findPresets();
    var clicked = false;
    var clickedText = '';
    console.log('[W4P][' + actionName + '] scanning ' + presets.length + ' presets for /' + presetRegex.source + '/');

    for (var i = 0; i < presets.length; i++) {
      var txt = (presets[i].textContent || '').trim();
      if (presetRegex.test(txt)) {
        var pr = presets[i].getBoundingClientRect();
        if (pr.width > 0 && pr.height > 0) {
          clickPreset(presets[i]);
          clicked = true;
          clickedText = txt;
          console.log('[W4P][' + actionName + '] clicked preset: "' + txt + '"');
          break;
        }
      }
    }

    // Fallback for MAX: try last preset if regex didn't match
    if (!clicked && /max/i.test(presetRegex.source) && presets.length > 0) {
      var last = presets[presets.length - 1];
      var lr = last.getBoundingClientRect();
      if (lr.width > 0 && lr.height > 0) {
        clickPreset(last);
        clicked = true;
        clickedText = (last.textContent || '').trim();
        console.log('[W4P][' + actionName + '] clicked last preset (MAX fallback): "' + clickedText + '"');
      }
    }

    if (!clicked) {
      console.log('[W4P][' + actionName + '] ABORT: no matching preset found. NOT executing.');
      return;
    }

    // Wait for Angular to update the BET/RAISE button amount, then verify and execute
    var checkCount = 0;
    var maxChecks = 10;  // 10 x 100ms = 1 second max wait
    var verifyTimer = setInterval(function() {
      checkCount++;
      var btn = findExecuteButton();
      if (!btn) {
        clearInterval(verifyTimer);
        console.log('[W4P][' + actionName + '] ABORT: BET/RAISE disappeared during wait');
        return;
      }
      var amountAfter = readButtonAmount(btn.el);

      // Execute if amount changed OR if we've checked enough times (preset may set same amount)
      if (amountAfter !== amountBefore || checkCount >= maxChecks) {
        clearInterval(verifyTimer);
        var btnText = (btn.el.textContent || '').trim().substring(0, 40);
        if (amountAfter === amountBefore && checkCount >= maxChecks) {
          // Amount didn't change — preset click may have failed (isTrusted blocked)
          console.log('[W4P][' + actionName + '] WARNING: amount unchanged after preset click (' +
            amountBefore + ' → ' + amountAfter + '). Preset "' + clickedText + '" may have been blocked.');
          console.log('[W4P][' + actionName + '] NOT executing — amount did not change. Manual action required.');
          return;
        }
        console.log('[W4P][' + actionName + '] amount_before=' + amountBefore + ' amount_after=' + amountAfter +
          ' preset="' + clickedText + '" button="' + btnText + '" — EXECUTING');
        nativeClick(btn.el);
        return;
      }
    }, 100);
  }

  // v21: setSliderValue REMOVED — no input[type="range"] exists in PokerBet.
  // Size is set by clicking preset <li> elements. See presetThenExecute().

  // v21: selectMax/selectMin/selectPot/selectAmount/raiseAmount/executeAllin/confirmRaise ALL REMOVED.
  // All sizing now goes through presetThenExecute(). All execution through findExecuteButton() + nativeClick().

  // ── Click simple action button (fold/check/call/cashout — no sizing needed) ──
  function clickAction(action) {
    var key = action.toLowerCase().replace(/[\s-]/g, '_');
    var sel = BTN_SEL[key];
    if (!sel) { console.log('[W4P] Unknown action:', action); return false; }
    var btn = document.querySelector(sel);
    if (btn && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
      nativeClick(btn);
      console.log('[W4P] Clicked:', action);
      return true;
    }
    console.log('[W4P] Button not visible:', action);
    return false;
  }

  // ── Buy-in handling (v15: faster timeouts) ───────────────────
  function handleBuyin(cmd) {
    var mode = (cmd.type || '').replace('buyin_', '').replace('rebuy_', '');
    // Try sg-buy-in-modal first (if already open)
    var modal = document.querySelector('sg-buy-in-modal');
    if (modal && modal.offsetParent !== null) {
      doBuyin(modal, mode, cmd.amount);
      return;
    }
    // Try clicking hero avatar to open buy-in
    var hero = document.querySelector('.player-mini-container-p.self-player');
    if (hero) {
      nativeClick(hero);
      setTimeout(function() {
        var m = document.querySelector('sg-buy-in-modal');
        if (m) doBuyin(m, mode, cmd.amount);
        else console.log('[W4P] Buy-in modal did not appear');
      }, 400);
    } else {
      // Fallback: generic buy-in button search
      var buyBtns = document.querySelectorAll('button, [class*="buy"], [class*="rebuy"]');
      for (var i = 0; i < buyBtns.length; i++) {
        var txt = (buyBtns[i].textContent || '').trim().toLowerCase();
        if (/buy.?in|rebuy|top.?up/i.test(txt) && buyBtns[i].offsetParent !== null) {
          nativeClick(buyBtns[i]);
          setTimeout(function() {
            var m = document.querySelector('sg-buy-in-modal');
            if (m) doBuyin(m, mode, cmd.amount);
          }, 400);
          return;
        }
      }
    }
  }

  function doBuyin(modal, mode, amount) {
    if (mode === 'max') {
      var maxBtn = modal.querySelector('.modal-balance-v li:nth-child(2) .last-v-p button');
      if (maxBtn && maxBtn.offsetParent !== null) {
        nativeClick(maxBtn);
        console.log('[W4P] Buy-in MAX clicked');
      }
    } else if (mode === 'min') {
      var minBtn = modal.querySelector('.modal-balance-v li:nth-child(2) .mini-button-view-m:first-child button');
      if (minBtn && minBtn.offsetParent !== null) {
        nativeClick(minBtn);
        console.log('[W4P] Buy-in MIN clicked');
      }
    } else if (amount) {
      // Custom amount — set slider/input
      var inputs = modal.querySelectorAll('input[type="number"], input[type="range"], input[type="text"]');
      for (var i = 0; i < inputs.length; i++) {
        if (inputs[i].offsetParent !== null) {
          var nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          nativeSet.call(inputs[i], String(amount));
          inputs[i].dispatchEvent(new Event('input', {bubbles: true}));
          inputs[i].dispatchEvent(new Event('change', {bubbles: true}));
          console.log('[W4P] Buy-in amount set:', amount);
          break;
        }
      }
    }
    // Confirm
    setTimeout(function() {
      var submit = modal.querySelector('.modal-button-container button');
      if (submit && submit.offsetParent !== null) {
        nativeClick(submit);
        console.log('[W4P] Buy-in confirmed');
      }
    }, 300);
  }

  // ── Command handler ──────────────────────────────────────────
  function handleCommand(cmd) {
    var action = (cmd.type || cmd.command || '').toLowerCase();
    console.log('[W4P] CMD:', action, cmd.amount ? 'amt=' + cmd.amount : '');

    // ── Pre-actions & buy-in ──
    if (action === 'buyin' || action === 'rebuy_max' || action === 'rebuy_min' || action === 'buyin_max' || action === 'buyin_min') {
      handleBuyin(cmd); return;
    }
    if (action === 'cashout_preselect' || action === 'cashout_pre') { _cashoutPre = true; console.log('[W4P] CASHOUT preselected — hyper-polling .cash_out-c'); return; }
    if (action === 'cashout_clear' || action === 'clear_cashout') { _cashoutPre = false; console.log('[W4P] CASHOUT preselect cleared'); return; }
    if (action === 'check_fold') { _preAction = 'check_fold'; console.log('[W4P] Pre-action: CHECK/FOLD'); return; }
    if (action === 'check_call') { _preAction = 'check_call'; console.log('[W4P] Pre-action: CHECK/CALL'); return; }
    if (action === 'clear' || action === 'clear_preaction') { _preAction = null; console.log('[W4P] Pre-action cleared'); return; }

    // ── Pure native button clicks — mirror PokerBet exactly ──
    var DIRECT = {
      fold:          '.control-b-view-p.fold-c',
      check:         '.control-b-view-p.check-c',
      call:          '.control-b-view-p.call-c',
      cashout:       '.control-b-view-p.cash_out-c',
      show:          '.control-b-view-p.show-c',
      run_it_twice:  '.control-b-view-p.run_it_twice-c',
      resume_hand:   '.control-b-view-p.resume_hand-c',
      back_to_game:  '.control-b-view-p.back_to_game-c'
    };
    if (DIRECT[action]) {
      var btn = document.querySelector(DIRECT[action]);
      var btnR = btn ? btn.getBoundingClientRect() : null;
      if (btn && btnR && btnR.width > 0 && btnR.height > 0) {
        nativeClick(btn); console.log('[W4P] Clicked native:', action);
      } else { console.log('[W4P] Button not visible:', action); }
      return;
    }

    // ── v21 PRESET-BASED SIZING (click preset → wait for <i> update → execute) ──

    // PLO: no all-in action. Legacy allin → MAX preset
    if (action === 'allin' || action === 'all-in' || action === 'all_in') {
      console.log('[W4P] PLO: allin remapped to MAX preset');
      presetThenExecute(/\bmax\b/i, 'ALLIN→MAX');
      return;
    }

    // RAISE / BET — execute only if no custom amount requested, or displayed amount matches
    if (action === 'raise' || action === 'bet') {
      var execBtn = findExecuteButton();
      if (!execBtn) {
        console.log('[W4P] ' + action + ': no visible BET/RAISE button');
        return;
      }
      var displayed = readButtonAmount(execBtn.el);
      if (cmd.amount) {
        // Custom amount requested — only execute if displayed amount already matches
        var requested = parseFloat(cmd.amount);
        if (!isNaN(requested) && displayed !== null && Math.abs(displayed - requested) < 0.01) {
          console.log('[W4P] ' + action + ': displayed=' + displayed + ' matches requested=' + requested + ' — EXECUTING');
          nativeClick(execBtn.el);
        } else {
          console.log('[W4P] ' + action + ': BLOCKED — custom amount=' + cmd.amount + ' but displayed=' + displayed + '. Custom slider not yet supported.');
        }
      } else {
        // No amount: execute at current displayed amount
        console.log('[W4P] ' + action + ': executing ' + execBtn.type + ' at displayed amount=' + displayed);
        nativeClick(execBtn.el);
      }
      return;
    }

    // POT: click POT preset → wait → execute
    if (action === 'pot') { presetThenExecute(/\bpot\b/i, 'POT'); return; }

    // MAX / RAISE_MAX: click MAX preset → wait → execute
    if (action === 'max' || action === 'raise_max') { presetThenExecute(/\bmax\b/i, 'MAX'); return; }

    // MIN / RAISE_MIN: click MIN preset → wait → execute
    if (action === 'min' || action === 'raise_min') { presetThenExecute(/\bmin\b/i, 'MIN'); return; }

    // HALF / 1/2 / 32%: click percentage preset → wait → execute
    if (action === 'half' || action === '1/2') { presetThenExecute(/1\/2|half|32/i, 'HALF'); return; }

    // CLICK: direct selector click (used by remote with detected selectors)
    if (action === 'click' && cmd.selector) {
      var clickEl = document.querySelector(cmd.selector);
      var clickR = clickEl ? clickEl.getBoundingClientRect() : null;
      if (clickEl && clickR && clickR.width > 0 && clickR.height > 0) {
        nativeClick(clickEl);
        console.log('[W4P] Clicked selector:', cmd.selector);
      } else {
        console.log('[W4P] Selector not found/hidden:', cmd.selector);
      }
      return;
    }

    console.log('[W4P] Unknown command:', action);
  }

  // clickPresetAndConfirm — REMOVED in v21. Replaced by presetThenExecute().
  // Stub kept to prevent ReferenceError if anything still calls it.
  function clickPresetAndConfirm(presetRegex) {
    console.log('[W4P] WARNING: clickPresetAndConfirm() DEPRECATED — use presetThenExecute()');
    presetThenExecute(presetRegex, 'LEGACY');
  }

  function runPreAction(avail) {
    if (!_preAction) return;
    if (_preAction === 'check_fold') {
      if (avail.indexOf('check') !== -1) clickAction('check');
      else if (avail.indexOf('fold') !== -1) clickAction('fold');
    } else if (_preAction === 'check_call') {
      if (avail.indexOf('check') !== -1) clickAction('check');
      else if (avail.indexOf('call') !== -1) clickAction('call');
    }
    _preAction = null;
  }

  // ── Command polling loop ─────────────────────────────────────
  function pollCommands() {
    if (!_seatToken) {
      window._w4p_cmdTimer = setTimeout(pollCommands, CMD_MS[_mode] || 500);
      return;
    }

    bridgeFetch('/commands/pending?token=' + encodeURIComponent(_seatToken), 'GET', null, function(resp) {
      if (resp && resp.ok && resp.data && resp.data.ok && resp.data.command) {
        handleCommand(resp.data.command);
        // Acknowledge immediately
        bridgeFetch('/commands/ack', 'POST', { token: _seatToken, command_id: resp.data.command.id });
      }
    });

    window._w4p_cmdTimer = setTimeout(pollCommands, CMD_MS[_mode] || 500);
  }

  // ── Auto-untick "Wait for Big Blind" ─────────────────────────
  function untickWaitBB() {
    var cbs = document.querySelectorAll('input[type="checkbox"]');
    for (var i = 0; i < cbs.length; i++) {
      if (cbs[i].checked) {
        var label = cbs[i].parentElement ? cbs[i].parentElement.textContent : '';
        if (/wait.*big\s*blind|big\s*blind/i.test(label)) {
          nativeClick(cbs[i]);
          console.log('[W4P] Unticked: Wait for Big Blind');
        }
      }
    }
    var toggles = document.querySelectorAll('.check-box-view-p.active, .toggle-switch.active, [class*="wait-bb"].active');
    for (var j = 0; j < toggles.length; j++) {
      var txt = toggles[j].textContent || '';
      if (/wait.*big\s*blind|big\s*blind/i.test(txt)) {
        nativeClick(toggles[j]);
      }
    }
  }

  // ── Main snapshot loop ───────────────────────────────────────
  function tryCashout() {
    if (!_cashoutPre) return;
    var btn = document.querySelector('.control-b-view-p.cash_out-c');
    if (btn && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
      nativeClick(btn);
      _cashoutPre = false;
      console.log('[W4P] CASHOUT executed via preselect');
    }
  }

  function tick() {
    _n++;
    var snap = buildSnapshot();

    if (!snap) {
      _mode = 'NO_TABLE';
      window._w4p_timer = setTimeout(tick, POLL_MS.NO_TABLE);
      return;
    }

    // Adaptive polling mode
    var hero = null;
    for (var i = 0; i < snap.seats.length; i++) {
      if (snap.seats[i].is_hero) { hero = snap.seats[i]; break; }
    }
    var avail = hero ? hero.available_actions : [];

    // Track board transitions (for pre-action reset only)
    var boardLen = snap.board.flop.length + (snap.board.turn ? 1 : 0) + (snap.board.river ? 1 : 0);
    if (boardLen === 0 && _lastBoardLen > 0) {
      // New hand — clear pre-actions but NOT cashout preselect
      _preAction = null;
    }
    _lastBoardLen = boardLen;

    // Try cashout BEFORE mode calculation (cashout button may appear at any time)
    tryCashout();

    if (avail.length > 0) _mode = 'HERO_TURN';
    else if (snap.street !== 'PREFLOP') _mode = 'HAND_ACTIVE';
    else _mode = 'IDLE';

    // Send on state change OR heartbeat
    var hash = stateHash(snap);
    var now = Date.now();
    var changed = hash !== _lastHash;
    var heartbeat = (now - _lastSendTime) >= HEARTBEAT_MS;

    if (changed || heartbeat) {
      _lastHash = hash;
      _lastSendTime = now;
      sendSnapshot(snap);
      sendToCollector(snap);

      if (hero) {
        console.log('[W4P] #' + _n + (heartbeat && !changed ? ' (hb)' : '') +
                    ' ' + snap.street + ' pot=R' + snap.pot_zar +
                    ' ' + hero.name + '@seat' + hero.seat_index +
                    ' [' + hero.hole_cards.join(',') + ']' +
                    ' seats=' + snap.seats.length +
                    ' board=' + (snap.board.flop.join('') || '-'));
      }
    }

    // Auto-execute pre-actions when hero's turn and actions available
    if (_preAction && avail.length > 0) {
      runPreAction(avail);
    }

    // Use faster polling when cashout preselected
    var pollMs = _cashoutPre ? CASHOUT_POLL_MS : (POLL_MS[_mode] || 1000);
    window._w4p_timer = setTimeout(tick, pollMs);
  }

  // ── Start ────────────────────────────────────────────────────
  untickWaitBB();
  window._w4p_bbTimer = setInterval(untickWaitBB, 5000);

  console.log('[W4P] v22 preset-first-execute + cashout-pre + pre-actions | session=' + _sessionId);
  console.log('[W4P] Polling: hero=' + POLL_MS.HERO_TURN + 'ms cmd=' + CMD_MS.HERO_TURN + 'ms');
  console.log('[W4P] API: ' + API_BASE + ' | Remote: potlimitomaha.xyz/remote');
  tick();

  // ── Public API for debugging ─────────────────────────────────
  window._w4p_buildSnapshot = buildSnapshot;
  window._w4pClickAction = clickAction;
  window._w4pHandleCommand = handleCommand;
  // v21: selectMax/selectMin/selectPot removed — use presetThenExecute directly
  window._w4pPresetExecute = presetThenExecute;
  window._w4pReadButtonAmount = readButtonAmount;
  window._w4pFindExecuteButton = findExecuteButton;
  window._w4pActions = getAvailableActions;
  window._w4p_detectButtons = detectButtons;
  window._w4p_getDetectedBtns = function() { return _detectedBtns; };
  // STEP 3: Force extraction test — run in console: _w4p_forceActions()
  // This injects fake actions into the NEXT snapshot to prove API→UI chain
  window._w4p_forceActions = function() {
    var origDetect = detectButtons;
    detectButtons = function() {
      var r = origDetect();
      r.actions = [
        {action:'fold', text:'Fold', amount:null, selector:'.control-b-view-p.fold-c'},
        {action:'call', text:'Call 2.00', amount:2.00, selector:'.control-b-view-p.call-c'},
        {action:'raise', text:'Raise', amount:null, selector:'.control-b-view-p.raise-c'}
      ];
      console.log('[W4P][STEP3] FORCED actions: fold,call,raise');
      return r;
    };
    console.log('[W4P][STEP3] Force mode ON — next snapshots will have fold/call/raise');
  };
  window._w4p_injected = true;
  window._w4p_stop = function() {
    clearTimeout(window._w4p_timer);
    clearTimeout(window._w4p_cmdTimer);
    clearInterval(window._w4p_bbTimer);
    if (_cashoutTimer) clearInterval(_cashoutTimer);
    console.log('[W4P] stopped');
  };
})();
