#!/usr/bin/env python3
"""
Bot Supervisor Service - Monitors and maintains all 9 poker bots.
Runs as a systemd service. Checks every 30s and takes corrective action.
"""
import subprocess
import json
import time
import os
import sys
from datetime import datetime

LOG_DIR = "/opt/plo-equity/logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Desired state: all 9 bots running at Belgrade
BOTS = {
    "bot-pile":              {"user": "pile",              "pass": "PokerPass123"},
    "bot-kana":              {"user": "kana",              "pass": "PokerPass123"},
    "bot-leni":              {"user": "leni",              "pass": "PokerPass123"},
    "bot-kele1":             {"user": "kele1",             "pass": "PokerPass123"},
    "bot-pretty88":          {"user": "pretty88",          "pass": "PokerPass123"},
    "bot-shax":              {"user": "shax",              "pass": "PokerPass123"},
    "bot-lont":              {"user": "lont",              "pass": "PokerPass123"},
    "bot-hele":              {"user": "hele",              "pass": "PokerPass123"},
    "bot-daniellekorevaar":  {"user": "DanielleKorevaar",  "pass": "PokerPass123"},
}

TABLE_NAME = "Belgrade"
IMAGE = "pokerbet-selenium:working"
API_BASE = "http://172.31.41.21:5000/api"
CHECK_INTERVAL = 30
MAX_RESTARTS_PER_HOUR = 5

# Track restart counts
restart_counts = {name: [] for name in BOTS}


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(f"{LOG_DIR}/supervisor.log", "a") as f:
        f.write(line + "\n")


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", 1
    except Exception as e:
        return str(e), 1


def is_running(name):
    out, rc = run(f"sudo docker ps --filter name=^{name}$ --format '{{{{.Status}}}}'")
    return bool(out) and "Up" in out


def get_logs(name, tail=10):
    out, _ = run(f"sudo docker logs {name} --tail {tail} 2>&1")
    return out


def restart_bot(name, bot_cfg):
    """Stop and recreate a bot container."""
    log(f"  RESTARTING {name}...")
    run(f"sudo docker rm -f {name} 2>/dev/null")
    time.sleep(2)
    cmd = (
        f"sudo docker run -d --name {name} --restart=always --shm-size=256m "
        f"-e POKER_USERNAME={bot_cfg['user']} "
        f"-e POKER_PASSWORD={bot_cfg['pass']} "
        f"-e TABLE_NAME={TABLE_NAME} "
        f"-e BUYIN_AMOUNT=MIN "
        f"-e API_BASE={API_BASE} "
        f"{IMAGE}"
    )
    out, rc = run(cmd)
    if rc == 0:
        log(f"  {name} restarted OK")
        restart_counts[name].append(time.time())
    else:
        log(f"  {name} restart FAILED: {out}")


def check_restart_limit(name):
    """Check if bot has been restarted too many times recently."""
    now = time.time()
    # Keep only restarts in last hour
    restart_counts[name] = [t for t in restart_counts[name] if now - t < 3600]
    return len(restart_counts[name]) < MAX_RESTARTS_PER_HOUR


def check_backend():
    """Verify the Flask backend is healthy."""
    out, rc = run(f"curl -s {API_BASE.replace('/api', '')}/api/health")
    try:
        data = json.loads(out)
        return data.get("ok", False)
    except:
        return False


def get_table_state():
    """Get current table state from API."""
    out, rc = run(f"curl -s {API_BASE}/table/latest")
    try:
        data = json.loads(out)
        return data.get("table", {})
    except:
        return {}


def check_bot(name, bot_cfg):
    """Check a single bot's health and take corrective action."""
    if not is_running(name):
        log(f"  {name}: NOT RUNNING")
        if check_restart_limit(name):
            restart_bot(name, bot_cfg)
        else:
            log(f"  {name}: RATE LIMITED - too many restarts, skipping")
        return "restarted"

    # Check logs for issues
    logs = get_logs(name, 5)

    if "FATAL" in logs:
        log(f"  {name}: FATAL error detected")
        if check_restart_limit(name):
            restart_bot(name, bot_cfg)
        else:
            log(f"  {name}: RATE LIMITED")
        return "fatal"

    if "Bot ready" in logs or "[OK]" in logs:
        return "ok"

    if "Logging in" in logs or "Starting Firefox" in logs:
        return "starting"

    return "unknown"


def main():
    log("=" * 60)
    log("BOT SUPERVISOR SERVICE STARTED")
    log(f"Monitoring {len(BOTS)} bots at table {TABLE_NAME}")
    log(f"Check interval: {CHECK_INTERVAL}s")
    log("=" * 60)

    while True:
        try:
            # Check backend health
            backend_ok = check_backend()
            if not backend_ok:
                log("BACKEND DOWN! Attempting restart...")
                run("sudo systemctl restart plo-equity")
                time.sleep(5)
                backend_ok = check_backend()
                if backend_ok:
                    log("Backend recovered")
                else:
                    log("Backend still down - will retry next cycle")

            # Check each bot
            statuses = {}
            for name, cfg in BOTS.items():
                status = check_bot(name, cfg)
                statuses[name] = status

            # Summary
            ok = sum(1 for s in statuses.values() if s == "ok")
            starting = sum(1 for s in statuses.values() if s == "starting")
            issues = sum(1 for s in statuses.values() if s not in ("ok", "starting"))

            if issues > 0 or ok < len(BOTS):
                log(f"STATUS: {ok} ok, {starting} starting, {issues} issues")
                for name, status in statuses.items():
                    if status not in ("ok",):
                        log(f"  {name}: {status}")

            # Get table state
            table = get_table_state()
            if table:
                seats = table.get("seats", [])
                occupied = sum(1 for s in seats if s.get("name"))
                street = table.get("street", "?")
                if occupied > 0:
                    log(f"TABLE: {street}, {occupied}/{len(seats)} seats occupied")

        except Exception as e:
            log(f"ERROR in supervisor loop: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
