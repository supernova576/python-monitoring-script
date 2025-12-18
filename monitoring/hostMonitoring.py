from utils.log import log
from utils.db import db as DB
from alerting.mailgunConnector import mailgunConnector

import json
import os
from pathlib import Path
from sys import exit as adieu
import traceback
from datetime import datetime


class hostMonitoring:
    def __init__(self) -> None:
        try:
            # -- Get config-parameters --
            path = Path(__file__).resolve().parent.parent / "conf.json"

            with open(f"{path}", "r") as f:
                j = json.loads(f.read())

                self.is_active: bool = j["hostMonitoring"]["is_active"]

                # alerting config
                try:
                    self.alerting_is_active: bool = j["alerting"]["rules"]["hostMonitoring"]["is_active"]
                    self.alerting_thresholds: dict = j["alerting"]["rules"]["hostMonitoring"].get("thresholds", {})
                    self.hostname: str = j["general"]["hostname"]
                except Exception:
                    self.alerting_is_active = False
                    self.alerting_thresholds = {}
                    self.hostname = "N/A"

                impl = j.get("alerting", {}).get("implementation", {})
                self.mailgun_alerting_is_active = bool(impl.get("mailgun", {}).get("is_active", False))
                self.smtp_alerting_is_active = bool(impl.get("smtp", {}).get("is_active", False))

                self.logger = log()

                # instantiate DB handler (DB may be configured as inactive and will then be a no-op)
                try:
                    self.db_conn = DB()
                except Exception:
                    # if DB cannot be initialized do not exit; keep monitoring functional
                    self.logger.warning("hostMonitoring: Could not initialize DB handler; continuing without DB ingestion.")
                    self.db_conn = None

                # placeholders for measured values
                self.measured = {
                    "free_ram_mb": None,
                    "load_avg": [None, None, None],
                    "swap_used_mb": None,
                    "disk_free": None
                }

            # -------------------------------------------------------

            self.logger.info("hostMonitoring: Initialized successfully.")
        except Exception:
            self.logger.error("hostMonitoring/__init__: {0}".format(traceback.format_exc()))
            adieu(1)
    
    def __check_if_module_is_active(self) -> None:
        try:
            if self.is_active == False:
                self.logger.info("hostMonitoring: Module is deactivated in conf.json. Exiting hostMonitoring.")
                adieu(0)
            
            self.logger.info("hostMonitoring: Module is active. Continuing hostMonitoring.")
            
        except Exception as e:
            self.logger.error("hostMonitoring/__check_if_module_is_active: {0}".format(traceback.format_exc()))
            adieu(1)

    def __free_ram_check(self) -> None:
        try:
            # -- Check free RAM --
            self.logger.info("hostMonitoring: Checking free RAM...")
            free_ram = os.popen("free -m | grep Mem | awk '{print $7}'").read().strip()
            self.logger.info(f"hostMonitoring: Free RAM: {free_ram} MB")

            try:
                self.measured["free_ram_mb"] = int(free_ram)
            except Exception:
                self.measured["free_ram_mb"] = None

            if self.db_conn:
                self.db_conn.save_host_check("free_ram_mb", free_ram)
            # --------------------------------------------------------------------------------
        except Exception as e:
            self.logger.error("hostMonitoring/__free_ram_check: {0}".format(traceback.format_exc()))
            adieu(1)

    def __load_avg_check(self) -> None:
        try:
            # -- Check load average --
            self.logger.info("hostMonitoring: Checking load average...")
            load_avg = os.popen("cat /proc/loadavg | awk '{print $1,$2,$3}'").read().strip()
            self.logger.info(f"hostMonitoring: Load Average (1, 5, 15 min): {load_avg}")

            parts = load_avg.split()
            try:
                vals = [float(p) for p in parts[:3]]
            except Exception:
                vals = [None, None, None]
            self.measured["load_avg"] = vals

            if self.db_conn:
                self.db_conn.save_host_check("load_average", load_avg)
            # --------------------------------------------------------------------------------
        except Exception as e:
            self.logger.error("hostMonitoring/__load_avg_check: {0}".format(traceback.format_exc()))
            adieu(1)

    def __swap_check(self) -> None:
        try:
            # -- Check swap usage --
            self.logger.info("hostMonitoring: Checking swap usage...")
            swap_used = os.popen("free -m | grep Swap | awk '{print $3}'").read().strip()
            self.logger.info(f"hostMonitoring: Swap Used: {swap_used} MB")

            try:
                self.measured["swap_used_mb"] = int(swap_used)
            except Exception:
                self.measured["swap_used_mb"] = None

            if self.db_conn:
                self.db_conn.save_host_check("swap_used_mb", swap_used)
            # --------------------------------------------------------------------------------
        except Exception as e:
            self.logger.error("hostMonitoring/__swap_check: {0}".format(traceback.format_exc()))
            adieu(1)
    
    def __disk_free_check(self) -> None:
        try:
            # -- Check disk free space --
            self.logger.info("hostMonitoring: Checking disk free space...")
            disk_free = os.popen("df -h / | tail -1 | awk '{print $4}'").read().strip()
            self.logger.info(f"hostMonitoring: Disk Free Space: {disk_free}")

            self.measured["disk_free"] = disk_free

            if self.db_conn:
                self.db_conn.save_host_check("disk_free", disk_free)
            # --------------------------------------------------------------------------------
        except Exception as e:
            self.logger.error("hostMonitoring/__disk_free_check: {0}".format(traceback.format_exc()))
            adieu(1)

    def check_host_params(self) -> None:
        try:
            self.logger.info("hostMonitoring: Starting service checks...")
            
            # -- Checks all basic services --
            self.__check_if_module_is_active()
            self.__disk_free_check()
            self.__free_ram_check()
            self.__load_avg_check()
            self.__swap_check()

            # -- Evaluate thresholds and alert if needed --
            try:
                violations = []
                th = self.alerting_thresholds or {}

                # load averages
                lvals = self.measured.get("load_avg", [None, None, None])
                for idx, key in enumerate(["load_average_1", "load_average_5", "load_average_15"]):
                    thresh = th.get(key)
                    val = lvals[idx] if lvals and len(lvals) > idx else None
                    if thresh is not None and val is not None:
                        try:
                            if float(val) > float(thresh):
                                violations.append({"metric": key, "value": val, "threshold": thresh})
                        except Exception:
                            pass

                # free RAM (alert if below threshold)
                free_ram = self.measured.get("free_ram_mb")
                if th.get("free_ram_mb") is not None and free_ram is not None:
                    try:
                        if int(free_ram) < int(th.get("free_ram_mb")):
                            violations.append({"metric": "free_ram_mb", "value": free_ram, "threshold": th.get("free_ram_mb")})
                    except Exception:
                        pass

                # swap used (alert if above threshold)
                swap_used = self.measured.get("swap_used_mb")
                if th.get("swap_used") is not None and swap_used is not None:
                    try:
                        if int(swap_used) > int(th.get("swap_used")):
                            violations.append({"metric": "swap_used_mb", "value": swap_used, "threshold": th.get("swap_used")})
                    except Exception:
                        pass

                if violations and self.alerting_is_active:
                    try:
                        ctx = {
                            "report_title": "Host-Monitoring Warnung",
                            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "violations": violations,
                            "footer_note": "Automatische Warnung: Host-Schwellenwerte überschritten."
                        }

                        # mailgun
                        if getattr(self, "mailgun_alerting_is_active", False):
                            try:
                                mg = mailgunConnector()
                                mg.mailgunSendMailHTML(f"Host {self.hostname}: Schwellenwerte überschritten", "hostMonitoring", ctx)
                            except Exception:
                                self.logger.warning(f"hostMonitoring: mailgun send failed: {traceback.format_exc()}")

                        # smtp
                        if getattr(self, "smtp_alerting_is_active", False):
                            try:
                                from alerting.smtpConnector import smtpConnector
                                smtp = smtpConnector()
                                smtp.smtpSendMailHTML(f"Host {self.hostname}: Schwellenwerte überschritten", "hostMonitoring", ctx)
                            except Exception:
                                self.logger.warning(f"hostMonitoring: smtp send failed: {traceback.format_exc()}")
                    except Exception:
                        self.logger.warning(f"hostMonitoring: Failed to send alert: {traceback.format_exc()}")

            except Exception:
                self.logger.warning(f"hostMonitoring: Error evaluating thresholds: {traceback.format_exc()}")

            self.logger.info("hostMonitoring: Service checks completed.")
        except Exception as e:
            self.logger.error("hostMonitoring/check_services: {0}".format(traceback.format_exc()))
            adieu(1)

    def delete_host_results(self) -> None:
        try:
            self.db_conn.delete_db_data("host_checks")
            self.logger.info("hostMonitoring: Host result files deleted successfully.")
        except Exception as e:
            self.logger.error(f"hostMonitoring/delete_host_results: An error occurred while deleting host result files: {e}")
            adieu(1)