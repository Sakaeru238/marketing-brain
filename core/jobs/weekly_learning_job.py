from datetime import datetime, timezone
from core.notifications.telegram_notifier import TelegramNotifier


class WeeklyLearningJob:
    def __init__(self):
        self.notifier = TelegramNotifier()

    def run(self):
        self.notifier.send("🧠 Weekly learning job ready. Connect PageAssessmentPipeline with Organic_Results + V3 metadata.")
        return {"status": "ready_for_pipeline_connection", "generated_at": datetime.now(timezone.utc).isoformat()}
