import json
import os
from datetime import datetime


class OutputWriter:
    def __init__(self):
        self.base_path = "performance/experiments"

    def save(self, data):

        os.makedirs(self.base_path, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        file_path = f"{self.base_path}/creative_{timestamp}.json"

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        return file_path