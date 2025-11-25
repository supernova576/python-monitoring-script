from utils.log import log
from utils.db import db as DB
from alerting.mailgunConnector import mailgunConnector

import json
import os
import hashlib
from pathlib import Path
from sys import exit as adieu
import traceback
from datetime import datetime

class fileMonitoring:
    def __init__(self) -> None:
        try:
            # -- Get config-parameters --
            path = Path(__file__).resolve().parent.parent / "conf.json"

            with open(f"{path}", "r") as f:
                j = json.loads(f.read())

                self.is_active: bool = j["fileMonitoring"]["is_active"]
                self.db_path: str = j["fileMonitoring"]["db_path"]
                self.files_to_monitor: list = j["fileMonitoring"]["files_to_monitor"]

                self.logger = log()

                # instantiate DB handler (DB may be configured as inactive and will then be a no-op)
                try:
                    self.db_conn = DB()
                except Exception:
                    # if DB cannot be initialized do not exit; keep monitoring functional
                    self.logger.warning("fileMonitoring: Could not initialize DB handler; continuing without DB ingestion.")
                    self.db_conn = None

                # Alerting rule
                try:
                    self.alerting_is_active: bool = j["alerting"]["rules"]["fileMonitoring"]["is_active"]
                except Exception:
                    self.alerting_is_active = False

                impl = j.get("alerting", {}).get("implementation", {})
                self.mailgun_alerting_is_active = bool(impl.get("mailgun", {}).get("is_active", False))
                self.smtp_alerting_is_active = bool(impl.get("smtp", {}).get("is_active", False))

            # -------------------------------------------------------

            self.logger.info("fileMonitoring: Initialized successfully.")
        except Exception:
            self.logger.error("fileMonitoring/__init__: {0}".format(traceback.format_exc()))
            adieu(1)
    
    def __check_if_module_is_active(self) -> None:
        try:
            if self.is_active == False:
                self.logger.warning("fileMonitoring: Module is deactivated in conf.json. Exiting fileMonitoring.")
                adieu(0)
            
            self.logger.info("fileMonitoring: Module is active. Continuing fileMonitoring.")
            
        except Exception as e:
            self.logger.error("fileMonitoring/__check_if_module_is_active: {0}".format(traceback.format_exc()))
            adieu(1)

    def __generate_new_file_hashes(self) -> dict:
        try:
            # -- Generate hash database for files --
            self.logger.info("fileMonitoring: Generating file hash database...")

            file_hashes = {}
            _error_handler = 0
            for file in self.files_to_monitor:
                # handle per-file read errors (permission denied, missing file, etc.)
                try:
                    with open(file, "r") as f:
                        data = f.read()
                        md5 = hashlib.md5(data.encode("utf-8")).hexdigest()
                    file_hashes[file] = md5
                except PermissionError:
                    # do not abort the entire run for a single unreadable file
                    self.logger.warning(f"fileMonitoring: Permission denied reading '{file}'; skipping (hash=None)")
                    file_hashes[file] = None
                    _error_handler += 1
                    continue
                except FileNotFoundError:
                    self.logger.warning(f"fileMonitoring: File not found: '{file}'; skipping (hash=None)")
                    file_hashes[file] = None
                    _error_handler += 1
                    continue
                except Exception:
                    # other read/IO errors - log and continue
                    self.logger.warning(f"fileMonitoring: Could not read '{file}': {traceback.format_exc().splitlines()[-1]}; skipping (hash=None)")
                    file_hashes[file] = None
                    _error_handler += 1
                    continue
            self.logger.info("fileMonitoring: File hash database generated successfully.")

            if _error_handler > 0:
                self.logger.warning(f"fileMonitoring: Completed with {_error_handler} file read errors. Cannot create new hash db")
                raise Exception("File read errors encountered")
            
            return file_hashes
        
        except Exception as e:
            self.logger.error("fileMonitoring/__generate_file_hash_db: {0}".format(traceback.format_exc()))
            adieu(1)

    def __get_file_hashes_from_db(self) -> dict:
        try:
            # -- Read hash database from file --
            self.logger.info("fileMonitoring: Reading file hash database from file...")

            with open(self.db_path, "r") as f:
                file_hashes = json.loads(f.read())

            self.logger.info("fileMonitoring: File hash database read successfully.")
            return file_hashes

        except Exception as e:
            self.logger.error("fileMonitoring/__get_file_hashes_from_db: {0}".format(traceback.format_exc()))
            adieu(1)
    
    def __compare_file_hashes(self, old_hashes: dict, new_hashes: dict) -> list:
        try:
            self.logger.info("fileMonitoring: Comparing file hashes...")
            changed = []
            for file in self.files_to_monitor:
                old = old_hashes.get(file)
                new = new_hashes.get(file)
                if old != new:
                    self.logger.warning(f"fileMonitoring: File {file} has been modified!")
                    if self.db_conn:
                        self.db_conn.save_file_check(file, new, "true")
                    changed.append({"path": file, "hash": new})
                else:
                    self.logger.info(f"fileMonitoring: File {file} is unchanged.")
                    if self.db_conn:
                        self.db_conn.save_file_check(file, new, "false")

            self.logger.info("fileMonitoring: File hash comparison completed.")
            return changed
        except Exception as e:
            self.logger.error("fileMonitoring/__compare_file_hashes: {0}".format(traceback.format_exc()))
            adieu(1)

    def __generate_new_file_hash_db(self, file_hashes: dict) -> None:
        try:
            self.logger.info("fileMonitoring: Generating new file hash database file...")

            with open(self.db_path, "w") as f:
                f.write(json.dumps(file_hashes, indent=4))

            self.logger.info("fileMonitoring: New file hash database file generated successfully.")

        except Exception as e:
            self.logger.error("fileMonitoring/__generate_new_file_hash_db: {0}".format(traceback.format_exc()))
            adieu(1)

    def __check_if_db_exists(self) -> bool:
        try:
            return os.path.isfile(self.db_path)
        except Exception as e:
            self.logger.error("fileMonitoring/__check_if_db_exists: {0}".format(traceback.format_exc()))
            adieu(1)

    def check_files(self) -> None:
        try:
            self.logger.info("fileMonitoring: Starting file checks...")
            
            # -- Checks all basic services --
            self.__check_if_module_is_active()
            if self.__check_if_db_exists() == False:
                self.logger.info("fileMonitoring: No existing hash database found. Generating new database...")
                new_hashes = self.__generate_new_file_hashes()
                self.__generate_new_file_hash_db(new_hashes)
                adieu(0)
            
            old_hashes = self.__get_file_hashes_from_db()
            new_hashes = self.__generate_new_file_hashes()

            changed_files = self.__compare_file_hashes(old_hashes, new_hashes)
            self.__generate_new_file_hash_db(new_hashes)

            # Alerting: if changes detected and alerting enabled, send email
            try:
                if changed_files and self.alerting_is_active:
                    ctx = {
                        "report_title": "Dateiänderungen entdeckt",
                        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "changed_files": changed_files,
                        "footer_note": "Automatische Meldung: Dateien wurden geändert."
                    }

                    # mailgun
                    if getattr(self, "mailgun_alerting_is_active", False):
                        try:
                            mg = mailgunConnector()
                            mg.mailgunSendMailHTML("Dateiänderungen auf System", "fileMonitoring", ctx)
                        except Exception:
                            self.logger.warning(f"fileMonitoring: mailgun send failed: {traceback.format_exc()}")

                    # smtp
                    if getattr(self, "smtp_alerting_is_active", False):
                        try:
                            from alerting.smtpConnector import smtpConnector
                            smtp = smtpConnector()
                            smtp.smtpSendMailHTML("Dateiänderungen auf System", "fileMonitoring", ctx)
                        except Exception:
                            self.logger.warning(f"fileMonitoring: smtp send failed: {traceback.format_exc()}")
            except Exception:
                self.logger.warning(f"fileMonitoring: Failed to send alert: {traceback.format_exc()}")

            self.logger.info("fileMonitoring: File checks completed.")
        except Exception as e:
            self.logger.error("fileMonitoring/check_files: {0}".format(traceback.format_exc()))
            adieu(1)
    
    def delete_file_results(self) -> None:
        try:
            self.db_conn.delete_db_data("file_checks")
            self.logger.info("fileMonitoring: File result files deleted successfully.")
        except Exception as e:
            self.logger.error(f"fileMonitoring/delete_file_results: An error occurred while deleting file result files: {e}")
            adieu(1)

    def delete_file_monitoring_db(self) -> None:
        try:
            Path(self.db_path).unlink()
            self.logger.info("fileMonitoring: File monitoring database deleted successfully.")
        except FileNotFoundError:
            self.logger.warning("fileMonitoring: File monitoring database not found. Nothing to delete.")
        except Exception as e:
            self.logger.error(f"fileMonitoring/delete_file_monitoring_db: An error occurred while deleting file monitoring database: {e}")
            adieu(1)
