import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.pipeline.master_pipeline import MasterPipeline
from core.engines.brand_intake_loader import BrandIntakeLoader
from core.engines.test_result_exporter import TestResultExporter


# =========================================================
# DEFAULT FILE PATHS
# =========================================================

DEFAULT_CONTROL_PANEL_FILE = os.path.join(
    PROJECT_ROOT,
    "data",
    "control_panels",
    "marketing_brain_control_panel.xlsx",
)

DEFAULT_MANUAL_INPUT_DIR = os.path.join(
    PROJECT_ROOT,
    "data",
    "manual_input",
)


# =========================================================
# HELPERS
# =========================================================


def to_text(data):
    return json.dumps(data, ensure_ascii=False, default=str).lower()


def read_text_file(file_path):
    if not file_path:
        return None
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def safe_len(value):
    if value is None:
        return 0
    if isinstance(value, (list, tuple, dict, str)):
        return len(value)
    return 0


def build_manual_claude_response_path(test_id):
    """
    File Claude manual response mặc định.
    Có thể thay bằng --claude-response-file khi chạy.
    """
    filename = f"{test_id}_claude_response.txt"
    return os.path.join(DEFAULT_MANUAL_INPUT_DIR, filename)


def summarize_brand_intake(brand_intake):
    if not isinstance(brand_intake, dict):
        return {}

    return {
        "test_id": brand_intake.get("test_id"),
        "objective": brand_intake.get("objective"),
        "claude_mode": brand_intake.get("claude_mode"),
        "use_brand_intake": brand_intake.get("use_brand_intake"),
        "use_alysha_strategy": brand_intake.get("use_alysha_strategy"),
        "expected_focus": brand_intake.get("expected_focus"),
        "success_check": brand_intake.get("success_check"),
        "brand_name": brand_intake.get("brand", {}).get("brand_name"),
        "product_name": brand_intake.get("product", {}).get("product_name"),
        "offer_text": brand_intake.get("offer", {}).get("offer_text"),
        "core_truth_count": safe_len(brand_intake.get("core_truth")),
        "guardrails_count": safe_len(brand_intake.get("guardrails")),
        "product_benefits_count": safe_len(brand_intake.get("product_benefits")),
        "product_usage_steps_count": safe_len(brand_intake.get("product_usage_steps")),
        "has_seed_audience": bool(brand_intake.get("audience_seed")),
        "has_ai_expanded_audience": bool(brand_intake.get("audience_ai_expanded")),
    }


def summarize_pipeline_result(result):
    if not isinstance(result, dict):
        return {}

    return {
        "has_research": result.get("research") is not None,
        "has_insight": result.get("insight") is not None,
        "has_strategy": result.get("strategy") is not None,
        "has_creative": result.get("creative") is not None,
        "campaign_count": safe_len(result.get("campaigns")),
        "ranked_campaign_count": safe_len(result.get("ranked_campaigns")),
        "top_campaign_exists": result.get("top_campaign") is not None,
        "top_campaigns_count": safe_len(result.get("top_campaigns")),
        "claude_mode": result.get("claude_mode"),
        "claude_api_status": result.get("claude_api_status"),
        "brief_file": result.get("brief_file"),
        "multi_brief_file": result.get("multi_brief_file"),
        "human_handoff_file": result.get("human_handoff_file"),
        "report_file": result.get("report"),
    }


def build_real_run_payload(
    test_id,
    control_panel_file,
    manual_claude_response_file,
    package,
    brand_intake,
    pipeline_result,
    claude_parse_result,
    learning_result,
    execution_trace,
):
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "test_id": test_id,
        "control_panel_file": control_panel_file,
        "manual_claude_response_file": manual_claude_response_file,
        "excel_test_run_row": package.get("test_run"),
        "excel_brand_row": package.get("brand"),
        "excel_product_row": package.get("product"),
        "excel_offer_row": package.get("offer"),
        "excel_seed_audience_row": package.get("seed_audience"),
        "excel_ai_audience_row": package.get("ai_audience"),
        "excel_brand_truth_rows": package.get("brand_truths"),
        "excel_brand_guardrail_rows": package.get("brand_guardrails"),
        "excel_product_benefit_rows": package.get("product_benefits"),
        "excel_product_usage_rows": package.get("product_usage"),
        "brand_intake_summary": summarize_brand_intake(brand_intake),
        "brand_intake_raw": brand_intake,
        "pipeline_summary": summarize_pipeline_result(pipeline_result),
        "pipeline_top_campaign": (
            pipeline_result.get("top_campaign")
            if isinstance(pipeline_result, dict)
            else None
        ),
        "pipeline_top_campaigns": (
            pipeline_result.get("top_campaigns")
            if isinstance(pipeline_result, dict)
            else None
        ),
        "pipeline_raw": pipeline_result,
        "claude_parse": claude_parse_result,
        "learning": learning_result,
        "execution_trace": execution_trace,
        "final_pass": execution_trace.get("final_pass"),
    }


