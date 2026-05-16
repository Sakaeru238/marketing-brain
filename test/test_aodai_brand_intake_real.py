import os
import sys
from pprint import pprint

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.pipeline.master_pipeline import MasterPipeline


def test_aodai_brand_intake_real():
    pipeline = MasterPipeline()

    test_id = "TEST_AODAI_01"

    brand_intake = pipeline.build_brand_intake(test_id)

    print("\n=== BRAND INTAKE ===")
    pprint(brand_intake)

    # Kiểm tra các điểm trọng yếu trước khi chạy sâu hơn
    print("\n=== QUICK CHECK ===")
    print("brand_name:", brand_intake["brand"]["brand_name"])
    print("product_name:", brand_intake["product"]["product_name"])
    print("offer_text:", brand_intake["offer"]["offer_text"])
    print("expected_focus:", brand_intake["expected_focus"])
    print("audience_seed:", brand_intake["audience_seed"]["audience_name"])

    if brand_intake["audience_ai_expanded"]:
        print(
            "audience_ai_expanded:",
            brand_intake["audience_ai_expanded"]["audience_name"],
        )
    else:
        print("audience_ai_expanded: None")

    # Guardrail check rất quan trọng cho AoDai
    all_text = str(brand_intake).lower()
    forbidden = ["coconut", "cacao", "lemon", "flavored coffee"]
    found_forbidden = [x for x in forbidden if x in all_text]

    print("\n=== GUARDRAIL CHECK ===")
    print("forbidden_terms_found:", found_forbidden)

    print("\n=== RESULT ===")
    print("PASS" if not found_forbidden else "FAIL")


if __name__ == "__main__":
    test_aodai_brand_intake_real()
