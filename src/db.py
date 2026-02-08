"""
Database: snapshots, agent_outputs, predictions, signals, last_alert, market_notes.
Safe migrations: CREATE TABLE IF NOT EXISTS, ADD COLUMN when missing.
"""
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from dataclasses import asdict
from src.models import Market, AgentOutput, Signal

# Forward ref for type hints
AgentOutput  # noqa: B018


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._migrate()

    def _init_schema(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                ts TEXT, ticker TEXT, yes_bid INTEGER, no_bid INTEGER,
                yes_ask INTEGER, no_ask INTEGER, volume INTEGER, open_interest INTEGER,
                PRIMARY KEY (ts, ticker)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_outputs (
                ts TEXT, ticker TEXT, vertical TEXT, json_blob TEXT,
                PRIMARY KEY (ts, ticker)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                ts TEXT, ticker TEXT, p_market REAL, p_model REAL, edge REAL, confidence REAL,
                PRIMARY KEY (ts, ticker)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                ts TEXT, ticker TEXT, action TEXT, payload_json TEXT, signal_score REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS last_alert (ticker TEXT PRIMARY KEY, ts TEXT)
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS market_notes (
                ticker TEXT PRIMARY KEY,
                notes_json TEXT,
                updated_at TEXT
            )
        """)
        self.conn.commit()

    def _migrate(self):
        """Add signal_score column to signals if missing (existing DBs)."""
        c = self.conn.cursor()
        c.execute("PRAGMA table_info(signals)")
        cols = [row[1] for row in c.fetchall()]
        if "signal_score" not in cols:
            c.execute("ALTER TABLE signals ADD COLUMN signal_score REAL")
            self.conn.commit()

    def save_snapshot(self, ts: str, market: Market):
        c = self.conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO snapshots
            (ts, ticker, yes_bid, no_bid, yes_ask, no_ask, volume, open_interest)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, market.ticker, market.yes_bid, market.no_bid,
              market.yes_ask, market.no_ask, market.volume, market.open_interest))
        self.conn.commit()

    def save_agent_output(self, output: AgentOutput):
        c = self.conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO agent_outputs (ts, ticker, vertical, json_blob)
            VALUES (?, ?, ?, ?)
        """, (output.timestamp, output.market_ticker, output.vertical,
              json.dumps(asdict(output))))
        self.conn.commit()

    def save_prediction(self, ts: str, ticker: str, p_market: float,
                        p_model: float, edge: float, confidence: float):
        c = self.conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO predictions (ts, ticker, p_market, p_model, edge, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, ticker, p_market, p_model, edge, confidence))
        self.conn.commit()

    def save_signal(self, ts: str, signal: Signal):
        c = self.conn.cursor()
        payload = signal.to_dict()
        score = getattr(signal, "signal_score", 0.0) or 0.0
        c.execute("""
            INSERT INTO signals (ts, ticker, action, payload_json, signal_score)
            VALUES (?, ?, 'ALERT', ?, ?)
        """, (ts, signal.ticker, json.dumps(payload), score))
        self.conn.commit()

    def update_last_alert(self, ticker: str, ts: str):
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO last_alert (ticker, ts) VALUES (?, ?)", (ticker, ts))
        self.conn.commit()

    def get_last_alert_time(self, ticker: str) -> Optional[str]:
        c = self.conn.cursor()
        c.execute("SELECT ts FROM last_alert WHERE ticker = ?", (ticker,))
        row = c.fetchone()
        return row[0] if row else None

    def get_recent_snapshots(self, ticker: str, minutes: int = 60) -> List[Tuple]:
        c = self.conn.cursor()
        cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        c.execute("""
            SELECT ts, yes_bid, volume FROM snapshots
            WHERE ticker = ? AND ts > ?
            ORDER BY ts DESC
        """, (ticker, cutoff))
        return c.fetchall()

    def get_signals_last_hour(self) -> int:
        c = self.conn.cursor()
        cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
        c.execute("SELECT COUNT(*) FROM signals WHERE ts > ?", (cutoff,))
        return c.fetchone()[0]

    # ---------- Query helpers for bot /signals ----------
    def get_signals(
        self,
        category: Optional[str] = None,
        min_edge: Optional[float] = None,
        min_confidence: Optional[float] = None,
        limit: int = 10,
        sort: str = "edge",
    ) -> List[Dict[str, Any]]:
        """Return recent signals with optional filters. sort: edge|confidence|volume|open_interest|recent|signal_score."""
        c = self.conn.cursor()
        # Build from signals table; payload_json has full signal
        c.execute("""
            SELECT ts, ticker, payload_json, signal_score FROM signals
            WHERE action = 'ALERT'
            ORDER BY ts DESC
            LIMIT 500
        """)
        rows = c.fetchall()
        out = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except Exception:
                continue
            vert = payload.get("vertical", "")
            if category and category != "all":
                if vert.upper() != category.upper():
                    continue
            edge = payload.get("edge", 0)
            conf = payload.get("confidence", 0)
            if min_edge is not None and edge < min_edge:
                continue
            if min_confidence is not None and conf < min_confidence:
                continue
            payload["ts"] = row["ts"]
            payload["signal_score"] = row["signal_score"] if row["signal_score"] is not None else (edge * conf)
            out.append(payload)
        # Sort
        if sort == "edge":
            out.sort(key=lambda x: x.get("edge", 0), reverse=True)
        elif sort == "confidence":
            out.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        elif sort == "volume":
            out.sort(key=lambda x: x.get("volume") or 0, reverse=True)
        elif sort == "open_interest":
            out.sort(key=lambda x: x.get("open_interest") or 0, reverse=True)
        elif sort == "signal_score":
            out.sort(key=lambda x: x.get("signal_score") or 0, reverse=True)
        # else recent: already DESC by ts, keep order
        return out[:limit]

    def get_last_signal_for_ticker(self, ticker: str) -> Optional[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT ts, payload_json FROM signals
            WHERE ticker = ? AND action = 'ALERT'
            ORDER BY ts DESC LIMIT 1
        """, (ticker,))
        row = c.fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
            payload["ts"] = row["ts"]
            return payload
        except Exception:
            return None

    def get_snapshot_history(self, ticker: str, limit: int = 10) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT ts, yes_bid, no_bid, yes_ask, no_ask, volume, open_interest
            FROM snapshots WHERE ticker = ?
            ORDER BY ts DESC LIMIT ?
        """, (ticker, limit))
        return [dict(r) for r in c.fetchall()]

    def get_last_agent_output(self, ticker: str) -> Optional[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT ts, json_blob FROM agent_outputs
            WHERE ticker = ? ORDER BY ts DESC LIMIT 1
        """, (ticker,))
        row = c.fetchone()
        if not row:
            return None
        try:
            return json.loads(row["json_blob"])
        except Exception:
            return None

    def get_last_poll_time(self) -> Optional[str]:
        """Latest snapshot ts (proxy for last poll)."""
        c = self.conn.cursor()
        c.execute("SELECT MAX(ts) FROM snapshots")
        row = c.fetchone()
        return row[0] if row and row[0] else None

    # ---------- Market notes (research layer) ----------
    def note_set(self, ticker: str, notes_json: Dict[str, Any]) -> None:
        c = self.conn.cursor()
        now = datetime.utcnow().isoformat() + "Z"
        c.execute("""
            INSERT OR REPLACE INTO market_notes (ticker, notes_json, updated_at)
            VALUES (?, ?, ?)
        """, (ticker, json.dumps(notes_json), now))
        self.conn.commit()

    def note_get(self, ticker: str) -> Optional[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT notes_json FROM market_notes WHERE ticker = ?", (ticker,))
        row = c.fetchone()
        if not row:
            return None
        try:
            return json.loads(row["notes_json"])
        except Exception:
            return None
