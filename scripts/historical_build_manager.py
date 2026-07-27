#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "derived" / "historical_feature_store_build.log"
PID_PATH = REPO_ROOT / "data" / "derived" / "historical_feature_store_build.pid"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "derived" / "historical_feature_store"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_historical_feature_store.py"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_pid_file() -> int | None:
    if not PID_PATH.exists():
        return None
    raw = PID_PATH.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _is_pid_active(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _load_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_checkpoint_month(output_dir: Path) -> str | None:
    checkpoint_root = output_dir / "checkpoints"
    if not checkpoint_root.exists():
        return None
    months = sorted([p.name for p in checkpoint_root.iterdir() if p.is_dir()])
    return months[-1] if months else None


def _start_build(start_date: str, end_date: str | None, output_dir: Path) -> int:
    existing_pid = _read_pid_file()
    if existing_pid is not None and _is_pid_active(existing_pid):
        print(f"REFUSED: build already running pid={existing_pid}")
        return 2

    _ensure_parent(LOG_PATH)
    _ensure_parent(PID_PATH)

    cmd = [
        sys.executable,
        str(BUILD_SCRIPT),
        "--start-date",
        start_date,
        "--output-dir",
        str(output_dir),
        "--resume",
    ]
    if end_date:
        cmd.extend(["--end-date", end_date])

    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    PID_PATH.write_text(f"{process.pid}\n", encoding="utf-8")
    print(f"STARTED pid={process.pid}")
    return 0


def _status(output_dir: Path) -> int:
    pid = _read_pid_file()
    if pid is None:
        print("STATUS: NO_PID_FILE")
        return 0

    active = _is_pid_active(pid)
    meta = _load_metadata(output_dir / "historical_feature_store_metadata.json")
    latest_month = _latest_checkpoint_month(output_dir)

    print(f"PID={pid}")
    print(f"ACTIVE={'YES' if active else 'NO'}")
    print(f"LOG_PATH={LOG_PATH}")
    print(f"PID_PATH={PID_PATH}")
    print(f"LATEST_CHECKPOINT_MONTH={latest_month or 'NONE'}")
    if meta:
        print(f"LAST_RECORDED_START_DATE={meta.get('start_date')}")
        print(f"LAST_RECORDED_END_DATE={meta.get('end_date')}")
        print(f"LAST_RECORDED_MONTHS_COMPLETED={meta.get('months_completed')}")
    return 0


def _stop() -> int:
    pid = _read_pid_file()
    if pid is None:
        print("STOP: NO_PID_FILE")
        return 0

    if not _is_pid_active(pid):
        print(f"STOP: PID_NOT_ACTIVE pid={pid}")
        return 0

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        print(f"STOP: PID_NOT_ACTIVE pid={pid}")
        return 0

    print(f"STOP_SENT pid={pid} signal=SIGTERM")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Signal-safe manager for historical feature-store build")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Start detached build")
    start_parser.add_argument("--start-date", required=True)
    start_parser.add_argument("--end-date", default=None)
    start_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))

    status_parser = subparsers.add_parser("status", help="Show build status")
    status_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))

    subparsers.add_parser("stop", help="Gracefully stop build process")

    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.command == "start":
        return _start_build(args.start_date, args.end_date, Path(args.output_dir))
    if args.command == "status":
        return _status(Path(args.output_dir))
    if args.command == "stop":
        return _stop()

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
