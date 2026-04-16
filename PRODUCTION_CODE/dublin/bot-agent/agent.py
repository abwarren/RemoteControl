#!/usr/bin/env python3
"""
Bot Agent API - Per-bot local Flask service.
Runs on each bot EC2 instance. Central controller communicates via HTTP.

Endpoints:
  GET  /            - Service info
  GET  /health      - Health probe
  GET  /status      - Bot state + VPASS checkpoint
  GET  /snapshot    - Latest table snapshot
  POST /command     - Execute action (fold/check/call/raise/cashout)
  POST /deploy      - Start bot lifecycle
  POST /stop        - Graceful shutdown
  GET  /screenshot  - Latest failure screenshot
  GET  /logs        - Last N lines of bot log
"""

import collections
import json
import os
import sys
import threading
import time
import traceback
import urllib.request
import urllib.error

from flask import Flask, jsonify, request, send_file

# Add bot_runner to path (lives alongside this file)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bot_runner

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_driver = None
_shutdown = threading.Event()
_started_at = time.time()
_log_buffer = collections.deque(maxlen=500)

# VPASS checkpoints (ordered)
VPASS_CHECKPOINTS = [
    "login_success",
    "lobby_visible",
    "table_selected",
    "seat_acquired",
    "buyin_confirmed",
    "seated_confirmed",
    "remote_control_synced",
]

_state = {
    "status": "IDLE",
    "checkpoint": None,
    "checkpoints_passed": [],
    "bot_id": None,
    "username": None,
    "table_name": None,
    "seated": False,
    "browser_alive": False,
    "last_snapshot": None,
    "last_snapshot_time": None,
    "last_screenshot": None,
    "error": None,
    "central_api": None,
    "policy": {
        "emergency_actions": 1,
        "after_first_action": "PASSIVE",
        "n4p_reinjection": True,
    },
}

RELAY_INTERVAL = 2
SNAPSHOT_FRESH_SEC = 3
N4P_HEARTBEAT_SEC = 15


def _set(**kwargs):
    with _lock:
        _state.update(kwargs)


def _get(*keys):
    with _lock:
        if len(keys) == 1:
            return _state.get(keys[0])
        return {k: _state.get(k) for k in keys}


def _pass_checkpoint(name):
    """Mark a VPASS checkpoint as passed."""
    with _lock:
        _state["checkpoint"] = name
        if name not in _state["checkpoints_passed"]:
            _state["checkpoints_passed"].append(name)
    _agent_log(f"VPASS: {name}")


def _agent_log(msg):
    """Log to buffer and bot_runner log."""
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    _log_buffer.append(line)
    bot_runner.log(msg)


