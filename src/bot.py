"""
Discord bot: slash commands for signals, categories, watchlist, market, mode, health, notes.
Run with: python -m src.bot
"""
import datetime
import json
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from src.settings import Config
from src.db import Database
from src.kalshi_api import KalshiClient
from src.classifier import MarketClassifier

DB_PATH = Config.DB_PATH
WATCHLIST_PATH = Config.WATCHLIST_PATH


def get_db() -> Database:
    return Database(DB_PATH)


def get_watchlist() -> dict:
    path = Path(WATCHLIST_PATH)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_watchlist(data: dict):
    path = Path(WATCHLIST_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot logged in as {bot.user}")


# ---------- /signals ----------
@bot.tree.command(name="signals", description="List top signals with filters")
@app_commands.describe(
    category="Filter by category",
    min_edge="Minimum edge (0-1)",
    min_confidence="Minimum confidence (0-1)",
    limit="Max results (1-25)",
    sort="Sort by",
)
@app_commands.choices(
    category=[
        app_commands.Choice(name="all", value="all"),
        app_commands.Choice(name="sports", value="sports"),
        app_commands.Choice(name="politics", value="politics"),
        app_commands.Choice(name="crypto", value="crypto"),
        app_commands.Choice(name="weather", value="weather"),
        app_commands.Choice(name="pop_culture", value="pop_culture"),
        app_commands.Choice(name="nfl", value="nfl"),
        app_commands.Choice(name="nba", value="nba"),
        app_commands.Choice(name="culture", value="culture"),
        app_commands.Choice(name="custom", value="custom"),
    ],
    sort=[
        app_commands.Choice(name="edge", value="edge"),
        app_commands.Choice(name="confidence", value="confidence"),
        app_commands.Choice(name="volume", value="volume"),
        app_commands.Choice(name="open_interest", value="open_interest"),
        app_commands.Choice(name="recent", value="recent"),
        app_commands.Choice(name="signal_score", value="signal_score"),
    ],
)
async def cmd_signals(
    interaction: discord.Interaction,
    category: app_commands.Choice[str] = None,
    min_edge: float = None,
    min_confidence: float = None,
    limit: int = 10,
    sort: app_commands.Choice[str] = None,
):
    await interaction.response.defer()
    cat = category.value if category else "all"
    if min_edge is None:
        min_edge = Config.EDGE_THRESHOLD
    if min_confidence is None:
        min_confidence = Config.CONFIDENCE_THRESHOLD
    limit = max(1, min(25, limit))
    sort_val = sort.value if sort else "edge"
    db = get_db()
    rows = db.get_signals(category=cat, min_edge=min_edge, min_confidence=min_confidence, limit=limit, sort=sort_val)
    if not rows:
        await interaction.followup.send("No signals match the filters.")
        return
    emb = discord.Embed(title="Top signals", color=0x3498DB)
    for i, s in enumerate(rows[:10], 1):
        title = (s.get("title") or s.get("ticker", ""))[:60]
        ticker = s.get("ticker", "?")
        edge = s.get("edge", 0) * 100
        conf = s.get("confidence", 0) * 100
        p_m = s.get("p_market", 0) * 100
        p_mod = s.get("p_model", 0) * 100
        why = s.get("why") or []
        why_text = "\n".join(f"• {w}" for w in why[:3])
        emb.add_field(
            name=f"{i}. {title}",
            value=f"`{ticker}` | Edge **{edge:+.1f}%** | Conf {conf:.0f}%\nMarket {p_m:.1f}% → Model {p_mod:.1f}%\n{why_text}",
            inline=False,
        )
    emb.set_footer(text=f"Sort: {sort_val} | Limit: {limit}")
    await interaction.followup.send(embed=emb)


# ---------- /categories ----------
@bot.tree.command(name="categories", description="Show categories and market counts")
async def cmd_categories(interaction: discord.Interaction):
    await interaction.response.defer()
    wl = get_watchlist()
    by_cat = {}
    for ticker, cat in wl.items():
        by_cat[cat] = by_cat.get(cat, 0) + 1
    lines = [f"**{k}**: {v} markets" for k, v in sorted(by_cat.items())]
    emb = discord.Embed(title="Categories", description="\n".join(lines) if lines else "No watchlist loaded.", color=0x2ECC71)
    emb.set_footer(text=f"Total: {len(wl)} markets")
    await interaction.followup.send(embed=emb)


# ---------- /watchlist ----------
@bot.tree.command(name="watchlist", description="Show watchlist, optional category filter")
@app_commands.describe(category="Filter by category (nfl, nba, culture)")
async def cmd_watchlist(interaction: discord.Interaction, category: str = None):
    await interaction.response.defer()
    wl = get_watchlist()
    if category:
        wl = {t: c for t, c in wl.items() if c.upper() == category.upper()}
    items = list(wl.items())[:30]
    if not items:
        await interaction.followup.send("Watchlist is empty or no matches.")
        return
    lines = [f"`{t}` → {c}" for t, c in items]
    emb = discord.Embed(title="Watchlist", description="\n".join(lines), color=0x9B59B6)
    if len(wl) > 30:
        emb.set_footer(text=f"Showing 30 of {len(wl)}")
    await interaction.followup.send(embed=emb)


# ---------- /watch add / watch remove (group) ----------
watch_group = app_commands.Group(name="watch", description="Manage watchlist")


@watch_group.command(name="add", description="Add ticker or query to watchlist")
@app_commands.describe(query_or_ticker="Ticker or search query", category="Category (nfl, nba, culture)")
async def cmd_watch_add(interaction: discord.Interaction, query_or_ticker: str, category: str = "CUSTOM"):
    await interaction.response.defer()
    wl = get_watchlist()
    ticker = query_or_ticker.strip().upper()
    cat = category.upper() if category else "CUSTOM"
    if cat not in ("NFL", "NBA", "CULTURE", "CUSTOM"):
        cat = "CUSTOM"
    wl[ticker] = cat
    save_watchlist(wl)
    await interaction.followup.send(f"Added `{ticker}` to watchlist as **{cat}**.")


@watch_group.command(name="remove", description="Remove ticker from watchlist")
@app_commands.describe(ticker="Ticker to remove")
async def cmd_watch_remove(interaction: discord.Interaction, ticker: str):
    await interaction.response.defer()
    wl = get_watchlist()
    t = ticker.strip().upper()
    if t not in wl:
        await interaction.followup.send(f"`{t}` not in watchlist.")
        return
    del wl[t]
    save_watchlist(wl)
    await interaction.followup.send(f"Removed `{t}` from watchlist.")


bot.tree.add_command(watch_group)


# ---------- /market ----------
@bot.tree.command(name="market", description="Show last snapshot and signal for a ticker")
@app_commands.describe(ticker="Market ticker")
async def cmd_market(interaction: discord.Interaction, ticker: str):
    await interaction.response.defer()
    t = ticker.strip().upper()
    db = get_db()
    hist = db.get_snapshot_history(t, limit=5)
    last_signal = db.get_last_signal_for_ticker(t)
    agent = db.get_last_agent_output(t)
    if not hist and not last_signal:
        await interaction.followup.send(f"No data for `{t}`.")
        return
    emb = discord.Embed(title=f"Market: {t}", color=0xE67E22)
    if last_signal:
        emb.add_field(name="Last signal", value=f"Edge {last_signal.get('edge', 0)*100:+.1f}% | Conf {last_signal.get('confidence', 0)*100:.0f}%", inline=False)
        emb.add_field(name="Why", value="\n".join(f"• {w}" for w in (last_signal.get("why") or [])), inline=False)
    if hist:
        lines = []
        for row in hist[:5]:
            ts = row.get("ts", "")[:19]
            yb = row.get("yes_bid")
            lines.append(f"{ts}: yes_bid={yb}")
        emb.add_field(name="Recent snapshots", value="\n".join(lines), inline=False)
    if agent:
        emb.add_field(name="Last agent vertical", value=agent.get("vertical", "?"), inline=True)
    await interaction.followup.send(embed=emb)


# ---------- /mode ----------
@bot.tree.command(name="mode", description="Show or set mode (A/B/C). C = full scan.")
@app_commands.describe(mode="Set mode to A, B, or C")
async def cmd_mode(interaction: discord.Interaction, mode: str = None):
    await interaction.response.defer()
    current = Config.MODE
    if mode:
        m = mode.upper()
        if m not in ("A", "B", "C"):
            await interaction.followup.send("Mode must be A, B, or C.")
            return
        # Persist in env is not trivial from bot; just report current from env
        await interaction.followup.send(f"Current mode (from env) is **{current}**. To change, set MODE={m} in .env and restart.")
        return
    emb = discord.Embed(title="Mode", description=f"**Current: {current}**\n• A/B: legacy\n• C: scan all markets, full categories", color=0x1ABC9C)
    await interaction.followup.send(embed=emb)


# ---------- /health ----------
@bot.tree.command(name="health", description="Last poll, API, DB, signals/hour")
async def cmd_health(interaction: discord.Interaction):
    await interaction.response.defer()
    db = get_db()
    last_poll = db.get_last_poll_time()
    signals_hour = db.get_signals_last_hour()
    kalshi = KalshiClient(Config.KALSHI_BASE_URL, Config.KALSHI_API_KEY)
    api_ok = kalshi.health_check()
    emb = discord.Embed(title="Health", color=0x27AE60)
    emb.add_field(name="Last poll (snapshots)", value=last_poll or "—", inline=False)
    emb.add_field(name="Kalshi API", value="OK" if api_ok else "Error", inline=True)
    emb.add_field(name="Signals (last hour)", value=str(signals_hour), inline=True)
    emb.add_field(name="Rate limit (max/hour)", value=str(Config.MAX_SIGNALS_PER_HOUR), inline=True)
    await interaction.followup.send(embed=emb)


# ---------- /note set / note get ----------
note_group = app_commands.Group(name="note", description="Research notes for a market")


@note_group.command(name="set", description="Set research note for a ticker")
@app_commands.describe(ticker="Market ticker", text="Note text (thesis, sources, etc.)")
async def cmd_note_set(interaction: discord.Interaction, ticker: str, text: str):
    await interaction.response.defer()
    t = ticker.strip().upper()
    db = get_db()
    notes = {"thesis": text, "sources": [], "key_facts": [], "last_update_ts": None}
    notes["last_update_ts"] = datetime.datetime.utcnow().isoformat() + "Z"
    db.note_set(t, notes)
    await interaction.followup.send(f"Note set for `{t}`.")


@note_group.command(name="get", description="Get research note for a ticker")
@app_commands.describe(ticker="Market ticker")
async def cmd_note_get(interaction: discord.Interaction, ticker: str):
    await interaction.response.defer()
    t = ticker.strip().upper()
    db = get_db()
    notes = db.note_get(t)
    if not notes:
        await interaction.followup.send(f"No note for `{t}`.")
        return
    thesis = notes.get("thesis", "")
    emb = discord.Embed(title=f"Note: {t}", description=thesis[:400], color=0x95A5A6)
    emb.set_footer(text=notes.get("last_update_ts", ""))
    await interaction.followup.send(embed=emb)


bot.tree.add_command(note_group)


def main():
    token = Config.DISCORD_BOT_TOKEN or os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("DISCORD_BOT_TOKEN not set. Set it in .env")
        return
    bot.run(token)


if __name__ == "__main__":
    main()