# =========================================================
# EXECUTION STEPS
# =========================================================


def load_excel_package(loader, test_id):
    return loader.load_test_run_package(test_id)


def build_brand_intake(pipeline, test_id):
    return pipeline.build_brand_intake(test_id)


def run_pipeline_as_is(pipeline):
    """
    Chạy source hiện tại đúng như production code đang có.
    Không inject thêm test-only wrapper.
    """
    return pipeline.run()


def maybe_parse_manual_claude_response(
    pipeline, claude_mode, manual_claude_response_file
):
    """
    Chỉ parse nếu:
    - mode là pro_manual
    - có file Claude response thật
    """
    result = {
        "enabled": False,
        "source_mode": None,
        "response_file_exists": False,
        "parsed": None,
        "parsed_file": None,
        "status": "skipped",
        "reason": None,
    }

    if claude_mode != "pro_manual":
        result["reason"] = "claude_mode_is_not_pro_manual"
        return result

    result["enabled"] = True
    result["source_mode"] = "pro_manual"
    result["response_file_exists"] = os.path.exists(manual_claude_response_file)

    if not result["response_file_exists"]:
        result["status"] = "skipped"
        result["reason"] = "manual_claude_response_file_not_found"
        return result

    raw_response = read_text_file(manual_claude_response_file)
    if not raw_response:
        result["status"] = "skipped"
        result["reason"] = "manual_claude_response_file_empty"
        return result

    parsed, parsed_file = pipeline.parse_claude_response(
        response=raw_response,
        source_mode="pro_manual",
        auto_save=True,
    )

    result["parsed"] = parsed
    result["parsed_file"] = str(parsed_file) if parsed_file else None
    result["status"] = "parsed" if parsed.get("status") == "parsed" else "error"
    return result


def maybe_run_learning_after_parse(pipeline, claude_parse_result):
    """
    Chỉ chạy learning nếu đã có parsed Claude response thật.
    """
    result = {
        "enabled": False,
        "status": "skipped",
        "reason": None,
        "learning": None,
        "feedback_profile": None,
        "feedback_file": None,
        "generator_learning": None,
        "evolution_rules": None,
        "validation_result": None,
        "snapshot_file": None,
        "evaluation": None,
    }

    if claude_parse_result.get("status") != "parsed":
        result["reason"] = "claude_parse_not_available"
        return result

    result["enabled"] = True

    learning = pipeline.learn_from_claude()
    feedback_profile, feedback_file = pipeline.build_campaign_feedback()
    evolution_rules = pipeline.build_evolution_rules()
    validation_result = pipeline.validate_evolution_rules()
    snapshot_file = pipeline.save_learning_snapshot()

    result["learning"] = learning
    result["feedback_profile"] = feedback_profile
    result["feedback_file"] = str(feedback_file) if feedback_file else None
    result["evolution_rules"] = evolution_rules
    result["validation_result"] = validation_result
    result["snapshot_file"] = str(snapshot_file) if snapshot_file else None
    result["status"] = "completed"

    return result


# =========================================================
# MAIN REAL TEST
# =========================================================


