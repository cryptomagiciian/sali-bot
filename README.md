# Sali — Kalshi Signals MVP

Discord bot + polling runner for Kalshi markets. **Category loop** (Option 2): scan all markets each cycle, surface best signals per category (Sports, Politics, Crypto, Weather, Pop Culture). Modes A/B/C still supported; watchlist override works in Mode C.

- **Runner**: polls Kalshi; with **ENABLE_CATEGORY_LOOP=true** (default) runs category-loop discovery (keywords → score → top_n per category → one aggregated webhook payload). Otherwise watchlist-based loop. Cooldown per ticker (COOLDOWN_MINUTES).
- **Bot**: slash commands for `/signals`, `/categories`, `/watchlist`, `/watch add|remove`, `/market`, `/mode`, `/health`, `/note set|get`.

Config: **`src/config/superbowl-config.json`** (Python) and **`src/config/superbowl.ts`** (TS). Event label and matchup use these (no hardcoded teams).

---

## Quick start

### 1. Env

```bash
cp .env.example .env
```

Edit `.env`:

- **KALSHI_BASE_URL** (default fine for elections API)
- **DISCORD_BOT_TOKEN** — create an app at [Discord Developer Portal](https://discord.com/developers/applications), bot token required for slash commands.
- **DISCORD_WEBHOOK_URL** — optional; used as fallback when not using bot for alerts.
- **USE_DISCORD_BOT** — `true` to prefer bot; alerts can still go to webhook if you post from runner.
- **MODE** — `C` for full scan across categories.
- **DRY_RUN** — `true`: discovery only, no live polling; `false`: run polling loop.
- **ENABLE_CATEGORY_LOOP** — `true` (default): each cycle pull all markets, match by category keywords (title/subtitle/event/ticker), score, take top_n per category, dedupe, send one notification. `false`: legacy watchlist-only loop.
- **TOP_N_PER_CATEGORY** — optional override: max signals per category per cycle (e.g. `5`). If unset, uses per-category `top_n` from `src/category_rules.py`.
- **COOLDOWN_MINUTES** — do not notify the same ticker more than once in this many minutes (default `30`).

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Run (two processes)

**Terminal 1 — Runner (polling + DB + optional webhook):**

```bash
python -m src.runner
```

- With `DRY_RUN=true`: discovers markets and updates `watchlist.json`; no loop.
- With `DRY_RUN=false`: runs the polling loop, snapshots, computes signals, writes DB; if webhook set and not using bot for alerts, posts there.

**Terminal 2 — Bot (Discord slash commands):**

```bash
python -m src.bot
```

- Requires **DISCORD_BOT_TOKEN** in `.env`.
- Invite the bot with scope `applications.commands`. Commands sync on startup.

---

## Discord commands (examples)

| Command | Description |
|--------|-------------|
| `/signals` | Top signals; options: category (all/nfl/nba/culture), min_edge, min_confidence, limit, sort (edge/confidence/volume/signal_score/recent) |
| `/categories` | Counts per category (from watchlist) |
| `/watchlist [category]` | List watchlist entries, optional filter |
| `/watch add <ticker_or_query> [category]` | Add to watchlist (persisted to watchlist.json) |
| `/watch remove <ticker>` | Remove from watchlist |
| `/market <ticker>` | Last snapshot, last signal, short history from DB |
| `/mode [A\|B\|C]` | Show or hint to set mode (C = full scan) |
| `/health` | Last poll time, Kalshi API status, DB, signals in last hour |
| `/note set <ticker> <text>` | Set research note for ticker (thesis/sources in DB) |
| `/note get <ticker>` | Get note for ticker |

---

## Project layout

- **src/settings.py** — Env, paths, Super Bowl config.
- **src/models.py** — Market, Features, Signal, AgentOutput.
- **src/db.py** — SQLite: snapshots, agent_outputs, predictions, signals, last_alert, **market_notes**.
- **src/kalshi_api.py** — Kalshi client (markets, orderbook).
- **src/classifier.py** — Keywords + gameId→league; categories NFL/NBA/CULTURE.
- **src/scoring.py** — Agent, Forecaster, **signal_score** (edge×confidence × liquidity × recency × spread).
- **src/runner.py** — WatchlistManager, SignalEngine, DiscordNotifier (webhook + category-picks embeds), polling loop; category loop when ENABLE_CATEGORY_LOOP=true.
- **src/category_rules.py** — Single source of truth: **CATEGORY_RULES** (sports, politics, crypto, weather, pop_culture) with keywords and top_n. Match on title + subtitle + event_ticker + event_name + ticker.
- **src/bot.py** — Discord bot and slash commands.
- **src/config/** — superbowl-config.json, gameIdToLeague.json (and TS sources).

Signal score formula (see `src/scoring.py`):

- `signal_score = (edge * confidence) * liquidity_factor * recency_factor * spread_factor`
- Liquidity: log(1 + (vol+oi)/2000), cap 1.5.
- Spread: penalty for wide spread.
- Recency: higher for recently moving markets.

---

## Super Bowl config check

```bash
npm run check:superbowl
```

Guards against legacy hardcoded strings and prints formatter output.
