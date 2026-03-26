from __future__ import annotations

import http.client
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
PID_FILE = PROJECT_DIR / "server.pid"
LOG_FILE = PROJECT_DIR / "server.log"
ERR_FILE = PROJECT_DIR / "server.err.log"
PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
PYTHONW = PROJECT_DIR / ".venv" / "Scripts" / "pythonw.exe"
HOST = "127.0.0.1"
PORT = 8080
MARKER = "ClawdSourcing"


def read_pid() -> int | None:
    try:
        raw = PID_FILE.read_text(encoding="utf-8").strip()
        return int(raw) if raw else None
    except (FileNotFoundError, ValueError):
        return None


def write_pid(pid: int) -> None:
    PID_FILE.write_text(str(pid), encoding="utf-8")


def clear_pid() -> None:
    PID_FILE.unlink(missing_ok=True)


def process_exists(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return str(pid) in result.stdout


def listener_pids() -> list[int]:
    result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False)
    pids: list[int] = []
    seen: set[int] = set()
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if "LISTENING" not in line or f":{PORT}" not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr = parts[1]
        if not local_addr.endswith(f":{PORT}"):
            continue
        pid_raw = parts[-1]
        if not pid_raw.isdigit():
            continue
        pid = int(pid_raw)
        if pid not in seen:
            seen.add(pid)
            pids.append(pid)
    return pids


def probe_root(timeout: float = 2.0) -> tuple[str, int | None]:
    conn = http.client.HTTPConnection(HOST, PORT, timeout=timeout)
    try:
        conn.request("GET", "/")
        response = conn.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        if MARKER in body:
            return "app", response.status
        return "other", response.status
    except OSError:
        return "down", None
    except Exception:
        return "down", None
    finally:
        conn.close()


def tail(path: Path, lines: int = 12) -> str:
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def launch_server() -> subprocess.Popen[bytes]:
    launcher = PYTHONW if PYTHONW.exists() else PYTHON
    stdout_handle = open(LOG_FILE, "ab", buffering=0)
    stderr_handle = open(ERR_FILE, "ab", buffering=0)
    creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(
        [str(launcher), "-m", "tokentrader.server"],
        cwd=str(PROJECT_DIR),
        stdin=subprocess.DEVNULL,
        stdout=stdout_handle,
        stderr=stderr_handle,
        creationflags=creationflags,
        close_fds=True,
    )


def current_server_pid() -> int | None:
    pids = listener_pids()
    if len(pids) == 1:
        return pids[0]
    saved_pid = read_pid()
    if saved_pid and process_exists(saved_pid):
        return saved_pid
    return None


def start() -> int:
    if not PYTHON.exists():
        print(f"Missing virtual environment interpreter: {PYTHON}")
        return 1

    state, _ = probe_root()
    saved_pid = read_pid()
    if state == "app":
        active_pid = current_server_pid()
        if active_pid:
            write_pid(active_pid)
            print(f"Server already running at http://{HOST}:{PORT} (PID {active_pid}).")
            return 0
        print(f"Server already running at http://{HOST}:{PORT}.")
        return 0

    if state == "other":
        print(f"Port {PORT} is already in use by another application.")
        return 1

    if saved_pid and not process_exists(saved_pid):
        clear_pid()

    proc = launch_server()
    write_pid(proc.pid)

    deadline = time.time() + 12
    while time.time() < deadline:
        time.sleep(1)
        state, _ = probe_root()
        if state == "app":
            active_pid = current_server_pid() or proc.pid
            write_pid(active_pid)
            print(f"Server started at http://{HOST}:{PORT} (PID {active_pid}).")
            return 0
        if state == "other":
            print(f"Port {PORT} became occupied by another application.")
            return 1
        if not process_exists(proc.pid):
            break

    print("Server did not become ready.")
    errors = tail(ERR_FILE)
    if errors:
        print("--- server.err.log ---")
        print(errors)
    return 1


def stop() -> int:
    stopped = False
    pids_to_kill: set[int] = set(listener_pids())
    pid = read_pid()
    if pid and process_exists(pid):
        pids_to_kill.add(pid)

    for target_pid in pids_to_kill:
        subprocess.run(
            ["taskkill", "/PID", str(target_pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        stopped = True

    clear_pid()

    deadline = time.time() + 8
    while time.time() < deadline:
        remaining = listener_pids()
        if not remaining:
            if stopped:
                print(f"Server stopped on http://{HOST}:{PORT}.")
            else:
                print("No running server was found.")
            return 0
        time.sleep(0.5)

    print(f"Server stop requested, but port {PORT} is still listening: {listener_pids()}")
    return 1


def status() -> int:
    state, code = probe_root()
    if state == "app":
        pid = current_server_pid()
        if pid:
            write_pid(pid)
        print(f"Server is running at http://{HOST}:{PORT}.")
        if pid:
            print(f"PID file: {pid}")
        return 0
    if state == "other":
        print(f"Port {PORT} responds, but it does not look like ClawdSourcing.")
        return 1
    print("Server is not running.")
    return 1


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"start", "stop", "status"}:
        print("Usage: server_control.py [start|stop|status]")
        return 1
    command = sys.argv[1]
    if command == "start":
        return start()
    if command == "stop":
        return stop()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
