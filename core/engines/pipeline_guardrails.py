"""
Step 62A - Pipeline Guardrails

Mục tiêu:
- chặn rules rỗng / lỗi / quá dài
- tránh drift đơn giản
"""


class PipelineGuardrails:
    def validate_evolution_rules(self, rules):
        issues = []

        if not isinstance(rules, dict):
            issues.append("Evolution rules must be a dict.")
            return {
                "valid": False,
                "issues": issues,
            }

        generation_rules = rules.get("generation_rules", [])

        if not isinstance(generation_rules, list):
            issues.append("generation_rules must be a list.")

        if len(generation_rules) > 50:
            issues.append("Too many generation rules.")

        for rule in generation_rules:
            if not isinstance(rule, dict):
                issues.append("Each generation rule must be a dict.")
                continue

            if "type" not in rule or "value" not in rule:
                issues.append("Rule missing type or value.")

            value = str(rule.get("value", "")).strip()
            if not value:
                issues.append("Rule value is empty.")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
        }
