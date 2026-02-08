"""
Single source of truth for category loop discovery.
Categories: sports, politics, crypto, weather, pop_culture.
Match on title + subtitle + event_ticker / event_name (when available) + ticker.
"""
from typing import Dict, List, Any

# top_n: max signals to surface per category per cycle.
# Overridable per-category or globally via TOP_N_PER_CATEGORY env.
CATEGORY_RULES: Dict[str, Dict[str, Any]] = {
    "sports": {
        "keywords": [
            "nfl", "nba", "mlb", "nhl", "super bowl", "superbowl", "playoff", "championship",
            "touchdown", "mvp", "all-star", "all star", "game", "score", "win", "team",
            "quarter", "halftime", "overtime", "season", "bowl", "finals", "slam dunk",
            "passing yards", "rushing", "receiving", "interception", "sack", "field goal",
        ],
        "top_n": 3,
    },
    "politics": {
        "keywords": [
            "election", "vote", "president", "congress", "senate", "governor", "democrat",
            "republican", "primary", "poll", "approval", "bill", "legislation", "cabinet",
            "white house", "trump", "biden", "harris", "nominee", "electoral", "ballot",
        ],
        "top_n": 3,
    },
    "crypto": {
        "keywords": [
            "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency", "blockchain",
            "solana", "sol", "defi", "nft", "token", "price", "market cap", "halving",
        ],
        "top_n": 3,
    },
    "weather": {
        "keywords": [
            "temperature", "hurricane", "storm", "snow", "rain", "drought", "flood",
            "heat", "cold", "forecast", "degrees", "fahrenheit", "celsius", "tornado",
            "wildfire", "climate", "weather",
        ],
        "top_n": 3,
    },
    "pop_culture": {
        "keywords": [
            "grammy", "oscar", "emmy", "award", "movie", "film", "album", "chart",
            "celebrity", "netflix", "streaming", "box office", "billboard", "tv",
            "halftime show", "commercial", "ad", "culture", "entertainment",
        ],
        "top_n": 3,
    },
}


def get_categories() -> List[str]:
    return list(CATEGORY_RULES.keys())


def get_keywords(category: str) -> List[str]:
    return list(CATEGORY_RULES.get(category, {}).get("keywords", []))


def get_top_n(category: str, default: int = 3) -> int:
    return int(CATEGORY_RULES.get(category, {}).get("top_n", default))


def match_market_to_categories(
    title: str,
    subtitle: str,
    event_ticker: str,
    event_name: str,
    ticker: str,
) -> List[tuple]:
    """
    Return list of (category, matched_keywords) for this market.
    Uses title, subtitle, event_ticker, event_name, ticker (all lowercased).
    """
    combined = " ".join(
        str(x).lower() for x in [title, subtitle, event_ticker, event_name, ticker] if x
    )
    out = []
    for cat, rule in CATEGORY_RULES.items():
        kws = rule.get("keywords", [])
        matched = [kw for kw in kws if kw in combined]
        if matched:
            out.append((cat, matched))
    return out
