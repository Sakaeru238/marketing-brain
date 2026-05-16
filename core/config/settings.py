import platform
from pathlib import Path


OS_TYPE = platform.system()

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CORE_DIR = PROJECT_ROOT / "core"
EXTERNAL_DIR = PROJECT_ROOT / "external"
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
PERFORMANCE_DIR = PROJECT_ROOT / "performance"
ASSETS_DIR = PROJECT_ROOT / "assets"
RUN_DIR = PROJECT_ROOT / "run"
AUTOMATION_DIR = PROJECT_ROOT / "automation"