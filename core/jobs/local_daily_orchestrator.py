import subprocess
from datetime import datetime, timezone
from core.notifications.telegram_notifier import TelegramNotifier


class LocalDailyOrchestrator:
    def __init__(self):
        self.notifier = TelegramNotifier()

    def run_command(self, command):
        proc = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {"command": command, "returncode": proc.returncode, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}

    def run_daily(self):
        commands = [
            "python -m core.jobs.publish_ready_organic_posts_to_facebook_job",
            "python -m test.collect_facebook_post_results",
            "python -m test.run_page_assessment_only",
            "python -m test.export_page_assessment_to_gsheet",
        ]
        results = []
        for cmd in commands:
            result = self.run_command(cmd)
            results.append(result)
            if result["returncode"] != 0:
                self.notifier.send(f"❌ Job failed\nCommand: {cmd}\nError: {result['stderr']}")
                break
        self.notifier.send(f"✅ Local daily organic jobs finished\nTime: {datetime.now(timezone.utc).isoformat()}")
        return results
