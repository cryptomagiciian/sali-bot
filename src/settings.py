"""
Configuration: env, paths, and Super Bowl config (single source of truth).
"""
import os
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths relative to repo root (parent of src/)
REPO_ROOT = Path(__file__).resolve().parent.parent
SUPERBOWL_CONFIG_PATH = REPO_ROOT / "src" / "config" / "superbowl-config.json"
GAME_ID_LEAGUE_PATH = REPO_ROOT / "src" / "config" / "gameIdToLeague.json"


def _load_superbowl():
    with open(SUPERBOWL_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


SUPERBOWL = _load_superbowl()


def superbowl_label_roman():
    return f"{SUPERBOWL['label']} {SUPERBOWL['roman']}"


def format_superbowl_matchup(use_abbreviations=False, separator=" vs "):
    h, a = SUPERBOWL["teams"]["home"], SUPERBOWL["teams"]["away"]
    left = h["abbreviation"] if use_abbreviations else h["name"]
    right = a["abbreviation"] if use_abbreviations else a["name"]
    return f"{left}{separator}{right}"


class Config:
    # Kalshi API
    KALSHI_BASE_URL = os.getenv("KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2").rstrip("/")
    KALSHI_API_KEY = os.getenv("KALSHI_API_KEY", "")

    # Discord: bot primary, webhook fallback
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
    USE_DISCORD_BOT = os.getenv("USE_DISCORD_BOT", "true").lower() == "true"

    # Polling
    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))

    # Signal thresholds
    EDGE_THRESHOLD = float(os.getenv("EDGE_THRESHOLD", "0.06"))
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))
    SPREAD_THRESHOLD = float(os.getenv("SPREAD_THRESHOLD", "0.10"))

    # Risk controls
    COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "30"))
    MAX_SIGNALS_PER_HOUR = int(os.getenv("MAX_SIGNALS_PER_HOUR", "10"))

    # Database
    DB_PATH = os.getenv("DB_PATH", "kalshi_signals.db")
    if not os.path.isabs(DB_PATH):
        DB_PATH = str(REPO_ROOT / DB_PATH)

    # Watchlist
    WATCHLIST_PATH = os.getenv("WATCHLIST_PATH", "watchlist.json")
    if not os.path.isabs(WATCHLIST_PATH):
        WATCHLIST_PATH = str(REPO_ROOT / WATCHLIST_PATH)

    # Mode: A / B / C. C = scan all markets, full categories.
    MODE = os.getenv("MODE", "C").upper()
    DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

    # Category loop discovery (Option 2)
    ENABLE_CATEGORY_LOOP = os.getenv("ENABLE_CATEGORY_LOOP", "true").lower() == "true"
    _top_n = os.getenv("TOP_N_PER_CATEGORY", "").strip()
    TOP_N_PER_CATEGORY = int(_top_n) if _top_n.isdigit() else None  # None = use per-category top_n from category_rules
