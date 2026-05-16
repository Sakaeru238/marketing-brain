from pathlib import Path

# ---------------------------------------------------
# Base directories
# ---------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = BASE_DIR / "core"
CONFIG_DIR = BASE_DIR / "config"
GLOBAL_CONFIG_DIR = CONFIG_DIR / "global"
BRANDS_CONFIG_DIR = CONFIG_DIR / "brands"
DATA_DIR = BASE_DIR / "data"
BRANDS_DATA_DIR = DATA_DIR / "brands"
PERFORMANCE_DIR = BASE_DIR / "performance"

# ---------------------------------------------------
# Manual / override inputs
# ---------------------------------------------------

MANUAL_INPUT_DIR = DATA_DIR / "manual_input"
MANUAL_OVERRIDES_DIR = DATA_DIR / "manual_overrides"

# ---------------------------------------------------
# Prompt storage
# ---------------------------------------------------

PROMPTS_DIR = DATA_DIR / "prompts"
RESEARCH_PROMPTS_DIR = PROMPTS_DIR / "research"
BRAND_INTAKE_PROMPTS_DIR = PROMPTS_DIR / "brand_intake"

# ---------------------------------------------------
# Research cache / outputs
# ---------------------------------------------------

RESEARCH_CACHE_DIR = DATA_DIR / "research_cache"
RESEARCH_RAW_DIR = RESEARCH_CACHE_DIR / "raw"
RESEARCH_NORMALIZED_DIR = RESEARCH_CACHE_DIR / "normalized"
RESEARCH_OUTPUT_DIR = DATA_DIR / "research"

# ---------------------------------------------------
# Knowledge / structured outputs
# ---------------------------------------------------

KNOWLEDGE_DIR = DATA_DIR / "knowledge"
BRAND_CONTEXT_DIR = KNOWLEDGE_DIR / "brand_context"
BRAND_INTAKE_DIR = KNOWLEDGE_DIR / "brand_intake"
WEBSITE_CONTEXT_DIR = KNOWLEDGE_DIR / "website_context"
RESEARCH_CONTEXT_DIR = KNOWLEDGE_DIR / "research_context"
INSIGHT_DIR = KNOWLEDGE_DIR / "insight"

# ---------------------------------------------------
# Performance folders
# ---------------------------------------------------

TEST_RESULTS_DIR = PERFORMANCE_DIR / "test_results"
CLAUDE_RESPONSES_DIR = PERFORMANCE_DIR / "claude_responses"
LEARNING_DIR = PERFORMANCE_DIR / "learning"
REPORTS_DIR = PERFORMANCE_DIR / "reports"

COMPETITOR_DIR = KNOWLEDGE_DIR / "competitors"
PAIN_POINT_DIR = KNOWLEDGE_DIR / "pain_points"
SIGNAL_DIR = KNOWLEDGE_DIR / "signals"

COMPETITOR_REGISTRY_DIR = KNOWLEDGE_DIR / "competitor_registry"
COMPETITOR_SIGNAL_DIR = KNOWLEDGE_DIR / "competitor_signals"

# ---------------------------------------------------
# Ensure dirs exist
# ---------------------------------------------------

for path in [
    CONFIG_DIR,
    GLOBAL_CONFIG_DIR,
    BRANDS_CONFIG_DIR,
    DATA_DIR,
    BRANDS_DATA_DIR,
    MANUAL_INPUT_DIR,
    MANUAL_OVERRIDES_DIR,
    PROMPTS_DIR,
    RESEARCH_PROMPTS_DIR,
    BRAND_INTAKE_PROMPTS_DIR,
    RESEARCH_CACHE_DIR,
    RESEARCH_RAW_DIR,
    RESEARCH_NORMALIZED_DIR,
    RESEARCH_OUTPUT_DIR,
    KNOWLEDGE_DIR,
    BRAND_CONTEXT_DIR,
    BRAND_INTAKE_DIR,
    WEBSITE_CONTEXT_DIR,
    RESEARCH_CONTEXT_DIR,
    INSIGHT_DIR,
    PERFORMANCE_DIR,
    TEST_RESULTS_DIR,
    CLAUDE_RESPONSES_DIR,
    LEARNING_DIR,
    REPORTS_DIR,
    COMPETITOR_DIR,
    PAIN_POINT_DIR,
    SIGNAL_DIR,
    COMPETITOR_REGISTRY_DIR,
    COMPETITOR_SIGNAL_DIR,
]:
    path.mkdir(parents=True, exist_ok=True)
