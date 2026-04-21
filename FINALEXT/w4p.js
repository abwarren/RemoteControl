// W4P Injectable v15.4 - PLO Remote Table Control (hero-only: .self-player class ONLY, no fallbacks)
// Paste into skillgames iframe console, or: fetch('https://potlimitomaha.xyz/w4p.js').then(r=>r.text()).then(eval)
// Scrapes ALL seats, sends structured snapshots, polls commands, clicks buttons
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

  // v15: tightened polling — faster detection, faster commands
  var POLL_MS = { HERO_TURN: 200, HAND_ACTIVE: 300, IDLE: 600, NO_TABLE: 2000 };
  var CMD_MS  = { HERO_TURN: 80, HAND_ACTIVE: 100, IDLE: 400 };
  var HEARTBEAT_MS = 8000;

  var _mode = 'IDLE';
  var _seatToken = null;
  var _preAction = null;    // 'check_fold' | 'check_call' | null
  var _lastHash = null;
  var _lastSendTime = 0;
  var _n = 0;
  var _sessionId = 'w4p_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);

  var RANK_MAP = { 'a':'A', 'k':'K', 'q':'Q', 'j':'J', 't':'T', '10':'T' };

  // ── Action button selectors (PokerBet / BetConstruct DOM) ───
  var BTN_SEL = {
    fold:         '.control-b-view-p.fold-c',
    check:        '.control-b-view-p.check-c',
    call:         '.control-b-view-p.call-c',
    raise:        '.control-b-view-p.raise-c',
    bet:          '.control-b-view-p.bet-c',
    cashout:      '.control-b-view-p.cash_out-c',
    allin:        '.control-b-view-p.raise-c',
    show:         '.control-b-view-p.show-c',
    run_it_twice: '.control-b-view-p.run_it_twice-c',
    resume_hand:  '.control-b-view-p.resume_hand-c',
    back_to_game: '.control-b-view-p.back_to_game-c'
  };

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

  // ── Available actions (hero only) ────────────────────────────
  function getAvailableActions() {
    var avail = [];
    // Primary: known selectors
    for (var name in BTN_SEL) {
      if (name === 'allin') continue;
      var btn = document.querySelector(BTN_SEL[name]);
      if (btn && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
        avail.push(name);
      }
    }
    // Fallback: scan ALL visible buttons/divs with action-like classes or text
    if (avail.length === 0) {
      var actionMap = {fold:'fold', check:'check', call:'call', raise:'raise', bet:'bet', cashout:'cashout', show:'show'};
      var candidates = document.querySelectorAll('[class*="fold"], [class*="check"], [class*="call"], [class*="raise"], [class*="bet-c"], [class*="cash_out"]');
      for (var i = 0; i < candidates.length; i++) {
        var el = candidates[i];
        if (el.offsetParent === null && el.offsetWidth === 0) continue;
        var cls = el.className.toLowerCase();
        for (var key in actionMap) {
          if (cls.indexOf(key) !== -1 && avail.indexOf(key) === -1) {
            avail.push(key);
          }
        }
      }
      // Last resort: buttons/spans with action text
      if (avail.length === 0) {
        var btns = document.querySelectorAll('button, [role="button"], .btn, [class*="control"]');
        for (var j = 0; j < btns.length; j++) {
          var b = btns[j];
          if (b.offsetParent === null && b.offsetWidth === 0) continue;
          var txt = (b.textContent || '').trim().toLowerCase();
          for (var key2 in actionMap) {
            if (txt === key2 && avail.indexOf(key2) === -1) avail.push(key2);
          }
        }
      }
      if (avail.length > 0 && _n <= 5) {
        console.log('[W4P] actions found via fallback:', avail.join(','));
      }
    }
    return avail;
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

    var avail = getAvailableActions();

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
      var isActive = ct.classList.contains('active') || !!ct.querySelector('.active-turn');

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
        available_actions: avail
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
      player_id:     heroName,
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

  // ── Send snapshot (direct fetch) ─────────────────────────────
  function sendSnapshot(snap) {
    fetch(API_BASE + '/snapshot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
      body: JSON.stringify(snap)
    })
    .then(function(r) { return r.json(); })
    .then(function(data) { handleSnapshotResponse(data); })
    .catch(function(e) {
      console.log('[W4P] fetch error:', e.message);
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
      if (inputs[i].offsetParent !== null && !inputs[i].closest('sg-buy-in-modal')) {
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
    if (btn && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
      btn.click();
      return true;
    }
    return false;
  }

  // ── Execute raise / bet with proper two-step flow ────────────
  // v15: Click RAISE to open slider → set amount → click confirm
  function executeRaise(amount) {
    var raiseBtn = document.querySelector(BTN_SEL.raise) || document.querySelector(BTN_SEL.bet);
    if (!raiseBtn || (raiseBtn.offsetParent === null && raiseBtn.offsetWidth === 0)) {
      console.log('[W4P] Raise/bet button not visible');
      return false;
    }

    // If no specific amount or allin, just click raise (uses current slider position)
    if (!amount || amount === 'max') {
      raiseBtn.click();
      if (amount === 'max') {
        // Try clicking MAX preset after a brief DOM settle
        setTimeout(function() {
          var maxBtn = document.querySelector('sg-poker-betting-slider .limits-buttons-v-p > ul > li:last-child');
          if (!maxBtn) maxBtn = document.querySelector('sg-poker-betting-slider .limits-buttons-v-p > ul > li:nth-child(4)');
          if (maxBtn && maxBtn.offsetParent !== null) {
            maxBtn.click();
            // Confirm the raise
            setTimeout(function() { confirmRaise(); }, 150);
          } else {
            confirmRaise();
          }
        }, 150);
      }
      console.log('[W4P] Clicked raise' + (amount === 'max' ? ' (ALL-IN)' : ''));
      return true;
    }

    // Specific amount: check if slider is already visible
    var slider = document.querySelector('sg-poker-betting-slider input[type="range"]');
    if (slider && slider.offsetParent !== null) {
      // Slider already open — set amount and confirm immediately
      setRaiseAmount(amount);
      setTimeout(function() { confirmRaise(); }, 100);
      console.log('[W4P] Raise amount=' + amount + ' (slider open)');
      return true;
    }

    // Slider not visible — click raise to open it, then set amount
    raiseBtn.click();
    setTimeout(function() {
      setRaiseAmount(amount);
      setTimeout(function() { confirmRaise(); }, 150);
    }, 200);

    console.log('[W4P] Raise amount=' + amount + ' (two-step)');
    return true;
  }

  // ── Confirm raise: click the confirm/execute button ──────────
  function confirmRaise() {
    // Try raise-confirm <i> element (BetConstruct pattern)
    var execBtn = document.querySelector('.f-right-column-p > ul > li:nth-child(3) > div > p > i');
    if (execBtn && execBtn.offsetParent !== null) { execBtn.click(); return; }
    // Fallback: the raise row itself
    var alt = document.querySelector('.f-right-column-p > ul > li:nth-child(3)');
    if (alt && alt.offsetParent !== null) { alt.click(); return; }
    // Last resort: re-click raise button (some UIs use same button)
    var raiseBtn = document.querySelector(BTN_SEL.raise);
    if (raiseBtn && raiseBtn.offsetParent !== null) raiseBtn.click();
  }

  // ── Click simple action button ───────────────────────────────
  function clickAction(action, amount) {
    var key = action.toLowerCase().replace(/[\s-]/g, '_');

    // Raise/bet/allin use the two-step flow
    if (key === 'raise' || key === 'bet') {
      return executeRaise(amount);
    }
    if (key === 'allin') {
      return executeRaise('max');
    }

    var sel = BTN_SEL[key];
    if (!sel) { console.log('[W4P] Unknown action:', action); return false; }

    var btn = document.querySelector(sel);
    if (btn && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
      btn.click();
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
      hero.click();
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
          buyBtns[i].click();
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
        maxBtn.click();
        console.log('[W4P] Buy-in MAX clicked');
      }
    } else if (mode === 'min') {
      var minBtn = modal.querySelector('.modal-balance-v li:nth-child(2) .mini-button-view-m:first-child button');
      if (minBtn && minBtn.offsetParent !== null) {
        minBtn.click();
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
        submit.click();
        console.log('[W4P] Buy-in confirmed');
      }
    }, 300);
  }

  // ── Command handler ──────────────────────────────────────────
  function handleCommand(cmd) {
    var action = cmd.type || cmd.command || '';
    console.log('[W4P] CMD:', action, cmd.amount ? 'amt=' + cmd.amount : '');

    if (action === 'buyin' || action === 'rebuy_max' || action === 'rebuy_min' || action === 'buyin_max' || action === 'buyin_min') {
      handleBuyin(cmd);
    } else if (action === 'check_fold') {
      _preAction = 'check_fold';
      console.log('[W4P] Pre-action set: CHECK/FOLD');
    } else if (action === 'check_call') {
      _preAction = 'check_call';
      console.log('[W4P] Pre-action set: CHECK/CALL');
    } else if (action === 'clear') {
      _preAction = null;
      console.log('[W4P] Pre-action cleared');
    } else if (BTN_SEL[action] || action === 'allin') {
      clickAction(action, cmd.amount);
    } else {
      console.log('[W4P] Unknown command:', action);
    }
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

    fetch(API_BASE + '/commands/pending?token=' + encodeURIComponent(_seatToken))
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.ok && data.command) {
          handleCommand(data.command);
          // Acknowledge immediately
          fetch(API_BASE + '/commands/ack', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: _seatToken, command_id: data.command.id })
          }).catch(function(){});
        }
      })
      .catch(function(){});

    window._w4p_cmdTimer = setTimeout(pollCommands, CMD_MS[_mode] || 500);
  }

  // ── Auto-untick "Wait for Big Blind" ─────────────────────────
  function untickWaitBB() {
    var cbs = document.querySelectorAll('input[type="checkbox"]');
    for (var i = 0; i < cbs.length; i++) {
      if (cbs[i].checked) {
        var label = cbs[i].parentElement ? cbs[i].parentElement.textContent : '';
        if (/wait.*big\s*blind|big\s*blind/i.test(label)) {
          cbs[i].click();
          console.log('[W4P] Unticked: Wait for Big Blind');
        }
      }
    }
    var toggles = document.querySelectorAll('.check-box-view-p.active, .toggle-switch.active, [class*="wait-bb"].active');
    for (var j = 0; j < toggles.length; j++) {
      var txt = toggles[j].textContent || '';
      if (/wait.*big\s*blind|big\s*blind/i.test(txt)) {
        toggles[j].click();
      }
    }
  }

  // ── Main snapshot loop ───────────────────────────────────────
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

      if (hero) {
        console.log('[W4P] #' + _n + (heartbeat && !changed ? ' (hb)' : '') +
                    ' ' + snap.street + ' pot=R' + snap.pot_zar +
                    ' ' + hero.name + '@seat' + hero.seat_index +
                    ' [' + hero.hole_cards.join(',') + ']' +
                    ' seats=' + snap.seats.length +
                    ' board=' + (snap.board.flop.join('') || '-'));
      }
    }

    // Fire pre-action if queued and actions available
    if (_preAction && avail.length > 0) {
      runPreAction(avail);
    }

    window._w4p_timer = setTimeout(tick, POLL_MS[_mode] || 1000);
  }

  // ── Start ────────────────────────────────────────────────────
  untickWaitBB();
  window._w4p_bbTimer = setInterval(untickWaitBB, 5000);

  console.log('[W4P] v15.0 SNAPPY | session=' + _sessionId);
  console.log('[W4P] Polling: hero=' + POLL_MS.HERO_TURN + 'ms cmd=' + CMD_MS.HERO_TURN + 'ms');
  console.log('[W4P] API: ' + API_BASE + ' | Remote: potlimitomaha.xyz/remote');
  tick();

  // ── Public API for debugging ─────────────────────────────────
  window._w4p_buildSnapshot = buildSnapshot;
  window._w4pClickAction = clickAction;
  window._w4pActions = getAvailableActions;
  window._w4p_injected = true;
  window._w4p_stop = function() {
    clearTimeout(window._w4p_timer);
    clearTimeout(window._w4p_cmdTimer);
    clearInterval(window._w4p_bbTimer);
    console.log('[W4P] stopped');
  };
})();
