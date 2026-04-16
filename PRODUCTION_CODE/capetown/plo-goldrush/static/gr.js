// GoldRush Remote Table Control - Browser Scraper v1.0
// Loads via: fetch('https://15.240.44.80/goldrush/gr.js').then(r=>r.text()).then(eval)

(function() {
  'use strict';

  // Configuration
  var API_BASE = window._gr_api_base || 'https://15.240.44.80/api';
  var API_KEY = 'gr_default';
  var POLL_MS = 2000;
  var COMMAND_POLL_MS = 1000;
  var SITE = 'goldrush'; // Platform identifier

  // State
  var _sessionId = generateSessionId();
  var _seatToken = sessionStorage.getItem('gr_seat_token') || null;
  var _preAction = null;
  var _lastSampleKey = null;
  var _n = 0;
  var _tableId = null;
  var _commandTimer = null;

  // Bot Identity
  var _botId = window._botId || localStorage.getItem('gr_bot_id') || 'unknown-gr-bot';
  if (window._botId) {
    localStorage.setItem('gr_bot_id', window._botId);
  }

  console.log('[GR] GoldRush Remote Control v1.0 loaded');
  console.log('[GR] Session ID:', _sessionId);
  console.log('[GR] Bot ID:', _botId);

  function generateSessionId() {
    return 'gr_sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  }

  function getTableId() {
    // TODO: Adapt to GoldRush URL structure
    var match = location.href.match(/\/table\/(\d+)/);
    return match ? 'goldrush_' + match[1] : null;
  }

  function buildSnapshot() {
    _tableId = getTableId();
    if (!_tableId) {
      console.log('[GR] No table ID found in URL');
      return null;
    }

    // TODO: Adapt DOM selectors for GoldRush
    // This is a template - adjust selectors based on GoldRush HTML structure

    var snapshot = {
      bot_id: _botId,
      site: SITE, // NEW: Platform tag
      payload_id: 'gr_snap_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
      session_id: _sessionId,
      table_id: _tableId,
      timestamp_utc: new Date().toISOString(),
      variant: 'plo4-6max', // Adjust based on GoldRush game type
      street: 'PREFLOP', // TODO: Detect from DOM
      seats: [], // TODO: Extract from GoldRush DOM
      board: { flop: [], turn: null, river: null }, // TODO: Extract from DOM
      action_buttons: { visible: false }, // TODO: Detect from DOM
      source_key: 'goldrush_remote',
      hand_id: _tableId + '_pending'
    };

    return snapshot;
  }

  function isReady(snap) {
    if (!snap) return { ready: false, reason: 'No snapshot' };

    var heroSeat = snap.seats.find(function(s) { return s.is_hero; });
    if (!heroSeat) return { ready: false, reason: 'No hero seat' };

    if (!_seatToken) {
      console.log('[GR] Initial connection - sending snapshot');
      return { ready: true, reason: 'Initial connection', sampleKey: 'initial_' + Date.now() };
    }

    if (snap.board.flop.length < 3) return { ready: false, reason: 'No flop yet' };
    if (heroSeat.hole_cards.length < 4) return { ready: false, reason: 'No hero cards' };

    var sampleKey = heroSeat.hole_cards.sort().join('') + '_' + snap.board.flop.sort().join('');

    if (sampleKey === _lastSampleKey) {
      return { ready: false, reason: 'Duplicate sample', sampleKey: sampleKey };
    }

    return { ready: true, reason: 'OK', sampleKey: sampleKey };
  }

  function executeNow(action) {
    console.log('[GR] Executing:', action);
    // TODO: Adapt button selectors for GoldRush
    var btnSelector = null;
    if (action === 'fold') btnSelector = '.goldrush-fold-btn'; // ADJUST SELECTOR
    else if (action === 'check') btnSelector = '.goldrush-check-btn'; // ADJUST SELECTOR
    else if (action === 'call') btnSelector = '.goldrush-call-btn'; // ADJUST SELECTOR
    else if (action === 'cashout') btnSelector = '.goldrush-cashout-btn'; // ADJUST SELECTOR

    if (!btnSelector) {
      console.log('[GR] Unknown action:', action);
      return;
    }

    var btn = document.querySelector(btnSelector);
    if (btn) {
      btn.click();
      console.log('[GR] ✓ Clicked:', action);
    } else {
      console.log('[GR] Button not visible:', action);
    }
  }

  function executePreAction(preAction, buttons) {
    console.log('[GR] Pre-action triggered:', preAction);

    if (preAction === 'check_fold') {
      if (buttons.check) executeNow('check');
      else if (buttons.fold) executeNow('fold');
    } else if (preAction === 'check_call') {
      if (buttons.check) executeNow('check');
      else if (buttons.call) executeNow('call');
    }

    _preAction = null;
  }

  function handleCommand(cmd) {
    console.log('[GR] Command received:', cmd.type);

    if (cmd.type === 'fold' || cmd.type === 'check' || cmd.type === 'call' || cmd.type === 'cashout') {
      executeNow(cmd.type);
    } else if (cmd.type === 'check_fold') {
      _preAction = 'check_fold';
      console.log('[GR] Pre-action set: check_fold');
    } else if (cmd.type === 'check_call') {
      _preAction = 'check_call';
      console.log('[GR] Pre-action set: check_call');
    } else if (cmd.type === 'clear') {
      _preAction = null;
      console.log('[GR] Pre-action cleared');
    }
  }

  function startCommandPolling() {
    if (_commandTimer) return;

    console.log('[GR] Starting command polling');

    _commandTimer = setInterval(function() {
      if (!_seatToken) return;

      fetch(API_BASE + '/commands/pending?token=' + _seatToken)
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.ok && data.command) {
            handleCommand(data.command);

            fetch(API_BASE + '/commands/ack', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                token: _seatToken,
                command_id: data.command.id
              })
            });
          }
        })
        .catch(function(err) {
          console.log('[GR] Command poll error:', err);
        });
    }, COMMAND_POLL_MS);
  }

  // Main polling loop
  setInterval(function() {
    _n++;

    var snap = buildSnapshot();
    if (!snap) return;

    var heroSeat = snap.seats.find(function(s) { return s.is_hero; });
    var activeSeats = snap.seats.filter(function(s) { return s.status === 'playing'; }).length;
    console.log('[GR] SNAPSHOT #' + _n + ': table=' + snap.table_id +
                ' | seats=' + snap.seats.length + ' active=' + activeSeats +
                ' | street=' + snap.street);

    var gate = isReady(snap);
    if (gate.ready) {
      if (!_seatToken) {
        console.log('[GR] Sending initial snapshot...');

        fetch(API_BASE + '/snapshot', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': API_KEY
          },
          body: JSON.stringify(snap)
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.ok) {
            _seatToken = data.seat_token;
            sessionStorage.setItem('gr_seat_token', _seatToken);
            console.log('[GR] ✓ Token received:', _seatToken.substr(0, 8) + '...');
            console.log('[GR] Seat index:', data.seat_index);

            startCommandPolling();
          } else {
            console.log('[GR] Snapshot failed:', data.error);
          }
        })
        .catch(function(err) {
          console.log('[GR] Network error:', err);
        });
      } else {
        fetch(API_BASE + '/snapshot', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': API_KEY
          },
          body: JSON.stringify(snap)
        })
        .then(function(r) { return r.json(); })
        .catch(function(err) {
          console.log('[GR] Heartbeat error:', err);
        });
      }

      _lastSampleKey = gate.sampleKey;
    } else {
      console.log('[GR] Not ready:', gate.reason);
    }

    if (_preAction && snap.action_buttons.visible) {
      executePreAction(_preAction, snap.action_buttons);
    }

  }, POLL_MS);

  console.log('[GR] Started polling (interval=' + POLL_MS + 'ms)');
  window._gr_buildSnapshot = buildSnapshot;
  window._gr_injected = true;
  window._gr_active = true;
})();
