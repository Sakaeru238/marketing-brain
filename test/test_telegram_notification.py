from dotenv import load_dotenv
load_dotenv()

from core.notifications.telegram_notifier import TelegramNotifier

if __name__ == "__main__":
    print(TelegramNotifier().send("✅ Telegram notification test from Marketing Brain"))
