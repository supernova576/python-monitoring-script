from pathlib import Path
import json

class log:

    def __init__(self) -> None:
        with open(Path(__file__).resolve().parent.parent / "conf.json", "r") as f:
            j = json.loads(f.read())
            
            self.log_file_path: str = j["logging"]["log_file_path"]
            self.is_active: bool = j["logging"]["is_active"]

    def info(self, message: str) -> None:
        if self.is_active:
            with open(self.log_file_path, "a") as log_file:
                log_file.write(f"[INFO] {message}\n")

    def warning(self, message: str) -> None:
        if self.is_active:       
            with open(self.log_file_path, "a") as log_file:
                log_file.write(f"[WARNING] {message}\n")

    def error(self, message: str) -> None:
        if self.is_active:      
            with open(self.log_file_path, "a") as log_file:
                log_file.write(f"[ERROR] {message}\n")

    def delete_logs(self) -> None:
        try:
            Path(self.log_file_path).unlink()
            self.info("Log file deleted successfully.")
        except FileNotFoundError:
            self.warning("Log file not found. Nothing to delete.")
        except Exception as e:
            self.error(f"An error occurred while deleting log file: {e}")