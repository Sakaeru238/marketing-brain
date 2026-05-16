import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.pipeline.master_pipeline import MasterPipeline


def test_step_55c():
    pipeline = MasterPipeline()

    response = """
    ```json
    {
        "campaign": {
            "angle": "Vietnamese Coffee",
            "cta": "Shop Now"
        }
    }
    ```
    """

    result = pipeline.parse_claude_response(response=response, source_mode="test")

    print("RESULT:", result)


if __name__ == "__main__":
    test_step_55c()
