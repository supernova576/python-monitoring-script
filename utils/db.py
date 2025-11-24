import sqlite3
import json
import traceback
from pathlib import Path
from datetime import datetime
from sys import exit as adieu

import utils.log as logger

class db:
    def __init__(self) -> None:
        try:
            # -- Get config-parameters --
            path = Path(__file__).resolve().parent.parent / "conf.json"

            j = {}
            if path.is_file():
                with open(f"{path}", "r") as f:
                    j = json.loads(f.read())

            # Read db config with safe defaults
            db_conf = j.get("db", {})
            logging_conf = j.get("logging", {})

            self.db_path: str = db_conf.get("db_path", str(Path(__file__).resolve().parent.parent / "db" / "monitoring.db"))
            self.is_active: bool = bool(db_conf.get("is_active", False))

            self.path_to_log_file: str = logging_conf.get("log_file_path", str(Path(__file__).resolve().parent.parent / "db" / "monitoring.log"))
            self.logger = logger(self.path_to_log_file)

            if not self.is_active:
                # DB module is deactivated in config: skip connecting and don't exit
                self.logger.info("sqlite_handler: DB module is deactivated in conf.json. Skipping DB initialization and ingestion.")
                self.conn = None
                self.cursor = None
                return

            # connect and initialize DB
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()

            self.logger.info("sqlite_handler: Connected to database successfully...")
            self.__init_db()
            self.logger.info(f"sqlite_handler: Initialized with DB at {self.db_path}")
        except Exception:
            # if logger exists, use it; else print
            try:
                self.logger.error("sqlite_handler/__init__: {0}".format(traceback.format_exc()))
            except Exception:
                print(traceback.format_exc())
            adieu(1)

    def __init_db(self) -> None:
        try:
            if not self.conn:
                # nothing to do when not connected
                return

            self.logger.info("sqlite_handler: Creating tables if not exist...")

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS file_checks (
                    id INT NOT NULL AUTO_INCREMENT,
                    timestamp VARCHAR(255),
                    file_path VARCHAR(255),
                    file_hash VARCHAR(255),
                    changed VARCHAR(10),
                    PRIMARY KEY (id)
                )
                """
            )

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS service_checks (
                    id INT NOT NULL AUTO_INCREMENT,
                    timestamp VARCHAR(255),
                    service_name VARCHAR(255),
                    is_active VARCHAR(10),
                    PRIMARY KEY (id)
                )
                """
            )

            self.conn.commit()
            self.logger.info("sqlite_handler: Tables ready.")
        except Exception:
            self.logger.error("sqlite_handler/init_db: {0}".format(traceback.format_exc()))
            adieu(1)

    def save_file_check(self, file_path: str, file_hash: str, changed: str) -> None:
        try:
            # skip ingestion when DB module is deactivated
            if not getattr(self, "is_active", False) or not getattr(self, "conn", None):
                try:
                    self.logger.info(f"sqlite_handler: DB disabled - skipping file check save for {file_path}")
                except Exception:
                    pass
                return

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.cursor.execute(
                "INSERT INTO file_checks (timestamp, file_path, file_hash, changed) VALUES (?, ?, ?, ?)",
                (ts, file_path, file_hash, changed),
            )
            self.conn.commit()
            self.logger.info(f"sqlite_handler: Saved file check for {file_path} (changed={changed})")
        except Exception:
            self.logger.error("sqlite_handler/save_file_check: {0}".format(traceback.format_exc()))
            adieu(1)

    def save_service_check(self, service_name: str, is_active: str) -> None:
        try:
            # skip ingestion when DB module is deactivated
            if not getattr(self, "is_active", False) or not getattr(self, "conn", None):
                try:
                    self.logger.info(f"sqlite_handler: DB disabled - skipping service check save for {service_name}")
                except Exception:
                    pass
                return

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.cursor.execute(
                "INSERT INTO service_checks (timestamp, service_name, is_active) VALUES (?, ?, ?)",
                (ts, service_name, is_active),
            )
            self.conn.commit()
            self.logger.info(f"sqlite_handler: Saved service check for {service_name} (is_active={is_active})")
        except Exception:
            self.logger.error("sqlite_handler/save_service_check: {0}".format(traceback.format_exc()))
            adieu(1)

    def get_recent_file_checks(self, limit: int = 100) -> list:
        try:
            self.cursor.execute(
                "SELECT id, timestamp, file_path, file_hash, changed FROM file_checks ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = self.cursor.fetchall()
            results = [dict(row) for row in rows]
            return results
        except Exception:
            self.logger.error("sqlite_handler/get_recent_file_checks: {0}".format(traceback.format_exc()))
            adieu(1)

    def get_recent_service_checks(self, limit: int = 100) -> list:
        try:
            self.cursor.execute(
                "SELECT id, timestamp, service_name, is_active FROM service_checks ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = self.cursor.fetchall()
            results = [dict(row) for row in rows]
            return results
        except Exception:
            self.logger.error("sqlite_handler/get_recent_service_checks: {0}".format(traceback.format_exc()))
            adieu(1)

    def __del__(self) -> None:
        try:
            if getattr(self, "conn", None):
                self.conn.close()
                self.logger.info("sqlite_handler: Connection closed.")
        except Exception:
            self.logger.error("sqlite_handler/close: {0}".format(traceback.format_exc()))

