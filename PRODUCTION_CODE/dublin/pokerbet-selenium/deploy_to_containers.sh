#!/bin/bash
# Deploy bot script and n4p.js to all bot containers
# Run after container restart/recreate to ensure files are in place
# Called by: systemd eip-snat.service (post-boot) or manually

BOT_SCRIPT=/opt/pokerbet-selenium/poker_bot.py
N4P_JS=/opt/plo-equity/static/n4p.js

for BOT in $(docker ps --format '{{.Names}}' | grep '^bot-'); do
  docker exec -u root $BOT mkdir -p /app 2>/dev/null
  docker cp $N4P_JS $BOT:/app/n4p.js 2>/dev/null
  docker cp $BOT_SCRIPT $BOT:/tmp/poker_bot.py 2>/dev/null
  echo "[$(date +%H:%M:%S)] Deployed to $BOT"
done
