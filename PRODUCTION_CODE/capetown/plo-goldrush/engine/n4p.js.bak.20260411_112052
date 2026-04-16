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
  
  // Collect ALL visible player hands at the current table
  function getAllPlayersAtTable(){
    const players=[];
    const seats=document.querySelectorAll('sg-poker-table-seat');
    
    for(const seat of seats){
      const seen=new Set();
      const hand=[];
      
      for(const el of seat.querySelectorAll('.single-cart-view-p')){
        const c=tok(el.getAttribute('class')||'');
        if(c&&!seen.has(c)){
          seen.add(c);
          hand.push(c);
        }
      }
      
      // Include any player with visible cards (4 or 6 cards for PLO)
      if(hand.length===4||hand.length===6){
        players.push(hand.join(''));
      }
    }
    
    return players;
  }
  
  // Get board cards for the current table
  function getBoard(){
    const boardEl=document.querySelector('sg-poker-board');
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
  
  // Build complete table snapshot
  function buildTableSnapshot(){
    const players=getAllPlayersAtTable();
    if(players.length===0)return null;
    
    const lines=[...players];
    const board=getBoard();
    if(board)lines.push(board);
    
    return lines.join('\n');
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
          console.log(`[N4P-TABLE] Snapshot #${count} (${lineCount} lines):\n${text}`,d);
        }
      }catch(e){
        console.error('[N4P-TABLE] Response error:',x.responseText);
      }
    };
    x.onerror=function(){
      console.error('[N4P-TABLE] Network error');
    };
    x.send(JSON.stringify({text}));
  }
  
  // Main collector tick
  function tick(){
    const snapshot=buildTableSnapshot();
    if(!snapshot)return;
    if(snapshot===last)return;
    
    last=snapshot;
    send(snapshot);
  }
  
  // Start polling
  window._n4p=setInterval(tick,1500);
  tick();
  console.log('[N4P-TABLE] v5.0 - ONE TABLE SNAPSHOT - all visible players + board');
})();
