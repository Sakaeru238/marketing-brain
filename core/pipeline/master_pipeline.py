from core.pipeline.research_pipeline import ResearchPipeline
from core.pipeline.insight_pipeline import InsightPipeline
from core.pipeline.strategy_pipeline import StrategyPipeline
from core.pipeline.creative_pipeline import CreativePipeline

from core.engines.output_writer import OutputWriter
from core.engines.learning_engine import LearningEngine
from core.engines.learning_writer import LearningWriter
from core.engines.report_writer import ReportWriter
from core.engines.campaign_generator import CampaignGenerator
from core.engines.campaign_ranker import CampaignRanker
from core.engines.brief_writer import BriefWriter
from core.engines.multi_brief_writer import MultiBriefWriter
from core.engines.claude_package_writer import ClaudePackageWriter
from core.engines.claude_handoff_writer import ClaudeHandoffWriter
from core.engines.human_handoff_writer import HumanHandoffWriter
from core.engines.claude_pro_writer import ClaudeProWriter
from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.engines.claude_response_parser import ClaudeResponseParser
from core.engines.claude_learning_engine import ClaudeLearningEngine
from core.engines.campaign_feedback_loop import CampaignFeedbackLoop
from core.engines.generator_learning_adapter import GeneratorLearningAdapter
from core.engines.evolution_engine import EvolutionEngine
from core.engines.learning_memory_store import LearningMemoryStore
from core.engines.pipeline_guardrails import PipelineGuardrails
from core.engines.pipeline_evaluator import PipelineEvaluator
from core.engines.brand_intake_engine import BrandIntakeEngine
from core.loaders.customer_feedback_loader import CustomerFeedbackLoader

from core.config.claude_mode_settings import get_claude_mode
import json
from core.config.paths import INSIGHT_DIR
import warnings
from urllib3.exceptions import NotOpenSSLWarning
from pathlib import Path

warnings.simplefilter("ignore", NotOpenSSLWarning)


