from dotenv import load_dotenv
load_dotenv()

import json
from core.jobs.local_daily_orchestrator import LocalDailyOrchestrator

if __name__ == "__main__":
    print(json.dumps(LocalDailyOrchestrator().run_daily(), ensure_ascii=False, indent=2))
