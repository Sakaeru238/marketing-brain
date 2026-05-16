"""
Claude Response Parser
----------------------

Step 55C - Claude Response Parser

Mục tiêu:
- Nhận output từ Claude (Pro hoặc API)
- Parse output thành structured data
- Detect format của Claude output
- Save output để dùng cho learning loop

Không thay đổi logic cũ
Không đổi tên function cũ
Chỉ bổ sung module mới
"""

import json
import re
from datetime import datetime
from pathlib import Path


class ClaudeResponseParser:
    """
    Claude Response Parser

    Nhiệm vụ:
    - Parse response từ Claude
    - Detect response format
    - Save parsed result
    """

    def __init__(self, save_dir="performance/claude_responses"):
        """
        Initialize parser

        save_dir ở đây sẽ được resolve từ PROJECT ROOT,
        không phụ thuộc thư mục hiện tại khi chạy lệnh.
        """

        # Lấy project root:
        # core/engines/claude_response_parser.py
        # -> engines
        # -> core
        # -> project root
        self.project_root = Path(__file__).resolve().parents[2]

        # Build absolute path từ root project
        self.save_dir = self.project_root / save_dir

        # Tạo folder nếu chưa tồn tại
        self.save_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------
    # MAIN PARSER
    # -----------------------------------------------------

    def parse(self, response, source_mode=None):
        """
        Parse Claude response

        Parameters
        ----------
        response : str | dict
            Output từ Claude

        source_mode : str
            claude_pro hoặc claude_api

        Returns
        -------
        dict
            Parsed response
        """

        parsed = {
            "timestamp": datetime.utcnow().isoformat(),
            "source_mode": source_mode,
            "raw_response": response,
            "parsed": None,
            "format": None,
            "status": "unknown",
        }

        try:
            # Extract JSON từ response
            parsed["parsed"] = self._extract_json(response)

            # Detect response format
            parsed["format"] = self._detect_format(parsed["parsed"])

            parsed["status"] = "parsed"

        except Exception as e:

            parsed["status"] = "error"
            parsed["error"] = str(e)

        return parsed

    # -----------------------------------------------------
    # JSON EXTRACTION
    # -----------------------------------------------------

    def _extract_json(self, response):
        """
        Extract JSON từ Claude response

        Support:
        - dict
        - JSON string
        - JSON trong ```json block
        - fallback text
        """

        # Case 1: response đã là dict
        if isinstance(response, dict):
            return response

        # Case 2: thử parse JSON trực tiếp
        try:
            return json.loads(response)
        except:
            pass

        # Case 3: tìm JSON trong code block
        json_match = re.search(r"```json(.*?)```", response, re.DOTALL)

        if json_match:
            json_str = json_match.group(1)

            return json.loads(json_str)

        # fallback: trả về text
        return {"text": response}

    # -----------------------------------------------------
    # FORMAT DETECTION
    # -----------------------------------------------------

    def _detect_format(self, parsed):
        """
        Detect Claude output format

        Return:
        -------
        str
            format type
        """

        if not isinstance(parsed, dict):
            return "unknown"

        # Claude execution output
        if "campaign" in parsed:
            return "claude_execution"

        # Claude review output
        if "review" in parsed:
            return "claude_review"

        # Claude refinement output
        if "refinement" in parsed:
            return "claude_refinement"

        # generic json
        return "generic"

    # -----------------------------------------------------
    # SAVE PARSED RESPONSE
    # -----------------------------------------------------

    def save(self, parsed):
        """
        Save parsed response

        Returns
        -------
        Path
            file path saved
        """

        filename = f"claude_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

        file_path = self.save_dir / filename

        with open(file_path, "w") as f:
            json.dump(parsed, f, indent=2)

        return file_path
