import utils.log as logger
from utils.db import db as DB

import json
import os
import hashlib
from pathlib import Path
from sys import exit as adieu
import traceback

class fileMonitoring:
    def __init__(self) -> None:
        try:
            # -- Get config-parameters --
            path = Path(__file__).resolve().parent / "conf.json"

            with open(f"{path}", "r") as f:
                j = json.loads(f.read())

                self.is_active: bool = j["fileMonitoring"]["is_active"]
                self.db_path: str = j["fileMonitoring"]["db_path"]
                self.files_to_monitor: list = j["fileMonitoring"]["files_to_monitor"]

                self.path_to_log_file: str = j["logging"]["log_file_path"]
                self.logger = logger(self.path_to_log_file)

                # instantiate DB handler (DB may be configured as inactive and will then be a no-op)
                try:
                    self.db_conn = DB()
                except Exception:
                    # if DB cannot be initialized do not exit; keep monitoring functional
                    self.logger.error("fileMonitoring: Could not initialize DB handler; continuing without DB ingestion.")
                    self.db_conn = None

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
            for file in self.files_to_monitor:
                with open(file, "r") as f:
                    data = f.read()
                    md5 = hashlib.md5(data.encode("utf-8")).hexdigest()
                
                file_hashes[file] = md5
            self.logger.info("fileMonitoring: File hash database generated successfully.")

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
    
    def __compare_file_hashes(self, old_hashes: dict, new_hashes: dict) -> None:
        try:
            self.logger.info("fileMonitoring: Comparing file hashes...")

            for file in self.files_to_monitor:
                if old_hashes[file] != new_hashes[file]:
                    self.logger.warning(f"fileMonitoring: File {file} has been modified!")
                    if self.db_conn:
                        self.db_conn.save_file_check(file, new_hashes[file], True)
                else:
                    self.logger.info(f"fileMonitoring: File {file} is unchanged.")
                    if self.db_conn:
                        self.db_conn.save_file_check(file, new_hashes[file], False)

            self.logger.info("fileMonitoring: File hash comparison completed.")
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

            self.__compare_file_hashes(old_hashes, new_hashes)
            self.__generate_new_file_hash_db(new_hashes)

            self.logger.info("fileMonitoring: File checks completed.")
        except Exception as e:
            self.logger.error("fileMonitoring/check_files: {0}".format(traceback.format_exc()))
            adieu(1)