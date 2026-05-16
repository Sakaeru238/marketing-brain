import json
from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.pipeline.page_assessment_pipeline import PageAssessmentPipeline

def main():
    output = PageAssessmentPipeline().run(
        claude_api_adapter=ClaudeAPIAdapter(),
        brand_id="AODAI",
        niche_id="vietnamese_coffee",
        page_id="AODAI_FB_US",
        platform_id="facebook",
        page_url="https://facebook.com/your-page-url",
        current_followers=0,
        current_likes=0,
        target_followers=1000,
        target_likes=1000,
        target_market="US",
        target_timezone="America/New_York",
    )
    print(json.dumps({
        "status": output.get("status"),
        "output_file": "data/output/organic/page_assessment/page_assessment_output.json",
        "parse_error": output.get("claude_page_assessment_parse_error"),
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
