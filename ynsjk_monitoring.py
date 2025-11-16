### Monitoring-Skript für Server ###
# Author: YNSJK_
# Version: 1.3
# Beschreibung: Monitoring des Servers für ausgewählte Services. Kann Mails versenden (via Mailgun)

## Version Change ##
# Version 1.0: Erste Version des Files
# Version 1.1: Aide abgeschafft, aber funktionierende Alternative gefunden :<)
# Version 1.2: Threshold Journal angepasst => 500 mb | bugfix dns => status unknown
# Version 1.3: Cleanup .json File and functions | adds check_nfs_connection | adds check_storage_used

# to be implemented: logging, snmp

import json
import os
import re
import requests
import sys
import hashlib
import glob
import time

###############
### CLASSES ###
###############

class ynsjk_services:

    def __init__(self, path_to_config: str) -> None:
        try:
            # -- Create Status-Dict to store all data --
            # Format:
            # {"Service Name": "Status"}
            self.statuses = {}

            # -- Create Handler for Mail Notification (if > 0) --
            self.mail_handler = 0

            # -- Get config-parameters from ynsjk_monitoring.json --
            with open(path_to_config, "r") as f:
                json_content = json.loads(f.read())

                self.hostname = str(json_content["ynsjk_services"]["hostname"])
                self.services = list[str](json_content["ynsjk_services"]["service_list"])
                self.dns_ip = str(json_content["ynsjk_services"]["dns_ip"])
                self.swap_limit_in_mb = int(json_content["ynsjk_services"]["swap_limit_in_mb"])
                self.swappiness_max = int(json_content["ynsjk_services"]["swappiness_max"])
                self.journal_max_size_in_mb = int(json_content["ynsjk_services"]["journal_max_size_in_mb"])
                self.nas_ip = str(json_content["ynsjk_services"]["nas_ip"])
                self.path_to_nfs_share = str(json_content["ynsjk_services"]["path_to_nfs_share"])
                self.max_storage_used_in_percent = int(json_content["ynsjk_services"]["max_storage_used_in_percent"])
            # -------------------------------------------------------
        except Exception as e:
            raise Exception("ynsjk_server/__init__: {0}".format(e))
    
    def __check_service_statuses(self) -> None:
        try:
            # -- Iterate from [ynsjk_services][service_list] --
            for service in self.services:
                self.statuses[service] = "UNKNOWN"

                # -- Check with systemctl quiet command, if service is active. If so, returns 0 --
                if int(os.system("systemctl is-active --quiet {0}".format(service))) == 0:
                    self.statuses[service] = "OK"
                else:
                    self.mail_handler += 1
                    self.statuses[service] = "ERROR"
                    os.system("service {0} start; service {0} restart".format(service))
                # --------------------------------------------------------------------------------
        except Exception as e:
            raise Exception("ynsjk_server/__check_service_statuses: {0}".format(e))
        
    def __check_dns(self) -> None:
        try:
            self.statuses["dns"] = "UNKNOWN"
            
            # -- Opens /etc/resolv.conf and matches all ipv4 adresses present --
            with open("/etc/resolv.conf", "r") as f:
                content = f.read()

                matches = re.findall(r'(?:[0-9]{1,3}\.){3}[0-9]{1,3}', content)

            # -- if ip does not match [ynsjk_services][dns_ip], overwrites entry with IP in json_file --
            for match in matches:
                if(str(match) == "{0}".format(str(self.dns_ip))):
                    self.statuses["dns"] = "OK"

            if self.statuses["dns"] != "OK":
                self.mail_handler += 1
                with open("/etc/resolv.conf", "w") as f:
                    overwrite_nameserver = "nameserver {0}\noptions edns0 trust-ad".format(str(self.dns_ip))
                    f.write(overwrite_nameserver)
                
                    self.statuses["dns"] = "WARNING" 
            # ------------------------------------------------------------------------------------------
        except Exception as e:
            raise Exception("ynsjk_server/__check_dns: {0}".format(e))

    def __check_swap(self) -> None:
        try:
            self.statuses["swap"] = "UNKNOWN"

            # -- gets current swap-size in MB --
            swap_before = os.popen("free -m | sed '/Swap:/ ! d' | awk '{print $3}'").read()
            swap_before = int(swap_before.replace("\n", ""))

            if swap_before > self.swap_limit_in_mb:
                self.mail_handler += 1
                # -- Register Swapfile-Name then free and remount --
                swapfile = os.popen("swapon -s | sed '/swap/ ! d' | awk '{print $1}'").read()
                swapfile = str(swapfile.replace("\n", ""))

                os.system("swapoff -a")
                os.system("swapon {0}".format(swapfile))
                # --------------------------------------------------

                # -- rechecks, if swapfile is present and empty now --
                swap_after = os.popen("free -m | sed '/Swap:/ ! d' | awk '{print $3}'").read()
                swap_after = int(swap_after.replace("\n", ""))

                self.statuses["swap"] = "WARNING"
                self.statuses["swap_in_mb"] = "{0} MB".format(str(swap_before))

                if swap_after != 0:
                    raise Exception("Swapfile nicht geleert | swap_vorher: {0}, swap_nachher: {1}, swapfile: {2}".format(str(swap_before), str(swap_after), swapfile))
                # ---------------------------------------------------
            else:
                self.statuses["swap"] = "OK"
                self.statuses["swap_in_mb"] = "{0} MB".format(str(swap_before))

        except Exception as e:
            raise Exception("ynsjk_server/__check_swap: {0}".format(e))

    def __check_swappiness(self) -> None:
        try:
            # -- gets current swapiness-value --
            swappiness_value = os.popen("cat /proc/sys/vm/swappiness").read()
            swappiness_value = int(swappiness_value.replace("\n", ""))
            # ----------------------------------

            # -- Checks if value is greater than [ynsjk_services][swapiness_max] --
            if swappiness_value > self.swappiness_max:
                self.mail_handler += 1
                os.system("sysctl vm.swappiness=25; sysctl -p")
                self.statuses["swappiness"] = "WARNING"
                self.statuses["swappiness_value"] = swappiness_value
            else:
                self.statuses["swappiness"] = "OK"
                self.statuses["swappiness_value"] = swappiness_value
            # ---------------------------------------------------------------------
        except Exception as e:
            raise Exception("ynsjk_server/__check_swappiness: {0}".format(e))
        
    def __check_journal_size(self) -> None:
        try:
            # -- sets folder_size to 0 MB and gets journal identifier --
            folder_size = 0
            journal_identifier = os.listdir(r"/var/log/journal")[0]

            full_path = "/var/log/journal/{0}".format(journal_identifier)
            # ----------------------------------------------------------

            # -- Calculates Folder Size in MB and compares it with [ynsjk_services][swap_limit_in_mb] --
            for file in os.listdir(full_path):
                folder_size += int(os.stat("{0}/{1}".format(full_path, file)).st_size)

            if int(folder_size / (1024 * 1024)) > int(self.journal_max_size_in_mb):
                self.mail_handler += 1
                self.statuses["journal"] = "WARNING"
                self.statuses["journal_in_mb"] = "{0} MB".format(folder_size / (1024 * 1024))
            # ------------------------------------------------------------------------------------------
        except Exception as e:
            raise Exception("ynsjk_services/__check_journal_size: {0}".format(e))

    def __check_nfs_connection(self) -> None:
        try:
            self.statuses["nfs"] = "UNKNOWN"
            
            # -- Check, if system is proxmox or not --
            if self.hostname in ["proxmox", "d-proxmox"]:
                handler = os.popen(f"df -h | grep -Eo \"{self.nas_ip}\"").read()

                if handler.replace("\n", "") == self.nas_ip:
                    self.statuses["nfs"] = "OK"
                else:
                    self.statuses["nfs"] = "ERROR"
            else:
                # -- check with df -h, if [ynsjk_services][path_to_nfs_share] is present (Servers) --
                handler = os.popen(f"df -h | grep -Eo \"{self.path_to_nfs_share}\"").read()

                if handler.replace("\n", "") == self.path_to_nfs_share:
                    self.statuses["nfs"] = "OK"
                else:
                    self.mail_handler += 1
                    self.statuses["nfs"] = "WARNING"
                    os.system(f"mount -t nfs {self.nas_ip}:/volume1/{self.hostname} /mnt/{self.hostname}")

                    # -- check again, if nfs-connection is present now --
                    handler = os.popen(f"df -h | grep -Eo \"{self.path_to_nfs_share}\"").read()

                    if handler.replace("\n", "") != self.path_to_nfs_share:
                        self.statuses["nfs"] = "ERROR"
                    
        except Exception as e:
            raise Exception(f"ynsjk_services/__check_nfs_connection: {e}")

    def __check_percent_of_storage_used(self) -> None:
        try:
            self.statuses["storage"] = "UNKNOWN"

            # -- get percent value of used storage --
            percent_used = int(os.popen("df -h / | awk '{print $5}' | grep -Eo \"[0-9]+\"").read().replace("\n", ""))

            if percent_used > self.max_storage_used_in_percent:
                self.statuses["storage"] = "WARNING"
                self.statuses["percent_used"] = f"{percent_used}%"
            else:
                self.statuses["storage"] = "OK"
                self.statuses["percent_used"] = f"{percent_used}%"
            # ----------------------------------------
        except Exception as e:
            raise Exception(f"ynsjk_services/__check_percent_of_storage_used: {e}")

    def __apt_get_update_upgrade(self) -> None:
        try:
            # -- Update and Upgrade of machine --
            os.system("apt-get update; apt-get upgrade -yq")
            # -----------------------------------
        except Exception as e:
            raise Exception("ynsjk_server/__apt_get_update_upgrade: {0}".format(e))

    def check_services(self) -> None:
        try:
            # -- Checks all basic services --
            self.__check_dns()
            self.__check_service_statuses()
            self.__check_swap()
            self.__check_swappiness()
            self.__check_journal_size()
            self.__check_nfs_connection()
            self.__check_percent_of_storage_used()
            # -------------------------------
        except Exception as e:
            raise Exception("ynsjk_server/check_services: {0}".format(e))
    
    def check_reboot(self) -> None:
        try:
            # -- Same as check_services(), but with delay and update/upgrade --
            time.sleep(20)
            self.__check_dns()
            self.__check_service_statuses()
            self.__check_swap()
            self.__check_swappiness()
            self.__check_journal_size()
            self.__check_nfs_connection()
            self.__apt_get_update_upgrade()
            self.__check_percent_of_storage_used()
            # ----------------------------------------------------------------
        except Exception as e:
            raise Exception("ynsjk_server/check_reboot: {0}".format(e))

