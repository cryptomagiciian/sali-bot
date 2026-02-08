"""
Data models for markets, features, signals, and agent output.
"""
from dataclasses import dataclass, asdict
from typing import List, Optional

__all__ = ["Market", "Features", "AgentOutput", "Signal"]


@dataclass
class Market:
    ticker: str
    title: str
    yes_bid: Optional[int] = None
    no_bid: Optional[int] = None
    yes_ask: Optional[int] = None
    no_ask: Optional[int] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None


@dataclass
class Features:
    catalyst_score: float
    info_strength: float
    consensus_shift: float
    volatility_flag: float
    market_microstructure: float


@dataclass
class AgentOutput:
    market_ticker: str
    title: str
    vertical: str
    timestamp: str
    features: Features
    confidence: float
    why: List[str]


@dataclass
class Signal:
    ticker: str
    title: str
    vertical: str
    yes_price: float
    p_market: float
    p_model: float
    edge: float
    confidence: float
    why: List[str]
    timestamp: str
    signal_score: float = 0.0  # computed ranking score
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    matched_keywords: Optional[List[str]] = None  # category loop: keywords that matched
    categories: Optional[List[str]] = None  # category loop: categories (for multi-match)

    def to_dict(self):
        d = asdict(self)
        return d
