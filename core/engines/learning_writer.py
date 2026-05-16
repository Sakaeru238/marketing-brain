import json
from datetime import datetime
from core.config.paths import PERFORMANCE_DIR


class LearningWriter:

    def __init__(self):
        self.learning_dir = PERFORMANCE_DIR / "learning"
        self.learning_dir.mkdir(parents=True, exist_ok=True)

    def save(self, learning_data):

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        file_path = self.learning_dir / f"learning_{timestamp}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(learning_data, f, indent=2)

        return {"file_name": file_path.name, "file_path": str(file_path)}
