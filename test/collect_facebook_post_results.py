from dotenv import load_dotenv
load_dotenv()

import json
from core.jobs.facebook_results_collector_job import FacebookResultsCollectorJob

if __name__ == "__main__":
    print(json.dumps(FacebookResultsCollectorJob().run(), ensure_ascii=False, indent=2))
