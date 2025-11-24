from utils.log import log
from utils.db import db as DB

import json
import os
from pathlib import Path
from sys import exit as adieu
import traceback

class hostMonitoring:
    def __init__(self) -> None:
        try:
            # -- Get config-parameters --
            path = Path(__file__).resolve().parent.parent / "conf.json"

            with open(f"{path}", "r") as f:
                j = json.loads(f.read())

                self.is_active: bool = j["hostMonitoring"]["is_active"]

                self.logger = log()

                # instantiate DB handler (DB may be configured as inactive and will then be a no-op)
                try:
                    self.db_conn = DB()
                except Exception:
                    # if DB cannot be initialized do not exit; keep monitoring functional
                    self.logger.warning("hostMonitoring: Could not initialize DB handler; continuing without DB ingestion.")
                    self.db_conn = None

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

            self.logger.info("hostMonitoring: Service checks completed.")
        except Exception as e:
            self.logger.error("hostMonitoring/check_services: {0}".format(traceback.format_exc()))
            adieu(1)