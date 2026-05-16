# ---------------------------------------------------
# Research feature flags
# ---------------------------------------------------

USE_COMPETITOR_DISCOVERY = True

# Current mode:
# - "claude_only" -> only Claude-based discovery
# - "apify_free"  -> later: Claude + Apify free-tier enrichment
# - "apify_paid"  -> later: Claude + richer social enrichment
RESEARCH_MODE = "claude_only"

# Max competitors to keep after discovery
MAX_COMPETITORS = 10

# Number of top competitors to prioritize for deeper enrichment later
TOP_COMPETITORS_FOR_ENRICHMENT = 5

# ---------------------------------------------------
# Apify settings (future-ready)
# ---------------------------------------------------

USE_APIFY = False
APIFY_MODE = "free"
APIFY_CACHE_DAYS = 7

# ---------------------------------------------------
# Output defaults
# ---------------------------------------------------

DEFAULT_TARGET_MARKETS = ["US", "CA"]

# Competitor layers we want Claude to reason about
COMPETITOR_LAYERS = [
    "same_target_market",
    "same_format",
    "same_coffee_type",
    "same_origin",
    "market_signal",
    "price_range",
]
