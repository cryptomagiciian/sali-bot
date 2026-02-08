"""
Polling runner: watchlist, discovery (Mode C), category loop (Option 2), webhook fallback.
Run with: python -m src.runner
"""
import json
import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import requests

from src.settings import Config
from src.db import Database
from src.kalshi_api import KalshiClient
from src.classifier import MarketClassifier
from src.scoring import Agent, Forecaster, compute_signal_score
from src.models import Market, Signal
from src.category_rules import (
    CATEGORY_RULES,
    get_top_n,
    match_market_to_categories,
)


# ---------- Watchlist ----------
class WatchlistManager:
    def __init__(self, watchlist_path: str):
        self.watchlist_path = watchlist_path
        self.watchlist: Dict[str, str] = {}
        self.load()

    def load(self):
        if os.path.exists(self.watchlist_path):
            with open(self.watchlist_path, "r", encoding="utf-8") as f:
                self.watchlist = json.load(f)

    def save(self):
        with open(self.watchlist_path, "w", encoding="utf-8") as f:
            json.dump(self.watchlist, f, indent=2)

    def add(self, ticker: str, category: str) -> None:
        self.watchlist[ticker] = category
        self.save()

    def remove(self, ticker: str) -> bool:
        if ticker in self.watchlist:
            del self.watchlist[ticker]
            self.save()
            return True
        return False

    def discover(self, kalshi: KalshiClient) -> Dict[str, str]:
        markets = kalshi.get_markets()
        discovered = {}
        for m in markets:
            ticker = m.get("ticker")
            title = m.get("title", "")
            if not ticker or not title:
                continue
            vertical = MarketClassifier.classify(title, ticker)
            if vertical:
                discovered[ticker] = vertical
        return discovered

    def update(self, discovered: Dict[str, str]):
        for ticker, vertical in discovered.items():
            if ticker not in self.watchlist:
                self.watchlist[ticker] = vertical
        self.save()


