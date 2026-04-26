// Button Auto-Detector for W4P Remote Control
// Scans the poker DOM, returns exact button map with selectors, text, amounts, state
// Inject alongside w4p.js or call window._w4p_detectButtons()

(function() {
  'use strict';

  // ── Action patterns ──────────────────────────────────────────
  var ACTION_RX = {
    fold:         /\bfold\b/i,
    check:        /\bcheck\b/i,
    call:         /\bcall\b/i,
    raise:        /\braise\b/i,
    bet:          /\bbet\b/i,
    allin:        /\ball[\s-]?in\b/i,
    cashout:      /\bcash[\s_-]?out\b/i,
    show:         /\bshow\b/i,
    muck:         /\bmuck\b/i,
    run_it_twice: /\brun[\s_]it[\s_]twice\b/i,
    resume_hand:  /\bresume\b/i,
    back_to_game: /\bback[\s_]to[\s_]game\b/i,
    sit_out:      /\bsit[\s_-]?out\b/i,
    im_back:      /\bi.?m[\s_]back\b/i,
    leave:        /\bleave\b/i,
  };

  var PRESET_RX = {
    min:     /\bmin\b/i,
    half:    /\bhalf\b|1\/2/i,
    pot:     /\bpot\b/i,
    max:     /\bmax\b|all[\s-]?in/i,
  };

  // ── Helpers ──────────────────────────────────────────────────
  function isVisible(el) {
    if (!el) return false;
    return el.offsetParent !== null || el.offsetWidth > 0 || el.offsetHeight > 0;
  }

  function getText(el) {
    return ((el.innerText || el.textContent || '') + ' ' +
            (el.getAttribute('aria-label') || '') + ' ' +
            (el.getAttribute('title') || '')).replace(/\s+/g, ' ').trim();
  }

  function getAmount(text) {
    var m = text.match(/([\d,]+\.?\d*)/);
    if (!m) return null;
    var n = parseFloat(m[1].replace(/,/g, ''));
    return isNaN(n) ? null : n;
  }

  function buildSelector(el) {
    if (!el) return null;
    if (el.id) return '#' + CSS.escape(el.id);

    var parts = [];
    var node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      var part = node.tagName.toLowerCase();
      if (node.className && typeof node.className === 'string') {
        var cls = node.className.trim().split(/\s+/).filter(function(c) {
          return c && !/^ng-|^cdk-|^active$|^hover$/.test(c);
        }).slice(0, 3);
        if (cls.length) part += '.' + cls.map(CSS.escape).join('.');
      }
      var siblings = node.parentElement
        ? Array.from(node.parentElement.children).filter(function(x) { return x.tagName === node.tagName; })
        : [];
      if (siblings.length > 1) {
        part += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
      }
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(' > ');
  }

  function getRect(el) {
    var r = el.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  }

  // ── Main detector ────────────────────────────────────────────
  function detectButtons() {
    var result = {
      actions: [],        // fold/check/call/raise/bet etc
      presets: [],        // min/half/pot/max slider presets
      slider: null,       // raise slider state
      other: [],          // unclassified clickable elements
      detected_at: new Date().toISOString(),
    };

    var seen = new Set();

    // ── 1. Scan known BetConstruct action buttons ──────────────
    var knownSel = {
      fold:         '.control-b-view-p.fold-c',
      check:        '.control-b-view-p.check-c',
      call:         '.control-b-view-p.call-c',
      raise:        '.control-b-view-p.raise-c',
      bet:          '.control-b-view-p.bet-c',
      cashout:      '.control-b-view-p.cash_out-c',
      show:         '.control-b-view-p.show-c',
      run_it_twice: '.control-b-view-p.run_it_twice-c',
      resume_hand:  '.control-b-view-p.resume_hand-c',
      back_to_game: '.control-b-view-p.back_to_game-c',
    };

    for (var action in knownSel) {
      var el = document.querySelector(knownSel[action]);
      if (el && isVisible(el)) {
        var text = getText(el);
        var btn = {
          action: action,
          text: text,
          amount: getAmount(text),
          selector: knownSel[action],
          selector_auto: buildSelector(el),
          rect: getRect(el),
          visible: true,
          source: 'known',
        };
        result.actions.push(btn);
        seen.add(el);
      }
    }

    // ── 2. Scan all visible clickable elements for actions ─────
    var candidates = document.querySelectorAll(
      'button, [role="button"], [class*="control-b"], [class*="fold"], ' +
      '[class*="check-c"], [class*="call-c"], [class*="raise-c"], [class*="bet-c"], ' +
      '[class*="cash_out"], [class*="show-c"], .btn, [class*="action"]'
    );

    for (var i = 0; i < candidates.length; i++) {
      var el2 = candidates[i];
      if (seen.has(el2) || !isVisible(el2)) continue;

      var text2 = getText(el2);
      if (!text2) continue;

      // Walk up to find action context
      var matched = false;
      var haystack = text2;
      var node = el2;
      for (var depth = 0; node && depth < 3; depth++, node = node.parentElement) {
        haystack += ' ' + getText(node);
      }

      for (var act in ACTION_RX) {
        if (ACTION_RX[act].test(haystack)) {
          // Don't duplicate if we already have this action from known selectors
          var already = result.actions.some(function(a) { return a.action === act; });
          if (!already) {
            result.actions.push({
              action: act,
              text: text2,
              amount: getAmount(text2),
              selector: buildSelector(el2),
              selector_auto: buildSelector(el2),
              rect: getRect(el2),
              visible: true,
              source: 'scan',
            });
          }
          seen.add(el2);
          matched = true;
          break;
        }
      }
    }

    // ── 3. Detect slider presets (min/half/pot/max) ────────────
    var presetEls = document.querySelectorAll(
      'sg-poker-betting-slider li, .limits-buttons-v-p li, ' +
      '[class*="limit"] li, [class*="preset"] li, [class*="amount"] li'
    );

    for (var p = 0; p < presetEls.length; p++) {
      var pel = presetEls[p];
      if (!isVisible(pel)) continue;
      var ptext = getText(pel);
      if (!ptext) continue;

      var presetAction = null;
      for (var pk in PRESET_RX) {
        if (PRESET_RX[pk].test(ptext)) {
          presetAction = pk;
          break;
        }
      }

      result.presets.push({
        action: presetAction || 'custom',
        text: ptext,
        amount: getAmount(ptext),
        selector: buildSelector(pel),
        rect: getRect(pel),
        visible: true,
        index: p,
      });
    }

    // ── 4. Detect raise slider state ──────────────────────────
    var rangeInput = document.querySelector('sg-poker-betting-slider input[type="range"]')
                  || document.querySelector('input[type="range"]');
    var amtInput = document.querySelector('sg-poker-betting-slider input[type="number"]')
                || document.querySelector('sg-poker-betting-slider input[type="text"]');
    if (!amtInput) {
      var inputs = document.querySelectorAll('input[type="number"], input[type="text"]');
      for (var ii = 0; ii < inputs.length; ii++) {
        if (isVisible(inputs[ii]) && !inputs[ii].closest('sg-buy-in-modal')) {
          amtInput = inputs[ii];
          break;
        }
      }
    }

    if (rangeInput || amtInput) {
      result.slider = {
        visible: isVisible(rangeInput) || isVisible(amtInput),
        current: amtInput ? parseFloat(amtInput.value) || 0 : (rangeInput ? parseFloat(rangeInput.value) || 0 : 0),
        min: rangeInput ? parseFloat(rangeInput.min) || 0 : null,
        max: rangeInput ? parseFloat(rangeInput.max) || 0 : null,
        step: rangeInput ? parseFloat(rangeInput.step) || 1 : null,
        range_selector: rangeInput ? buildSelector(rangeInput) : null,
        input_selector: amtInput ? buildSelector(amtInput) : null,
      };
    }

    // ── 5. Summary ────────────────────────────────────────────
    result.action_names = result.actions.map(function(a) { return a.action; });
    result.preset_names = result.presets.map(function(p) { return p.action; });
    result.count = result.actions.length;

    return result;
  }

  // ── Expose globally ──────────────────────────────────────────
  window._w4p_detectButtons = detectButtons;

  // Log on load
  var d = detectButtons();
  console.log(
    '%c[W4P-DETECT] ' + d.count + ' actions: ' + d.action_names.join(', '),
    'color:#00ff99;font-weight:bold',
    d
  );
  if (d.presets.length) {
    console.log('[W4P-DETECT] Presets:', d.preset_names.join(', '));
  }
  if (d.slider) {
    console.log('[W4P-DETECT] Slider:', d.slider.visible ? 'visible' : 'hidden',
                'min=' + d.slider.min, 'max=' + d.slider.max, 'cur=' + d.slider.current);
  }
})();
