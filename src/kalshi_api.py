"""
Kalshi API client: markets and orderbook.
"""
import time
from typing import Dict, List, Optional

import requests


class KalshiClient:
    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def get_markets(self, limit: int = 1000, status: str = "open") -> List[Dict]:
        url = f"{self.base_url}/markets"
        params = {"limit": limit, "status": status}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("markets", [])
        except Exception as e:
            print(f"Error fetching markets: {e}")
            return []

    def get_market_orderbook(self, ticker: str, max_retries: int = 2) -> Optional[Dict]:
        """Fetch orderbook; on 429 rate limit: backoff and retry, then skip (return None)."""
        url = f"{self.base_url}/markets/{ticker}/orderbook"
        backoff = 2
        for attempt in range(max_retries + 1):
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 429:
                    try:
                        retry_after = int(resp.headers.get("Retry-After", backoff))
                    except (TypeError, ValueError):
                        retry_after = backoff
                    retry_after = min(max(retry_after, 1), 60)
                    if attempt < max_retries:
                        print(f"Rate limited (429) for {ticker}, backing off {retry_after}s")
                        time.sleep(retry_after)
                        backoff *= 2
                        continue
                    print(f"Rate limited (429) for {ticker}, skipping after retries")
                    return None
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                if attempt < max_retries and "429" in str(e):
                    print(f"Rate limited for {ticker}, backing off {backoff}s")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                print(f"Error fetching orderbook for {ticker}: {e}")
                return None
        return None

    def health_check(self) -> bool:
        """Return True if API is reachable."""
        try:
            resp = self.session.get(f"{self.base_url}/markets", params={"limit": 1}, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
