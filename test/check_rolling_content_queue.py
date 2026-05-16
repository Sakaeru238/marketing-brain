from dotenv import load_dotenv
load_dotenv()

import json
from core.jobs.rolling_content_queue_job import RollingContentQueueJob

if __name__ == "__main__":
    print(json.dumps(RollingContentQueueJob().run(), ensure_ascii=False, indent=2))
