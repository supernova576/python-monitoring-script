from utils.log import log
from utils.db import db as DB

import json
import os
from pathlib import Path
from sys import exit as adieu
import traceback

class serviceMonitoring:
    def __init__(self) -> None:
        try:
            # -- Get config-parameters --
            path = Path(__file__).resolve().parent.parent / "conf.json"

            with open(f"{path}", "r") as f:
                j = json.loads(f.read())

                self.is_active: bool = j["serviceMonitoring"]["is_active"]
                self.hostname: str = j["serviceMonitoring"]["hostname"]
                self.apt_service_list: list = j["serviceMonitoring"]["service_list"]

                self.logger = log()

                # instantiate DB handler (DB may be configured as inactive and will then be a no-op)
                try:
                    self.db_conn = DB()
                except Exception:
                    # if DB cannot be initialized do not exit; keep monitoring functional
                    self.logger.warning("serviceMonitoring: Could not initialize DB handler; continuing without DB ingestion.")
                    self.db_conn = None

            # -------------------------------------------------------

            self.logger.info("serviceMonitoring: Initialized successfully.")
        except Exception:
            self.logger.error("serviceMonitoring/__init__: {0}".format(traceback.format_exc()))
            adieu(1)
    
    def __check_if_module_is_active(self) -> None:
        try:
            if self.is_active == False:
                self.logger.info("serviceMonitoring: Module is deactivated in conf.json. Exiting serviceMonitoring.")
                adieu(0)
            
            self.logger.info("serviceMonitoring: Module is active. Continuing serviceMonitoring.")
            
        except Exception as e:
            self.logger.error("serviceMonitoring/__check_if_module_is_active: {0}".format(traceback.format_exc()))
            adieu(1)

    def __check_service_statuses(self) -> None:
        try:
            # -- Iterate from service list --
            for service in self.apt_service_list:
                self.logger.info(f"serviceMonitoring: Checking service: {service}")

                # -- Check with systemctl quiet command, if service is active. If so, returns 0 --
                if int(os.system("systemctl is-active --quiet {0}".format(service))) == 0:
                    self.logger.info(f"serviceMonitoring: Service {service} is active.")
                    self.db_conn.save_service_check(service, "active")
                else:
                    self.logger.warning(f"serviceMonitoring: Service {service} is NOT active")
                    self.db_conn.save_service_check(service, "inactive")
                # --------------------------------------------------------------------------------
        except Exception as e:
            self.logger.error("serviceMonitoring/__check_service_statuses: {0}".format(traceback.format_exc()))
            adieu(1)

    def check_services(self) -> None:
        try:
            self.logger.info("serviceMonitoring: Starting service checks...")
            
            # -- Checks all basic services --
            self.__check_if_module_is_active()
            self.__check_service_statuses()

            self.logger.info("serviceMonitoring: Service checks completed.")
        except Exception as e:
            self.logger.error("serviceMonitoring/check_services: {0}".format(traceback.format_exc()))
            adieu(1)