class MasterPipeline:
    def __init__(self):
        # =====================================================
        # Pipeline chính
        # =====================================================
        self.research_pipeline = ResearchPipeline()
        self.insight_pipeline = InsightPipeline()
        self.strategy_pipeline = StrategyPipeline()
        self.creative_pipeline = CreativePipeline()

        # =====================================================
        # Engine hỗ trợ output / learning / report
        # =====================================================
        self.writer = OutputWriter()
        self.learning_engine = LearningEngine()
        self.learning_writer = LearningWriter()
        self.report_writer = ReportWriter()

        # =====================================================
        # Campaign system
        # =====================================================
        self.campaign_generator = CampaignGenerator()
        self.campaign_ranker = CampaignRanker()

        # =====================================================
        # Brief / handoff system
        # =====================================================
        self.brief_writer = BriefWriter()
        self.multi_brief_writer = MultiBriefWriter()
        self.human_handoff_writer = HumanHandoffWriter()

        # =====================================================
        # Claude system
        # =====================================================
        self.claude_package_writer = ClaudePackageWriter()
        self.claude_handoff_writer = ClaudeHandoffWriter()
        self.claude_pro_writer = ClaudeProWriter()
        self.claude_api_adapter = ClaudeAPIAdapter()

        # =====================================================
        # Claude response parser / learning
        # =====================================================
        self.claude_response_parser = ClaudeResponseParser()
        self.claude_learning_engine = ClaudeLearningEngine()

        # =====================================================
        # Feedback / evolution / evaluation
        # =====================================================
        self.campaign_feedback_loop = CampaignFeedbackLoop()
        self.generator_learning_adapter = GeneratorLearningAdapter()
        self.evolution_engine = EvolutionEngine()
        self.learning_memory_store = LearningMemoryStore()
        self.pipeline_guardrails = PipelineGuardrails()
        self.pipeline_evaluator = PipelineEvaluator()

        # =====================================================
        # Brand Intake
        # =====================================================
        self.brand_intake_engine = BrandIntakeEngine()

        # =====================================================
        # VOC / Customer Feedback
        # =====================================================
        self.customer_feedback_loader = CustomerFeedbackLoader()

    # ---------------------------------------------------
    # Step 1 - Brand Intake
    # ---------------------------------------------------
    def build_brand_intake(
        self,
        _id,
        control_panel_file=None,
        claude_mode="off",
        claude_api_adapter=None,
    ):
        """
        Build brand-intake context từ Excel theo _id.
        Đây là business logic final, không phải function phục vụ test.
        """
        if control_panel_file:
            engine = BrandIntakeEngine(workbook_path=control_panel_file)
            return engine.build_from_test_id(
                _id,
                claude_mode=claude_mode,
                claude_api_adapter=claude_api_adapter,
            )

        return self.brand_intake_engine.build_from_test_id(
            _id,
            claude_mode=claude_mode,
            claude_api_adapter=claude_api_adapter,
        )

    # ---------------------------------------------------
    # Step 55C - Claude Response Parser
    # ---------------------------------------------------
    def parse_claude_response(self, response, source_mode=None, auto_save=True):
        """
        Parse Claude response và optionally save.
        Giữ return tuple để không phá interface cũ.
        """
        parsed = self.claude_response_parser.parse(response, source_mode=source_mode)

        file_path = None
        if auto_save:
            file_path = self.claude_response_parser.save(parsed)

        return parsed, file_path

    # ---------------------------------------------------
    # Step 56 - Learn từ Claude responses
    # ---------------------------------------------------
    def learn_from_claude(self):
        learning = self.claude_learning_engine.learn()
        return learning

    # ---------------------------------------------------
    # Step 57 - Build campaign feedback
    # ---------------------------------------------------
    def build_campaign_feedback(self):
        learning = self.learn_from_claude()
        feedback_profile = self.campaign_feedback_loop.build_feedback_profile(learning)
        feedback_file = self.campaign_feedback_loop.save_feedback_profile(
            feedback_profile
        )
        return feedback_profile, feedback_file

    # ---------------------------------------------------
    # Step 57 - Apply feedback vào campaigns
    # ---------------------------------------------------
    def apply_campaign_feedback(self, campaigns):
        feedback_profile, feedback_file = self.build_campaign_feedback()

        adjusted_campaigns = self.campaign_feedback_loop.apply_feedback(
            campaigns, feedback_profile
        )

        return {
            "feedback_profile": feedback_profile,
            "feedback_file": feedback_file,
            "adjusted_campaigns": adjusted_campaigns,
        }

    # ---------------------------------------------------
    # Step 58 - Apply learning vào generator
    # ---------------------------------------------------
    def apply_generator_learning(self, campaigns):
        feedback_profile, _ = self.build_campaign_feedback()
        hints = self.generator_learning_adapter.build_generator_hints(feedback_profile)
        adjusted = self.generator_learning_adapter.apply_hints(campaigns, hints)

        return {
            "hints": hints,
            "adjusted_campaigns": adjusted,
        }

    # ---------------------------------------------------
    # Step 59 - Build evolution rules
    # ---------------------------------------------------
    def build_evolution_rules(self):
        learning = self.learn_from_claude()
        feedback_profile, _ = self.build_campaign_feedback()
        evolution_rules = self.evolution_engine.build_rules(learning, feedback_profile)
        return evolution_rules

    # ---------------------------------------------------
    # Step 60 - Save learning snapshot
    # ---------------------------------------------------
    def save_learning_snapshot(self):
        learning = self.learn_from_claude()
        feedback_profile, _ = self.build_campaign_feedback()
        evolution_rules = self.build_evolution_rules()

        snapshot_file = self.learning_memory_store.save_snapshot(
            learning, feedback_profile, evolution_rules
        )

        return snapshot_file

    # ---------------------------------------------------
    # Step 62A - Validate evolution rules
    # ---------------------------------------------------
    def validate_evolution_rules(self):
        evolution_rules = self.build_evolution_rules()
        validation = self.pipeline_guardrails.validate_evolution_rules(evolution_rules)

        return {
            "evolution_rules": evolution_rules,
            "validation": validation,
        }

    # ---------------------------------------------------
    # Step 62B - Evaluate generator learning
    # ---------------------------------------------------
    def evaluate_generator_learning(self, campaigns):
        result = self.apply_generator_learning(campaigns)
        adjusted_campaigns = result["adjusted_campaigns"]

        evaluation = self.pipeline_evaluator.evaluate_campaigns(adjusted_campaigns)

        return {
            "hints": result["hints"],
            "adjusted_campaigns": adjusted_campaigns,
            "evaluation": evaluation,
        }

    # ---------------------------------------------------
    # Internal helper - normalize Claude API raw response
    # ---------------------------------------------------
    def _normalize_claude_api_response(self, api_result):
        """
        Chuẩn hóa response thật từ Claude API adapter.
        Không phải function test-only; đây là business normalization final.
        """
        if api_result is None:
            return None

        if isinstance(api_result, str):
            return api_result

        if isinstance(api_result, dict):
            for key in ["response_text", "response", "content", "result", "text"]:
                value = api_result.get(key)
                if value:
                    return value

        return str(api_result)

    # ---------------------------------------------------
    # Step 1B - Load Customer Feedback / VOC
    # ---------------------------------------------------
    def load_customer_feedback_raw(self, feedback_file=None):
        """
        Load raw customer feedback text.

        This is optional input.
        If no file exists, return an empty string so the pipeline can still run.
        """

        if feedback_file:
            loader = CustomerFeedbackLoader(feedback_file=feedback_file)
            return loader.load()

        return self.customer_feedback_loader.load()

    # ---------------------------------------------------
    # Strategy-only production test
    # ---------------------------------------------------
    def run_strategy_only(
        self,
        _id=None,
        control_panel_file=None,
        customer_feedback_file=None,
        brand_intake=None,
        save_output=True,
    ):
        """
        Run the official pipeline only up to Strategy.

        Flow:
        Brand Intake / provided brand_intake
        → Research
        → Insight
        → Strategy
        → STOP

        Purpose:
        Validate Alysha-ready strategy output before building Creative Engine.
        """

        claude_mode = get_claude_mode(
            test_id=_id,
            control_panel_file=control_panel_file,
        )

        if brand_intake is None and _id:
            brand_intake = self.build_brand_intake(
                _id,
                control_panel_file=control_panel_file,
                claude_mode=claude_mode,
                claude_api_adapter=self.claude_api_adapter,
            )

        customer_feedback_raw = self.load_customer_feedback_raw(
            feedback_file=customer_feedback_file,
        )

        research_output = self.research_pipeline.run(
            _id=_id,
            brand_intake=brand_intake,
            claude_mode=claude_mode,
            claude_api_adapter=self.claude_api_adapter,
        )

        insight_output = self.insight_pipeline.run(
            research_output,
            claude_mode=claude_mode,
            claude_api_adapter=self.claude_api_adapter,
        )

        strategy_output = self.strategy_pipeline.run(
            insight_output,
            brand_intake=brand_intake,
            customer_feedback_raw=customer_feedback_raw,
            claude_mode=claude_mode,
            claude_api_adapter=self.claude_api_adapter,
        )

        if save_output:
            from datetime import datetime

            base_path = Path.cwd() / "data" / "output"

            latest_path = base_path / "strategy_output.json"
            history_path = (
                base_path
                / "history"
                / "strategy"
                / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

            latest_path.parent.mkdir(parents=True, exist_ok=True)
            history_path.parent.mkdir(parents=True, exist_ok=True)

            latest_path.write_text(
                json.dumps(strategy_output, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            history_path.write_text(
                json.dumps(strategy_output, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            print(f"\n✅ Saved latest strategy output to {latest_path}")
            print(f"📦 Saved strategy history to {history_path}")

        return {
            "_id": _id,
            "claude_mode": claude_mode,
            "brand_intake": brand_intake,
            "customer_feedback_used": bool(customer_feedback_raw),
            "customer_feedback_length": len(customer_feedback_raw or ""),
            "research": research_output,
            "insight": insight_output,
            "strategy": strategy_output,
        }

    # ---------------------------------------------------
    # Official production run
    # ---------------------------------------------------
    def run(self, _id=None, control_panel_file=None, customer_feedback_file=None):
        """
        Official production run.

        Nếu có _id:
        - build brand_intake thật từ Excel
        - resolve claude_mode thật từ claude_mode_settings

        Nếu không có _id:
        - dùng fallback mode từ env/default
        """
        claude_mode = get_claude_mode(
            test_id=_id,
            control_panel_file=control_panel_file,
        )

        brand_intake = None
        if _id:
            brand_intake = self.build_brand_intake(
                _id,
                control_panel_file=control_panel_file,
                claude_mode=claude_mode,
                claude_api_adapter=self.claude_api_adapter,
            )

        customer_feedback_raw = self.load_customer_feedback_raw(
            feedback_file=customer_feedback_file,
        )

        # =====================================================
        # 1. Chạy pipeline lõi
        # =====================================================
        research_output = self.research_pipeline.run(
            _id=_id,
            brand_intake=brand_intake,
            claude_mode=claude_mode,
            claude_api_adapter=self.claude_api_adapter,
        )

        insight_output = self.insight_pipeline.run(
            research_output,
            claude_mode=claude_mode,
            claude_api_adapter=self.claude_api_adapter,
        )

        # Save insight as a dedicated file for easier inspection/debugging
        if _id:
            insight_path = INSIGHT_DIR / f"{_id}_insight.json"
            insight_path.parent.mkdir(parents=True, exist_ok=True)
            insight_path.write_text(
                json.dumps(insight_output, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        strategy_output = self.strategy_pipeline.run(
            insight_output,
            brand_intake=brand_intake,
            customer_feedback_raw=customer_feedback_raw,
            claude_mode=claude_mode,
            claude_api_adapter=self.claude_api_adapter,
        )

        creative_output = self.creative_pipeline.run(
            strategy_output,
            brand_intake=brand_intake,
        )

        self.writer.save(creative_output)

        # =====================================================
        # 2. Learning memory
        # =====================================================
        learning_memory = self.learning_engine.learning_memory()
        learning_file = self.learning_writer.save(learning_memory)

        feedback_summary = {
            "best_objectives": learning_memory.get("top_performance_objectives", [])[
                :3
            ],
            "best_skills": learning_memory.get("top_performance_skills", [])[:3],
            "total_experiments": learning_memory.get("total_experiments", 0),
        }

        # =====================================================
        # 3. Campaign generation + ranking
        # =====================================================
        campaigns = self.campaign_generator.generate(
            creative_output["data"]["creative_ideas"]
        )

        ranked_campaigns = self.campaign_ranker.rank(campaigns, feedback_summary)
        top_campaign = ranked_campaigns[0] if ranked_campaigns else None
        top_campaigns = ranked_campaigns[:3]

        # =====================================================
        # 4. Brief system
        # =====================================================
        brief_data = self.brief_writer.build_brief(top_campaign, feedback_summary)
        brief_file = self.brief_writer.save(brief_data)

        multi_brief = []
        for campaign in top_campaigns:
            brief = self.brief_writer.build_brief(campaign, feedback_summary)
            multi_brief.append(brief)

        multi_brief_file = self.multi_brief_writer.save(multi_brief)

        # =====================================================
        # 5. Human handoff
        # =====================================================
        human_handoff = self.human_handoff_writer.build_package(
            top_campaign,
            top_campaigns,
            feedback_summary,
            brief_data,
        )
        human_handoff_file = self.human_handoff_writer.save(human_handoff)

        # =====================================================
        # 6. Claude readiness
        # =====================================================
        claude_api_status = self.claude_api_adapter.readiness()

        # =====================================================
        # 7. Claude execution (official mode)
        # =====================================================
        claude_package = None
        claude_package_file = None
        claude_handoff = None
        claude_handoff_file = None
        claude_review = None
        claude_review_file = None
        claude_execution = None
        claude_execution_file = None
        claude_pro_package = None
        claude_pro_package_file = None

        claude_api_result = None
        claude_raw_response = None
        claude_parsed = None
        claude_parsed_file = None

        if claude_mode == "pro_manual":
            claude_package = self.claude_package_writer.build_package(
                top_campaign,
                top_campaigns,
                feedback_summary,
                brief_data,
                multi_brief,
            )
            claude_package_file = self.claude_package_writer.save(claude_package)

            claude_handoff = self.claude_handoff_writer.build_refinement_prompt(
                claude_package_file,
                top_campaign,
            )
            claude_handoff_file = self.claude_handoff_writer.save(
                claude_handoff,
                prefix="claude_handoff",
            )

            claude_review = self.claude_handoff_writer.build_review_prompt(
                claude_package_file,
                top_campaign,
            )
            claude_review_file = self.claude_handoff_writer.save(
                claude_review,
                prefix="claude_review",
            )

            claude_execution = self.claude_handoff_writer.build_execution_prompt(
                claude_package_file,
                top_campaign,
            )
            claude_execution_file = self.claude_handoff_writer.save(
                claude_execution,
                prefix="claude_execution",
            )

            claude_pro_package = self.claude_pro_writer.build_package(
                top_campaign,
                top_campaigns,
                brief_data,
                multi_brief,
                feedback_summary,
                claude_execution,
            )
            claude_pro_package_file = self.claude_pro_writer.save(claude_pro_package)

        elif claude_mode == "api":
            claude_package = self.claude_package_writer.build_package(
                top_campaign,
                top_campaigns,
                feedback_summary,
                brief_data,
                multi_brief,
            )
            claude_package_file = self.claude_package_writer.save(claude_package)

            try:
                claude_api_result = self.claude_api_adapter.run(
                    package=claude_package,
                    top_campaign=top_campaign,
                    top_campaigns=top_campaigns,
                    feedback_summary=feedback_summary,
                    brief_data=brief_data,
                    multi_brief=multi_brief,
                    brand_intake=brand_intake,
                )
            except TypeError:
                try:
                    claude_api_result = self.claude_api_adapter.run(
                        package=claude_package,
                        top_campaign=top_campaign,
                        brand_intake=brand_intake,
                    )
                except TypeError:
                    claude_api_result = self.claude_api_adapter.run(claude_package)

            claude_raw_response = self._normalize_claude_api_response(claude_api_result)

            if claude_raw_response:
                claude_parsed, claude_parsed_file = self.parse_claude_response(
                    response=claude_raw_response,
                    source_mode="api",
                    auto_save=True,
                )

        elif claude_mode == "off":
            pass

        else:
            raise ValueError(f"Claude mode không hợp lệ: {claude_mode}")

        # =====================================================
        # 8. Learning after real Claude response
        # =====================================================
        claude_learning = None
        claude_feedback_profile = None
        claude_feedback_file = None
        claude_evolution_rules = None
        claude_evolution_validation = None
        claude_learning_snapshot_file = None

        if claude_parsed:
            claude_learning = self.learn_from_claude()
            claude_feedback_profile, claude_feedback_file = (
                self.build_campaign_feedback()
            )
            claude_evolution_rules = self.build_evolution_rules()
            claude_evolution_validation = self.validate_evolution_rules()
            claude_learning_snapshot_file = self.save_learning_snapshot()

        # =====================================================
        # 9. Existing generator learning / evaluation
        # =====================================================
        evolution_rules = self.build_evolution_rules()
        evolution_validation = self.pipeline_guardrails.validate_evolution_rules(
            evolution_rules
        )

        learning_snapshot_file = self.learning_memory_store.save_snapshot(
            self.learn_from_claude(),
            self.build_campaign_feedback()[0],
            evolution_rules,
        )

        generator_learning_result = self.apply_generator_learning(campaigns)
        generator_learning_evaluation = self.pipeline_evaluator.evaluate_campaigns(
            generator_learning_result["adjusted_campaigns"]
        )

        # =====================================================
        # 10. Report data
        # =====================================================
        report_data = {
            "_id": _id,
            "brand_intake": brand_intake,
            "customer_feedback_used": bool(customer_feedback_raw),
            "customer_feedback_length": len(customer_feedback_raw or ""),
            "best_objectives": feedback_summary["best_objectives"],
            "best_skills": feedback_summary["best_skills"],
            "creative_ideas": creative_output["data"]["creative_ideas"],
            "campaigns": campaigns,
            "ranked_campaigns": ranked_campaigns,
            "top_campaign": top_campaign,
            "top_campaigns": top_campaigns,
            "brief": brief_data,
            "multi_brief": multi_brief,
            "human_handoff": human_handoff,
            "claude_mode": claude_mode,
            "claude_api_status": claude_api_status,
            "claude_raw_response": claude_raw_response,
            "claude_parsed": claude_parsed,
            "claude_learning": claude_learning,
        }

        report_file = self.report_writer.save(report_data)

        # =====================================================
        # 11. Final return
        # =====================================================
        return {
            "_id": _id,
            "brand_intake": brand_intake,
            "customer_feedback_used": bool(customer_feedback_raw),
            "customer_feedback_length": len(customer_feedback_raw or ""),
            "research": research_output,
            "insight": insight_output,
            "strategy": strategy_output,
            "creative": creative_output,
            "campaigns": campaigns,
            "ranked_campaigns": ranked_campaigns,
            "top_campaign": top_campaign,
            "top_campaigns": top_campaigns,
            "learning": learning_file,
            "feedback_summary": feedback_summary,
            "brief": brief_data,
            "brief_file": brief_file,
            "multi_brief": multi_brief,
            "multi_brief_file": multi_brief_file,
            "human_handoff": human_handoff,
            "human_handoff_file": human_handoff_file,
            "claude_mode": claude_mode,
            "claude_api_status": claude_api_status,
            "claude_package": claude_package,
            "claude_package_file": claude_package_file,
            "claude_handoff": claude_handoff,
            "claude_handoff_file": claude_handoff_file,
            "claude_review": claude_review,
            "claude_review_file": claude_review_file,
            "claude_execution": claude_execution,
            "claude_execution_file": claude_execution_file,
            "claude_pro_package": claude_pro_package,
            "claude_pro_package_file": claude_pro_package_file,
            "claude_api_result": claude_api_result,
            "claude_raw_response": claude_raw_response,
            "claude_parsed": claude_parsed,
            "claude_parsed_file": claude_parsed_file,
            "claude_learning": claude_learning,
            "claude_feedback_profile": claude_feedback_profile,
            "claude_feedback_file": claude_feedback_file,
            "claude_evolution_rules": claude_evolution_rules,
            "claude_evolution_validation": claude_evolution_validation,
            "claude_learning_snapshot_file": claude_learning_snapshot_file,
            "evolution_rules": evolution_rules,
            "evolution_validation": evolution_validation,
            "learning_snapshot_file": learning_snapshot_file,
            "generator_learning": generator_learning_result,
            "generator_learning_evaluation": generator_learning_evaluation,
            "report": report_file,
        }
