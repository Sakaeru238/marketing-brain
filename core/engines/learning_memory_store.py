"""
Step 60 - Learning Memory Store

Mục tiêu:
- lưu learning / feedback / evolution rules
- dùng lại ở lần chạy sau
"""

import json
from datetime import datetime
from pathlib import Path


class LearningMemoryStore:
    def __init__(self, save_dir="performance/learning"):
        self.project_root = Path(__file__).resolve().parents[2]
        self.save_dir = self.project_root / save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, learning, feedback_profile, evolution_rules):
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "learning": learning,
            "feedback_profile": feedback_profile,
            "evolution_rules": evolution_rules,
        }

        file_path = (
            self.save_dir
            / f"learning_snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)

        return file_path

    def load_latest_snapshot(self):
        files = sorted(self.save_dir.glob("learning_snapshot_*.json"), reverse=True)
        if not files:
            return None

        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)
