#!/bin/bash
# Bot Failsafe Monitor v2 - Dublin server
# Checks: bot processes, Flask health, Cape Town tunnel
# Restarts dead bots, logs all events
# Persisted: systemd bot-monitor.service

LOG=/var/log/bot_monitor.log
API_BASE=http://172.31.17.239:5000/api

declare -A CREDS=(
  [bot-kele1]="kele1:PokerPass123"
  [bot-kana]="kana:PokerPass123"
  [bot-leni]="leni:PokerPass123"
  [bot-shax]="shax:PokerPass123"
  [bot-pretty88]="pretty88:PokerPass123"
  [bot-lont]="lont:PokerPass123"
  [bot-daniellek]="DanielleKorevaar:Ashleyjancouys@1"
  [bot-pile]="pile:PokerPass123"
  [bot-hele]="hele:PokerPass123"
)

restart_bot() {
  local BOT=$1
  local CRED="${CREDS[$BOT]}"
  local USER="${CRED%%:*}"
  local PASS="${CRED##*:}"
  docker exec $BOT pkill -f poker_bot.py 2>/dev/null
  sleep 2
  docker exec -u root $BOT mkdir -p /app 2>/dev/null
  docker cp /opt/plo-equity/static/n4p.js $BOT:/app/n4p.js 2>/dev/null
  docker cp /opt/pokerbet-selenium/poker_bot.py $BOT:/tmp/poker_bot.py 2>/dev/null
  docker exec -d $BOT bash -c "export API_BASE=$API_BASE POKER_USERNAME=$USER POKER_PASSWORD='$PASS' TABLE_NAME=Belgrade; cd /tmp && python3 poker_bot.py > /tmp/bot.log 2>&1"
  echo "$(date '+%Y-%m-%d %H:%M:%S') [RESTART] $BOT ($USER)" >> $LOG
}

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> $LOG; }

log "[START] Bot monitor v2 started (Dublin)"

ITER=0
while true; do
  ITER=$((ITER+1))
  
  # --- Check Flask ---
  FLASK_OK=$(curl -s --connect-timeout 5 $API_BASE/health 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("ok",False),d.get("active_tables",0))' 2>/dev/null)
  if [ -z "$FLASK_OK" ] || echo "$FLASK_OK" | grep -q "False"; then
    log "[ALERT] Flask not responding - waiting"
    sleep 30
    continue
  fi
  
  # --- Check bots ---
  DEAD=0; ALIVE=0
  for BOT in bot-kele1 bot-kana bot-leni bot-shax bot-pretty88 bot-lont bot-daniellek bot-pile bot-hele; do
    RUNNING=$(docker inspect -f '{{.State.Running}}' $BOT 2>/dev/null)
    [ "$RUNNING" != "true" ] && continue
    
    PID=$(docker exec $BOT pgrep -f poker_bot.py 2>/dev/null | head -1)
    if [ -z "$PID" ]; then
      log "[DEAD] $BOT - no process"
      restart_bot $BOT
      DEAD=$((DEAD+1))
      continue
    fi
    
    FATAL=$(docker exec $BOT tail -5 /tmp/bot.log 2>/dev/null | grep -c 'FATAL\|Traceback\|NameError')
    if [ "$FATAL" -gt 0 ]; then
      log "[CRASH] $BOT - fatal in log"
      restart_bot $BOT
      DEAD=$((DEAD+1))
      continue
    fi
    # Check for lost table view (stuck bot)
    LOST=$(docker exec $BOT tail -3 /tmp/bot.log 2>/dev/null | grep -c "Lost table view|No snapshot.*pmc=0")
    if [ "$LOST" -gt 0 ]; then
      log "[STALE] $BOT - lost table, restarting"
      restart_bot $BOT
      DEAD=$((DEAD+1))
      continue
    fi
    ALIVE=$((ALIVE+1))
  done
  
  # --- Status every 5 min ---
  if [ $((ITER % 5)) -eq 0 ]; then
    TABLES=$(echo "$FLASK_OK" | awk '{print $2}')
    log "[STATUS] alive=$ALIVE dead=$DEAD tables=$TABLES"
  fi
  
  sleep 60
done
