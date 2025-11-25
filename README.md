# Python Monitoring Script
![CI](https://github.com/supernova576/python-monitoring-script/actions/workflows/pytest.yml/badge.svg)

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

Additional packages required for alerting and templating:
- `jinja2` (for HTML templates)
- `requests` (for Mailgun API calls)

## Quick start
1. Inspect and edit `conf.json` to configure monitored paths, hosts, and services.
2. Run the monitor from the project root:

```bash
python3 monitor.py
```

3. Check generated logs and reports in the project or via `utils/report_generator.py`.

## Configuration
Edit `conf.example.json` to specify the targets to monitor. The project uses a small local data store (see `utils/db.py`) to persist state between runs.
Then rename `conf.example.json` to `conf.json` and run the script.

**Alerting**

This project now supports HTML alerting via two implementations which can run in parallel:

- **Mailgun** (`alerting.mailgunConnector`) — posts to the Mailgun HTTP API.
- **SMTP** (`alerting.smtpConnector`) — sends HTML emails via SMTP/SMTPS with optional STARTTLS.

Both implementations use Jinja2 templates located in the `alerting/html_templates/` folder. For the monitoring modules there are matching templates:

- `serviceMonitoring.html` — used for service alerts
- `hostMonitoring.html` — used for host threshold alerts
- `fileMonitoring.html` — used for file-change alerts

Which implementations are active is controlled in `conf.json` under `alerting.implementation`. Example configuration (Mailgun + SMTP schema):

```json
"alerting": {
	"rules": {
		"serviceMonitoring": { "is_active": true },
		"hostMonitoring": { "is_active": true, "thresholds": { "load_average_1": 2, "free_ram_mb": 1000 } },
		"fileMonitoring": { "is_active": true }
	},
	"implementation": {
		"mailgun": {
			"is_active": true,
			"webroot": "https://api.mailgun.net/v3/YOUR_DOMAIN/messages",
			"api_key": "key-...",
			"recipient": "ops@example.com",
			"sender": "Monitoring <monitor@yourhost.local>"
		},
		"smtp": {
			"is_active": false,
			"host": "smtp.example.com",
			"port": 587,
			"username": "user@example.com",
			"password": "secret",
			"use_tls": true,
			"use_ssl": false,
			"recipient": "ops@example.com",
			"sender": "Monitoring <monitor@yourhost.local>"
		}
	}
}
```

Notes:
- Each monitoring module reads the per-module rule in `alerting.rules` to decide whether to evaluate alerts at all (e.g. `alerting.rules.serviceMonitoring.is_active`).
- If a rule is active, alerts are sent to all implementations that are enabled under `alerting.implementation` (both Mailgun and SMTP can be active simultaneously).

Template context (overview): when an alert is sent, the monitoring modules pass a small context dict to the template. Example keys by module:

- `serviceMonitoring`: `report_title`, `generated_at`, `inactive_services` (list of {name, host, last_state}), `footer_note`
- `hostMonitoring`: `report_title`, `generated_at`, `violations` (list of {metric, value, threshold}), `footer_note`
- `fileMonitoring`: `report_title`, `generated_at`, `changed_files` (list of {path, hash}), `footer_note`

The connectors render the matching template and then send it via Mailgun API and/or SMTP depending on which implementations are active.

## Development
- Add or modify monitors in `monitoring/` and update `monitor.py` to include new tasks.

**Test Results**

- **CI Badge:** shows the status of the `pytest` workflow. The pipeline uploads a JUnit XML test report artifact named `test-report` on every run.
- **View latest report:** open the Actions run for the `CI — Pytest` workflow in GitHub to download the `test-report` artifact (JUnit XML) and inspect detailed results.

If you prefer, I can add a workflow step to automatically summarize the latest test results and commit a small summary into this `README.md` (requires `GITHUB_TOKEN` to commit). Ask me to enable that and I'll add it.

If you change or add templates, place them into `alerting/html_templates/` and ensure they follow Jinja2 HTML conventions.

If you'd like, I can also centralize alert sending into a single `AlertDispatcher` utility that will manage connectors and make the monitoring modules simpler (currently each module sends to configured connectors directly). Just tell me if you want that refactor.

## License & Contributing
This is a small private project — modify freely for personal or internal use. If you want help adding features, open an issue or submit a patch.
