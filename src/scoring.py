"""
Scoring: Agent (features + confidence), Forecaster (p_model, edge), signal_score.
All deterministic. Formula documented below.
"""
import math
from datetime import datetime, timedelta
from typing import List, Tuple

from src.models import Market, Features, AgentOutput
from src.settings import superbowl_label_roman


# ---------- Signal score formula (documented) ----------
# signal_score = (edge * confidence) * liquidity_factor * recency_factor * spread_factor
# - liquidity_factor: log(1 + (volume + open_interest)/2000), capped at 1.5
# - spread_factor: 1 - min(1.0, spread_pct / 0.20)  (wider spread → lower score)
# - recency_factor: 1.0 if last_move_minutes <= 15 else max(0.5, 1.0 - (minutes - 15) / 120)


def liquidity_factor(volume: int, open_interest: int) -> float:
    v = (volume or 0) + (open_interest or 0)
    return min(1.5, math.log1p(v / 2000.0))


def spread_factor(spread_pct: float) -> float:
    return max(0.2, 1.0 - min(1.0, spread_pct / 0.20))


def recency_factor(last_move_minutes_ago: float) -> float:
    if last_move_minutes_ago <= 15:
        return 1.0
    return max(0.5, 1.0 - (last_move_minutes_ago - 15) / 120.0)


def compute_signal_score(
    edge: float,
    confidence: float,
    volume: int = 0,
    open_interest: int = 0,
    spread_pct: float = 0.10,
    last_move_minutes_ago: float = 0.0,
) -> float:
    base = edge * confidence
    lf = liquidity_factor(volume, open_interest)
    sf = spread_factor(spread_pct)
    rf = recency_factor(last_move_minutes_ago)
    return base * lf * sf * rf


# ---------- Agent (feature computation) ----------

class Agent:
    def __init__(self, db):
        self.db = db

    def compute_features(self, market: Market, vertical: str) -> Tuple[Features, float, List[str]]:
        snapshots = self.db.get_recent_snapshots(market.ticker, minutes=60)
        now = datetime.now()
        super_bowl_date = datetime(2026, 2, 8)
        days_until = (super_bowl_date.date() - now.date()).days

        if vertical in ["NFL", "CULTURE"] and days_until <= 1:
            catalyst_score = 0.9
        elif vertical in ["NFL", "CULTURE"] and days_until <= 3:
            catalyst_score = 0.6
        else:
            catalyst_score = 0.3

        volume = market.volume or 0
        oi = market.open_interest or 0
        info_strength = min(1.0, (volume + oi) / 10000)

        consensus_shift = 0.0
        if len(snapshots) >= 2 and snapshots[0][1] is not None and snapshots[-1][1] is not None:
            recent_price = snapshots[0][1]
            old_price = snapshots[-1][1]
            consensus_shift = (recent_price - old_price) / 100.0

        volatility_flag = 0.0
        if len(snapshots) >= 2:
            prices = [s[1] for s in snapshots if s[1] is not None]
            if len(prices) >= 2:
                max_move = max(abs(prices[i] - prices[i + 1]) for i in range(len(prices) - 1))
                if max_move >= 5:
                    volatility_flag = 1.0

        spread = 0.20
        if market.yes_bid is not None and market.yes_ask is not None:
            spread = max(0.0, (market.yes_ask - market.yes_bid) / 100.0)
        market_microstructure = 1.0 - min(1.0, spread / 0.20)

        features = Features(
            catalyst_score=catalyst_score,
            info_strength=info_strength,
            consensus_shift=consensus_shift,
            volatility_flag=volatility_flag,
            market_microstructure=market_microstructure,
        )
        confidence = info_strength * 0.4 + market_microstructure * 0.6
        why = []
        if catalyst_score > 0.6:
            why.append(f"High catalyst: {superbowl_label_roman()} very soon")
        if volatility_flag > 0:
            why.append("Recent price volatility detected")
        if consensus_shift > 0.03:
            why.append(f"Bullish shift: +{consensus_shift*100:.1f}¢")
        elif consensus_shift < -0.03:
            why.append(f"Bearish shift: {consensus_shift*100:.1f}¢")
        if market_microstructure > 0.7:
            why.append("Tight spread / better microstructure")
        if not why:
            why.append("Standard signal based on model edge")
        return features, confidence, why

    def process(self, market: Market, vertical: str) -> AgentOutput:
        features, confidence, why = self.compute_features(market, vertical)
        return AgentOutput(
            market_ticker=market.ticker,
            title=market.title,
            vertical=vertical,
            timestamp=datetime.now().isoformat(),
            features=features,
            confidence=confidence,
            why=why,
        )


# ---------- Forecaster ----------

class Forecaster:
    def __init__(self):
        self.weights = {
            "catalyst_score": 0.15,
            "info_strength": 0.10,
            "consensus_shift": 0.40,
            "volatility_flag": 0.05,
            "market_microstructure": 0.05,
        }
        self.bias = 0.0

    def predict(self, features: Features, p_market: float) -> Tuple[float, float]:
        linear = self.bias
        linear += self.weights["catalyst_score"] * features.catalyst_score
        linear += self.weights["info_strength"] * features.info_strength
        linear += self.weights["consensus_shift"] * features.consensus_shift
        linear += self.weights["volatility_flag"] * features.volatility_flag
        linear += self.weights["market_microstructure"] * features.market_microstructure
        p_model = p_market + linear
        p_model = max(0.01, min(0.99, p_model))
        edge = p_model - p_market
        return p_model, edge
