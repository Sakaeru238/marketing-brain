import os
from core.config.claude_mode_settings import CLAUDE_MODE

# =========================================================
# CẤU HÌNH CLAUDE API
#
# Chỉ sẵn sàng khi:
# - CLAUDE_MODE = "api"
# - có API key
# =========================================================

CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")

CLAUDE_MODEL = os.getenv(
    "CLAUDE_MODEL",
    "claude-sonnet-4-20250514"
).strip()

CLAUDE_API_ENABLED = CLAUDE_MODE == "api"