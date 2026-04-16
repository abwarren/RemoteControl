#!/usr/bin/env python3
"""
Bot Deployment System — docker exec orchestrator.

Instead of running Chrome on the host, this copies bot_runner.py into
each player's container and launches it via `docker exec`.  Each player's
traffic exits through its own EIP (multi-ENI SNAT routing).

Host-side responsibilities:
  - Validate the deploy request
  - Copy bot_runner.py into the target container
  - Launch the runner via `docker exec` (background)
  - Poll /tmp/bot_status.json inside the container for progress
  - Expose status to the Flask API
"""

import os
import time
import uuid
import json
import logging
import threading
import subprocess
import sqlite3
from datetime import datetime

PLAYERS_DB = "/opt/plo-equity/players.db"
BOT_RUNNER_PATH = "/opt/plo-equity/bot_runner.py"
N4P_JS_PATH = "/opt/plo-equity/static/n4p.js"
DEPLOY_LOG = "/tmp/bot_deployment.log"


def _log(msg):
    """Write directly to deploy log file (visible outside Flask)."""
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(DEPLOY_LOG, "a") as f:
            f.write(line)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Credentials from DB
# ---------------------------------------------------------------------------

def get_credentials():
    """Pull active player credentials (including table_name) from the database."""
    conn = sqlite3.connect(PLAYERS_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT username, password, container_name, docker_ip, eni, eip, table_name "
        "FROM players WHERE active=1 ORDER BY id"
    ).fetchall()
    conn.close()
    return {i + 1: dict(r) for i, r in enumerate(rows)}


# ---------------------------------------------------------------------------
# Global status tracking
# ---------------------------------------------------------------------------

_bot_deployments = {}
_bot_statuses = {}
_status_lock = threading.Lock()


def update_bot_status(bot_id, status, error=None, metadata=None):
    with _status_lock:
        entry = _bot_statuses.setdefault(bot_id, {})
        entry["status"] = status
        entry["last_update"] = time.time()
        if error:
            entry["error"] = error
        if metadata:
            entry["metadata"] = metadata


def get_bot_status(bot_id):
    with _status_lock:
        return dict(_bot_statuses.get(bot_id, {"status": "UNKNOWN"}))


def get_deployment_status(deployment_id):
    with _status_lock:
        dep = _bot_deployments.get(deployment_id)
        if not dep:
            return None
        bots = []
        for bid in dep.get("bot_ids", []):
            bots.append({"bot_id": bid, **_bot_statuses.get(bid, {"status": "UNKNOWN"})})
        return {
            "deployment_id": deployment_id,
            "created_at": dep.get("created_at"),
            "bot_count": dep.get("bot_count"),
            "bots": bots,
        }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_deploy_request(req):
    # table_name is optional — falls back to per-player value in DB

    if req.get("buy_in_mode") not in ("MAX", "MIN"):
        return {"ok": False, "error": "buy_in_mode must be MAX or MIN"}

    bot_count = req.get("bot_count")
    if not isinstance(bot_count, int):
        return {"ok": False, "error": "bot_count must be integer"}

    max_players = len(get_credentials())
    if bot_count < 1 or bot_count > max_players:
        return {"ok": False, "error": f"bot_count must be between 1 and {max_players}"}

    if req.get("first_action_policy") not in ("CHECK_OR_CALL_ONCE", None):
        return {"ok": False, "error": "Invalid first_action_policy"}

    if req.get("mode") != "SEATING_ONLY":
        return {"ok": False, "error": "Only SEATING_ONLY mode allowed"}

    return {"ok": True}


def generate_deployment_id():
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"dep_{ts}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------

