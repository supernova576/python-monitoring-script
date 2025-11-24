from utils.log import log
from utils.db import db as DB

import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from sys import exit as adieu
import json
import traceback

class reportGenerator:
    def __init__(self) -> None:
        try:
            # -- Get config-parameters --
            path = Path(__file__).resolve().parent.parent / "conf.json"

            with open(f"{path}", "r") as f:
                j = json.loads(f.read())

                self.is_active: bool = j["reportGenerator"]["is_active"]
                self.path_to_reports: str = j["reportGenerator"]["root_path"]
                # optional: number of days to show in time-range-limited plots
                self.plot_days: int = int(j["reportGenerator"].get("plot_days", 7))

            self.logger = log()

            # instantiate DB handler (DB may be configured as inactive and will then be a no-op)
            try:
                self.db_conn = DB()
            except Exception:
                # if DB cannot be initialized do not exit; keep monitoring functional
                self.logger.warning("reportGenerator: Could not initialize DB handler; continuing without DB ingestion.")
                self.db_conn = None

            # prepare output directories (dated parent folder + markdown/ and plots/)
            try:
                self.__prepare_output_dirs()
            except Exception:
                # if directory creation fails, continue but use configured path as fallback
                self.logger.warning("reportGenerator: Could not create dated report directories; using configured path as fallback.")
                print(traceback.format_exc())

            # -------------------------------------------------------

            self.logger.info("reportGenerator: Initialized successfully.")
        except Exception:
            self.logger.error("reportGenerator/__init__: {0}".format(traceback.format_exc()))
            adieu(1)

    def __prepare_output_dirs(self):

        base = Path(self.path_to_reports)
        # ensure base exists
        base.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y_%m_%d")
        folder_name = f"report_{date_str}"
        candidate = base / folder_name
        idx = 1
        while candidate.exists():
            candidate = base / f"{folder_name}_{idx}"
            idx += 1

        candidate.mkdir(parents=True, exist_ok=False)
        self.report_root = candidate
        self.markdown_dir = self.report_root 
        self.plots_dir = self.report_root / "plots"
        self.plots_dir.mkdir()
        self.logger.info(f"reportGenerator: Created report dirs at {self.report_root}")
    
    def __check_if_module_is_active(self) -> None:
        try:
            if self.is_active == False:
                self.logger.info("reportGenerator: Module is deactivated in conf.json. Exiting reportGenerator.")
                adieu(0)
            
            self.logger.info("reportGenerator: Module is active. Continuing reportGenerator.")
            
        except Exception as e:
            self.logger.error("reportGenerator/__check_if_module_is_active: {0}".format(traceback.format_exc()))
            adieu(1)

    def __ensure_datetime_series(self, df, ts_col="timestamp"):
        if ts_col not in df.columns:
            df["ts"] = pd.NaT
            return df
        df["ts"] = pd.to_datetime(df[ts_col], errors="coerce", utc=False)
        return df

    def __safe_is_true(self, val):
        """Tolerante Prüfung, ob ein Text/Value 'true' ist."""
        if val is None:
            return False
        # Handle booleans directly
        if isinstance(val, bool):
            return val

        # Handle numeric types (non-zero => True)
        if isinstance(val, (int, float)):
            try:
                return float(val) != 0.0
            except Exception:
                pass

        s = str(val).strip().lower()
        true_vals = {"1", "true", "t", "yes", "y", "active", "up", "on"}
        false_vals = {"0", "false", "f", "no", "n", "inactive", "down", "off"}

        if s in true_vals:
            return True
        if s in false_vals:
            return False

        # Fallback: try numeric conversion
        try:
            return float(s) != 0.0
        except Exception:
            return False

    def __save_plot(self, fig, fname):
        # Prefer plots_dir if available, otherwise fallback to configured path
        try:
            out_path = Path(self.plots_dir) / fname
        except Exception:
            out_path = Path(self.path_to_reports) / fname
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(out_path), bbox_inches="tight")
        plt.close(fig)
        return str(out_path)

    def __plot_time_series(self, df, x_col, y_col, title, xlabel="time", ylabel="", out_fname=None, date_format=True, last_n_days: int = None, label: str = None):
        """Allgemeine Zeitreihen-Plot-Funktion (Option B styling)."""
        fig, ax = plt.subplots(figsize=(10, 4.5))
        # Linie + Marker: always draw markers so single-point series are visible
        if label:
            ax.plot(df[x_col], df[y_col], linewidth=1.2, marker='o', markersize=4, label=label)
            ax.legend()
        else:
            ax.plot(df[x_col], df[y_col], linewidth=1.2, marker='o', markersize=4)
        ax.set_title(title, fontsize=12, fontweight="semibold")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.8)
        # Datumformatierung
        if date_format:
            try:
                import matplotlib.dates as mdates
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(mdates.AutoDateLocator()))
            except Exception:
                pass
        # Optionally limit x-axis to the last N days (if requested)
        if last_n_days is not None:
            try:
                xs = pd.to_datetime(df[x_col], errors='coerce')
                max_x = xs.max()
                if pd.notna(max_x):
                    min_x = max_x - timedelta(days=int(last_n_days))
                    ax.set_xlim(min_x, max_x)
            except Exception:
                pass

        fig.tight_layout()
        if out_fname:
            return self.__save_plot(fig, out_fname)
        else:
            plt.show()
            plt.close(fig)
            return None

    def __create_file_checks_plots(self, df_file_checks: pd.DataFrame):
        if df_file_checks.empty:
            return None
        
        df = df_file_checks.copy()
        df = self.__ensure_datetime_series(df, "timestamp")
        df["changed_flag"] = df["changed"].apply(self.__safe_is_true)
        df["date"] = df["ts"].dt.date

        daily = df.groupby("date", dropna=True)["changed_flag"].sum().reset_index()
        daily = daily.sort_values("date")

        if daily.empty:
            return None
        # Plot
        out = self.__plot_time_series(
            df=daily,
            x_col="date",
            y_col="changed_flag",
            title="File changes per day",
            xlabel="Date",
            ylabel="Number of changed files",
            out_fname="file_changes_timeline.png",
            date_format=False,
            last_n_days=self.plot_days,
            label="changed files"
        )
        return out

    def __create_service_checks_plots(self, df_service_checks):
        results = {}
        if df_service_checks.empty:
            return results
        df = df_service_checks.copy()
        df = self.__ensure_datetime_series(df, "timestamp")

        # normalize is_active
        df["is_active_flag"] = df["is_active"].apply(self.__safe_is_true)

        # Uptime per service (in %)
        service_group = df.groupby("service_name", dropna=False)
        uptime = service_group["is_active_flag"].agg(['sum', 'count']).reset_index()
        uptime["uptime_pct"] = (uptime["sum"] / uptime["count"]) * 100
        uptime = uptime.sort_values("uptime_pct", ascending=False)

        # Bar plot for uptime
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.bar(uptime["service_name"].astype(str), uptime["uptime_pct"], linewidth=0.5)
        ax.set_title("Service uptime (%) per service")
        ax.set_xlabel("Service")
        ax.set_ylabel("Uptime (%)")
        ax.set_ylim(0, 100)
        ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.8)
        plt.xticks(rotation=45, ha="right")
        fig.tight_layout()
        results["service_uptime_png"] = self.__save_plot(fig, "service_uptime.png")
        # add legend indicating the measured metric
        try:
            ax.legend(["uptime_pct"])
        except Exception:
            pass

        # Down-events per day (count of is_active == False)
        df["date"] = df["ts"].dt.date
        df["down_flag"] = ~df["is_active_flag"]
        down_daily = df.groupby("date", dropna=True)["down_flag"].sum().reset_index().sort_values("date")
        if not down_daily.empty:
            out = self.__plot_time_series(
                df=down_daily,
                x_col="date",
                y_col="down_flag",
                title="Down events per day",
                xlabel="Date",
                ylabel="Number of down events",
                out_fname="service_down_events.png",
                date_format=False,
                last_n_days=self.plot_days,
                label="down events"
            )
            results["service_down_events_png"] = out
        else:
            results["service_down_events_png"] = None

        # also return the uptime table for inclusion in markdown
        results["uptime_table"] = uptime[["service_name", "count", "sum", "uptime_pct"]].rename(
            columns={"count": "checks", "sum": "active_checks"}
        )
        return results

    # observed_value to numeric - handle common non-numeric formats
    def __parse_observed(self, val: str, metric_name: str):
        if val is None:
            return None
        s = str(val).strip()
        # load_average like '1.08 1.14 1.12' -> take first value
        if metric_name == "load_average":
            parts = s.split()
            try:
                return float(parts[0])
            except Exception:
                return None
        # disk_free like '195G' or '200M' -> convert to GB
        if metric_name == "disk_free":
            import re
            m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([KMGTkmgt]?)$", s)
            if not m:
                return None
            num = float(m.group(1))
            unit = m.group(2).upper()
            if unit == "T":
                return num * 1024.0
            if unit == "G" or unit == "":
                return num
            if unit == "M":
                return num / 1024.0
            if unit == "K":
                return num / (1024.0 * 1024.0)
            return None
        # default: try numeric conversion
        try:
            return float(s)
        except Exception:
            return None

    def __create_host_metric_plot(self, df_host_checks, metric_name, png_name, ylabel=None):
        if df_host_checks.empty:
            return None
        df = df_host_checks.copy()
        df = df[df["name"] == metric_name]
        if df.empty:
            return None
        df = self.__ensure_datetime_series(df, "timestamp")
        # Special handling for load_average: it's three values (1,5,15 min)
        if metric_name == "load_average":
            # parse observed_value like '1.08 1.14 1.12' into three numeric columns
            def parse_load(s):
                if s is None:
                    return (None, None, None)
                parts = str(s).strip().split()
                vals = []
                for i in range(3):
                    try:
                        vals.append(float(parts[i]))
                    except Exception:
                        vals.append(None)
                return tuple(vals)

            parsed = df["observed_value"].apply(parse_load)
            df[["v1", "v2", "v3"]] = pd.DataFrame(parsed.tolist(), index=df.index)
            df = df.dropna(subset=["ts"]).sort_values("ts")
            if df.empty:
                return None

            fig, ax = plt.subplots(figsize=(10, 4.5))
            # plot three series with different colors and markers
            ax.plot(df["ts"], df["v1"], linewidth=1.2, marker="o", markersize=4, label="1min")
            ax.plot(df["ts"], df["v2"], linewidth=1.2, marker="s", markersize=4, label="5min")
            ax.plot(df["ts"], df["v3"], linewidth=1.2, marker="^", markersize=4, label="15min")
            ax.set_title(f"{metric_name} over time", fontsize=12, fontweight="semibold")
            ax.set_xlabel("Time")
            ax.set_ylabel(ylabel if ylabel else metric_name)
            ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.8)
            ax.legend()
            try:
                import matplotlib.dates as mdates
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(mdates.AutoDateLocator()))
            except Exception:
                pass

            # apply last_n_days range if available
            try:
                max_x = df["ts"].max()
                if pd.notna(max_x):
                    min_x = max_x - timedelta(days=int(self.plot_days))
                    ax.set_xlim(min_x, max_x)
            except Exception:
                pass

            fig.tight_layout()
            return self.__save_plot(fig, png_name)

        # default numeric handling for single-value metrics
        df["val_num"] = df["observed_value"].apply(lambda v: self.__parse_observed(v, metric_name=metric_name))
        df = df.dropna(subset=["ts", "val_num"]).sort_values("ts")
        if df.empty:
            return None
        return self.__plot_time_series(
            df=df,
            x_col="ts",
            y_col="val_num",
            title=f"{metric_name} over time",
            xlabel="Time",
            ylabel=ylabel if ylabel else metric_name,
            out_fname=png_name,
            date_format=True,
            last_n_days=self.plot_days,
            label=(ylabel if ylabel else metric_name)
        )

    def __build_markdown_report(self, tables_preview, image_paths, uptime_table=None, out_md: str = ""):
        lines = []
        lines.append("# Monitoring Report\n")
        lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n")
        lines.append("---\n")

        # Tabelle Previews
        for table_name, df in tables_preview.items():
            lines.append(f"## Table: {table_name}\n")
            lines.append(f"**Total rows:** {len(df)}\n\n")
            if not df.empty:
                lines.append(df.head(20).to_markdown(index=False))
            else:
                lines.append("_No data available_")
            lines.append("\n---\n")

        # File checks chart
        md_dir = os.path.dirname(out_md) if out_md else None
        if image_paths.get("file_changes_timeline"):
            rel = os.path.relpath(image_paths['file_changes_timeline'], start=md_dir) if md_dir else os.path.basename(image_paths['file_changes_timeline'])
            lines.append("## File checks - Changes timeline\n")
            lines.append(f"![File changes timeline]({rel})\n")
            lines.append("\n---\n")

        # Service checks
        lines.append("## Service checks\n")
        if uptime_table is not None and not uptime_table.empty:
            lines.append("### Uptime per service\n")
            lines.append(uptime_table.to_markdown(index=False))
            lines.append("\n")
        if image_paths.get("service_uptime"):
            rel = os.path.relpath(image_paths['service_uptime'], start=md_dir) if md_dir else os.path.basename(image_paths['service_uptime'])
            lines.append(f"![Service uptime]({rel})\n")
        if image_paths.get("service_down_events"):
            rel = os.path.relpath(image_paths['service_down_events'], start=md_dir) if md_dir else os.path.basename(image_paths['service_down_events'])
            lines.append("### Down events per day\n")
            lines.append(f"![Down events per day]({rel})\n")
        lines.append("\n---\n")

        # Host checks
        lines.append("## Host checks (metrics)\n")
        if image_paths.get("cpu_load"):
            rel = os.path.relpath(image_paths['cpu_load'], start=md_dir) if md_dir else os.path.basename(image_paths['cpu_load'])
            lines.append("### CPU - load_average\n")
            lines.append(f"![CPU load]({rel})\n")
        if image_paths.get("ram_free"):
            rel = os.path.relpath(image_paths['ram_free'], start=md_dir) if md_dir else os.path.basename(image_paths['ram_free'])
            lines.append("### RAM - free_ram_mb\n")
            lines.append(f"![RAM free]({rel})\n")
        if image_paths.get("disk_free"):
            rel = os.path.relpath(image_paths['disk_free'], start=md_dir) if md_dir else os.path.basename(image_paths['disk_free'])
            lines.append("### Disk - disk_free\n")
            lines.append(f"![Disk free]({rel})\n")
        lines.append("\n---\n")

        # Footer
        lines.append("_End of report_\n")

        md_text = "\n".join(lines)
        with open(out_md, "w", encoding="utf-8") as f:
            f.write(md_text)
        return out_md

    def generate_report(self) -> None:

        self.__check_if_module_is_active()

        # Load tables (full)
        df_file_checks = self.db_conn.load_table_for_report("file_checks") if self.db_conn else pd.DataFrame()
        df_service_checks = self.db_conn.load_table_for_report("service_checks") if self.db_conn else pd.DataFrame()
        df_host_checks = self.db_conn.load_table_for_report("host_checks") if self.db_conn else pd.DataFrame()
        
        # include all tables preview (limit to first 20 rows)
        tables_preview = {}
        for tname in ("file_checks", "service_checks", "host_checks"):
            df_tmp = self.db_conn.load_table_for_report(tname, 20) if self.db_conn else pd.DataFrame()
            tables_preview[tname] = df_tmp

        # Create plots
        image_paths = {}

        self.logger.info("Creating file_checks timeline plot...")
        image_paths["file_changes_timeline"] = self.__create_file_checks_plots(df_file_checks)

        self.logger.info("Creating service_checks plots (uptime + down events)...")
        svc_results = self.__create_service_checks_plots(df_service_checks)
        image_paths["service_uptime"] = svc_results.get("service_uptime_png")
        image_paths["service_down_events"] = svc_results.get("service_down_events_png")
        uptime_table = svc_results.get("uptime_table")

        self.logger.info("Creating host_checks plots (CPU, RAM, Disk)...")
        image_paths["cpu_load"] = self.__create_host_metric_plot(df_host_checks, "load_average", "cpu_load_average.png", ylabel="load average")
        image_paths["ram_free"] = self.__create_host_metric_plot(df_host_checks, "free_ram_mb", "free_ram_mb.png", ylabel="free RAM (MB)")
        image_paths["disk_free"] = self.__create_host_metric_plot(df_host_checks, "disk_free", "disk_free.png", ylabel="disk free (units)")
        # Build markdown
        self.logger.info("Building markdown report...")
        md_out = Path(self.markdown_dir) / "monitoring_report.md"
        md_path = self.__build_markdown_report(tables_preview, image_paths, uptime_table=uptime_table, out_md=str(md_out))
        self.logger.info(f"Markdown report written to: {md_path}")

        # Summary
        self.logger.info("Generated files:")
        for key, v in image_paths.items():
            if v:
                self.logger.info(f" - {key}: {v}")
        self.logger.info(f" - Markdown: {md_path}")
