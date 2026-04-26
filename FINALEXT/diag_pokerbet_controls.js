// PokerBet Control Model Diagnostic — READ-ONLY, zero clicks
// Paste into the skillgames iframe console during hero's turn
// Reports: all action buttons, slider state, presets, amount input, DOM structure
(function() {
  console.log('=== POKERBET CONTROL DIAGNOSTIC ===');
  console.log('Time:', new Date().toISOString());

  // ── 1. Action buttons (BTN_SEL equivalents) ──
  var btnSelectors = {
    fold:         '.control-b-view-p.fold-c',
    check:        '.control-b-view-p.check-c',
    call:         '.control-b-view-p.call-c',
    raise:        '.control-b-view-p.raise-c',
    bet:          '.control-b-view-p.bet-c',
    cashout:      '.control-b-view-p.cash_out-c',
    allin:        '.control-b-view-p.all_in-c'
  };

  console.log('\n── ACTION BUTTONS ──');
  for (var name in btnSelectors) {
    var el = document.querySelector(btnSelectors[name]);
    if (el) {
      var r = el.getBoundingClientRect();
      var txt = (el.textContent || '').trim().substring(0, 40);
      var vis = r.width > 0 && r.height > 0;
      console.log('  ' + name.toUpperCase() + ': FOUND | visible=' + vis +
        ' | text="' + txt + '" | tag=' + el.tagName +
        ' | classes=' + el.className.substring(0, 80) +
        ' | rect=' + Math.round(r.width) + 'x' + Math.round(r.height));

      // Check for child <p>, <i>, <span> that might be the real click target
      var children = el.querySelectorAll('p, i, span, a, div, button');
      if (children.length > 0) {
        console.log('    children (' + children.length + '):');
        for (var ci = 0; ci < Math.min(children.length, 5); ci++) {
          var c = children[ci];
          var cr = c.getBoundingClientRect();
          console.log('      [' + ci + '] <' + c.tagName.toLowerCase() + '> text="' +
            (c.textContent || '').trim().substring(0, 30) + '" class="' +
            c.className.substring(0, 50) + '" vis=' + (cr.width > 0));
        }
      }
    } else {
      console.log('  ' + name.toUpperCase() + ': NOT FOUND');
    }
  }

  // ── 2. Slider component ──
  console.log('\n── SLIDER COMPONENT ──');
  var sgSlider = document.querySelector('sg-poker-betting-slider');
  if (sgSlider) {
    var sgR = sgSlider.getBoundingClientRect();
    console.log('  sg-poker-betting-slider: FOUND | visible=' + (sgR.width > 0) +
      ' | rect=' + Math.round(sgR.width) + 'x' + Math.round(sgR.height) +
      ' | display=' + getComputedStyle(sgSlider).display +
      ' | classes=' + sgSlider.className.substring(0, 80));
  } else {
    console.log('  sg-poker-betting-slider: NOT FOUND (slider panel not open?)');
  }

  // Range input (the slider itself)
  var rangeInputs = document.querySelectorAll('input[type="range"]');
  console.log('  input[type="range"]: ' + rangeInputs.length + ' found');
  for (var ri = 0; ri < rangeInputs.length; ri++) {
    var rng = rangeInputs[ri];
    var rngR = rng.getBoundingClientRect();
    console.log('    [' + ri + '] value=' + rng.value + ' min=' + rng.min + ' max=' + rng.max +
      ' step=' + rng.step + ' visible=' + (rngR.width > 0) +
      ' | parent=' + (rng.parentElement ? rng.parentElement.tagName + '.' + rng.parentElement.className.substring(0, 40) : 'none'));
  }

  // ── 3. Amount/number input ──
  console.log('\n── AMOUNT INPUT ──');
  var amtSel1 = document.querySelector('sg-poker-betting-slider input[type="number"]');
  var amtSel2 = document.querySelector('sg-poker-betting-slider input[type="text"]');
  var amtInputs = document.querySelectorAll('input[type="number"], input[type="text"]');
  console.log('  sg-poker-betting-slider input[number]: ' + (amtSel1 ? 'FOUND val=' + amtSel1.value : 'NOT FOUND'));
  console.log('  sg-poker-betting-slider input[text]:   ' + (amtSel2 ? 'FOUND val=' + amtSel2.value : 'NOT FOUND'));
  console.log('  All number/text inputs: ' + amtInputs.length);
  for (var ai = 0; ai < amtInputs.length; ai++) {
    var inp = amtInputs[ai];
    var inpR = inp.getBoundingClientRect();
    var inBuyIn = inp.closest('sg-buy-in-modal');
    console.log('    [' + ai + '] type=' + inp.type + ' value="' + inp.value + '" visible=' + (inpR.width > 0) +
      ' inBuyIn=' + !!inBuyIn +
      ' | parent=' + (inp.parentElement ? inp.parentElement.tagName + '.' + inp.parentElement.className.substring(0, 40) : 'none'));
  }

  // ── 4. Preset buttons ──
  console.log('\n── PRESET BUTTONS ──');
  var presetSelectors = [
    'sg-poker-betting-slider .limits-buttons-v-p li',
    'sg-poker-betting-slider li',
    '.limits-buttons-v-p li',
    '[class*="limit"] li',
    '[class*="preset"] li',
    '[class*="amount"] li'
  ];
  // Deduplicated set
  var seen = new Set();
  var allPresets = [];
  for (var ps = 0; ps < presetSelectors.length; ps++) {
    var found = document.querySelectorAll(presetSelectors[ps]);
    for (var fi = 0; fi < found.length; fi++) {
      if (!seen.has(found[fi])) {
        seen.add(found[fi]);
        allPresets.push({el: found[fi], selector: presetSelectors[ps]});
      }
    }
  }
  console.log('  Total unique presets: ' + allPresets.length);
  for (var pi = 0; pi < allPresets.length; pi++) {
    var p = allPresets[pi];
    var pr = p.el.getBoundingClientRect();
    var pTxt = (p.el.textContent || '').trim();
    console.log('    [' + pi + '] text="' + pTxt + '" visible=' + (pr.width > 0) +
      ' | class="' + p.el.className.substring(0, 50) + '"' +
      ' | tag=' + p.el.tagName +
      ' | selector="' + p.selector + '"');
    // Children that might be the real click target
    var pKids = p.el.querySelectorAll('span, a, button, div');
    for (var pk = 0; pk < Math.min(pKids.length, 3); pk++) {
      console.log('      child: <' + pKids[pk].tagName.toLowerCase() + '> text="' +
        (pKids[pk].textContent || '').trim() + '" class="' + pKids[pk].className.substring(0, 40) + '"');
    }
  }

  // ── 5. Control panel structure ──
  console.log('\n── CONTROL PANEL STRUCTURE ──');
  // The f-right-column-p is the main control area
  var ctrlPanel = document.querySelector('.f-right-column-p');
  if (ctrlPanel) {
    var cpR = ctrlPanel.getBoundingClientRect();
    console.log('  .f-right-column-p: FOUND | visible=' + (cpR.width > 0));
    var topLis = ctrlPanel.querySelectorAll(':scope > ul > li');
    console.log('  Top-level <li> children: ' + topLis.length);
    for (var tl = 0; tl < topLis.length; tl++) {
      var tlR = topLis[tl].getBoundingClientRect();
      var tlTxt = (topLis[tl].textContent || '').trim().substring(0, 60);
      console.log('    [' + tl + '] text="' + tlTxt + '" visible=' + (tlR.width > 0) +
        ' class="' + topLis[tl].className.substring(0, 60) + '"');
    }
  } else {
    console.log('  .f-right-column-p: NOT FOUND');
  }

  // ── 6. Confirm/execute button search ──
  console.log('\n── LOOKING FOR CONFIRM/EXECUTE BUTTON ──');
  // Look for anything that might be a separate "confirm raise" or "submit" button
  var confirmCandidates = document.querySelectorAll(
    '[class*="confirm"], [class*="submit"], [class*="execute"], [class*="accept"], ' +
    '[class*="raise-confirm"], [class*="bet-confirm"], [class*="ok-btn"]');
  console.log('  Confirm/submit candidates: ' + confirmCandidates.length);
  for (var cc = 0; cc < confirmCandidates.length; cc++) {
    var cEl = confirmCandidates[cc];
    var cR = cEl.getBoundingClientRect();
    console.log('    [' + cc + '] tag=' + cEl.tagName + ' text="' + (cEl.textContent || '').trim().substring(0, 40) +
      '" class="' + cEl.className.substring(0, 60) + '" visible=' + (cR.width > 0));
  }

  // ── 7. Two-state button check ──
  console.log('\n── RAISE/BET BUTTON STATE ANALYSIS ──');
  // Does the raise button change after slider opens?
  var raiseEl = document.querySelector('.control-b-view-p.raise-c');
  var betEl = document.querySelector('.control-b-view-p.bet-c');
  var activeBtn = raiseEl || betEl;
  if (activeBtn) {
    console.log('  Active button: ' + (raiseEl ? 'RAISE' : 'BET'));
    console.log('  Tag: ' + activeBtn.tagName);
    console.log('  Full class list: "' + activeBtn.className + '"');
    console.log('  innerHTML preview: ' + activeBtn.innerHTML.substring(0, 200));
    // Check if it has any state attributes
    var attrs = activeBtn.attributes;
    console.log('  Attributes (' + attrs.length + '):');
    for (var at = 0; at < attrs.length; at++) {
      if (attrs[at].name !== 'class') {
        console.log('    ' + attrs[at].name + '="' + attrs[at].value.substring(0, 60) + '"');
      }
    }
    // Check Angular state
    var ngAttrs = [];
    for (var na = 0; na < attrs.length; na++) {
      if (attrs[na].name.indexOf('ng') !== -1 || attrs[na].name.indexOf('_ng') !== -1) {
        ngAttrs.push(attrs[na].name);
      }
    }
    if (ngAttrs.length > 0) console.log('  Angular attrs: ' + ngAttrs.join(', '));
  }

  // ── 8. Full control area HTML dump (compact) ──
  console.log('\n── FULL CONTROL AREA HTML (first 2000 chars) ──');
  var controlArea = document.querySelector('.f-right-column-p') ||
    document.querySelector('sg-poker-betting-slider') ||
    document.querySelector('[class*="control"]');
  if (controlArea) {
    // Remove excessive whitespace
    var html = controlArea.outerHTML.replace(/\s+/g, ' ').substring(0, 2000);
    console.log(html);
  }

  // ── 9. Check if slider is inside or outside the raise button ──
  console.log('\n── SLIDER POSITION RELATIVE TO RAISE BUTTON ──');
  if (sgSlider && activeBtn) {
    console.log('  Slider is child of raise button: ' + activeBtn.contains(sgSlider));
    console.log('  Raise button is child of slider: ' + sgSlider.contains(activeBtn));
    console.log('  Common parent: ' + (sgSlider.parentElement === activeBtn.parentElement ?
      'SAME (' + sgSlider.parentElement.tagName + '.' + sgSlider.parentElement.className.substring(0, 40) + ')' :
      'DIFFERENT'));
  }

  console.log('\n=== END DIAGNOSTIC ===');
  console.log('NEXT STEP: If slider is not visible, click RAISE manually in PokerBet,');
  console.log('then run this diagnostic again to see the slider/presets/amount input.');
})();
