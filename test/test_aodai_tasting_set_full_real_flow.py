import os
import sys
from pprint import pprint

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("FILE STARTED")

from core.pipeline.master_pipeline import MasterPipeline
from core.engines.brand_intake_loader import BrandIntakeLoader

CONTROL_PANEL_FILE = os.path.join(
    PROJECT_ROOT,
    "data",
    "control_panels",
    "marketing_brain_control_panel.xlsx",
)

TEST_ID = "TEST_AODAI_01"


def test_aodai_tasting_set_full_real_flow():
    print("TEST FUNCTION STARTED")

    loader = BrandIntakeLoader(CONTROL_PANEL_FILE)
    pipeline = MasterPipeline()

    print("\n============================")
    print("ROUND 1 — BRAND INTAKE")
    print("============================")

    package = loader.load_test_run_package(TEST_ID)

    brand = package["brand"]
    product = package["product"]

    print("Brand:", brand["brand_name"])
    print("Product:", product["product_name"])

    # round 1 check

    round_1_pass = True

    if "AoDai" not in brand["brand_name"]:
        round_1_pass = False

    if "Tasting" not in product["product_name"]:
        round_1_pass = False

    print("Round 1 PASS:", round_1_pass)

    print("\n============================")
    print("ROUND 2 — PIPELINE STRATEGY")
    print("============================")

    # run pipeline

    pipeline.set_brand_intake(package)

    result = pipeline.run()

    campaigns = result.get("top_campaigns", [])

    pprint(campaigns)

    round_2_pass = len(campaigns) >= 1

    print("Round 2 PASS:", round_2_pass)

    print("\n============================")
    print("FINAL RESULT")
    print("============================")

    final_pass = round_1_pass and round_2_pass

    print("FINAL PASS:", final_pass)


if __name__ == "__main__":
    test_aodai_tasting_set_full_real_flow()
