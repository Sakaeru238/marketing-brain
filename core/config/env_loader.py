import os
from pathlib import Path
from dotenv import load_dotenv


def load_env():
    """
    Load .env file từ root project.
    """
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"

    if env_path.exists():
        load_dotenv(env_path)

    return {
        "CLAUDE_API_KEY": os.getenv("CLAUDE_API_KEY"),
    }