# ---------- Webhook notifier ----------
class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_signal(self, signal: Signal) -> bool:
        if not self.webhook_url:
            return False
        color = 0x00ff00 if signal.edge >= 0.10 else (0xffff00 if signal.edge >= 0.06 else 0xff9900)
        embed = {
            "title": f"Signal: {signal.title[:80]}",
            "color": color,
            "fields": [
                {"name": "Ticker", "value": f"`{signal.ticker}`", "inline": True},
                {"name": "Edge", "value": f"**{signal.edge*100:+.1f}%**", "inline": True},
                {"name": "Confidence", "value": f"{signal.confidence*100:.0f}%", "inline": True},
                {"name": "Why", "value": "\n".join(f"• {w}" for w in signal.why), "inline": False},
            ],
            "footer": {"text": f"Sali • {signal.timestamp}"},
        }
        try:
            resp = requests.post(
                self.webhook_url,
                json={"embeds": [embed], "username": "Sali"},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception:
            return False

    def send_category_picks(
        self,
        picks_by_category: Dict[str, List[Signal]],
        ts: str,
    ) -> bool:
        """Send one embed per category with top picks (ticker, title, p_market, p_model, edge, confidence, signal_score, matched_keywords, why)."""
        if not self.webhook_url:
            return False
        embeds = []
        for category, signals in picks_by_category.items():
            if not signals:
                continue
            color = 0x3498DB
            lines = []
            for s in signals:
                title_short = (s.title or s.ticker)[:50]
                mk = (s.matched_keywords or [])[:5]
                mk_str = ", ".join(mk) if mk else "—"
                why_str = "\n".join(f"• {w}" for w in (s.why or [])[:3])
                lines.append(
                    f"**{s.ticker}** — {title_short}\n"
                    f"p_market {s.p_market*100:.1f}% → p_model {s.p_model*100:.1f}% | "
                    f"edge **{s.edge*100:+.1f}%** | conf {s.confidence*100:.0f}% | score {getattr(s, 'signal_score', 0):.3f}\n"
                    f"matched: {mk_str}\n{why_str}"
                )
            body = "\n\n".join(lines)
            if len(body) > 1000:
                body = body[:997] + "..."
            embeds.append({
                "title": f"Category: {category}",
                "color": color,
                "description": body,
                "footer": {"text": f"Sali • {ts}"},
            })
        if not embeds:
            return False
        try:
            resp = requests.post(
                self.webhook_url,
                json={"embeds": embeds, "username": "Sali"},
                timeout=15,
            )
            resp.raise_for_status()
            return True
        except Exception:
            return False


# ---------- Helpers ----------
def _first_price(levels):
    if not levels:
        return None
    top = levels[0]
    if isinstance(top, (list, tuple)) and len(top) >= 1:
        return top[0]
    if isinstance(top, dict):
        return top.get("price")
    return None


# ---------- Signal engine ----------
class SignalEngine:
    def __init__(self, config: Config):
        self.config = config
        self.db = Database(config.DB_PATH)
        self.kalshi = KalshiClient(config.KALSHI_BASE_URL, config.KALSHI_API_KEY)
        self.agent = Agent(self.db)
        self.forecaster = Forecaster()
        self.notifier = DiscordNotifier(config.DISCORD_WEBHOOK_URL)
        self.watchlist = WatchlistManager(config.WATCHLIST_PATH)

    def check_cooldown(self, ticker: str) -> bool:
        last = self.db.get_last_alert_time(ticker)
        if not last:
            return True
        elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds() / 60
        return elapsed >= self.config.COOLDOWN_MINUTES

    def check_rate_limit(self) -> bool:
        return self.db.get_signals_last_hour() < self.config.MAX_SIGNALS_PER_HOUR

    def process_market(
        self,
        ticker: str,
        vertical: str,
        market_map: Dict,
        matched_keywords: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
    ) -> Optional[Signal]:
        orderbook = self.kalshi.get_market_orderbook(ticker)
        if not orderbook:
            return None
        yes_bid = _first_price(orderbook.get("yes_bids", []))
        no_bid = _first_price(orderbook.get("no_bids", []))
        if yes_bid is None:
            return None
        mdata = market_map.get(ticker)
        if not mdata:
            return None
        title = mdata.get("title", ticker)
        volume = int(mdata.get("volume") or 0)
        open_interest = int(mdata.get("open_interest") or 0)
        market = Market(
            ticker=ticker,
            title=title,
            yes_bid=int(yes_bid),
            no_bid=int(no_bid) if no_bid is not None else None,
            yes_ask=None,
            no_ask=None,
            volume=volume,
            open_interest=open_interest,
        )
        ts = datetime.now().isoformat()
        self.db.save_snapshot(ts, market)
        p_market = market.yes_bid / 100.0
        agent_output = self.agent.process(market, vertical)
        self.db.save_agent_output(agent_output)
        p_model, edge = self.forecaster.predict(agent_output.features, p_market)
        self.db.save_prediction(ts, ticker, p_market, p_model, edge, agent_output.confidence)

        spread_pct = 0.10
        if market.yes_ask is not None and market.yes_bid is not None:
            spread_pct = max(0, (market.yes_ask - market.yes_bid) / 100.0)

        if (edge >= self.config.EDGE_THRESHOLD and
                agent_output.confidence >= self.config.CONFIDENCE_THRESHOLD and
                spread_pct <= self.config.SPREAD_THRESHOLD):
            if not self.check_cooldown(ticker):
                return None
            if not self.check_rate_limit():
                return None

            signal_score = compute_signal_score(
                edge=edge,
                confidence=agent_output.confidence,
                volume=volume,
                open_interest=open_interest,
                spread_pct=spread_pct,
                last_move_minutes_ago=0.0,
            )
            signal = Signal(
                ticker=ticker,
                title=title,
                vertical=vertical,
                yes_price=market.yes_bid,
                p_market=p_market,
                p_model=p_model,
                edge=edge,
                confidence=agent_output.confidence,
                why=agent_output.why,
                timestamp=ts,
                signal_score=signal_score,
                volume=volume,
                open_interest=open_interest,
                matched_keywords=matched_keywords,
                categories=categories,
            )
            return signal
        return None

    def run_discovery_dry_run(self):
        discovered = self.watchlist.discover(self.kalshi)
        by_vertical = defaultdict(list)
        for ticker, vertical in discovered.items():
            by_vertical[vertical].append(ticker)
        markets = self.kalshi.get_markets()
        market_map = {m.get("ticker"): m for m in markets if m.get("ticker")}
        for vertical in ["NFL", "NBA", "CULTURE"]:
            tickers = by_vertical[vertical]
            print(f"\n{vertical} ({len(tickers)} markets):")
            for tkr in sorted(tickers)[:15]:
                title = market_map.get(tkr, {}).get("title", "")
                print(f"  • {tkr}: {title}")
            if len(tickers) > 15:
                print(f"  ... and {len(tickers) - 15} more")
        print(f"\nTotal discovered: {len(discovered)} markets")
        self.watchlist.update(discovered)

    def run_category_loop_once(
        self,
        market_map: Dict[str, Dict],
        top_n_override: Optional[int] = None,
    ) -> Dict[str, List[Signal]]:
        """
        Scan all markets, match to categories by keywords, score, take top_n per category.
        Dedupe: if a ticker appears in multiple categories, keep best signal_score and label with all categories.
        Returns picks_by_category (only tickers passing cooldown are included in the payload).
        """
        # 1) For each market, get (category, matched_keywords) list
        ticker_to_matches: Dict[str, List[Tuple[str, List[str]]]] = defaultdict(list)
        for ticker, m in market_map.items():
            title = m.get("title", "")
            subtitle = m.get("subtitle", "")
            event_ticker = m.get("event_ticker", "")
            event_name = m.get("event_title", "") or m.get("event_name", "") or ""
            for cat, matched in match_market_to_categories(
                title, subtitle, event_ticker, event_name, ticker
            ):
                ticker_to_matches[ticker].append((cat, matched))

        # 2) For each (ticker, category, matched_keywords), compute signal; collect (signal, category)
        candidates: List[Tuple[Signal, str, List[str]]] = []
        for ticker, cat_matched_list in ticker_to_matches.items():
            # Use first category as vertical for scoring; we'll attach all categories to signal later
            category = cat_matched_list[0][0]
            all_matched = []
            for _, mkw in cat_matched_list:
                all_matched.extend(mkw)
            all_matched = list(dict.fromkeys(all_matched))  # dedupe order-preserving
            all_cats = list(dict.fromkeys(c[0] for c in cat_matched_list))
            signal = self.process_market(
                ticker,
                category,
                market_map,
                matched_keywords=all_matched,
                categories=all_cats,
            )
            if signal:
                # Attach all categories and combined matched keywords
                signal.categories = all_cats
                signal.matched_keywords = all_matched
                candidates.append((signal, category, all_matched))

        # 3) Per category: rank by signal_score, take top_n
        by_cat: Dict[str, List[Tuple[Signal, List[str]]]] = defaultdict(list)
        for sig, cat, mkw in candidates:
            by_cat[cat].append((sig, mkw))
        for cat in by_cat:
            by_cat[cat].sort(key=lambda x: x[0].signal_score, reverse=True)
            top_n = top_n_override if top_n_override is not None else (self.config.TOP_N_PER_CATEGORY or get_top_n(cat))
            by_cat[cat] = by_cat[cat][:top_n]

        # 4) Dedupe by ticker: keep best signal_score; if same ticker in multiple categories, keep one entry per category for display but only notify once per ticker (cooldown)
        seen_tickers: Dict[str, float] = {}  # ticker -> best signal_score
        for cat in list(by_cat.keys()):
            kept = []
            for sig, mkw in by_cat[cat]:
                if sig.ticker not in seen_tickers or seen_tickers[sig.ticker] < sig.signal_score:
                    seen_tickers[sig.ticker] = sig.signal_score
                # Keep in this category list for display (we'll filter by cooldown when sending)
                kept.append((sig, mkw))
            by_cat[cat] = kept

        # 5) Build picks_by_category: only include tickers not in cooldown
        picks_by_category: Dict[str, List[Signal]] = {}
        for cat, pairs in by_cat.items():
            picks_by_category[cat] = []
            for sig, _ in pairs:
                if self.check_cooldown(sig.ticker):
                    picks_by_category[cat].append(sig)
        return picks_by_category

    def run_loop(self):
        print("Sali (Kalshi Signals) STARTED")
        print(f"Poll: {self.config.POLL_INTERVAL}s | Edge >= {self.config.EDGE_THRESHOLD*100:.1f}%")
        print(f"Category loop: {self.config.ENABLE_CATEGORY_LOOP} | Watchlist: {len(self.watchlist.watchlist)} markets\n")
        iteration = 0
        try:
            while True:
                iteration += 1
                markets = self.kalshi.get_markets()
                market_map = {m.get("ticker"): m for m in markets if m.get("ticker")}

                if self.config.ENABLE_CATEGORY_LOOP:
                    # Option 2: scan all markets, top_n per category, one aggregated notification
                    picks_by_category = self.run_category_loop_once(market_map)
                    # Persist signals to DB and notify
                    ts = datetime.now().isoformat()
                    notified = set()
                    for cat, signals in picks_by_category.items():
                        for sig in signals:
                            self.db.save_signal(sig.timestamp, sig)
                            if sig.ticker not in notified and not self.config.DRY_RUN:
                                notified.add(sig.ticker)
                                self.db.update_last_alert(sig.ticker, ts)
                    if not self.config.DRY_RUN and picks_by_category and self.notifier.webhook_url:
                        self.notifier.send_category_picks(picks_by_category, ts)
                        print(f"[{iteration}] Category loop: sent {sum(len(s) for s in picks_by_category.values())} picks")
                else:
                    # Legacy: watchlist-based loop
                    if iteration % 20 == 1:
                        discovered = self.watchlist.discover(self.kalshi)
                        self.watchlist.update(discovered)
                    signals_sent = 0
                    for ticker, vertical in list(self.watchlist.watchlist.items()):
                        signal = self.process_market(ticker, vertical, market_map)
                        if signal:
                            self.db.save_signal(signal.timestamp, signal)
                            if not self.config.DRY_RUN and self.notifier.send_signal(signal):
                                self.db.update_last_alert(ticker, signal.timestamp)
                                signals_sent += 1
                    print(f"[{iteration}] Processed {len(self.watchlist.watchlist)} markets, sent {signals_sent} signals")

                time.sleep(self.config.POLL_INTERVAL)
        except KeyboardInterrupt:
            print("Shutting down.")


def main():
    config = Config()
    if not config.DRY_RUN and not config.DISCORD_WEBHOOK_URL and not config.DISCORD_BOT_TOKEN:
        print("WARNING: No Discord webhook or bot token. Signals will not be sent.")
    engine = SignalEngine(config)
    if config.DRY_RUN:
        engine.run_discovery_dry_run()
    else:
        engine.run_loop()


if __name__ == "__main__":
    main()
