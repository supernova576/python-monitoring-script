import sqlite3
import json
import traceback
from pathlib import Path
from datetime import datetime
from sys import exit as adieu
import pandas as pd

from utils.log import log

class db:
    def __init__(self) -> None:
        try:
            # -- Get config-parameters --
            path = Path(__file__).resolve().parent.parent / "conf.json"

            with open(f"{path}", "r") as f:
                j = json.loads(f.read())

                self.is_active: bool = j["db"]["is_active"]
                self.db_path: str = j["db"]["db_path"]

            self.logger = log()

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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    file_path TEXT,
                    file_hash TEXT,
                    changed TEXT
                )
                """
            )

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS service_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    service_name TEXT,
                    is_active TEXT
                )
                """
            )

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS host_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    name TEXT,
                    observed_value TEXT
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

    def save_host_check(self, name: str, observed_value: str) -> None:
        try:
            # skip ingestion when DB module is deactivated
            if not getattr(self, "is_active", False) or not getattr(self, "conn", None):
                try:
                    self.logger.info(f"sqlite_handler: DB disabled - skipping service check save for {name}")
                except Exception:
                    pass
                return

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.cursor.execute(
                "INSERT INTO host_checks (timestamp, name, observed_value) VALUES (?, ?, ?)",
                (ts, name, observed_value),
            )
            self.conn.commit()
            self.logger.info(f"sqlite_handler: Saved host check for {name} (value={observed_value})")
        except Exception:
            self.logger.error("sqlite_handler/save_host_check: {0}".format(traceback.format_exc()))
            adieu(1)

    def load_table_for_report(self, table_name: str, limit: int = 0) -> pd.DataFrame:
        try:
            if limit == 0:
                return pd.read_sql_query(f"SELECT * FROM {table_name}", self.conn)
            else:
                return pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT {limit}", self.conn)
        
        except Exception:
            self.logger.error("sqlite_handler/load_table_for_report: {0}".format(traceback.format_exc()))
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
    
    def get_recent_host_checks(self, limit: int = 100) -> list:
        try:
            self.cursor.execute(
                "SELECT id, timestamp, name, value FROM host_checks ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = self.cursor.fetchall()
            results = [dict(row) for row in rows]
            return results
        except Exception:
            self.logger.error("sqlite_handler/get_recent_host_checks: {0}".format(traceback.format_exc()))
            adieu(1)

    def __del__(self) -> None:
        try:
            if getattr(self, "conn", None):
                self.conn.close()
                self.logger.info("sqlite_handler: Connection closed.")
        except Exception:
            self.logger.error("sqlite_handler/close: {0}".format(traceback.format_exc()))

