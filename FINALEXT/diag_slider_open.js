// PokerBet Slider-Open Diagnostic — READ-ONLY, zero clicks
// Run this AFTER you manually click the RAISE/BET button in PokerBet
// so the slider panel is open and visible
(function() {
  console.log('=== POKERBET SLIDER-OPEN DIAGNOSTIC ===');
  console.log('Time:', new Date().toISOString());

  // ── 1. Slider range input ──
  console.log('\n── SLIDER INPUT ──');
  var slider = document.querySelector('sg-poker-betting-slider input[type="range"]')
    || document.querySelector('input[type="range"]');
  if (slider) {
    console.log('  FOUND: value=' + slider.value + ' min=' + slider.min +
      ' max=' + slider.max + ' step=' + slider.step);
    console.log('  getAttribute("value")=' + slider.getAttribute('value'));
    console.log('  getAttribute("min")=' + slider.getAttribute('min'));
    console.log('  getAttribute("max")=' + slider.getAttribute('max'));
    var sR = slider.getBoundingClientRect();
    console.log('  Visible: ' + (sR.width > 0) + ' (' + Math.round(sR.width) + 'x' + Math.round(sR.height) + ')');
    console.log('  Parent chain: ' + slider.parentElement.tagName + '.' +
      slider.parentElement.className.substring(0, 40) + ' → ' +
      slider.parentElement.parentElement.tagName + '.' +
      slider.parentElement.parentElement.className.substring(0, 40));
  } else {
    console.log('  NOT FOUND — is the slider panel open?');
  }

  // ── 2. Amount text/number input ──
  console.log('\n── AMOUNT INPUT ──');
  var amtInputs = document.querySelectorAll('input[type="number"], input[type="text"]');
  var relevantInputs = [];
  for (var i = 0; i < amtInputs.length; i++) {
    var inp = amtInputs[i];
    var iR = inp.getBoundingClientRect();
    if (iR.width > 0 && iR.height > 0 && !inp.closest('sg-buy-in-modal')) {
      relevantInputs.push(inp);
      console.log('  [' + relevantInputs.length + '] type=' + inp.type + ' value="' + inp.value +
        '" | name=' + (inp.name || 'none') + ' id=' + (inp.id || 'none') +
        ' | parent=' + inp.parentElement.tagName + '.' + inp.parentElement.className.substring(0, 40));

      // Check Angular bindings on input
      var attrs = inp.attributes;
      for (var a = 0; a < attrs.length; a++) {
        if (attrs[a].name.indexOf('ng') !== -1 || attrs[a].name.indexOf('formcontrol') !== -1 ||
            attrs[a].name.indexOf('model') !== -1 || attrs[a].name.indexOf('bind') !== -1) {
          console.log('    Angular attr: ' + attrs[a].name + '="' + attrs[a].value + '"');
        }
      }
    }
  }
  if (relevantInputs.length === 0) {
    console.log('  No visible amount inputs found');
  }

  // ── 3. All preset buttons ──
  console.log('\n── PRESET BUTTONS (ALL <li> inside slider area) ──');
  var presets = document.querySelectorAll(
    'sg-poker-betting-slider li, .limits-buttons-v-p li');
  console.log('  Count: ' + presets.length);
  for (var pi = 0; pi < presets.length; pi++) {
    var p = presets[pi];
    var pR = p.getBoundingClientRect();
    var pTxt = (p.textContent || '').trim();
    console.log('  [' + pi + '] "' + pTxt + '" visible=' + (pR.width > 0) +
      ' class="' + p.className.substring(0, 60) + '"');
    // What's inside?
    var kids = p.children;
    for (var k = 0; k < kids.length; k++) {
      console.log('    <' + kids[k].tagName.toLowerCase() + '> "' +
        (kids[k].textContent || '').trim() + '" class="' + kids[k].className.substring(0, 40) + '"');
    }
  }

  // ── 4. The RAISE/BET button while slider is open ──
  console.log('\n── RAISE/BET BUTTON (WHILE SLIDER OPEN) ──');
  var raiseBtn = document.querySelector('.control-b-view-p.raise-c');
  var betBtn = document.querySelector('.control-b-view-p.bet-c');
  var btn = raiseBtn || betBtn;
  if (btn) {
    var bR = btn.getBoundingClientRect();
    console.log('  ' + (raiseBtn ? 'RAISE' : 'BET') + ': visible=' + (bR.width > 0) +
      ' text="' + (btn.textContent || '').trim().substring(0, 40) + '"');
    console.log('  Full HTML: ' + btn.outerHTML.substring(0, 300));
    // Does the button text show an amount?
    var btnText = (btn.textContent || '').trim();
    var amountInBtn = btnText.match(/[\d,.]+/);
    if (amountInBtn) {
      console.log('  ** AMOUNT IN BUTTON TEXT: ' + amountInBtn[0] + ' **');
      console.log('  (This means the button shows the selected amount)');
    }
  } else {
    console.log('  RAISE/BET button NOT FOUND while slider open');
    console.log('  (Does it disappear when slider opens? Look for alternative confirm button)');
  }

  // ── 5. All visible buttons/clickables in control area ──
  console.log('\n── ALL CLICKABLE ELEMENTS IN CONTROL AREA ──');
  var controlArea = document.querySelector('.f-right-column-p');
  if (controlArea) {
    var clickables = controlArea.querySelectorAll('button, [role="button"], a, li, div[class*="btn"], div[class*="button"], p > i');
    console.log('  Clickable elements: ' + clickables.length);
    for (var ci = 0; ci < Math.min(clickables.length, 20); ci++) {
      var c = clickables[ci];
      var cR = c.getBoundingClientRect();
      if (cR.width > 0) {
        console.log('  [' + ci + '] <' + c.tagName.toLowerCase() + '> "' +
          (c.textContent || '').trim().substring(0, 30) + '" class="' +
          c.className.substring(0, 50) + '" visible');
      }
    }
  }

  // ── 6. Key question: what happens when RAISE is clicked while slider is open? ──
  console.log('\n── HYPOTHESIS TEST ──');
  console.log('  Slider visible: ' + !!(slider && slider.getBoundingClientRect().width > 0));
  console.log('  Slider value: ' + (slider ? slider.value : 'N/A'));
  console.log('  Slider max: ' + (slider ? slider.max : 'N/A'));
  console.log('  Amount input value: ' + (relevantInputs.length > 0 ? relevantInputs[0].value : 'N/A'));
  console.log('  RAISE button visible: ' + !!(btn && btn.getBoundingClientRect().width > 0));
  console.log('');
  console.log('  TO TEST: manually change slider to a specific value (e.g. 5),');
  console.log('  then run this script again to confirm the input/slider reflects 5.');
  console.log('  Then click RAISE in PokerBet UI and observe what amount is bet.');
  console.log('  If PokerBet bets 5, the button reads the current slider/input value.');
  console.log('  If PokerBet bets 1BB, something else is wrong.');

  // ── 7. Entire slider component HTML ──
  console.log('\n── SLIDER COMPONENT FULL HTML (first 3000 chars) ──');
  var sgSlider = document.querySelector('sg-poker-betting-slider');
  if (sgSlider) {
    console.log(sgSlider.outerHTML.replace(/\s+/g, ' ').substring(0, 3000));
  } else {
    console.log('  sg-poker-betting-slider not found');
  }

  console.log('\n=== END SLIDER DIAGNOSTIC ===');
})();