class ynsjk_file_monitoring:

    def __init__(self, path_to_config: str) -> None:
        try:
            # -- Create Status-Dict to store all data --
            # Format:
            # {"File Name": "Status"}
            self.statuses = {}

            # -- Create Handler for Mail Notification (if > 0) --
            self.mail_handler = 0

            # -- loads all configuration parameters from ynsjk_monitoring.json --
            with open(path_to_config, "r") as f:
                json_content = json.loads(f.read())

                self.db_path = str(json_content["ynsjk_file_monitoring"]["db_path"])
                self.files_to_monitor = list[str](json_content["ynsjk_file_monitoring"]["files_to_monitor"])
                self.hostname = str(json_content["ynsjk_services"]["hostname"])
            # --------------------------------------------------------------------
        except Exception as e:
            raise Exception("ynsjk_file_monitoring/__init__: {0}".format(e))
    
    def __load_old_file_db(self) -> dict:
        try:
            # -- reads old data stored in DB and returns dict --
            with open(self.db_path, "r") as f:
                return json.load(f)
            # --------------------------------------------------
        except Exception as e:
            raise Exception("ynsjk_file_monitoring/__load_old_file_db: {0}".format(e))
    
    def __load_new_file_db(self) -> dict:
        try:
            # -- calculates md5 hashes of files in [ynsjk_file_monitoring][files_to_monitor] --
            file_hashes = {}
            for file in self.files_to_monitor:
                with open(file, "r") as f:
                    data = f.read()
                    md5 = hashlib.md5(data.encode("utf-8")).hexdigest()
                
                file_hashes[file] = md5
            return file_hashes
            # ----------------------------------------------------------------------------------
        except Exception as e:
            raise Exception("ynsjk_file_monitoring/__load_new_file_db: {0}".format(e))
    
    def compare_file_hashes(self) -> None:
        try:
            # -- compares old and new filehashes --
            for file_old, md5_old in self.__load_old_file_db().items():
                for file_new, md5_new in self.__load_new_file_db().items():
                    if file_old == file_new and md5_old == md5_new:
                        self.statuses[file_new] = "OK"
                    elif file_old == file_new and md5_old != md5_new:
                        self.mail_handler += 1
                        self.statuses[file_new] = "CHANGED"
            # -------------------------------------
        except Exception as e:
            raise Exception("ynsjk_file_monitoring/compare_file_hashes: {0}".format(e))
    
    def update_file_db(self) -> None:
        try:
            # -- Updates file database with new MD5 hashes --
            with open(self.db_path, "w") as f:
                f.write(json.dumps(self.__load_new_file_db()))
            # -----------------------------------------------
        except Exception as e:
            raise Exception("ynsjk_file_monitoring/update_file_db: {0}".format(e))

