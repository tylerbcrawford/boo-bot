# Boo Bot

Modular Discord bot for media server management — book requests, TV/movie search, smart notifications, YouTube trailers, and AI-powered search.

Built with Python, [discord.py](https://discordpy.readthedocs.io/), and the Cogs extension system.

## Why I Built This

I run a 49-service self-hosted media server (Plex, Sonarr, Radarr, Readarr, Prowlarr, and more) for a small community of friends and family. [Notifiarr](https://notifiarr.com/) handles webhook notifications from these services, but it posts as a generic bot with no personality and no context — raw embed dumps that most people ignore.

I wanted a bot that owns the server's Discord presence. One that rebrands every notification under a single identity, adds YouTube trailers to new media announcements, suppresses notification floods when entire seasons land at once, and gives users clean request workflows instead of asking them to navigate Sonarr's UI. Each feature is built as an independent cog, so I can develop, test, and deploy them without touching unrelated code.

This is the real bot running in production.

## Features

### Book Management
Multi-instance Readarr integration with 3-tier search fallback.

- Supports 4 Readarr instances (ebooks x 2, audiobooks x 2), each with independent search and configuration
- Fallback chain: Readarr API lookup → Prowlarr indexer shell-out (6-minute timeout) → monitoring-only add for external acquisition
- Author-scoped cleanup: polling loop catches Readarr's async catalog ingestion and unmonitors unwanted sibling titles before triggering search

### Media Requests
Sonarr and Radarr integration with duplicate detection.

- Poster thumbnails in selection embeds with emoji reaction selection (1-5)
- HTTP 400 response parsing distinguishes "already in library" from real API errors
- Shows monitored for all seasons on add; movies auto-search immediately

### Notification Rebranding
Intercepts Notifiarr webhook messages and reposts them as Boo Bot.

- Cross-cog communication: checks Episode Suppressor state before rebranding to prevent race conditions
- Request lifecycle: consolidates Notifiarr's 3-message request flow into a single message with edit-in-place fulfillment
- YouTube trailers via TMDb API with a retry queue (3 attempts over 7 hours for movies)
- Season-aware: S01 gets the series trailer, S02+ gets a season-specific trailer only

### Episode Suppression
Prevents notification floods when new series are added or bulk imports land.

- Three detection strategies: explicit trigger, new-season detection, and a rapid-fire sliding window (3+ episodes in 5 minutes)
- Fuzzy series name matching (strips articles, punctuation, year suffixes)
- Atomic JSON persistence (write-to-temp-then-rename) for crash-safe state

### Manual Import Detection
Fills a gap in Notifiarr's webhook coverage for Readarr.

- Readarr doesn't fire webhooks for manual imports (confirmed upstream — Readarr is EOL)
- Async polling with `asyncio.to_thread` and a seeding pattern that prevents replay storms on startup
- Mirrors Notifiarr's embed style so manual imports look identical to automatic ones

### AI Search
Perplexity-powered search with a channel-as-interface pattern.

- No command prefix — any message posted in the search channel triggers a query
- Citation extraction, 4-pass answer cleaning, and response chunking for Discord's 2000-character limit
- Per-user cooldown with configurable interval

## Architecture

```
boo-bot/
├── bot.py                        # Entry point — loads cogs, handles errors
├── config.py                     # Configuration from environment variables
├── entrypoint.sh                 # Docker entrypoint (installs deps, runs bot)
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable reference
├── data/                         # Runtime state (gitignored)
│   ├── episode_suppressions.json
│   ├── trailer_retries.json
│   ├── request_messages.json
│   └── manual_import_state.json
├── cogs/                         # Feature modules
│   ├── books.py                  # Book requests via Readarr
│   ├── media.py                  # TV/movie requests via Sonarr & Radarr
│   ├── notifiarr_rebrander.py    # Notification rebranding + trailers
│   ├── episode_suppressor.py     # Episode flood suppression
│   ├── readarr_manual_import.py  # Manual import detection
│   └── perplexity_search.py      # AI-powered search
└── utils/                        # Shared utilities
    ├── api_clients.py            # Readarr, Sonarr, Radarr API clients
    ├── trailarr_client.py        # TMDb API v3 client for trailer lookups
    └── trailer_retry_manager.py  # Retry queue for failed trailer lookups
```

**Why Cogs?** Each feature is isolated in its own file, can be hot-reloaded without restarting the bot, and communicates with other cogs through `bot.cogs['Name']` when coordination is needed (e.g., the rebrander checks the suppressor before acting).

**Key patterns:**
- JSON state persistence with atomic writes (write to temp, then rename)
- Unified API client error handling with success/error/already-exists return types
- Async-first design with `asyncio.to_thread` for blocking HTTP calls

## Commands

### Book Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!book <query>` | Search and add a book (requests channel) | `!book Taipei by Tao Lin` |
| `!audiobook <query>` | Search and add an audiobook (requests channel) | `!audiobook The Name of the Wind` |
| `!searchbook <query>` | Search books without adding | `!searchbook Stephen King` |
| `!readarr` | Test Readarr connection | `!readarr` |

### Media Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!tv <query>` | Search and add a TV show (requests channel) | `!tv Breaking Bad` |
| `!movie <query>` | Search and add a movie (requests channel) | `!movie Inception` |
| `!sonarr` | Test Sonarr connection | `!sonarr` |
| `!radarr` | Test Radarr connection | `!radarr` |

Search returns up to 5 results in a numbered embed with poster thumbnails. React with 1-5 to select (60s timeout). Single results are added automatically. Duplicate detection returns a friendly "already in library" message.

### Episode Suppressor Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `!suppressions` | Show active suppressions | Manage Messages |
| `!cleanup episodes <show> <hours>` | Manually suppress a show | Manage Messages |
| `!cleanup purge <show> <limit>` | Delete episode notifications | Manage Messages |
| `!cleanup purge all <limit>` | Delete all episode notifications | Manage Messages |
| `!cleanup clear <show>` | Remove suppression for a show | Manage Messages |
| `!cleanup clear all` | Remove all suppressions | Manage Messages |

### Rebrander Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `!rebrander` | Show rebrander status and pending requests | — |
| `!addtrailer <msg_id> <title> [year]` | Manually add trailer to a message | Admin |

### Manual Import Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `!imports` | Show manual import notifier status | — |

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/tylerbcrawford/boo-bot.git
cd boo-bot

python3 -m venv venv
source venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your Discord token and API keys. See [Configuration](#configuration) for details.

### 3. Run

```bash
source venv/bin/activate
python3 bot.py
```

The bot prints a startup banner listing loaded cogs and connected guilds.

## Configuration

All settings are configured through environment variables in `.env`. Copy `.env.example` as a starting point.

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | Yes | Bot token from Discord Developer Portal |
| `COMMAND_PREFIX` | No | Command prefix (default: `!`) |
| `READARR_URL` / `_API_KEY` | For books | Primary Readarr instance |
| `READARR_AUDIOBOOK_URL` / `_API_KEY` | For audiobooks | Audiobook Readarr instance |
| `READARR2_URL` / `_API_KEY` | Optional | Second ebook instance |
| `READARR_AUDIO2_URL` / `_API_KEY` | Optional | Second audiobook instance |
| `SONARR_URL` / `_API_KEY` | For TV | Sonarr instance |
| `RADARR_URL` / `_API_KEY` | For movies | Radarr instance |
| `TMDB_API_KEY` | For trailers | TMDb API key (v3 auth) |
| `TRAILARR_ENABLED` | No | Enable trailer lookups (default: `true`) |
| `EPISODE_SUPPRESSION_HOURS` | No | Suppression window in hours (default: `24`) |
| `EPISODE_SUPPRESSION_CHANNEL` | No | Channel to monitor (default: `general`) |
| `MANUAL_IMPORT_POLL_INTERVAL` | No | Polling interval in seconds (default: `60`) |
| `PERPLEXITY_API_KEY` | For AI search | Perplexity API key |
| `PERPLEXITY_CHANNEL_NAME` | No | Channel name for search (default: `perplexity`) |
| `PERPLEXITY_MODEL` | No | Perplexity model (default: `sonar`) |
| `PERPLEXITY_COOLDOWN_SECONDS` | No | Per-user cooldown (default: `10`) |

Each Readarr instance also accepts `ROOT_FOLDER_PATH`, `QUALITY_PROFILE_ID`, and `METADATA_PROFILE_ID`. See `.env.example` for the full list with Docker vs. local URL examples.

## Docker Deployment

```yaml
services:
  discord-bot:
    image: python:3.11-slim
    container_name: discord-bot
    restart: unless-stopped
    working_dir: /app
    volumes:
      - ./boo-bot:/app
    env_file:
      - ./boo-bot/.env
    command: /app/entrypoint.sh
    networks:
      - media
```

The `entrypoint.sh` script installs dependencies and starts the bot with unbuffered output. Mount the project directory so the `data/` folder persists state across restarts.

## API Keys

| Service | Purpose | Where to get it |
|---------|---------|-----------------|
| Discord | Bot authentication | [Developer Portal](https://discord.com/developers/applications) — Bot tab → Reset Token |
| TMDb | YouTube trailer lookups | [TMDb Settings](https://www.themoviedb.org/settings/api) — Request API Key → copy v3 key |
| Readarr / Sonarr / Radarr | Media management | Each app's Settings → General → Security → API Key |
| Perplexity | AI search | [Perplexity API](https://docs.perplexity.ai/) |

When setting up the Discord bot, enable **Message Content Intent** under Privileged Gateway Intents, and grant the bot `Send Messages`, `Embed Links`, `Read Message History`, `Add Reactions`, and `Manage Messages` permissions.

## Troubleshooting

**Bot won't start** — Verify `DISCORD_TOKEN` is set in `.env` and the token hasn't been regenerated in the Developer Portal.

**Commands not working** — Ensure Message Content Intent is enabled in the Discord Developer Portal. Check that the bot has the correct permissions in your server and the command prefix matches (default: `!`).

**Module not found** — Activate the virtual environment (`source venv/bin/activate`) and run `pip install -r requirements.txt`.

**Cog not loading** — Check syntax with `python3 -m py_compile cogs/your_cog.py`. Verify the cog is listed in the `cog_modules` array in `bot.py`. Check bot logs for the specific error.

**Docker issues** — Run `docker logs <container-name> -f` to see bot output. Make sure the project directory is mounted as a volume so `data/` state persists.

## License

MIT License — see [LICENSE](LICENSE).

## Acknowledgments

- Built with [Claude Code](https://claude.com/claude-code)