def docker_exec(container, cmd, timeout=10):
    """Run a command inside a container and return (returncode, stdout, stderr)."""
    full_cmd = ["docker", "exec", container] + cmd
    try:
        proc = subprocess.run(
            full_cmd, capture_output=True, text=True, timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"


def docker_cp(src, container, dest):
    """Copy a file from host into a container."""
    result = subprocess.run(
        ["docker", "cp", src, f"{container}:{dest}"],
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode == 0


def read_container_status(container):
    """Read /tmp/bot_status.json from inside a container."""
    rc, out, _ = docker_exec(container, ["cat", "/tmp/bot_status.json"], timeout=5)
    if rc == 0 and out.strip():
        try:
            return json.loads(out.strip())
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# Bot worker (one thread per player)
# ---------------------------------------------------------------------------

TERMINAL_STATUSES = {
    "REMOTE_CONTROL_ACTIVE",
    "DISCONNECTED",
    "ERROR",
    "TABLE_NOT_FOUND",
    "SEAT_NOT_AVAILABLE",
    "BUY_IN_FAILED",
    "SEATING_FAILED",
    "FIRST_ACTION_TIMEOUT",
}


def bot_worker(job):
    """
    Deploy a single player:
      1. Copy bot_runner.py into the container
      2. Launch it via docker exec (background subprocess)
      3. Poll /tmp/bot_status.json until terminal state
    """
    try:
        _bot_worker_inner(job)
    except Exception as e:
        import traceback
        _log(f"[{job.get('bot_id','?')}] FATAL: {e}\n{traceback.format_exc()}")
        update_bot_status(job.get("bot_id", "unknown"), "ERROR", error=f"Thread crash: {e}")


def _bot_worker_inner(job):
    bot_id = job["bot_id"]
    container = job["container_name"]
    username = job["username"]
    password = job["password"]
    table_name = job["table_name"]
    buy_in_mode = job["buy_in_mode"]
    auto_buyin = job.get("auto_buyin_enabled", False)
    first_action = job.get("first_action_policy")

    _log(f"[{bot_id}] bot_worker started for {username} → {container}")
    update_bot_status(bot_id, "PREPARING", metadata={"container": container})

    # 1. Clear old status / log inside the container
    rc, out, err = docker_exec(container, ["rm", "-f", "/tmp/bot_status.json", "/tmp/bot_deploy.log"])
    _log(f"[{bot_id}] clear old files: rc={rc}")

    # 2. Copy bot_runner.py into the container
    if not docker_cp(BOT_RUNNER_PATH, container, "/tmp/bot_runner.py"):
        _log(f"[{bot_id}] docker cp FAILED for {container}")
        update_bot_status(bot_id, "ERROR", error=f"Failed to copy bot_runner.py into {container}")
        return
    _log(f"[{bot_id}] docker cp bot_runner.py OK")

    # 2b. Copy n4p.js into the container (for remote control injection)
    if os.path.exists(N4P_JS_PATH):
        if docker_cp(N4P_JS_PATH, container, "/tmp/n4p.js"):
            _log(f"[{bot_id}] docker cp n4p.js OK")
        else:
            _log(f"[{bot_id}] WARNING: docker cp n4p.js FAILED (continuing without it)")
    else:
        _log(f"[{bot_id}] WARNING: {N4P_JS_PATH} not found on host")

    # 3. Build the command
    cmd = [
        "python3", "/tmp/bot_runner.py",
        "--username", username,
        "--password", password,
        "--table", table_name,
        "--buyin", buy_in_mode,
        "--bot-id", bot_id,
    ]
    if auto_buyin:
        cmd.append("--auto-buyin")
    if first_action:
        cmd.extend(["--first-action", first_action])

    # 4. Launch via docker exec (non-blocking subprocess)
    full_cmd = ["docker", "exec", "-d", container] + cmd
    _log(f"[{bot_id}] launching: {' '.join(full_cmd)}")
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=10)
        _log(f"[{bot_id}] exec rc={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}")
    except Exception as e:
        _log(f"[{bot_id}] docker exec launch FAILED: {e}")
        update_bot_status(bot_id, "ERROR", error=f"docker exec launch failed: {e}")
        return

    update_bot_status(bot_id, "LAUNCHED", metadata={"container": container})
    _log(f"[{bot_id}] LAUNCHED in {container}")

    # 5. Poll the status file inside the container
    poll_interval = 3  # seconds
    max_poll_time = 300  # 5 minutes max
    start = time.time()

    while time.time() - start < max_poll_time:
        time.sleep(poll_interval)
        status_data = read_container_status(container)
        if status_data:
            s = status_data.get("status", "UNKNOWN")
            update_bot_status(
                bot_id, s,
                error=status_data.get("error"),
                metadata=status_data.get("metadata"),
            )
            if s in TERMINAL_STATUSES:
                return

    # Timed out polling
    update_bot_status(bot_id, "POLL_TIMEOUT", error="Status polling exceeded 5 minutes")


# ---------------------------------------------------------------------------
# Deploy entry point (called by Flask)
# ---------------------------------------------------------------------------

def deploy_bots(request_data):
    """Validate request, spawn one thread per player, return deployment ID."""
    _log(f"[deploy_bots] called with: {json.dumps(request_data, default=str)}")
    validation = validate_deploy_request(request_data)
    if not validation["ok"]:
        return validation

    deployment_id = generate_deployment_id()
    bot_count = request_data["bot_count"]

    with _status_lock:
        _bot_deployments[deployment_id] = {
            "deployment_id": deployment_id,
            "created_at": time.time(),
            "bot_count": bot_count,
            "bot_ids": [],
            "request": request_data,
        }

    all_creds = get_credentials()

    for i in range(bot_count):
        bot_id = f"bot_{deployment_id}_{i}"
        bot_index = i + 1
        creds = all_creds.get(bot_index, {"username": "pile", "password": "PokerPass123", "container_name": "bot-pile"})

        with _status_lock:
            _bot_deployments[deployment_id]["bot_ids"].append(bot_id)
            _bot_statuses[bot_id] = {
                "status": "QUEUED",
                "deployment_id": deployment_id,
                "last_update": time.time(),
            }

        job = {
            "bot_id": bot_id,
            "deployment_id": deployment_id,
            "username": creds["username"],
            "password": creds["password"],
            "container_name": creds["container_name"],
            "table_name": request_data.get("table_name") or creds.get("table_name") or "Multan",
            "buy_in_mode": request_data["buy_in_mode"],
            "auto_buyin_enabled": request_data.get("auto_buyin_enabled", False),
            "first_action_policy": request_data.get("first_action_policy"),
            "mode": request_data["mode"],
        }

        _log(f"[deploy_bots] spawning thread for {bot_id} → {creds['container_name']}")
        thread = threading.Thread(target=bot_worker, args=(job,), daemon=True)
        thread.start()
        _log(f"[deploy_bots] thread started: {thread.name} alive={thread.is_alive()}")

    return {
        "ok": True,
        "deployment_id": deployment_id,
        "accepted_bots": bot_count,
        "mode": request_data["mode"],
        "status": "DEPLOY_STARTED",
    }
