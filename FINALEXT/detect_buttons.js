// ═══════════════════════════════════════════════════════════════
// PokerBet Button Selector Detector
// Run this INSIDE the PokerBet iframe (same context as w4p.js)
// Discovers exact CSS selectors for all action buttons, presets,
// slider, and ALL-IN path. Reports what works and what's broken.
// ═══════════════════════════════════════════════════════════════
(() => {
  const results = { buttons: {}, presets: {}, slider: {}, allElements: [] };

  // ── 1. KNOWN BTN_SEL selectors from w4p.js ──
  const BTN_SEL = {
    fold:         '.control-b-view-p.fold-c',
    check:        '.control-b-view-p.check-c',
    call:         '.control-b-view-p.call-c',
    raise:        '.control-b-view-p.raise-c',
    bet:          '.control-b-view-p.bet-c',
    cashout:      '.control-b-view-p.cash_out-c',
    show:         '.control-b-view-p.show-c',
    run_it_twice: '.control-b-view-p.run_it_twice-c',
    all_in:       '.control-b-view-p.all_in-c',
  };

  console.log('%c=== POKERBET BUTTON DETECTOR ===', 'color:#ff0;font-size:16px;font-weight:bold');

  // Test each known selector
  for (const [name, sel] of Object.entries(BTN_SEL)) {
    const el = document.querySelector(sel);
    const visible = el && (el.offsetParent !== null || el.offsetWidth > 0);
    results.buttons[name] = {
      selector: sel,
      found: !!el,
      visible: !!visible,
      text: el ? el.textContent.trim().substring(0, 50) : null,
      classes: el ? el.className : null,
      tag: el ? el.tagName : null,
      rect: visible ? el.getBoundingClientRect() : null,
    };

    const icon = el ? (visible ? '🟢' : '🟡') : '🔴';
    console.log(
      `${icon} %c${name.padEnd(14)}%c ${sel.padEnd(35)} ${el ? (visible ? 'VISIBLE' : 'HIDDEN') : 'NOT FOUND'}`,
      'color:#0ff;font-weight:bold',
      'color:#888',
      el ? `"${el.textContent.trim().substring(0, 30)}"` : ''
    );
  }

  // ── 2. SCAN for ALL buttons/clickable elements with action-like classes ──
  console.log('%c\n=== SCANNING ALL ACTION ELEMENTS ===', 'color:#ff0;font-size:14px');

  const actionPatterns = [
    'fold', 'check', 'call', 'raise', 'bet', 'all.in', 'allin', 'all_in',
    'cash.out', 'cashout', 'show', 'run.it', 'resume', 'back.to',
    'control', 'action', 'submit', 'confirm'
  ];

  const allClickable = document.querySelectorAll(
    'button, [role="button"], [class*="control"], [class*="-c"], ' +
    '[class*="fold"], [class*="check"], [class*="call"], [class*="raise"], ' +
    '[class*="bet"], [class*="all_in"], [class*="allin"], [class*="all-in"], ' +
    '[class*="cash"], [class*="show"], [class*="action"], [class*="submit"]'
  );

  const seen = new Set();
  allClickable.forEach(el => {
    const cls = el.className || '';
    const txt = (el.textContent || '').trim().substring(0, 60);
    const tag = el.tagName;
    const visible = el.offsetParent !== null || el.offsetWidth > 0;
    const key = cls + '|' + txt;
    if (seen.has(key)) return;
    seen.add(key);

    // Build a reliable CSS selector for this element
    let selector = '';
    if (el.id) {
      selector = '#' + CSS.escape(el.id);
    } else {
      const classes = (cls || '').split(/\s+/).filter(c => c && c.length < 40);
      if (classes.length) {
        selector = tag.toLowerCase() + '.' + classes.map(CSS.escape).join('.');
      } else {
        selector = tag.toLowerCase();
      }
    }

    // Detect which action this element represents
    let matchedAction = null;
    const haystack = (cls + ' ' + txt).toLowerCase();
    for (const pat of actionPatterns) {
      if (new RegExp(pat, 'i').test(haystack)) {
        matchedAction = pat.replace(/[.]/g, '_');
        break;
      }
    }

    if (matchedAction || visible) {
      const icon = visible ? '🟢' : '⚫';
      results.allElements.push({
        action: matchedAction,
        selector,
        tag,
        classes: cls.substring(0, 80),
        text: txt.substring(0, 40),
        visible,
        rect: visible ? el.getBoundingClientRect() : null,
      });

      if (matchedAction) {
        console.log(
          `${icon} %c${(matchedAction || '').padEnd(12)}%c ${tag.padEnd(6)} cls="${cls.substring(0, 50)}" %c"${txt.substring(0, 30)}"`,
          'color:#0f0;font-weight:bold',
          'color:#888',
          'color:#ff0'
        );
      }
    }
  });

  // ── 3. SLIDER / PRESETS (critical for ALL-IN) ──
  console.log('%c\n=== SLIDER & PRESETS ===', 'color:#ff0;font-size:14px');

  // Range slider
  const sliders = document.querySelectorAll('input[type="range"]');
  sliders.forEach((s, i) => {
    const parent = s.closest('sg-poker-betting-slider') || s.parentElement;
    const visible = s.offsetParent !== null;
    results.slider.range = {
      found: true, visible, min: s.min, max: s.max, value: s.value,
      parentTag: parent?.tagName,
      parentClass: parent?.className?.substring(0, 60),
    };
    console.log(
      `${visible ? '🟢' : '🟡'} SLIDER: min=${s.min} max=${s.max} val=${s.value} ${visible ? 'VISIBLE' : 'HIDDEN'}`,
      'color:#0ff'
    );
  });
  if (!sliders.length) console.log('🔴 No range slider found');

  // Preset buttons (li items inside slider area)
  const presetSelectors = [
    'sg-poker-betting-slider .limits-buttons-v-p li',
    'sg-poker-betting-slider li',
    '.limits-buttons-v-p li',
    '[class*="limit"] li',
    '[class*="preset"] li',
    '[class*="amount"] li',
  ];

  let presetFound = false;
  for (const psel of presetSelectors) {
    const items = document.querySelectorAll(psel);
    if (items.length > 0) {
      console.log(`%c  Preset selector: ${psel} → ${items.length} items`, 'color:#0ff');
      items.forEach((item, idx) => {
        const txt = item.textContent.trim();
        const visible = item.offsetParent !== null;
        const isMax = /max|all.*in/i.test(txt);
        const isMin = /min/i.test(txt);
        const isPot = /pot/i.test(txt) && !/half/i.test(txt);
        const label = isMax ? 'MAX/ALL-IN' : isMin ? 'MIN' : isPot ? 'POT' : txt;

        const icon = isMax ? '🎯' : visible ? '🟢' : '⚫';
        console.log(
          `  ${icon} preset[${idx}]: %c"${txt}"%c ${visible ? 'VISIBLE' : 'HIDDEN'} ${isMax ? '← THIS IS ALL-IN' : ''}`,
          'color:#ff0;font-weight:bold',
          'color:#888'
        );

        if (isMax || isMin || isPot) {
          results.presets[label] = {
            selector: psel + `:nth-child(${idx + 1})`,
            text: txt,
            visible,
            index: idx,
          };
        }
      });
      presetFound = true;
      break; // Use first matching selector
    }
  }
  if (!presetFound) {
    console.log('%c  🔴 NO PRESET BUTTONS FOUND — this is why ALL-IN fails!', 'color:#f00;font-weight:bold;font-size:14px');
    // Deep scan for anything that might be a preset
    console.log('%c  Scanning for hidden preset elements...', 'color:#888');
    const allLi = document.querySelectorAll('li');
    allLi.forEach(li => {
      const txt = (li.textContent || '').trim().toLowerCase();
      if (/max|min|pot|all.in|1\/2|half|x\d/i.test(txt) && txt.length < 20) {
        const parent = li.parentElement;
        console.log(
          `  🔍 Found li: "${txt}" parent=${parent?.tagName}.${(parent?.className || '').substring(0, 40)} visible=${li.offsetParent !== null}`,
        );
      }
    });
  }

  // ── 4. CONFIRM BUTTON (the raise/bet confirm after slider set) ──
  console.log('%c\n=== CONFIRM BUTTON ===', 'color:#ff0;font-size:14px');
  const confirmSels = [
    BTN_SEL.raise,
    BTN_SEL.bet,
    '.control-b-view-p.raise-c',
    '.control-b-view-p.bet-c',
    'button[class*="confirm"]',
    '[class*="submit"]',
  ];
  for (const csel of confirmSels) {
    const el = document.querySelector(csel);
    if (el) {
      const visible = el.offsetParent !== null;
      console.log(
        `${visible ? '🟢' : '🟡'} ${csel} → "${el.textContent.trim().substring(0, 30)}" ${visible ? 'VISIBLE' : 'HIDDEN'}`,
      );
    }
  }

  // ── 5. ALL-IN PATH DIAGNOSIS ──
  console.log('%c\n=== ALL-IN PATH DIAGNOSIS ===', 'color:#f00;font-size:16px;font-weight:bold');

  const raiseBtn = document.querySelector(BTN_SEL.raise) || document.querySelector(BTN_SEL.bet);
  const slider = document.querySelector('sg-poker-betting-slider input[type="range"]') || document.querySelector('input[type="range"]');
  const maxPreset = results.presets['MAX/ALL-IN'];

  const steps = [
    { step: '1. RAISE/BET button exists', ok: !!raiseBtn, detail: raiseBtn ? raiseBtn.className : 'NOT FOUND' },
    { step: '2. RAISE/BET button visible', ok: raiseBtn && (raiseBtn.offsetParent !== null || raiseBtn.offsetWidth > 0), detail: '' },
    { step: '3. Slider exists', ok: !!slider, detail: slider ? `min=${slider.min} max=${slider.max}` : 'NOT FOUND' },
    { step: '4. Slider visible', ok: slider && slider.offsetParent !== null, detail: '' },
    { step: '5. MAX preset found', ok: !!maxPreset, detail: maxPreset ? maxPreset.text : 'NOT FOUND — ALL-IN WILL FAIL' },
    { step: '6. MAX preset visible', ok: maxPreset?.visible, detail: '' },
  ];

  steps.forEach(s => {
    console.log(
      `${s.ok ? '✅' : '❌'} ${s.step} ${s.detail}`,
    );
  });

  if (!maxPreset) {
    console.log('%c\n⚠️  FIX: The ALL-IN handler calls selectMax() which looks for a preset button', 'color:#f80;font-size:13px');
    console.log('%c   containing "max" or "all in" text. If PokerBet doesn\'t show presets', 'color:#f80;font-size:13px');
    console.log('%c   until RAISE is clicked, we need to click RAISE first, wait, then find MAX.', 'color:#f80;font-size:13px');
    console.log('%c   Or: set slider.value = slider.max directly + confirm.', 'color:#0f0;font-size:13px');
  }

  // ── 6. EXPORT ──
  window._pokerBetButtons = results;
  console.log('%c\nFull results stored in window._pokerBetButtons', 'color:#888');
  console.log('%cCopy with: copy(JSON.stringify(window._pokerBetButtons, null, 2))', 'color:#888');

  return results;
})();