# -------------------------------------------------------

#################
### FUNCTIONS ###
#################

def send_mail_html(path_to_config_file: str, subject: str, body: str) -> None:
    try:
        # -- sends mail according to ynsjk_monitoring.json --
        # Format:
        # {"subject", "html"}
        with open(path_to_config_file, "r") as f:
            mail_config = json.loads(f.read())

            auth = (mail_config["mail"]["username"], mail_config["mail"]["api_key"])
            data = {
                "from": mail_config["mail"]["from"],
                "to": mail_config["mail"]["to"],
                "subject": subject,
                "html": body
            }
            response = requests.post(mail_config["mail"]["webroot"], auth=auth, data=data)
            response.raise_for_status()
    except Exception as e:
        raise Exception("send_mail_html: {0}".format(e))

def generate_html_report_for_ynsjk_services(service_dict: dict) -> str:
    try:
        html = "<h2>Service-Error</h2><br><br>"
        for service, status in service_dict.items():
            html = f"{html}<b>Service: {service}</b>, Status {status}<br>"

        return html        
    except Exception as e:
        raise Exception(f"generate_html_report_for_ynsjk_services: {e}")
    
def generate_html_report_for_ynsjk_file_monitoring(service_dict: dict) -> str:
    try:
        html = "<h2>Files Changed</h2><br><br>"
        for file, status in service_dict.items():
            html = f"{html}<b>File: {file}</b>, Status: {status}<br>"

        return html
    except Exception as e:
        raise Exception(f"generate_html_report_for_ynsjk_file_monitoring: {e}")
