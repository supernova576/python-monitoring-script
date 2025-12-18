from utils.log import log

import json
import smtplib
import ssl
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import jinja2
from sys import exit as adieu


class smtpConnector:
    def __init__(self):
        try:
            path = Path(__file__).resolve().parent.parent / "conf.json"
            with open(f"{path}", "r") as f:
                j = json.loads(f.read())

                # try to read implementation-specific config
                smtp_cfg = None
                try:
                    smtp_cfg = j["alerting"]["implementation"]["smtp"]
                except Exception:
                    try:
                        smtp_cfg = j["alerting"]["smtp"]
                    except Exception:
                        smtp_cfg = None

                if not smtp_cfg:
                    raise KeyError("smtp configuration not found in conf.json")

                self.is_active = smtp_cfg.get("is_active", False)
                self.host = smtp_cfg.get("host", "localhost")
                self.port = int(smtp_cfg.get("port", 25))
                self.username = smtp_cfg.get("username")
                self.password = smtp_cfg.get("password")
                self.use_tls = smtp_cfg.get("use_tls", False)
                self.use_ssl = smtp_cfg.get("use_ssl", False)
                # recipient/sender may be per-alert or global fallback
                self.recipient = smtp_cfg.get("recipient")
                self.sender = smtp_cfg.get("sender", f"monitoring@{Path.cwd().name}")

                self.logger = log()

            self.logger.info("smtpConnector: Initialized successfully.")
        except Exception:
            # If the logger isn't available, print traceback and exit
            try:
                log().error("smtpConnector/__init__: {0}".format(traceback.format_exc()))
            except Exception:
                print(traceback.format_exc())
            adieu(1)

    def __load_html_template_by_name(self, filename: str, context: dict = None) -> str:
        try:
            if not self.is_active:
                self.logger.info("smtpConnector: Module deactivated in conf.json. Skipping template load.")
                return ""

            templates_dir = Path(__file__).resolve().parent / "html_templates"
            template_path = templates_dir / filename
            if not template_path.exists():
                self.logger.error(f"smtpConnector: Template not found: {template_path}")
                return ""

            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(templates_dir)),
                autoescape=jinja2.select_autoescape(["html", "xml"])
            )

            tpl = env.get_template(filename)
            self.logger.info(f"smtpConnector: loading template {filename}...")
            return tpl.render(**(context or {}))

        except Exception:
            self.logger.error("smtpConnector/__load_html_template_by_name: {0}".format(traceback.format_exc()))
            return ""

    def smtpSendMailHTML(self, subject: str, template_id: str, template_context: dict) -> None:
        try:
            if not self.is_active:
                self.logger.info("smtpConnector: SMTP disabled in conf.json. Skipping send.")
                return

            # determine template filename
            filename = None
            if template_id == "serviceMonitoring":
                filename = "serviceMonitoring.html"
            elif template_id == "hostMonitoring":
                filename = "hostMonitoring.html"
            elif template_id == "fileMonitoring":
                filename = "fileMonitoring.html"
            elif template_id == "hostStartup":
                filename = "hostStartup.html"
            else:
                self.logger.warning(f"smtpConnector: Unknown template_id '{template_id}'. Aborting send.")
                return

            html = self.__load_html_template_by_name(filename, template_context)

            # Compose message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = template_context.get("from", self.sender)
            msg["To"] = template_context.get("to", self.recipient or template_context.get("recipient", ""))

            part = MIMEText(html, "html")
            msg.attach(part)

            # Send via SMTP
            if self.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, context=context) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.sendmail(msg["From"], [msg["To"]], msg.as_string())
            else:
                with smtplib.SMTP(self.host, self.port) as server:
                    server.ehlo()
                    if self.use_tls:
                        server.starttls()
                        server.ehlo()
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.sendmail(msg["From"], [msg["To"]], msg.as_string())

            self.logger.info(f"smtpConnector: Email sent to {msg['To']}")

        except Exception:
            self.logger.error("smtpConnector/smtpSendMailHTML: {0}".format(traceback.format_exc()))
            adieu(1)
