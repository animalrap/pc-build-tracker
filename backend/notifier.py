import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

log = logging.getLogger(__name__)


def send_discord(webhook: str, part_name: str, retailer_or_body: str,
                 price: float | None, target: float | None,
                 url: str | None, is_summary: bool = False):
    if not webhook:
        return
    try:
        if is_summary:
            payload = {
                "embeds": [{
                    "title": f"Build Tracker — {part_name}",
                    "description": retailer_or_body,
                    "color": 0x57F287,
                    "footer": {"text": datetime.now().strftime("%Y-%m-%d %H:%M")},
                }]
            }
        else:
            savings = round(target - price, 2) if target and price else 0
            fields = [
                {"name": "Retailer", "value": retailer_or_body, "inline": True},
                {"name": "Price",    "value": f"**${price:.2f}**", "inline": True},
                {"name": "Target",   "value": f"${target:.2f}", "inline": True},
                {"name": "Savings",  "value": f"${savings:.2f} below target", "inline": False},
            ]
            if url:
                fields.append({"name": "Link", "value": url, "inline": False})

            payload = {
                "embeds": [{
                    "title": f"Deal found: {part_name}",
                    "color": 0x57F287,
                    "fields": fields,
                    "footer": {"text": datetime.now().strftime("%Y-%m-%d %H:%M")},
                }]
            }

        r = requests.post(webhook, json=payload, timeout=10)
        r.raise_for_status()
        log.info(f"Discord notification sent for {part_name}")
    except Exception as e:
        log.warning(f"Discord send failed: {e}")


def send_email(cfg: dict, part_name: str, retailer: str,
               price: float, target: float, url: str | None):
    if not all([cfg.get("from"), cfg.get("to"), cfg.get("password")]):
        return
    try:
        savings = round(target - price, 2)
        subject = f"Deal alert: {part_name} @ ${price:.2f} on {retailer}"
        body = f"""
Deal found for your PC build!

Part     : {part_name}
Retailer : {retailer}
Price    : ${price:.2f}
Target   : ${target:.2f}
Savings  : ${savings:.2f} below your target
{f'Link     : {url}' if url else ''}

Checked at {datetime.now().strftime('%Y-%m-%d %H:%M')}

-- PC Build Tracker
"""
        msg = MIMEMultipart()
        msg["From"] = cfg["from"]
        msg["To"] = cfg["to"]
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(cfg.get("smtp_host", "smtp.gmail.com"),
                          cfg.get("smtp_port", 587)) as server:
            server.starttls()
            server.login(cfg["from"], cfg["password"])
            server.sendmail(cfg["from"], cfg["to"], msg.as_string())
        log.info(f"Email sent for {part_name}")
    except Exception as e:
        log.warning(f"Email send failed: {e}")
