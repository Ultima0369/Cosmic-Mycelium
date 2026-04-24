# Continuous Operation Scripts

> These scripts run the Cosmic Mycelium system in continuous modes.
> Place them in `cosmic_mycelium/scripts/` and configure as needed.

---

## `run_infant_continuous.sh` — Infant Lifecycle Loop

```bash
#!/usr/bin/env bash
# Run the infant in continuous breath-cycle mode.
# Logs to logs/infant_continuous.log (rotated daily).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/infant_continuous_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "=== Cosmic Mycelium Infant — Continuous Mode ==="
echo "Start: $(date -Iseconds)" | tee -a "$LOG_FILE"
echo "Project root: $PROJECT_ROOT" | tee -a "$LOG_FILE"

# Activate virtualenv if present
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Run infant with unbounded cycles
cd "$PROJECT_ROOT"
python3 -m cosmic_mycelium.infant.main \
    --cycles 0 \
    --log-file "$LOG_FILE" \
    "$@"

echo "End: $(date -Iseconds)" | tee -a "$LOG_FILE"
```

---

## `watch_physics.sh` — Physics Anchor Watchdog

```bash
#!/usr/bin/env bash
# Continuously run physics validation tests.
# Fails (exits non-zero) if energy drift exceeds 0.1%.
# Use with cron or systemd timer for CI-like gatekeeping.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$PROJECT_ROOT/logs/physics_watchdog_$(date +%Y%m%d).log"

mkdir -p "$(dirname "$LOG_FILE")"

cd "$PROJECT_ROOT"

# Run only physics-marked tests with verbose output
python3 -m pytest tests/physics/ -v --tb=short 2>&1 | tee -a "$LOG_FILE"

# Extract pass/fail summary
if [ "${PIPESTATUS[0]}" -eq 0 ]; then
    echo "[$(date -Iseconds)] ✓ Physics anchor holding" >> "$LOG_FILE"
    exit 0
else
    echo "[$(date -Iseconds)] ✗ PHYSICAL ANCHOR BROKEN — energy drift exceeds threshold!" \
        | tee -a "$LOG_FILE"
    exit 1
fi
```

---

## `monitor_sympnet_health.py` — Live Health Dashboard

```python
#!/usr/bin/env python3
"""Poll SympNet engine health and emit metrics/alert on drift."""

import time
import json
from pathlib import Path
from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine

METRICS_FILE = Path("logs/sympnet_health.jsonl")
ALERT_THRESHOLD = 0.001  # 0.1%

def main():
    engine = SympNetEngine()
    q, p = 1.0, 0.5
    dt = 0.01

    METRICS_FILE.parent.mkdir(exist_ok=True)

    while True:
        # Run a batch of steps
        for _ in range(100):
            q, p = engine.step(q, p, dt)

        health = engine.get_health()
        record = {
            "timestamp": time.time(),
            "status": health["status"],
            "avg_drift": health["avg_drift"],
            "damping": health["damping"],
            "total_energy": health["total_energy"],
        }

        with METRICS_FILE.open("a") as f:
            f.write(json.dumps(record) + "\n")

        if health["avg_drift"] > ALERT_THRESHOLD:
            print(f"⚠️  ALERT: drift={health['avg_drift']:.6%} exceeds {ALERT_THRESHOLD:.6%}")

        time.sleep(1.0)

if __name__ == "__main__":
    main()
```

---

## `cron.example` — Scheduled Tasks

```cron
# ── Cosmic Mycelium — Continuous Process Schedule ────────────────────────────
# m h  dom mon dow   command

# Run physics anchor validation every hour
0 * * * * /home/lg/L00/cosmic_mycelium/cosmic_mycelium/scripts/watch_physics.sh >> /dev/null 2>&1

# Rotate logs daily (midnight)
0 0 * * * find /home/lg/L00/cosmic_mycelium/logs/ -name "*.log" -mtime +7 -delete

# Optional: run full test suite daily at 03:00
0 3 * * * cd /home/lg/L00/cosmic_mycelium && python3 -m pytest tests/ -q --tb=line
```

Install with: `crontab cron.example` (after reviewing paths).

---

## systemd Unit Example (Optional)

`~/.config/systemd/user/cosmic-infant.service`:
```ini
[Unit]
Description=Cosmic Mycelium Infant Continuous Process
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/lg/L00/cosmic_mycelium
ExecStart=/home/lg/L00/cosmic_mycelium/cosmic_mycelium/scripts/run_infant_continuous.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

Enable: `systemctl --user enable --now cosmic-infant.service`

---

## Notes

- All scripts log to `logs/` (auto-created).
- The physics watchdog is the **gatekeeper**: if energy drift exceeds 0.1%,
  the script exits non-zero — hook this into alerting (email, Slack, etc.).
- Health metrics are written as JSONL for easy ingestion by Grafana/Prometheus.
