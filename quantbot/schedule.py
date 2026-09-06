"""launchd scheduling for the three daily paper sessions (macOS).

Sessions are defined in Eastern time; launchd runs on local wall-clock time,
so we convert at install time. Both zones observe US DST, so the offset is
stable year-round unless the machine's timezone itself changes. Missed jobs
(machine asleep) run once on wake; `trade --session auto` is idempotent so a
late run just processes the most recent session once.
"""
from __future__ import annotations

import datetime as dt
import plistlib
import subprocess
import sys
import zoneinfo
from pathlib import Path

from .config import PROJECT_ROOT
from .data import ET

LABEL = "com.quantbot.hf"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_DIR = PROJECT_ROOT / "paper_state" / "hf"

# ET run times: a few minutes after each session so Yahoo has the print.
# The 15:32 run only matters if an intraday (15:30-entry) sleeve is funded.
def _run_times_et() -> list[tuple[int, int]]:
    from .strategies.hf_ensemble import EnsembleParams
    # Second run each session is a retry: `trade` is idempotent, so if the
    # first run found Yahoo late (loud failure) the retry processes it.
    times = [(9, 33), (9, 38), (9, 47), (16, 8), (16, 25)]
    if EnsembleParams.from_profile().alloc.get("intraday_momentum", 0) > 0:
        times.insert(3, (15, 32))
    return times


RUN_TIMES_ET = _run_times_et()


def _local_times() -> list[tuple[int, int]]:
    et = zoneinfo.ZoneInfo(ET)
    local = dt.datetime.now().astimezone().tzinfo
    today = dt.date.today()
    out = []
    for h, m in RUN_TIMES_ET:
        t = dt.datetime.combine(today, dt.time(h, m), tzinfo=et).astimezone(local)
        out.append((t.hour, t.minute))
    return out


def _plist() -> dict:
    intervals = []
    for h, m in _local_times():
        for wd in range(1, 6):  # Mon-Fri
            intervals.append({"Hour": h, "Minute": m, "Weekday": wd})
    return {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(PROJECT_ROOT / "run.py"), "hf", "trade", "--session", "auto"],
        "WorkingDirectory": str(PROJECT_ROOT),
        "StartCalendarInterval": intervals,
        "StandardOutPath": str(LOG_DIR / "launchd.out.log"),
        "StandardErrPath": str(LOG_DIR / "launchd.err.log"),
        "EnvironmentVariables": {"MPLCONFIGDIR": "/tmp/mpl", "PATH": "/usr/local/bin:/usr/bin:/bin"},
        "RunAtLoad": False,
    }


def show_schedule() -> None:
    print("Paper sessions (ET -> local):")
    for (eh, em), (lh, lm) in zip(RUN_TIMES_ET, _local_times()):
        print(f"  {eh:02d}:{em:02d} ET  ->  {lh:02d}:{lm:02d} local")
    print(f"\nlaunchd plist: {PLIST_PATH} ({'installed' if PLIST_PATH.exists() else 'not installed'})")
    print("Install with: python3 run.py hf schedule --install")
    print("Or cron (ET machine):")
    for h, m in RUN_TIMES_ET:
        print(f"  {m} {h} * * 1-5 cd {PROJECT_ROOT} && {sys.executable} run.py hf trade --session auto "
              f">> paper_state/hf/cron.log 2>&1")


def install_launchd() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=False, capture_output=True)
    with PLIST_PATH.open("wb") as f:
        plistlib.dump(_plist(), f)
    res = subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"launchctl load failed: {res.stderr.strip()}")
    else:
        print(f"Installed {LABEL}:")
        show_schedule()


def uninstall_launchd() -> None:
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=False, capture_output=True)
        PLIST_PATH.unlink()
        print(f"Removed {LABEL}")
    else:
        print("Not installed")
