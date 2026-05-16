"""
Step 56 - Claude Learning Engine

Mục tiêu:
- đọc parsed Claude responses
- extract learning signals
- chuẩn hóa learning format
- trả về learning memory

Không ảnh hưởng logic cũ
"""

import json
from pathlib import Path
from datetime import datetime


class ClaudeLearningEngine:

    def __init__(self, response_dir="performance/claude_responses"):
        """
        Initialize Claude Learning Engine

        Parameters
        ----------
        response_dir : str
            thư mục chứa parsed Claude responses
        """

        self.response_dir = Path(response_dir)

    # -----------------------------------------------------
    # LOAD RESPONSES
    # -----------------------------------------------------

    def load_responses(self):
        """
        Load tất cả parsed Claude responses

        Returns
        -------
        list
        """

        responses = []

        if not self.response_dir.exists():
            return responses

        for file in self.response_dir.glob("*.json"):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                    responses.append(data)
            except Exception:
                continue

        return responses

    # -----------------------------------------------------
    # EXTRACT LEARNING SIGNALS
    # -----------------------------------------------------

    def extract_learning(self, responses):
        """
        Extract learning signals từ Claude responses
        """

        learning = {
            "timestamp": datetime.utcnow().isoformat(),
            "campaign_angles": [],
            "cta_patterns": [],
            "audience_patterns": [],
            "formats": [],
        }

        for response in responses:

            parsed = response.get("parsed", {})

            if not isinstance(parsed, dict):
                continue

            # Campaign angle
            campaign = parsed.get("campaign")

            if campaign:

                angle = campaign.get("angle")
                cta = campaign.get("cta")
                audience = campaign.get("audience")

                if angle:
                    learning["campaign_angles"].append(angle)

                if cta:
                    learning["cta_patterns"].append(cta)

                if audience:
                    learning["audience_patterns"].append(audience)

            # Format learning
            format_type = response.get("format")

            if format_type:
                learning["formats"].append(format_type)

        return learning

    # -----------------------------------------------------
    # MAIN LEARNING FUNCTION
    # -----------------------------------------------------

    def learn(self):
        """
        Main learning pipeline
        """

        responses = self.load_responses()

        learning = self.extract_learning(responses)

        return learning
