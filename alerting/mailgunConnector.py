from utils.log import log

import json
import requests
from pathlib import Path
from sys import exit as adieu
import traceback
import jinja2

class mailgunConnector:
    def __init__(self):
        try:
            # -- Get config-parameters --
            path = Path(__file__).resolve().parent.parent / "conf.json"

            with open(f"{path}", "r") as f:
                j = json.loads(f.read())

                # support both new and old config layouts
                mg_cfg = None
                try:
                    mg_cfg = j["alerting"]["implementation"]["mailgun"]
                except Exception:
                    try:
                        mg_cfg = j["alerting"]["mailgun"]
                    except Exception:
                        mg_cfg = None

                if not mg_cfg:
                    raise KeyError("mailgun configuration not found in conf.json")

                self.is_active: bool = mg_cfg.get("is_active", False)
                self.webroot: str = mg_cfg.get("webroot", "")
                self.api_key: str = mg_cfg.get("api_key", "")
                self.recipient: str = mg_cfg.get("recipient", "")
                self.sender: str = mg_cfg.get("sender", "")

                self.logger = log()
            # -------------------------------------------------------

            self.logger.info("mailgunConnector: Initialized successfully.")
        except Exception:
            self.logger.error("mailgunConnector/__init__: {0}".format(traceback.format_exc()))
            adieu(1)

    
    def __load_html_template_by_name(self, filename: str, context: dict = None) -> str:
        try:
            if not self.is_active:
                self.logger.info("mailgunConnector: Module is deactivated in conf.json. Skipping template load.")
                return ""

            templates_dir = Path(__file__).resolve().parent / "html_templates"
            template_path = templates_dir / filename

            if not template_path.exists():
                self.logger.error(f"mailgunConnector: Template not found: {template_path}")
                return ""

            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(templates_dir)),
                autoescape=jinja2.select_autoescape(["html", "xml"])
            )

            tpl = env.get_template(filename)
            self.logger.info(f"loading template {filename}...")
            return tpl.render(**(context or {}))

        except Exception:
            self.logger.error("mailgunConnector/__load_html_template_by_name: {0}".format(traceback.format_exc()))
            return ""
        
    def mailgunSendMailHTML(self, subject: str, template_id: str, template_context: dict) -> None:
        try:
            if self.is_active:
                self.logger.info("Start to send mail via mailgun")

                # Map template_id to loader/rendering
                html = ""
                if template_id == "serviceMonitoring":
                    self.logger.info("matched serviceMonitoring template")
                    html = self.__load_html_template_by_name("serviceMonitoring.html", template_context)
                elif template_id == "hostMonitoring":
                    self.logger.info("matched hostMonitoring template")
                    # reuse template loading mechanism but with filename
                    html = self.__load_html_template_by_name("hostMonitoring.html", template_context)
                elif template_id == "fileMonitoring":
                    self.logger.info("matched fileMonitoring template")
                    html = self.__load_html_template_by_name("fileMonitoring.html", template_context)
                else:
                    self.logger.warning(f"mailgunConnector: Unknown template_id '{template_id}'. No email sent.")
                    return

                self.logger.info("Successfully loaded template")
                
                auth=("api", self.api_key)
                data = {
                    "from": self.sender,
                    "to": self.recipient,
                    "subject": str(subject),
                    "html": html
                }
                response = requests.post(self.webroot, auth=auth, data=data)
                response.raise_for_status()

        except Exception:
            self.logger.error("mailgunConnector/mailgunSendMailHTML: {0}".format(traceback.format_exc()))
            adieu(1)