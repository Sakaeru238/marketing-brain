import argparse

from core.pipeline.master_pipeline import MasterPipeline
from core.engines.test_result_exporter import TestResultExporter
from core.config.paths import DATA_DIR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--_id", dest="_id", required=False)
    parser.add_argument("--test-id", dest="_id", required=False)
    parser.add_argument(
        "--control-panel-file",
        default=str(DATA_DIR / "control_panels" / "marketing_brain_control_panel.xlsx"),
    )
    args = parser.parse_args()

    if not args._id:
        raise ValueError("Bạn phải truyền --_id hoặc --test-id")

    pipeline = MasterPipeline()
    exporter = TestResultExporter()

    result = pipeline.run(
        _id=args._id,
        control_panel_file=args.control_panel_file,
    )

    json_file = exporter.export_json(args._id, result)
    excel_file = exporter.export_excel(args._id, result)

    print("\n=== OFFICIAL REAL RUN COMPLETED ===")
    print("TEST ID:", args._id)
    print("CLAUDE MODE:", result.get("claude_mode"))
    print("TOP CAMPAIGN EXISTS:", result.get("top_campaign") is not None)
    print("CLAUDE PARSED:", result.get("claude_parsed") is not None)
    print("JSON:", json_file)
    print("EXCEL:", excel_file)


if __name__ == "__main__":
    main()