# ---------------------------------------

############
### MAIN ###
############

def main():
    try:
        # -- Declare variables --
        # Runtypes (USAGE: python3 /path/to/this/file "status|reboot|aide|aide_generate_file")
        # {"status" => "Checks all services according to the check_services-method"}
        # {"reboot" => "same as status, but with delay and update/upgrade"}
        # {"aide"} => "triggers file-checks with md5 comparison"
        # {"aide_generate_file"} => "generates a new db-file (used after deployment or file list change)"

        global CONFIG_FILE
        CONFIG_FILE = "/root/scripts/ynsjk_monitoring.json"
        runtype = sys.argv[1]
        # -----------------------
        
        # -- Run Script according to runtype --
        if runtype == "status":
            services = ynsjk_services(CONFIG_FILE)
            services.check_services()

            if services.mail_handler > 0:
                send_mail_html(CONFIG_FILE, "Service-Error auf {0}".format(services.hostname), generate_html_report_for_ynsjk_services(services.statuses))
        elif runtype == "reboot":
            services = ynsjk_services(CONFIG_FILE)
            send_mail_html(CONFIG_FILE, f"{services.hostname} just came online!", "Services will be checked and Update/Upgrade will be executed.")
            services.check_reboot()

            if services.mail_handler > 0:
                send_mail_html(CONFIG_FILE, "Service-Error auf {0}".format(services.hostname), generate_html_report_for_ynsjk_services(services.statuses))
        elif runtype == "aide":
            file_monitoring = ynsjk_file_monitoring(CONFIG_FILE)
            file_monitoring.compare_file_hashes()
            file_monitoring.update_file_db()

            if file_monitoring.mail_handler > 0:
                send_mail_html(CONFIG_FILE, "File-Change auf {0}".format(file_monitoring.hostname), generate_html_report_for_ynsjk_file_monitoring(file_monitoring.statuses))
        elif runtype == "aide_generate_file":
            file_monitoring = ynsjk_file_monitoring(CONFIG_FILE)
            file_monitoring.update_file_db()
        else:
            raise Exception("main/runtype: Invalider Runtype definiert")
        
        # --------------------------------
    except Exception as e:
        # print(e)
        send_mail_html(CONFIG_FILE, "Script-Error", "<h2>Fehler</h2><br><br>{0}".format(str(e)))
        
# ------------------------------------------------------------

# -- Execute --
if __name__ == "__main__":
    main()