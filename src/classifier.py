"""
Market classification: keyword rules + gameId→league mapping (Mode C).
Categories: NFL, NBA, CULTURE, and custom (watchlist overrides).
"""
import json
from typing import Optional

from src.settings import REPO_ROOT, SUPERBOWL

# ---------- Keyword builders from Super Bowl config ----------
def _sb_event_anchors():
    label = SUPERBOWL["label"].lower()
    roman = SUPERBOWL["roman"].lower()
    return [label, "superbowl", f"sb {roman}", f"{label} {roman}", "big game"]

def _sb_team_keywords():
    kw = []
    for side in ("home", "away"):
        t = SUPERBOWL["teams"][side]
        kw.append(t["city"].lower())
        kw.append(t["name"].split()[-1].lower())
        kw.append(t["abbreviation"].lower())
    kw.extend(["pats", "hawks"])
    return kw

NFL_KEYWORDS = [
    *_sb_event_anchors(),
    *_sb_team_keywords(),
    "mvp", "touchdown", "td", "passing yards", "rushing yards", "receiving yards", "receptions",
    "interception", "sack", "field goal", "fg", "overtime", "coin toss", "first score", "last score",
    "total points", "first quarter", "first half", "second half", "anytime touchdown",
]

NBA_KEYWORDS = [
    "all-star", "all star", "asw", "all-star weekend",
    "slam dunk", "dunk contest", "3-point", "three-point", "skills challenge",
]

SB_ANCHORS = [
    *_sb_event_anchors(),
    "levi's stadium", "santa clara", "bay area",
]

HALFTIME_KEYWORDS = [
    "halftime", "half-time", "apple music", "apple music halftime",
    "bad bunny", "benito", "benito antonio",
]
ANTHEM_KEYWORDS = ["national anthem", "star-spangled banner", "anthem", "charlie puth"]
COMMERCIAL_KEYWORDS = [
    "commercial", "commercials", "ad", "ads", "teaser", "spot", "super bowl ad", "big game ad",
]
PARTY_KEYWORDS = ["nfl honors", "fanatics", "michael rubin", "afterparty", "party", "celebrity"]
CULTURE_KEYWORDS = HALFTIME_KEYWORDS + ANTHEM_KEYWORDS + COMMERCIAL_KEYWORDS + PARTY_KEYWORDS

# ---------- gameId → league (mirror of getLeagueFromGameId.ts) ----------
_GAME_ID_LEAGUE: Optional[dict] = None

def _load_game_id_league():
    global _GAME_ID_LEAGUE
    if _GAME_ID_LEAGUE is not None:
        return _GAME_ID_LEAGUE
    path = REPO_ROOT / "src" / "config" / "gameIdToLeague.json"
    try:
        with open(path, encoding="utf-8") as f:
            _GAME_ID_LEAGUE = json.load(f)
    except Exception:
        _GAME_ID_LEAGUE = {}
    return _GAME_ID_LEAGUE

def get_league_from_game_id(game_id: str) -> Optional[str]:
    return _load_game_id_league().get(game_id)

def is_nfl_game_id(game_id: str) -> bool:
    return get_league_from_game_id(game_id) == "NFL"


class MarketClassifier:
    """Classify market into NFL, NBA, CULTURE (or None). Uses keywords + optional gameId mapping."""

    @staticmethod
    def classify(title: str, ticker: Optional[str] = None) -> Optional[str]:
        # gameId mapping: ticker often contains or equals event/market id
        if ticker:
            league = get_league_from_game_id(ticker)
            if league:
                return league
        t = title.lower()
        if any(kw in t for kw in NBA_KEYWORDS):
            return "NBA"
        has_sb = any(kw in t for kw in SB_ANCHORS)
        has_culture = any(kw in t for kw in CULTURE_KEYWORDS)
        if has_sb and has_culture:
            return "CULTURE"
        if any(kw in t for kw in COMMERCIAL_KEYWORDS + PARTY_KEYWORDS):
            return "CULTURE"
        if any(kw in t for kw in NFL_KEYWORDS):
            return "NFL"
        return None

    @staticmethod
    def all_categories():
        return ["NFL", "NBA", "CULTURE", "CUSTOM"]