def run_real_flow_test(test_id, control_panel_file, manual_claude_response_file):
    pipeline = MasterPipeline()
    loader = BrandIntakeLoader(control_panel_file)
    exporter = TestResultExporter()

    execution_trace = {
        "test_id": test_id,
        "control_panel_loaded": False,
        "excel_package_loaded": False,
        "brand_intake_built": False,
        "pipeline_run_executed": False,
        "brand_intake_used_directly_by_pipeline": False,
        "claude_mode_from_excel": None,
        "manual_claude_response_attempted": False,
        "manual_claude_response_parsed": False,
        "learning_executed": False,
        "feedback_executed": False,
        "evolution_executed": False,
        "result_json_exported": False,
        "result_excel_exported": False,
        "final_pass": False,
    }

    # -----------------------------------------------------
    # 1. Load Excel package thật
    # -----------------------------------------------------
    execution_trace["control_panel_loaded"] = os.path.exists(control_panel_file)

    package = load_excel_package(loader, test_id)
    execution_trace["excel_package_loaded"] = package is not None

    # -----------------------------------------------------
    # 2. Build brand-intake thật
    # -----------------------------------------------------
    brand_intake = build_brand_intake(pipeline, test_id)
    execution_trace["brand_intake_built"] = brand_intake is not None

    # Cờ này phản ánh thực trạng source hiện tại.
    # Hiện source vẫn chưa inject brand_intake trực tiếp vào pipeline.run().
    execution_trace["brand_intake_used_directly_by_pipeline"] = False

    # -----------------------------------------------------
    # 3. Run pipeline thật như source đang có
    # -----------------------------------------------------
    pipeline_result = run_pipeline_as_is(pipeline)
    execution_trace["pipeline_run_executed"] = pipeline_result is not None
    execution_trace["claude_mode_from_excel"] = brand_intake.get("claude_mode")

    # -----------------------------------------------------
    # 4. Claude parse thật nếu có manual response file
    # -----------------------------------------------------
    claude_parse_result = maybe_parse_manual_claude_response(
        pipeline=pipeline,
        claude_mode=brand_intake.get("claude_mode"),
        manual_claude_response_file=manual_claude_response_file,
    )
    execution_trace["manual_claude_response_attempted"] = claude_parse_result.get(
        "enabled", False
    )
    execution_trace["manual_claude_response_parsed"] = (
        claude_parse_result.get("status") == "parsed"
    )

    # -----------------------------------------------------
    # 5. Learning thật nếu có parsed Claude response
    # -----------------------------------------------------
    learning_result = maybe_run_learning_after_parse(
        pipeline=pipeline,
        claude_parse_result=claude_parse_result,
    )
    execution_trace["learning_executed"] = learning_result.get("enabled", False)
    execution_trace["feedback_executed"] = (
        learning_result.get("feedback_profile") is not None
    )
    execution_trace["evolution_executed"] = (
        learning_result.get("evolution_rules") is not None
    )

    # -----------------------------------------------------
    # 6. Build payload thật
    # -----------------------------------------------------
    payload = build_real_run_payload(
        test_id=test_id,
        control_panel_file=control_panel_file,
        manual_claude_response_file=manual_claude_response_file,
        package=package,
        brand_intake=brand_intake,
        pipeline_result=pipeline_result,
        claude_parse_result=claude_parse_result,
        learning_result=learning_result,
        execution_trace=execution_trace,
    )

    # -----------------------------------------------------
    # 7. Export kết quả thật
    # -----------------------------------------------------
    json_file = exporter.export_json(test_id, payload)
    excel_file = exporter.export_excel(test_id, payload)

    execution_trace["result_json_exported"] = json_file is not None
    execution_trace["result_excel_exported"] = excel_file is not None

    # -----------------------------------------------------
    # 8. Final pass
    # -----------------------------------------------------
    # Final pass ở đây chỉ phản ánh:
    # - input thật đọc được
    # - pipeline thật chạy được
    # - kết quả thật export được
    #
    # Không giả vờ rằng brand_intake đã được pipeline dùng trực tiếp,
    # nếu source hiện tại chưa làm điều đó.
    execution_trace["final_pass"] = (
        execution_trace["control_panel_loaded"]
        and execution_trace["excel_package_loaded"]
        and execution_trace["brand_intake_built"]
        and execution_trace["pipeline_run_executed"]
        and execution_trace["result_json_exported"]
        and execution_trace["result_excel_exported"]
    )

    payload["execution_trace"] = execution_trace
    payload["final_pass"] = execution_trace["final_pass"]

    # Ghi lại payload cuối cùng một lần nữa để execution_trace mới nhất nằm trong file JSON
    json_file = exporter.export_json(test_id, payload)
    excel_file = exporter.export_excel(test_id, payload)

    return payload, json_file, excel_file


# =========================================================
# CLI
# =========================================================


def main():
    parser = argparse.ArgumentParser(
        description="Run real flow test from Excel control panel."
    )
    parser.add_argument(
        "--test-id", required=True, help="test_id trong sheet Test_Runs"
    )
    parser.add_argument(
        "--control-panel-file",
        default=DEFAULT_CONTROL_PANEL_FILE,
        help="Đường dẫn file Excel control panel",
    )
    parser.add_argument(
        "--claude-response-file",
        default=None,
        help="Đường dẫn file Claude response thật (manual). Nếu bỏ trống sẽ dùng mặc định theo test_id.",
    )

    args = parser.parse_args()

    test_id = args.test_id
    control_panel_file = args.control_panel_file
    manual_claude_response_file = (
        args.claude_response_file or build_manual_claude_response_path(test_id)
    )

    payload, json_file, excel_file = run_real_flow_test(
        test_id=test_id,
        control_panel_file=control_panel_file,
        manual_claude_response_file=manual_claude_response_file,
    )

    print("\n============================")
    print("REAL FLOW TEST COMPLETED")
    print("============================")
    print("TEST ID:", payload.get("test_id"))
    print("FINAL PASS:", payload.get("final_pass"))

    print("\n--- BRAND INTAKE SUMMARY ---")
    print(
        json.dumps(
            payload.get("brand_intake_summary", {}), indent=2, ensure_ascii=False
        )
    )

    print("\n--- PIPELINE SUMMARY ---")
    print(json.dumps(payload.get("pipeline_summary", {}), indent=2, ensure_ascii=False))

    print("\n--- EXECUTION TRACE ---")
    print(json.dumps(payload.get("execution_trace", {}), indent=2, ensure_ascii=False))

    print("\n--- RESULT FILES ---")
    print("JSON :", json_file)
    print("EXCEL:", excel_file)


if __name__ == "__main__":
    main()
