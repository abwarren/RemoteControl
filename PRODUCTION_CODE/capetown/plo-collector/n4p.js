(function(){
  clearInterval(window._n4p);
  window._n4p=null;
  
  const API='https://nuts4poker.com/collector/save';
  let last='',count=0;
  
  // Parse card from class attribute
  function tok(cls){
    const h=(cls||'').split(/\s+/).filter(t=>/^icon-layer2_([hdcs])(a|k|q|j|10|[2-9])_p-c-d$/i.test(t));
    if(!h.length)return null;
    const m=h[h.length-1].match(/^icon-layer2_([hdcs])(a|k|q|j|10|[2-9])_p-c-d$/i);
    return ({a:'A',k:'K',q:'Q',j:'J','10':'T'}[m[2].toLowerCase()]||m[2]).toUpperCase()+m[1].toLowerCase();
  }
  
  // Get hero hand from a specific table container
  function getHeroFromTable(tableContainer){
    const seats=tableContainer.querySelectorAll('sg-poker-table-seat');
    for(const seat of seats){
      // Check if this is hero seat (has visible cards)
      const cardElements=seat.querySelectorAll('.single-cart-view-p');
      if(cardElements.length===0)continue;
      
      const seen=new Set();
      const hand=[];
      
      for(const el of cardElements){
        const c=tok(el.getAttribute('class')||'');
        if(c&&!seen.has(c)){
          seen.add(c);
          hand.push(c);
        }
      }
      
      // Hero hand should be 4 or 6 cards
      if(hand.length===4||hand.length===6){
        return hand.join('');
      }
    }
    return null;
  }
  
  // Get board from a specific table container
  function getBoardFromTable(tableContainer){
    const boardEl=tableContainer.querySelector('sg-poker-board');
    if(!boardEl)return null;
    
    const seen=new Set();
    const board=[];
    
    for(const el of boardEl.querySelectorAll('.single-cart-view-p')){
      if(el.closest('sg-poker-table-seat'))continue; // Skip player cards
      const c=tok(el.getAttribute('class')||'');
      if(c&&!seen.has(c)){
        seen.add(c);
        board.push(c);
      }
    }
    
    return board.length>=3?board.join(''):null; // At least flop
  }
  
  // Collect ALL hero hands from ALL open tables
  function getAllHeroHands(){
    const lines=[];
    
    // Find all table containers
    const tables=document.querySelectorAll('sg-poker-table');
    
    if(tables.length===0){
      // Fallback: if no table wrappers, try global seat search
      const hero=getHeroFromTable(document);
      if(hero)lines.push(hero);
      
      const board=getBoardFromTable(document);
      if(board)lines.push(board);
    }else{
      // Multi-table: collect hero from each table
      for(const table of tables){
        const hero=getHeroFromTable(table);
        if(hero){
          lines.push(hero);
          
          // Try to get board for this table too
          const board=getBoardFromTable(table);
          if(board)lines.push(board);
        }
      }
    }
    
    return lines;
  }
  
  // Send snapshot to collector
  function send(text){
    const x=new XMLHttpRequest();
    x.open('POST',API);
    x.setRequestHeader('Content-Type','application/json');
    x.onload=function(){
      try{
        const d=JSON.parse(x.responseText);
        if(!d.dup){
          count++;
          const lineCount=text.split('\n').length;
          console.log(`[N4P-MULTI] Snapshot #${count} (${lineCount} lines):\n${text}`);
        }
      }catch(e){
        console.error('[N4P-MULTI] Response error:',x.responseText);
      }
    };
    x.onerror=function(){
      console.error('[N4P-MULTI] Network error');
    };
    x.send(JSON.stringify({text}));
  }
  
  // Main collector tick
  function tick(){
    const lines=getAllHeroHands();
    
    if(lines.length===0){
      console.log('[N4P-MULTI] No hero hands found');
      return;
    }
    
    const text=lines.join('\n');
    if(text===last)return;
    
    last=text;
    send(text);
  }
  
  // Start polling
  window._n4p=setInterval(tick,1500);
  tick();
  console.log('[N4P-MULTI] v4.0 running - MULTI-TABLE hero collection - stop: clearInterval(window._n4p)');
})();
