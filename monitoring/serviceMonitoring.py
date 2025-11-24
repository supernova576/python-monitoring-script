from utils.log import log
from utils.db import db as DB

import json
import os
from pathlib import Path
from sys import exit as adieu
import traceback
import socket

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
                self.dns_list: list = j["serviceMonitoring"]["domain_list"]

                self.check_dns: bool = j["serviceMonitoring"]["check_dns"]
                self.check_internet_connectivity: bool = j["serviceMonitoring"]["check_internet_connectivity"]

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
    
    def __check_dns(self) -> None:
        try:
            if self.check_dns:
                self.logger.info("Performing DNS Check")
                _dns_handler = 0
                for dns_lookup in self.dns_list:
                    try:
                        ip = socket.gethostbyname(dns_lookup)
                        
                        self.logger.info(f"Host {dns_lookup} resolved to {ip}")
                    except socket.gaierror:
                        self.logger.warning(f"Host {dns_lookup} did not resolve!!")
                        _dns_handler += 1
                    
                if _dns_handler > 0:
                    self.db_conn.save_service_check("dns", "inactive")
                else:
                    self.db_conn.save_service_check("dns", "active")
            else:
                self.logger.warning("Skipped DNS Check... Not enabled in conf.json")
        except Exception:
            self.logger.warning(f"serviceMonitoring: Error in __check_dns: {traceback.format_exc()}")
            adieu(1)

    def __check_internet_connectivity(self) -> None:
        try:
            if self.check_internet_connectivity:
                self.logger.info("Performing Internet Connectivity check...")

                conn = socket.create_connection(("8.8.8.8", 53), 3)
                conn.close()

                self.db_conn.save_service_check("internet", "active")
            else:
                self.logger.warning("Skipped Internet Connectivity check... Not enabled in conf.json")
        except Exception:
            self.logger.warning("serviceMonitoring: Could not reach 8.8.8.8 on Port 53")
            self.db_conn.save_service_check("internet", "inactive")

    def check_services(self) -> None:
        try:
            self.logger.info("serviceMonitoring: Starting service checks...")
            
            # -- Checks all basic services --
            self.__check_if_module_is_active()
            self.__check_service_statuses()
            self.__check_dns()
            self.__check_internet_connectivity()

            self.logger.info("serviceMonitoring: Service checks completed.")
        except Exception as e:
            self.logger.error("serviceMonitoring/check_services: {0}".format(traceback.format_exc()))
            adieu(1)
    
    def delete_service_results(self) -> None:
        try:
            # Assuming service results are stored in a specific file, e.g., "service_results.json"
            self.db_conn.delete_db_data("service_checks")
            self.logger.info("serviceMonitoring: Service result files deleted successfully.")
        except Exception as e:
            self.logger.error(f"serviceMonitoring/delete_service_results: An error occurred while deleting service result files: {e}")
            adieu(1)