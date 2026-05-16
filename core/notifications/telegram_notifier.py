import os
import requests


class TelegramNotifier:
    def __init__(self, bot_token=None, chat_id=None, enabled=None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        if enabled is None:
            enabled = os.getenv("TELEGRAM_NOTIFY_ENABLED", "true").lower() != "false"
        self.enabled = enabled

    def send(self, message: str):
        if not self.enabled:
            return {"status": "disabled"}
        if not self.bot_token or not self.chat_id:
            return {"status": "missing_config"}
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message, "disable_web_page_preview": False}
        response = requests.post(url, json=payload, timeout=20)
        try:
            data = response.json()
        except Exception:
            data = {"raw_text": response.text}
        return {"status_code": response.status_code, "ok": response.ok, "data": data}
