#!/usr/bin/env python3
"""
Kalshi Signals MVP - Demo/Test Script
Tests classification and signal generation without requiring Discord
"""

import os
os.environ["DRY_RUN"] = "false"
os.environ["DISCORD_WEBHOOK_URL"] = ""  # Disable Discord for demo

from kalshi_signals import (
    MarketClassifier,
    Config,
    Database,
    Agent,
    Forecaster,
    Market,
    Features,
    SUPERBOWL,
    superbowl_label_roman,
)
from datetime import datetime

def test_classification():
    print("\n" + "="*60)
    print("TEST: Market Classification")
    print("="*60 + "\n")

    sb = superbowl_label_roman()
    pats = SUPERBOWL["teams"]["home"]["name"].split()[-1]  # Patriots
    hawks = SUPERBOWL["teams"]["away"]["name"].split()[-1]  # Seahawks
    test_cases = [
        (f"Will the {pats} win {sb}?", "NFL"),
        (f"Will the {hawks} win {sb}?", "NFL"),
        (f"{sb} MVP winner", "NFL"),
        ("How many touchdowns in first quarter of Super Bowl?", "NFL"),
        ("Will Bad Bunny perform at Super Bowl halftime?", "CULTURE"),
        ("Length of national anthem at Super Bowl", "CULTURE"),
        ("Will there be a Budweiser commercial during Super Bowl?", "CULTURE"),
        ("NBA All-Star 3-point contest winner", "NBA"),
        ("All-Star Game total points", "NBA"),
        ("Will there be an NFL Honors afterparty?", "CULTURE"),
    ]

    for title, expected in test_cases:
        result = MarketClassifier.classify(title)
        status = "✅" if result == expected else "❌"
        print(f"{status} {title[:70]}")
        print(f"   Expected: {expected}, Got: {result}\n")

def test_agent_features():
    print("\n" + "="*60)
    print("TEST: Agent Feature Computation")
    print("="*60 + "\n")

    db = Database(":memory:")
    agent = Agent(db)

    market = Market(
        ticker="TEST-PATS-WIN",
        title=f"Will the {SUPERBOWL['teams']['home']['name'].split()[-1]} win {superbowl_label_roman()}?",
        yes_bid=55,
        yes_ask=None,
        no_bid=45,
        no_ask=None,
        volume=50000,
        open_interest=100000
    )

    output = agent.process(market, "NFL")

    print(f"Market: {output.title}")
    print(f"Ticker: {output.market_ticker}")
    print(f"Vertical: {output.vertical}\n")

    print("Features:")
    print(f"  Catalyst Score: {output.features.catalyst_score:.2f}")
    print(f"  Info Strength: {output.features.info_strength:.2f}")
    print(f"  Consensus Shift: {output.features.consensus_shift:.2f}")
    print(f"  Volatility Flag: {output.features.volatility_flag:.2f}")
    print(f"  Market Microstructure: {output.features.market_microstructure:.2f}")

    print(f"\nConfidence: {output.confidence*100:.1f}%")

    print("\nReasoning:")
    for why in output.why:
        print(f"  • {why}")

def test_forecaster():
    print("\n" + "="*60)
    print("TEST: Forecaster Edge Calculation")
    print("="*60 + "\n")

    forecaster = Forecaster()

    test_scenarios = [
        ("High catalyst, bullish shift", Features(0.9, 0.6, 0.05, 0.0, 0.8), 0.50),
        ("Low catalyst, no shift", Features(0.3, 0.4, 0.0, 0.0, 0.6), 0.50),
        ("Bearish shift", Features(0.5, 0.5, -0.04, 0.0, 0.7), 0.50),
        ("Volatile market", Features(0.6, 0.3, 0.02, 1.0, 0.5), 0.50),
    ]

    for name, features, p_market in test_scenarios:
        p_model, edge = forecaster.predict(features, p_market)

        print(f"Scenario: {name}")
        print(f"  Market Prob: {p_market*100:.1f}%")
        print(f"  Model Prob: {p_model*100:.1f}%")
        print(f"  Edge: {edge*100:+.1f}%")

        if abs(edge) >= 0.06:
            print("  🎯 SIGNAL TRIGGERED (edge >= 6%)")
        print()

def test_signal_generation():
    print("\n" + "="*60)
    print("TEST: Signal Generation Pipeline")
    print("="*60 + "\n")

    db = Database(":memory:")
    agent = Agent(db)
    forecaster = Forecaster()

    away = SUPERBOWL["teams"]["away"]["name"].split()[-1]
    home = SUPERBOWL["teams"]["home"]["name"].split()[-1]
    market = Market(
        ticker="TEST-SB-SEA-NE",
        title=f"Will the {away} beat the {home} in {superbowl_label_roman()}?",
        yes_bid=48,
        yes_ask=None,
        volume=100000,
        open_interest=200000
    )

    ts = datetime.now().isoformat()
    db.save_snapshot(ts, market)

    p_market = market.yes_bid / 100.0
    output = agent.process(market, "NFL")
    p_model, edge = forecaster.predict(output.features, p_market)

    print(f"Market: {market.title}")
    print(f"YES Bid: {market.yes_bid}¢")
    print(f"Market Prob: {p_market*100:.1f}%")
    print(f"Model Prob: {p_model*100:.1f}%")
    print(f"Edge: {edge*100:+.1f}%")
    print(f"Confidence: {output.confidence*100:.0f}%")

    print("\nThreshold Checks:")
    print(f"  Edge >= 6%: {'✅' if edge >= 0.06 else '❌'} ({edge*100:.1f}%)")
    print(f"  Confidence >= 65%: {'✅' if output.confidence >= 0.65 else '❌'} ({output.confidence*100:.0f}%)")

    if edge >= 0.06 and output.confidence >= 0.65:
        print("\n🎯 SIGNAL WOULD BE SENT TO DISCORD")
        print("\nReasoning:")
        for why in output.why:
            print(f"  • {why}")

def main():
    print("\n" + "="*60)
    print("🧪 Kalshi Signals MVP - Test Suite (Sali)")
    print("="*60)

    test_classification()
    test_agent_features()
    test_forecaster()
    test_signal_generation()

    print("\n" + "="*60)
    print("✅ All tests completed")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
