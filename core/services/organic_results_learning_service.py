import json
import re
from collections import defaultdict
from statistics import mean
from typing import Dict, List, Tuple

from core.engines.claude_api_adapter import ClaudeAPIAdapter


class OrganicResultsLearningService:
    """
    Turns collected Organic_Results metrics into:
    - Vietnamese AI learning fields for Google Sheets
    - English AI learning fields for local JSONL memory / next-run organic generation
    - Vietnamese daily aggregate learning rows for Daily_Learning_Log

    Uses Claude when configured; falls back to deterministic bilingual learning strings when unavailable.
    """

    def __init__(self):
        self.claude = ClaudeAPIAdapter()

    def _to_float(self, value, default=0.0) -> float:
        try:
            if str(value or "").strip() == "-":
                return default
            return float(value or 0)
        except Exception:
            return default

    def _to_int(self, value, default=0) -> int:
        try:
            if str(value or "").strip() == "-":
                return default
            return int(float(value or 0))
        except Exception:
            return default

    def _metric_text(self, value) -> str:
        value = str(value if value is not None else "").strip()
        return value if value and value != "-" else "-"

    def _group_key(self, row: Dict) -> Tuple[str, str, str, str, str]:
        return (
            str(row.get("date", "")),
            str(row.get("brand_id", "")),
            str(row.get("page_id", "")),
            str(row.get("platform_id", "")),
            str(row.get("campaign_id", "")),
        )

    def _normalize_response_text(self, raw) -> str:
        if hasattr(raw, "content"):
            try:
                return "\n".join([b.text for b in raw.content if hasattr(b, "text")])
            except Exception:
                return str(raw)
        if isinstance(raw, dict):
            for key in ["response", "content", "text", "result", "response_text"]:
                if raw.get(key):
                    return str(raw[key])
        return str(raw)

    def _parse_json_response(self, raw) -> Dict:
        text = self._normalize_response_text(raw)
        try:
            return json.loads(text)
        except Exception:
            pass
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError("Learning response did not contain valid JSON.")
        return json.loads(match.group())

    def _safe_join(self, values: List[str]) -> str:
        cleaned = []
        for value in values:
            value = str(value or "").strip()
            if value and value not in cleaned:
                cleaned.append(value)
        return " | ".join(cleaned)

    def _best_and_worst(self, rows: List[Dict]) -> Tuple[Dict, Dict]:
        ranked = sorted(rows, key=lambda r: self._to_float(r.get("engagement_rate")), reverse=True)
        return ranked[0], ranked[-1]

    def _page_context_for(self, page_context_by_key: Dict, row: Dict) -> Dict:
        brand_id = row.get("brand_id")
        page_id = row.get("page_id")
        page_url = row.get("page_url")
        platform_id = row.get("platform_id")
        return (
            page_context_by_key.get((brand_id, page_id, platform_id))
            or page_context_by_key.get((brand_id, page_id, ""))
            or page_context_by_key.get((brand_id, page_url, platform_id))
            or page_context_by_key.get((brand_id, page_url, ""))
            or {}
        )

    def _post_summary_en(self, row: Dict) -> str:
        return (
            f"Post {row.get('post_id', '')} collected: reach={self._metric_text(row.get('reach'))}, "
            f"impressions={self._metric_text(row.get('impressions'))}, clicks={self._metric_text(row.get('clicks'))}, "
            f"likes={self._metric_text(row.get('likes'))}, comments={self._metric_text(row.get('comments'))}, "
            f"shares={self._metric_text(row.get('shares'))}, engagement_rate={self._metric_text(row.get('engagement_rate'))}."
        )

    def _post_summary_vi(self, row: Dict) -> str:
        return (
            f"Bài {row.get('post_id', '')}: reach={self._metric_text(row.get('reach'))}, "
            f"impressions={self._metric_text(row.get('impressions'))}, clicks={self._metric_text(row.get('clicks'))}, "
            f"likes={self._metric_text(row.get('likes'))}, comments={self._metric_text(row.get('comments'))}, "
            f"shares={self._metric_text(row.get('shares'))}, engagement_rate={self._metric_text(row.get('engagement_rate'))}."
        )

    def _fallback_group_analysis(self, rows: List[Dict], page_context: Dict) -> Dict:
        best, worst = self._best_and_worst(rows)
        avg_er = mean([self._to_float(r.get("engagement_rate")) for r in rows]) if rows else 0
        growth_goal = str(page_context.get("growth_goal") or "increase organic page performance")
        content_goal = str(
            page_context.get("default_content_goal")
            or page_context.get("today_content_goal")
            or "improve the next organic content batch"
        )

        per_post = []
        for row in rows:
            er = self._to_float(row.get("engagement_rate"))
            relative_en = "above" if er >= avg_er else "below"
            relative_vi = "cao hơn" if er >= avg_er else "thấp hơn"
            ai_learning_en = (
                f"This post performed {relative_en} the batch-average engagement rate ({avg_er:.2f}%). "
                "Use its content role, pillar, hook and posting window as a signal for the next content batch."
            )
            ai_learning_vi = (
                f"Bài này có engagement rate {relative_vi} mức trung bình của batch ({avg_er:.2f}%). "
                "Nên xem vai trò nội dung, pillar, hook và khung giờ đăng của bài này như tín hiệu cho batch tiếp theo."
            )
            if er >= avg_er:
                ai_next_action_en = (
                    f"Repeat or expand this pattern in the next organic batch while staying aligned with campaign goal: {growth_goal}."
                )
                ai_next_action_vi = (
                    f"Lặp lại hoặc mở rộng pattern này ở batch organic tiếp theo, đồng thời vẫn bám mục tiêu campaign: {growth_goal}."
                )
            else:
                ai_next_action_en = (
                    f"Revise the angle, hook or engagement prompt for similar posts next time to better support campaign goal: {growth_goal}."
                )
                ai_next_action_vi = (
                    f"Với các bài tương tự ở lần sau, cần sửa angle, hook hoặc engagement prompt để hỗ trợ mục tiêu campaign tốt hơn: {growth_goal}."
                )
            per_post.append(
                {
                    "post_id": row.get("post_id", ""),
                    "facebook_post_id": row.get("facebook_post_id", ""),
                    "ai_result_summary_en": self._post_summary_en(row),
                    "ai_learning_en": ai_learning_en,
                    "ai_next_action_en": ai_next_action_en,
                    "ai_result_summary_vi": self._post_summary_vi(row),
                    "ai_learning_vi": ai_learning_vi,
                    "ai_next_action_vi": ai_next_action_vi,
                }
            )

        daily_vi = {
            "growth_goal": f"Mục tiêu tăng trưởng hiện tại: {growth_goal}",
            "today_content_goal": f"Mục tiêu nội dung hôm nay: {content_goal}",
            "posts_reviewed": len(rows),
            "best_post_id": best.get("post_id", ""),
            "worst_post_id": worst.get("post_id", ""),
            "winning_content_roles_ai": self._safe_join([best.get("content_role", "")]),
            "weak_content_roles_ai": self._safe_join([worst.get("content_role", "")]),
            "winning_pillars_ai": self._safe_join([best.get("content_pillar", "")]),
            "weak_pillars_ai": self._safe_join([worst.get("content_pillar", "")]),
            "winning_hooks_ai": self._safe_join([best.get("hook_type", ""), best.get("hook", "")]),
            "weak_hooks_ai": self._safe_join([worst.get("hook_type", ""), worst.get("hook", "")]),
            "audience_signal_ai": (
                f"Engagement rate trung bình của batch là {avg_er:.2f}%. "
                f"Bài tốt nhất là {best.get('post_id', '')}; bài yếu nhất là {worst.get('post_id', '')}."
            ),
            "content_improvement_ai": "Ưu tiên lặp lại role, pillar và hook mạnh; các pattern yếu cần được siết lại trước khi dùng tiếp.",
            "keep_strategy_ai": "Giữ các pattern đang outperform mức trung bình batch và vẫn phù hợp với mục tiêu campaign.",
            "strategy_review_needed_ai": "có" if avg_er < 1.0 else "không",
            "next_day_content_goal_ai": f"Ngày tiếp theo nên tập trung vào mục tiêu nội dung: {content_goal}.",
            "next_day_content_roles_ai": self._safe_join([best.get("content_role", "")]),
            "next_day_content_pillars_ai": self._safe_join([best.get("content_pillar", "")]),
            "next_day_post_format_mix_ai": self._safe_join([best.get("post_format", "")]),
            "next_day_product_mention_level_ai": self._safe_join([best.get("product_mention_level", "")]),
            "next_day_tone_ai": "Giữ hoặc điều chỉnh tone dựa trên các bài đang hoạt động tốt, strategy hiện tại và context campaign; không dùng default_tone làm nguồn quyết định.",
            "next_day_notes_ai": f"Ưu tiên pattern mạnh nhất từ {best.get('post_id', '')}; cải thiện hoặc tránh pattern yếu từ {worst.get('post_id', '')}.",
        }
        return {"per_post": per_post, "daily_learning_vi": daily_vi}

    def _build_prompt(self, rows: List[Dict], page_context: Dict) -> str:
        compact_rows = []
        for row in rows:
            compact_rows.append(
                {
                    "post_id": row.get("post_id"),
                    "facebook_post_id": row.get("facebook_post_id"),
                    "content_role": row.get("content_role"),
                    "content_pillar": row.get("content_pillar"),
                    "hook_type": row.get("hook_type"),
                    "hook": row.get("hook"),
                    "post_format": row.get("post_format"),
                    "product_mention_level": row.get("product_mention_level"),
                    "desired_post_outcome": row.get("desired_post_outcome"),
                    "desired_action": row.get("desired_action"),
                    "recommended_posting_window": row.get("recommended_posting_window"),
                    "metrics": {
                        "likes": row.get("likes"),
                        "comments": row.get("comments"),
                        "shares": row.get("shares"),
                        "reach": row.get("reach"),
                        "impressions": row.get("impressions"),
                        "clicks": row.get("clicks"),
                        "engagement_rate": row.get("engagement_rate"),
                    },
                }
            )

        payload = {
            "page_context": {
                "brand_id": page_context.get("brand_id"),
                "niche_id": page_context.get("niche_id"),
                "page_id": page_context.get("page_id"),
                "platform_id": page_context.get("platform_id"),
                "growth_goal": page_context.get("growth_goal"),
                "default_content_goal": page_context.get("default_content_goal"),
                "default_product_mention_level": page_context.get("default_product_mention_level"),
                "posting_frequency_target": page_context.get("posting_frequency_target"),
            },
            "collected_results": compact_rows,
        }

        return (
            "You are the organic performance learning layer for a marketing AI system. "
            "Analyze the collected Facebook organic post results and produce actionable learning to improve the next data/content batch. "
            "Return JSON only.\n\n"
            "Language rule:\n"
            "- Fields ending with `_en` MUST be written in English. They are stored in local JSONL learning memory and reused by the next organic generation job.\n"
            "- Fields ending with `_vi`, and all fields inside `daily_learning_vi`, MUST be written in Vietnamese for Google Sheets readability.\n\n"
            "Required JSON schema:\n"
            "{\n"
            '  "per_post": [\n'
            "    {\n"
            '      "post_id": "...",\n'
            '      "facebook_post_id": "...",\n'
            '      "ai_result_summary_en": "concise factual result summary in English",\n'
            '      "ai_learning_en": "what the system learned from this post in English",\n'
            '      "ai_next_action_en": "what the next organic generation should do differently or repeat in English",\n'
            '      "ai_result_summary_vi": "tóm tắt kết quả thực tế bằng tiếng Việt",\n'
            '      "ai_learning_vi": "bài học AI rút ra bằng tiếng Việt",\n'
            '      "ai_next_action_vi": "hành động cần áp dụng cho batch organic tiếp theo bằng tiếng Việt"\n'
            "    }\n"
            "  ],\n"
            '  "daily_learning_vi": {\n'
            '    "growth_goal": "...",\n'
            '    "today_content_goal": "...",\n'
            '    "posts_reviewed": 0,\n'
            '    "best_post_id": "...",\n'
            '    "worst_post_id": "...",\n'
            '    "winning_content_roles_ai": "...",\n'
            '    "weak_content_roles_ai": "...",\n'
            '    "winning_pillars_ai": "...",\n'
            '    "weak_pillars_ai": "...",\n'
            '    "winning_hooks_ai": "...",\n'
            '    "weak_hooks_ai": "...",\n'
            '    "audience_signal_ai": "...",\n'
            '    "content_improvement_ai": "...",\n'
            '    "keep_strategy_ai": "...",\n'
            '    "strategy_review_needed_ai": "có hoặc không, không thêm từ khác",\n'
            '    "next_day_content_goal_ai": "...",\n'
            '    "next_day_content_roles_ai": "...",\n'
            '    "next_day_content_pillars_ai": "...",\n'
            '    "next_day_post_format_mix_ai": "...",\n'
            '    "next_day_product_mention_level_ai": "...",\n'
            '    "next_day_tone_ai": "...",\n'
            '    "next_day_notes_ai": "..."\n'
            "  }\n"
            "}\n\n"
            "Rules:\n"
            "- Base conclusions on metrics, campaign/page goals and content metadata.\n"
            "- `ai_next_action_en` and `ai_next_action_vi` must directly improve the next organic generation batch.\n"
            "- Do not fabricate metrics. If a metric is `-`, treat it as unavailable rather than zero.\n"
            "- Keep results practical and concise.\n\n"
            f"INPUT:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _analyze_group(self, rows: List[Dict], page_context: Dict) -> Dict:
        readiness = self.claude.readiness()
        if not readiness.get("ready"):
            return self._fallback_group_analysis(rows, page_context)

        try:
            response = self.claude.run(
                prompt=self._build_prompt(rows, page_context),
                max_tokens=6500,
                temperature=0.2,
            )
            parsed = self._parse_json_response(response)
            if not isinstance(parsed.get("per_post"), list) or not isinstance(parsed.get("daily_learning_vi"), dict):
                raise ValueError("Learning response missing per_post or daily_learning_vi.")
            return parsed
        except Exception:
            return self._fallback_group_analysis(rows, page_context)

    def enrich_results_and_build_daily_logs(self, results: List[Dict], page_context_by_key: Dict) -> Tuple[List[Dict], List[Dict]]:
        grouped = defaultdict(list)
        for row in results:
            grouped[self._group_key(row)].append(row)

        enriched_results = []
        daily_logs = []
        for _, rows in grouped.items():
            first = rows[0]
            page_context = self._page_context_for(page_context_by_key, first)
            analysis = self._analyze_group(rows, page_context)
            per_post_map = {
                str(item.get("facebook_post_id") or item.get("post_id") or ""): item
                for item in analysis.get("per_post", [])
            }

            for row in rows:
                key_fb = str(row.get("facebook_post_id") or "")
                key_post = str(row.get("post_id") or "")
                item = per_post_map.get(key_fb) or per_post_map.get(key_post) or {}

                # Google Sheets output is Vietnamese.
                row["ai_result_summary"] = item.get("ai_result_summary_vi") or self._post_summary_vi(row)
                row["ai_learning"] = item.get("ai_learning_vi") or ""
                row["ai_next_action"] = item.get("ai_next_action_vi") or ""

                # Local JSONL memory remains English so the next generation job learns from an English canonical memory layer.
                row["ai_result_summary_en"] = item.get("ai_result_summary_en") or self._post_summary_en(row)
                row["ai_learning_en"] = item.get("ai_learning_en") or ""
                row["ai_next_action_en"] = item.get("ai_next_action_en") or ""
                enriched_results.append(row)

            daily = analysis.get("daily_learning_vi", {}) or {}
            organic_run_ids = self._safe_join([r.get("organic_run_id", "") for r in rows])
            daily_record = {
                "campaign_id": first.get("campaign_id", ""),
                "learning_id": f"LEARN_{first.get('brand_id', '')}_{first.get('page_id', '')}_{first.get('date', '')}".replace("-", ""),
                "date": first.get("date", ""),
                "brand_id": first.get("brand_id", ""),
                "niche_id": first.get("niche_id", ""),
                "page_id": first.get("page_id", ""),
                "platform_id": first.get("platform_id", ""),
                "organic_run_id": organic_run_ids,
                "growth_goal": daily.get("growth_goal") or page_context.get("growth_goal", ""),
                "today_content_goal": daily.get("today_content_goal") or page_context.get("default_content_goal", ""),
                "posts_reviewed": daily.get("posts_reviewed", len(rows)),
                "best_post_id": daily.get("best_post_id", ""),
                "worst_post_id": daily.get("worst_post_id", ""),
                "winning_content_roles_ai": daily.get("winning_content_roles_ai", ""),
                "weak_content_roles_ai": daily.get("weak_content_roles_ai", ""),
                "winning_pillars_ai": daily.get("winning_pillars_ai", ""),
                "weak_pillars_ai": daily.get("weak_pillars_ai", ""),
                "winning_hooks_ai": daily.get("winning_hooks_ai", ""),
                "weak_hooks_ai": daily.get("weak_hooks_ai", ""),
                "audience_signal_ai": daily.get("audience_signal_ai", ""),
                "content_improvement_ai": daily.get("content_improvement_ai", ""),
                "keep_strategy_ai": daily.get("keep_strategy_ai", ""),
                "strategy_review_needed_ai": daily.get("strategy_review_needed_ai", ""),
                "next_day_content_goal_ai": daily.get("next_day_content_goal_ai", ""),
                "next_day_content_roles_ai": daily.get("next_day_content_roles_ai", ""),
                "next_day_content_pillars_ai": daily.get("next_day_content_pillars_ai", ""),
                "next_day_post_format_mix_ai": daily.get("next_day_post_format_mix_ai", ""),
                "next_day_product_mention_level_ai": daily.get("next_day_product_mention_level_ai", ""),
                "next_day_tone_ai": daily.get("next_day_tone_ai", ""),
                "next_day_notes_ai": daily.get("next_day_notes_ai", ""),
            }
            daily_logs.append(daily_record)

        return enriched_results, daily_logs
