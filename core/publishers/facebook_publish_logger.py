import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


class FacebookPublishLogger:
    """
    Writes structured publish logs to logs/facebook_publish/YYYY-MM-DD/events.jsonl
    """

    def __init__(self, base_dir: str = "logs/facebook_publish"):
        self.base_dir = Path(base_dir)

    def log(self, event: Dict):
        today = datetime.now(timezone.utc).date().isoformat()
        log_dir = self.base_dir / today
        log_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(event or {}),
        }

        log_file = log_dir / "events.jsonl"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

        return str(log_file)
