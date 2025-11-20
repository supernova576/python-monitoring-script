from pathlib import Path
import json

class log:

    def __init__(self, path_to_log_file: str) -> None:
        self.log_file_path: str = path_to_log_file

    def info(self, message: str) -> None:
        with open(self.log_file_path, "a") as log_file:
            log_file.write(f"[INFO] {message}\n")

    def warning(self, message: str) -> None:           
        with open(self.log_file_path, "a") as log_file:
            log_file.write(f"[WARNING] {message}\n")

    def error(self, message: str) -> None:           
        with open(self.log_file_path, "a") as log_file:
            log_file.write(f"[ERROR] {message}\n")