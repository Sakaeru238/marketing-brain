import os
from core.engines.brand_intake_loader import BrandIntakeLoader

DEFAULT_CLAUDE_MODE = os.getenv("CLAUDE_MODE", "api").strip().lower()

CLAUDE_MODE = DEFAULT_CLAUDE_MODE

def _normalize_mode(mode: str) -> str:
    mode = (mode or "").strip().lower()

    if mode in {"api", "pro", "pro_manual", "manual"}:
        if mode == "manual":
            return "pro_manual"
        if mode == "pro":
            return "pro_manual"
        return mode

    return "api"


def get_claude_mode(test_id=None, control_panel_file=None):
    if test_id and str(test_id).strip().lower().startswith("test_"):
        return "pro_manual"

    return _normalize_mode(DEFAULT_CLAUDE_MODE)