def _take_screenshot(driver, label="error"):
    """Save screenshot on failure, return path."""
    bot_id = _get("bot_id") or "unknown"
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = f"/tmp/bot_{bot_id}_{label}_{ts}.png"
    try:
        driver.save_screenshot(path)
        _set(last_screenshot=path)
        _agent_log(f"Screenshot saved: {path}")
        return path
    except Exception as e:
        _agent_log(f"Screenshot failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return jsonify({"service": "bot-agent", "version": "2.0", "bot_id": _get("bot_id")})


@app.route("/health")
def health():
    global _driver
    alive = False
    try:
        if _driver:
            _driver.title
            alive = True
    except Exception:
        pass

    body = {
        "healthy": _get("status") != "ERROR",
        "uptime": round(time.time() - _started_at),
        "browser_alive": alive,
    }
    return jsonify(body), 200 if body["healthy"] else 503


@app.route("/status")
def status():
    with _lock:
        return jsonify({k: v for k, v in _state.items() if k != "last_snapshot"})


@app.route("/snapshot")
def snapshot():
    global _driver
    snap = None
    ts = _get("last_snapshot_time")

    if ts and (time.time() - ts) < SNAPSHOT_FRESH_SEC:
        snap = _get("last_snapshot")

    if snap is None and _driver:
        try:
            snap = _driver.execute_script(
                "return typeof window._n4p_buildSnapshot === 'function' "
                "? window._n4p_buildSnapshot() : null"
            )
            if snap:
                snap["bot_id"] = _get("bot_id")
                _set(last_snapshot=snap, last_snapshot_time=time.time())
        except Exception as e:
            return jsonify({"error": str(e)}), 503

    if snap is None:
        return jsonify({"error": "no snapshot available"}), 503
    return jsonify(snap)


@app.route("/command", methods=["POST"])
def command():
    global _driver
    if not _driver or _get("status") != "REMOTE_CONTROL_ACTIVE":
        return jsonify({"ok": False, "error": "bot not active"}), 400

    data = request.get_json(force=True)
    action = data.get("action", "").lower()
    cmd_id = data.get("id", f"cmd_{int(time.time()*1000)}")
    amount = data.get("amount")

    cmd = {"id": cmd_id, "action": action, "amount": amount}
    central = _get("central_api")

    try:
        bot_runner.execute_command(_driver, cmd, central or "")
        return jsonify({"ok": True, "executed": True, "action": action, "id": cmd_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/deploy", methods=["POST"])
def deploy():
    if _get("status") not in ("IDLE", "STOPPED", "ERROR"):
        return jsonify({"ok": False, "error": "bot already running"}), 409

    data = request.get_json(force=True)
    required = ["bot_id", "username", "password", "table_name"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"ok": False, "error": f"missing fields: {missing}"}), 400

    policy = data.get("policy", {})
    _set(
        status="DEPLOYING",
        checkpoint=None,
        checkpoints_passed=[],
        bot_id=data["bot_id"],
        username=data["username"],
        table_name=data["table_name"],
        central_api=data.get("central_api", "http://172.31.17.239:5000/api"),
        error=None,
        seated=False,
        browser_alive=False,
        last_snapshot=None,
        last_snapshot_time=None,
        last_screenshot=None,
        policy={
            "emergency_actions": policy.get("emergency_actions", 1),
            "after_first_action": policy.get("after_first_action", "PASSIVE"),
            "n4p_reinjection": policy.get("n4p_reinjection", True),
        },
    )
    _shutdown.clear()
    _log_buffer.clear()

    t = threading.Thread(target=_deploy_worker, args=(data,), daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "deployment started"}), 202


@app.route("/stop", methods=["POST"])
def stop():
    global _driver
    _shutdown.set()
    if _driver:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None
    _set(status="STOPPED", browser_alive=False, seated=False)
    _agent_log("Bot stopped via /stop")
    return jsonify({"ok": True, "message": "bot stopped"})


@app.route("/screenshot")
def screenshot_endpoint():
    path = _get("last_screenshot")
    if path and os.path.exists(path):
        return send_file(path, mimetype="image/png")
    return jsonify({"error": "no screenshot available"}), 404


@app.route("/logs")
def logs():
    limit = request.args.get("limit", 100, type=int)
    lines = list(_log_buffer)[-limit:]
    return jsonify({"lines": lines, "count": len(lines)})


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

def _deploy_worker(params):
    """Run the full bot lifecycle with VPASS checkpoint tracking."""
    global _driver

    def _fail(driver, error, label="error"):
        """Handle deployment failure: screenshot + set error state."""
        _agent_log(f"DEPLOY FAILED: {error}")
        if driver:
            _take_screenshot(driver, label)
            try:
                driver.quit()
            except Exception:
                pass
        _driver = None
        _set(status="ERROR", error=error, browser_alive=False)

    try:
        _set(status="STARTING")
        _agent_log(f"Deploying {params['username']} → {params['table_name']}")
        driver = bot_runner.start_browser()
        _driver = driver
        _set(browser_alive=True)

        # Open site
        _set(status="OPENING_SITE")
        driver.get("https://www.pokerbet.co.za")
        bot_runner.human_pause(2.0, 3.0)

        # Login
        _set(status="LOGGING_IN")
        bot_runner.login(driver, params["username"], params["password"])
        _pass_checkpoint("login_success")

        # Open poker client
        _set(status="OPENING_POKER")
        bot_runner.open_poker_client(driver)
        _pass_checkpoint("lobby_visible")

        # Find table
        _set(status="SCANNING_TABLES")
        found = bot_runner.find_and_open_table(driver, params["table_name"])
        if not found:
            _fail(driver, f"Table '{params['table_name']}' not found", "table_not_found")
            return
        _pass_checkpoint("table_selected")

        # Buy in
        _set(status="SETTING_BUY_IN")
        buyin_mode = params.get("buy_in_mode", "MIN")
        auto_buyin = params.get("auto_buyin", False)
        result = bot_runner.handle_buy_in(driver, buyin_mode, auto_buyin)
        if not result["ok"]:
            _fail(driver, result.get("error", "Buy-in failed"), "buyin_failed")
            return
        _pass_checkpoint("buyin_confirmed")

        # Seat acquired
        _pass_checkpoint("seat_acquired")

        # Verify seated
        _set(status="VERIFYING_SEATED")
        seated = bot_runner.verify_seated(driver, params["table_name"])
        if not seated["ok"]:
            _fail(driver, "Seating verification failed", "seating_failed")
            return
        _set(seated=True)
        _pass_checkpoint("seated_confirmed")

        # Inject n4p.js
        _set(status="INJECTING_N4P")
        bot_runner.inject_n4p(driver, params["username"], params["bot_id"])

        # First action assist
        first_action = params.get("first_action")
        if first_action:
            _set(status="WAITING_FOR_FIRST_TURN")
            bot_runner.first_action_assist(driver, first_action)

        # Active
        _set(status="REMOTE_CONTROL_ACTIVE")
        _pass_checkpoint("remote_control_synced")
        _agent_log(f"{params['bot_id']} is REMOTE_CONTROL_ACTIVE")

        # Start n4p heartbeat monitor
        policy = _get("policy")
        if policy and policy.get("n4p_reinjection"):
            monitor = threading.Thread(
                target=_n4p_heartbeat,
                args=(driver, params["username"], params["bot_id"]),
                daemon=True,
            )
            monitor.start()

        # Start snapshot relay loop
        _snapshot_relay_loop(driver, params["bot_id"], _get("central_api"))

        _set(status="DISCONNECTED", browser_alive=False)

    except Exception as e:
        tb = traceback.format_exc()
        _agent_log(f"Deploy error: {e}\n{tb}")
        if _driver:
            _take_screenshot(_driver, "exception")
            try:
                _driver.quit()
            except Exception:
                pass
            _driver = None
        _set(status="ERROR", error=str(e), browser_alive=False)


def _n4p_heartbeat(driver, username, bot_id):
    """Check n4p.js every 15s, re-inject if lost."""
    while not _shutdown.is_set():
        try:
            injected = driver.execute_script("return window._n4p_injected === true")
            if not injected:
                _agent_log("N4P heartbeat: lost, re-injecting...")
                bot_runner.inject_n4p(driver, username, bot_id)
                _agent_log("N4P heartbeat: re-injection done")
        except Exception as e:
            if "disconnected" in str(e).lower() or "session" in str(e).lower():
                _agent_log(f"N4P heartbeat: browser gone: {e}")
                break
            _agent_log(f"N4P heartbeat error: {e}")
        _shutdown.wait(N4P_HEARTBEAT_SEC)


def _snapshot_relay_loop(driver, bot_id, central_api):
    """Read snapshots from browser, cache locally, relay to central API."""
    error_count = 0
    snap_count = 0

    while not _shutdown.is_set():
        try:
            snap = driver.execute_script(
                "return typeof window._n4p_buildSnapshot === 'function' "
                "? window._n4p_buildSnapshot() : null"
            )
            if snap is None:
                if error_count % 30 == 0:
                    _agent_log("Relay: _n4p_buildSnapshot not available")
                error_count += 1
                time.sleep(RELAY_INTERVAL)
                continue

            snap["bot_id"] = bot_id
            _set(last_snapshot=snap, last_snapshot_time=time.time())

            if central_api:
                try:
                    data = json.dumps(snap).encode("utf-8")
                    req = urllib.request.Request(
                        f"{central_api}/snapshot",
                        data=data,
                        headers={"Content-Type": "application/json", "X-API-Key": "trk_default"},
                        method="POST",
                    )
                    urllib.request.urlopen(req, timeout=5)
                    snap_count += 1
                    if snap_count % 30 == 0:
                        _agent_log(f"Relay: {snap_count} snapshots sent")
                except urllib.error.URLError as e:
                    if error_count % 30 == 0:
                        _agent_log(f"Relay: POST failed: {e}")
                    error_count += 1

            time.sleep(RELAY_INTERVAL)

        except Exception as e:
            if "disconnected" in str(e).lower() or "session" in str(e).lower():
                _agent_log(f"Relay: Browser disconnected: {e}")
                break
            error_count += 1
            if error_count % 30 == 0:
                _agent_log(f"Relay: error #{error_count}: {e}")
            time.sleep(RELAY_INTERVAL)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("AGENT_PORT", "5001"))
    app.run(host="0.0.0.0", port=port, threaded=True)
