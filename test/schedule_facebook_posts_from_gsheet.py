from dotenv import load_dotenv
load_dotenv()
import json
import os

from core.jobs.publish_ready_organic_posts_to_facebook_job import (
    run_publish_ready_organic_posts_to_facebook_job,
)


def main():
    brand_id = os.getenv("PUBLISH_BRAND_ID", "AODAI")
    page_id = os.getenv("PUBLISH_PAGE_ID", "AODAI_FB_US")
    platform_id = os.getenv("PUBLISH_PLATFORM_ID", "facebook")
    page_url = os.getenv("PUBLISH_PAGE_URL")

    result = run_publish_ready_organic_posts_to_facebook_job(
        brand_id=brand_id,
        page_id=page_id,
        platform_id=platform_id,
        page_url=page_url,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
