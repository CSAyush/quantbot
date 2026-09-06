#!/usr/bin/env bash
# One-shot setup for an always-on Linux box (Ubuntu/Debian; e.g. a $4-6/month
# VPS or an Oracle/GCP free-tier VM). Installs Python deps, sets the machine's
# cron to Eastern time, and schedules the two paper sessions with retries.
#
# Usage (on the server, from the repo directory):
#   bash deploy/setup_server.sh
#
# To move the existing paper history over, copy paper_state/ from the laptop
# first (e.g. `rsync -a paper_state/ user@server:~/quantbot/paper_state/`),
# then stop the laptop's launchd job: `python3 run.py hf schedule --uninstall`.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="$(command -v python3)"
LOG_DIR="$REPO_DIR/paper_state/hf"
mkdir -p "$LOG_DIR" /tmp/mpl

echo "== installing dependencies"
if command -v apt-get >/dev/null; then
  sudo apt-get update -qq && sudo apt-get install -y -qq python3-pip python3-venv cron >/dev/null
fi
"$PY" -m pip install --user -q -r "$REPO_DIR/requirements.txt"

echo "== cron (times in America/New_York; retries are idempotent)"
CRON_TZ_LINE="CRON_TZ=America/New_York"
CMD="cd $REPO_DIR && MPLCONFIGDIR=/tmp/mpl $PY run.py hf trade --session auto >> $LOG_DIR/cron.log 2>&1"
STATUS="cd $REPO_DIR && MPLCONFIGDIR=/tmp/mpl $PY run.py hf status --no-plot >> $LOG_DIR/status.log 2>&1"
( crontab -l 2>/dev/null | grep -v "quantbot" | grep -v "^CRON_TZ=" || true
  echo "$CRON_TZ_LINE"
  echo "33 9  * * 1-5 $CMD  # quantbot open"
  echo "38 9  * * 1-5 $CMD  # quantbot open retry"
  echo "47 9  * * 1-5 $CMD  # quantbot open retry"
  echo "12 16 * * 1-5 $CMD  # quantbot close"
  echo "25 16 * * 1-5 $CMD  # quantbot close retry"
  echo "40 16 * * 1-5 $STATUS  # quantbot daily status line"
) | crontab -
sudo systemctl enable --now cron 2>/dev/null || true

echo "== smoke test"
cd "$REPO_DIR" && MPLCONFIGDIR=/tmp/mpl "$PY" run.py hf status --no-plot | head -8

echo
echo "Done. Sessions run at 09:33/09:38/09:47 and 16:12/16:25 ET, Mon-Fri."
echo "Logs: $LOG_DIR/cron.log  |  status: python3 run.py hf status"
