#!/usr/bin/env python3
"""
Kalshi Signals MVP — compatibility entry point.
Delegates to the modular runner. Re-exports for demo.py and legacy imports.

Usage:
  DRY_RUN=true  python kalshi_signals.py   # discovery only
  DRY_RUN=false python kalshi_signals.py   # polling loop

Discord bot (separate process): python -m src.bot
"""
from src.runner import main
from src.settings import Config, SUPERBOWL, superbowl_label_roman
from src.db import Database
from src.models import Market, Features
from src.classifier import MarketClassifier
from src.scoring import Agent, Forecaster

__all__ = [
    "main",
    "Config",
    "SUPERBOWL",
    "superbowl_label_roman",
    "Database",
    "Market",
    "Features",
    "MarketClassifier",
    "Agent",
    "Forecaster",
]

if __name__ == "__main__":
    main()
