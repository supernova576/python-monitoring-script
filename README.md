# Python Monitoring Script

Lightweight Python scripts for simple monitoring tasks: file changes, host availability, and service checks, with local reporting and utilities.

## What it does
- Monitors files for changes and tracks changes over time.
- Performs basic host and service monitoring (ping/port checks or custom checks implemented in `monitoring/`).
- Stores monitoring data in a small local JSON/DB and can generate simple reports via `utils/report_generator.py`.

## Project layout
- `monitor.py` — main entrypoint to run monitoring tasks.
- `conf.json` — configuration file used by the scripts (edit to customize what to monitor).
- `monitoring/` — implementations:
	- `fileMonitoring.py` — file watchers and checksum-based change detection.
	- `hostMonitoring.py` — host checks (load avg, free ram, ...).
	- `serviceMonitoring.py` — service checks.
- `utils/` — helpers for storage, logging and report generation (`db.py`, `log.py`, `report_generator.py`).

## Requirements
- Python 3.8+ 
- pandas
- matplotlib
- tabulate

## Quick start
1. Inspect and edit `conf.json` to configure monitored paths, hosts, and services.
2. Run the monitor from the project root:

```bash
python3 monitor.py
```

3. Check generated logs and reports in the project or via `utils/report_generator.py`.

## Configuration
Edit `conf.json` to specify the targets to monitor. The project uses a small local data store (see `utils/db.py`) to persist state between runs.

## Development
- Add or modify monitors in `monitoring/` and update `monitor.py` to include new tasks.

## License & Contributing
This is a small private project — modify freely for personal or internal use. If you want help adding features, open an issue or submit a patch.
