# 800801 Discord Bot

A modular Discord bot using the **Cogs system** for easy feature management. Currently supports book management via Readarr, with extensible architecture for adding TV shows (Sonarr), movies (Radarr), and other features.

**Docker Container**: `800801-discord-bot` (service name: `discord-bot`)

**GitHub Repository**: [https://github.com/tylerbcrawford/800801-discord-bot](https://github.com/tylerbcrawford/800801-discord-bot) (Private)

## ✅ Current Status: Fully Operational

**Last Updated**: January 2, 2026

### ✅ Completed:
- ✅ Bot restructured with modular cogs architecture
- ✅ Virtual environment created (`venv/`) and dependencies installed
- ✅ Discord bot token configured
- ✅ Readarr API configured
- ✅ Sonarr API configured
- ✅ Radarr API configured
- ✅ Bot successfully tested locally (connects to Discord server)
- ✅ Docker Compose service configured and working
- ✅ All code files created (`bot.py`, `config.py`, `cogs/`, `utils/`)
- ✅ **Docker startup issue FIXED** - Bot now runs successfully in container
- ✅ **Notifiarr Rebrander** - Rebrand Notifiarr posts in #general as bot (Dec 21, 2024)
- ✅ **YouTube Trailer Integration** - Automatic trailer links for movies AND TV series (Dec 29, 2024)
- ✅ **Episode Suppressor** - Prevent episode notification floods (Dec 29, 2024)
- ✅ **Episode Suppressor Race Condition Fix** - Fixed suppression not working (Dec 30, 2025)
- ✅ **Trailer Format Update** - New compact trailer message format (Dec 30, 2025)
- ✅ **Requests Channel Integration** - Smart media request workflow with reply preservation (Jan 2, 2026)

### 🔧 Docker Startup Fix (December 18, 2024):
**Problem**: Command chaining with `sh -c "pip install ... && python bot.py"` wasn't executing the second command.

**Solution**: Created dedicated [`entrypoint.sh`](./entrypoint.sh) script with:
- Proper shell script structure using `set -e` for error handling
- `exec python -u bot.py` for unbuffered output and proper process management
- Updated [`docker-compose.yml`](../docker-compose.yml) to use `command: /app/entrypoint.sh`

**Result**: Bot now starts successfully in Docker, connects to Discord, and is ready to receive commands!

### 🔧 Recent Updates

#### Media Request Fix Implementation Plan (January 10, 2026)
**Status**: 📋 Implementation plan created

**Root Cause Identified**: Book additions fail because the bot creates invalid foreign IDs (`google-{id}`, `google-author-{name}`) that Readarr rejects. Readarr requires valid Goodreads IDs from its metadata providers.

**Solution**: Comprehensive 3-phase implementation plan to:
- **Phase 1**: Fix book workflow using Readarr's `/api/v1/search` endpoint
- **Phase 2**: Add `!tv` command for Sonarr integration (port 8989)
- **Phase 3**: Add `!movie` command for Radarr integration (port 7878)

**Documentation**: See implementation plan in project folder for detailed step-by-step guide with code examples, testing workflows, and rollback strategies.

#### Requests Channel Integration (January 2, 2026)
**Feature**: Smart media request workflow that consolidates Notifiarr's 3-message flow into a clean, user-friendly experience.

**Problem**: Notifiarr posts three separate messages for media requests:
1. "Request Link" - User needs to click this
2. "Adding Movie/Show" - Confirmation of request
3. "Requested media available" - Fulfillment notification (as reply to requester)

This cluttered the #requests channel and made it hard to track request status.

**Solution**:
- **Request Link**: Rebranded as Boo Bot, stays visible for 30 seconds (for user to click), then auto-deletes
- **Adding Movie/Show**: Rebranded as Boo Bot, stored for later editing
- **Fulfillment**: Deletes the "Adding Movie" message and posts a new rebranded reply preserving the @mention

**Result**:
- Clean workflow with proper user notifications
- Request link visible temporarily (30s) for user interaction
- Final fulfillment message preserves reply chain and mentions the requester
- Persistent state tracking survives bot restarts ([data/request_messages.json](data/request_messages.json))

**Technical Details**:
- Title extraction from embed description: `I've added **Title** to the system`
- Reply preservation using Discord's `reference` parameter
- Fallback handling when request messages aren't found
- Works alongside existing #general channel rebranding

#### Episode Suppressor Race Condition Fix (December 30, 2025)
**Problem**: Episode notifications were appearing in Discord despite suppression being active. The `episode_suppressor` cog and `notifiarr_rebrander` cog both listened to `on_message`, creating a race condition where episodes were rebranded before suppression could delete them.

**Solution**:
- Modified `notifiarr_rebrander` to check with `episode_suppressor` **before** rebranding
- If episode is suppressed: deletes original Notifiarr message and returns early (no rebranding)
- If episode is not suppressed: continues with normal rebranding workflow
- Increments suppression counter when episodes are deleted

**Result**: Episode suppression now works reliably! Suppressed episodes are deleted immediately without being rebranded or displayed to users.

#### Trailer Format Update
**Old Format**:
```
🎬 Bridgerton Trailer:
https://www.youtube.com/watch?v=gpv7ayf_tyE
```

**New Format**:
```
🎬Trailer:
Bridgerton
https://www.youtube.com/watch?v=gpv7ayf_tyE
```

**Changes**:
- Removed space after emoji for compact look
- Title on separate line for better readability
- Applied to all trailer types: movies, TV series (S01), and TV seasons (S02+)
- Updated in all locations: rebrander, retry mechanism, and manual `!addtrailer` command

### 🎯 Next Steps:
1. **Fix book workflow**: Implement Phase 1 of media request fix plan (use Readarr metadata search API)
2. **Test book commands**: Verify `!book` and `!audiobook` work across all 4 Readarr instances
3. **Add TV command**: Implement `!tv` command for Sonarr (Phase 2)
4. **Add movie command**: Implement `!movie` command for Radarr (Phase 3)

📋 See implementation plan document for detailed execution steps.

### ⚡ Quick Test (Works Locally):
The bot **does work** when run directly (not in Docker):
```bash
cd boo-bot
source venv/bin/activate
python3 bot.py
# Output: "Boo Bot - Ready" + "Connected to 1 guild(s)"
```

**Available commands** (tested working locally):
- `!book <title>` - Search and add books to Readarr
- `!audiobook <title>` - Search and add audiobooks to Readarr
- `!searchbook <query>` - Search books without adding
- `!readarr` - Test Readarr connection
- `!sonarr` - Test Sonarr connection
- `!radarr` - Test Radarr connection

---

## 🎯 Features

### Current Features

- **📚 Book Management** (Readarr Integration)
  - Search books via Google Books API and OpenLibrary
  - Add books to Readarr automatically
  - Bypass Readarr's broken BookInfo API
  - Interactive book selection with reactions

- **🎬 Notifiarr Rebrander** (YouTube Trailer Integration + Smart Request Workflow)
  - **Dual-channel monitoring**: Rebrand messages in both #general and #requests
  - **#general channel**: Automatic YouTube trailer integration for new media
    - **Automatically adds YouTube trailer links** for new movies AND TV series via TMDb API
    - **Rich YouTube previews**: Trailers sent as separate messages with embedded thumbnails and video info
    - **New compact trailer format** (Dec 30, 2025):
      ```
      🎬Trailer:
      Movie Title (2025)
      https://www.youtube.com/watch?v=...
      ```
    - **Movie trailers**: Immediate lookup with retry mechanism (checks 3 times over ~7 hours)
    - **TV series trailers**: Smart season detection with bulk-add protection
      - New series (S01): Shows Season 1 trailer immediately (even during suppression)
      - New season episodes (S02E01, S03E01): Shows season-specific trailer AFTER 24h suppression expires
      - Only first episode of each season triggers trailer lookup (S02E01 yes, S02E02 no)
      - Bulk-add detection: Prevents spam during mass imports
  - **#requests channel**: Smart 3-message consolidation workflow (Jan 2, 2026)
    - **Request Link**: Rebrand, show 30s, auto-delete (user can click)
    - **Adding Movie/Show**: Rebrand and store for fulfillment
    - **Fulfillment**: Replace with reply preserving @mention to requester
    - **Result**: Clean request tracking with proper user notifications
    - **Persistent**: State survives restarts ([data/request_messages.json](data/request_messages.json))
  - **Episode suppression integration**: Suppressed episodes are deleted before rebranding (prevents race condition)
  - **Clean notifications**: Automatically removes filename field from episode notifications
  - Edits messages when trailers become available (movies only)
  - Persists retry state across bot restarts

- **📺 Episode Suppressor** (Smart Notification Management)
  - **Prevents episode notification floods** when new TV series are added
  - Automatically suppresses episode notifications for 24 hours after series added
  - **Race condition fixed** (Dec 30, 2025): Works reliably with notifiarr_rebrander integration
  - Persistent state across bot restarts (survives container restarts)
  - Manual override commands for administrators
  - Detailed logging and status tracking
  - Configurable suppression window

### Planned Features
- **📚 Book Request Fix** (Phase 1) - Fix invalid Goodreads ID issue, use Readarr metadata search
- **📺 TV Show Management** (Phase 2) - Add `!tv` command for Sonarr integration
- **🎬 Movie Management** (Phase 3) - Add `!movie` command for Radarr integration
- **🛠️ Server Administration** (Moderation, user management)
- **🎉 Fun Commands** (Games, polls, social features)
- **🔔 Notifications** (Webhooks for download completion)

📋 **Implementation Plan Available**: See project folder for detailed 3-phase plan to fix books and add TV/movie support.

## 🏗️ Architecture

This bot uses Discord.py's **Cogs system** for modular organization:

```
800801-discord-bot/
├── bot.py                     # Main entry point, loads cogs
├── config.py                  # Configuration management
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (secrets)
├── .env.example              # Example configuration
├── venv/                     # Virtual environment
├── data/                     # Persistent state (runtime data, not committed to git)
│   ├── episode_suppressions.json  # Episode suppression state
│   ├── trailer_retries.json       # Trailer retry queue
│   └── request_messages.json      # Request/fulfillment message mapping (#requests channel)
├── cogs/                     # Feature modules (hot-reloadable)
│   ├── __init__.py
│   ├── books.py             # Book commands (!book, !audiobook, !searchbook, !readarr)
│   ├── media.py             # TV/Movie commands (!sonarr, !radarr)
│   ├── notifiarr_rebrander.py # Notifiarr rebranding with YouTube trailers
│   ├── episode_suppressor.py  # Episode notification suppression
│   ├── readarr_manual_import.py # Detect manual Readarr imports and notify
│   └── perplexity_search.py  # AI-powered search via Perplexity API
└── utils/                    # Shared utilities
    ├── __init__.py
    ├── api_clients.py       # Readarr, Sonarr, Radarr API clients
    ├── book_search.py       # Google Books & OpenLibrary search
    ├── trailarr_client.py   # TMDb API v3 client for YouTube trailer lookups
    └── trailer_retry_manager.py # Retry queue manager for failed trailer lookups
```

### Why Cogs?
- **Modular**: Each feature is isolated in its own file
- **Hot-reload**: Reload individual cogs without restarting bot
- **Scalable**: Easy to add new features without touching existing code
- **Organized**: Clear separation of concerns
- **Collaborative**: Multiple developers can work on different cogs

### Key Architecture Decisions (for LLM Agents)

**Config**: [config.py](config.py) reads `.env` → validated on startup → env vars with defaults

**API Integration**: Client classes in `utils/` → init in cog → 5sec timeout → error logging

**State**: JSON in `data/` → load on init → save on modify → background cleanup (asyncio)

**Message Flow**: `on_message` → validate → integration checks → action → persist state

**Trailers** ([trailarr_client.py](utils/trailarr_client.py)): TMDb API v3 → search media → get videos → filter YouTube trailers → season-specific w/fallback → retry manager (movies: 3x/7h)

**Cog Communication**: `self.bot.cogs['Name']` → prevents race conditions (e.g., rebrander checks suppressor)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd boo-bot

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install packages
pip install -r requirements.txt
```

### 2. Get Discord Bot Token

1. Go to https://discord.com/developers/applications
2. Click "New Application" and name it
3. Go to "Bot" tab → Click "Add Bot"
4. Under "Token" click "Reset Token" and copy it
5. Enable "Message Content Intent" under "Privileged Gateway Intents"
6. Go to "OAuth2" → "URL Generator":
   - Select scopes: `bot`
   - Select permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Add Reactions`
   - Copy the generated URL and open it to invite bot to your server

### 3. Configure Bot

Edit the [`.env`](./.env) file with your credentials:

```bash
# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token_here
COMMAND_PREFIX=!

# Readarr Configuration (for books)
READARR_URL=http://localhost:8787
READARR_API_KEY=your_readarr_api_key
ROOT_FOLDER_PATH=/data/books/user1/ebooks
QUALITY_PROFILE_ID=1
METADATA_PROFILE_ID=1

# Sonarr Configuration (optional - for TV shows)
SONARR_URL=http://localhost:8989
SONARR_API_KEY=your_sonarr_api_key

# Radarr Configuration (optional - for movies)
RADARR_URL=http://localhost:7878
RADARR_API_KEY=your_radarr_api_key

# TMDb API Configuration (required for YouTube trailer lookups)
# Get your API key from https://www.themoviedb.org/settings/api
TMDB_API_KEY=your_tmdb_api_key_here

# Trailarr Configuration (YouTube trailer integration)
TRAILARR_URL=http://trailarr:7889
TRAILARR_ENABLED=true

# Episode Suppressor Configuration
EPISODE_SUPPRESSION_HOURS=24
EPISODE_SUPPRESSION_CHANNEL=general

```

### 4. Run Bot

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run bot
python3 bot.py

# Or run in background
nohup python3 bot.py > bot.log 2>&1 &

# View logs
tail -f bot.log
```

## 📚 Available Commands

### Book Commands (`cogs/books.py`)

| Command | Description | Example |
|---------|-------------|---------|
| `!book <query>` | Search and add a book to Readarr (requests channel only) | `!book Taipei by Tao Lin` |
| `!audiobook <query>` | Search and add an audiobook to Readarr (requests channel only) | `!audiobook The Name of the Wind by Patrick Rothfuss` |
| `!searchbook <query>` | Search for books without adding | `!searchbook Stephen King` |
| `!readarr` | Test Readarr connection | `!readarr` |

### Media Commands (`cogs/media.py`)

| Command | Description | Example |
|---------|-------------|---------|
| `!tv <query>` | Search and add a TV show to Sonarr (requests channel only) | `!tv Breaking Bad` |
| `!movie <query>` | Search and add a movie to Radarr (requests channel only) | `!movie Inception` |
| `!sonarr` | Test Sonarr connection | `!sonarr` |
| `!radarr` | Test Radarr connection | `!radarr` |

**How requests work**: Search returns up to 5 results in a numbered embed with poster thumbnails. React with 1️⃣-5️⃣ to select (60s timeout). Single results are added automatically. Shows are monitored for all seasons; movies auto-search on add. Duplicate detection returns a friendly "already in library" message.

### Episode Suppressor Commands (`cogs/episode_suppressor.py`)

| Command | Description | Permission Required | Example |
|---------|-------------|---------------------|---------|
| `!suppressions` | Show active episode suppressions | Manage Messages | `!suppressions` |
| `!cleanup episodes <show> <hours>` | Manually suppress episodes for a show | Manage Messages | `!cleanup episodes "Breaking Bad" 24` |
| `!cleanup purge <show> <limit>` | Delete episode notifications from history | Manage Messages | `!cleanup purge "Good Omens" 100` |
| `!cleanup purge all <limit>` | Delete all episode notifications | Manage Messages | `!cleanup purge all 200` |
| `!cleanup clear <show>` | Remove suppression for specific show | Manage Messages | `!cleanup clear "The Wire"` |
| `!cleanup clear all` | Remove all suppressions | Manage Messages | `!cleanup clear all` |

**Flow**: New series notification → suppress all episodes 24h → count & log → resume → persists in `episode_suppressions.json`

**Configuration** (`.env`):
```bash
EPISODE_SUPPRESSION_HOURS=24        # Duration of suppression window
EPISODE_SUPPRESSION_CHANNEL=general # Channel to monitor
```

### Notifiarr Rebrander (`cogs/notifiarr_rebrander.py`)

**Automatic Background Service with YouTube Trailer Integration + Smart Request Workflow**

The Notifiarr Rebrander automatically:
- Monitors **#general** and **#requests** channels for Notifiarr bot messages
- Deletes original messages and reposts as the bot
- **#general**: Adds YouTube trailer links for new movies AND TV series (via TMDb API)
- **#requests**: Consolidates 3-message request flow into clean workflow with reply preservation

| Command | Description | Example |
|---------|-------------|---------|
| `!rebrander` | Show rebrander status, channels, and pending requests | `!rebrander` |
| `!addtrailer <message_id> <title> [year]` | Manually add trailer to existing message (Admin only) | `!addtrailer 1234567890 "The Matrix" 1999` |

**Configuration**: `TRAILARR_URL`, `TRAILARR_ENABLED`, `TMDB_API_KEY` (see API Keys section below for setup)

**#general Channel - Movie Trailer Flow**: Notifiarr post → TMDb query → if found: embed + separate trailer message | if not: retry queue (3x: 1h, 3h, 7h) → edit when available

**#general Channel - TV Trailer Flow**:
- New series → S01/series trailer (immediate, ignores suppression)
- S##E01 (S02+) → season trailer if suppression expired (no fallback, prevents spam)
- Other episodes → no trailer

**#requests Channel - Request Workflow** (Jan 2, 2026):
1. **Request Link**: Rebrand → show 30s → auto-delete
2. **Adding Movie/Show**: Rebrand → store message ID mapped to media title
3. **Fulfillment**: Delete stored message → post new reply preserving @mention

**Cleanup**: Auto-removes "Filename" field from episode embeds, preserves all other properties

**Technical**:
- TMDb API v3 | 40 req/10sec limit
- Integrates with Episode Suppressor | TV trailers not retried
- Request mapping: Title extraction from embed description | Reply preservation via Discord reference
- State persistence: `data/request_messages.json` (survives restarts)

## 🔑 API Keys & External Services

This bot integrates with several external APIs. Here's what you need to know:

### Discord API
- **Purpose**: Bot authentication and messaging
- **Required**: Yes | **Rate Limits**: ~50 msg/sec globally, ~5/5sec per channel
- **Get Token**: https://discord.com/developers/applications | **Config**: `DISCORD_TOKEN`

### TMDb API (The Movie Database)
- **Purpose**: YouTube trailer URL lookups for movies and TV shows
- **Required**: Only if `TRAILARR_ENABLED=true`
- **Rate Limits**: 40 requests/10 seconds (free tier)
- **Get Your Key**: Sign up → https://www.themoviedb.org/settings/api → Request API Key → Developer → Copy "API Key (v3 auth)"
- **Config**: `TMDB_API_KEY` in `.env`

### Readarr/Sonarr/Radarr APIs
- **Readarr**: Book management | Required for `!book`, `!audiobook`, `!searchbook`
- **Sonarr**: TV shows (future) | **Radarr**: Movies (future)
- **Get API Key**: App Settings → General → Security → API Key
- **Config**: `{SERVICE}_URL` and `{SERVICE}_API_KEY` in `.env`

**LLM Agent Notes**: Keys in `.env` (never commit) | TMDb direct (Trailarr no query API) | `TrailarrClient` handles TMDb | Lookups in `notifiarr_rebrander` | Auto-retry via `TrailerRetryManager` | Rate limit aware

## 🔧 Adding New Features

### Adding a New Cog

1. **Create new cog file**: `cogs/my_feature.py`

```python
from discord.ext import commands

class MyFeature(commands.Cog):
    """My awesome feature"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='mycommand')
    async def my_command(self, ctx):
        await ctx.send("Hello from my feature!")

async def setup(bot):
    await bot.add_cog(MyFeature(bot))
```

2. **Register cog in [`bot.py`](./bot.py)**:

```python
cog_modules = [
    'cogs.books',
    'cogs.media',
    'cogs.my_feature',  # Add your new cog here
]
```

3. **Restart bot** - Your new commands are now available!

### Hot-Reloading Cogs (Advanced)

You can reload cogs without restarting the bot by adding a reload command:

```python
@bot.command()
@commands.is_owner()
async def reload(ctx, cog: str):
    await bot.reload_extension(f'cogs.{cog}')
    await ctx.send(f'✅ Reloaded {cog}')
```

## 🐛 Troubleshooting

### Bot won't start

```bash
# Check Discord token
cat .env | grep DISCORD_TOKEN

# Ensure virtual environment is activated
which python  # Should show venv path

# Check for Python errors
python3 bot.py
```

### Docker Operations

```bash
# Restart the bot
docker compose restart discord-bot

# View bot logs
docker logs 800801-discord-bot --tail 50
docker logs 800801-discord-bot -f  # Follow logs

# Check if bot is running
docker ps | grep 800801-discord-bot

# Enter container shell
docker exec -it 800801-discord-bot bash
```

### "Module not found" errors

```bash
# Reinstall dependencies
pip install -r requirements.txt

# Or upgrade packages
pip install --upgrade discord.py requests python-dotenv
```

### Cog not loading

```bash
# Check cog syntax
python3 -m py_compile cogs/your_cog.py

# Check bot.py cog_modules list
grep "cog_modules" bot.py

# Check logs for error details
docker logs 800801-discord-bot | grep -A 10 "Failed to load"
```

### Commands not working

1. Verify "Message Content Intent" is enabled in Discord Developer Portal
2. Check bot has permissions in your Discord server
3. Verify command prefix matches (default: `!`)

### Episode Suppressor Issues

**Issue**: Episodes not being suppressed
1. Check status: `!suppressions`
2. Verify channel: `EPISODE_SUPPRESSION_CHANNEL=general`
3. Check logs: `docker logs 800801-discord-bot | grep suppression`
4. Verify data file: `docker exec 800801-discord-bot ls -la data/episode_suppressions.json`

**Issue**: Suppressions lost after restart
- Verify `/app/data` volume mounted in docker-compose
- Check file permissions on `data/` directory
- Ensure data directory exists: `docker exec 800801-discord-bot mkdir -p /app/data`

### Trailer Issues

**Issue**: Trailers not appearing for movies
1. **Check TMDb API key**: Verify `TMDB_API_KEY` is set in `.env` file
2. **Test TMDb API**: `curl "https://api.themoviedb.org/3/search/movie?api_key=YOUR_KEY&query=Matrix"`
3. **Check bot logs**: `docker logs 800801-discord-bot | grep TMDb`
4. **Verify config**: Ensure `TRAILARR_ENABLED=true` in `.env`
5. **Check trailer logs**: `docker logs 800801-discord-bot | grep trailer`
6. **Verify retry queue**: `docker exec 800801-discord-bot cat data/trailer_retries.json`
7. **Rate limiting**: If you see many 429 errors, you're hitting TMDb rate limits (40 req/10sec)

**Issue**: TV series trailers not showing for new series (Season 1)
1. Verify TMDb has trailers: Search series on https://www.themoviedb.org/
2. Check series detection: `docker logs 800801-discord-bot | grep "series"`
3. Check logs: `docker logs 800801-discord-bot | grep "Looking for"`
4. Verify media type detection in logs

**Issue**: Season 2+ trailers not showing (S02E01, S03E01)
1. **Check suppression status**: `!suppressions` - If series is suppressed, trailers skipped until 24h expires
2. **Verify first episode**: Only S02E01 triggers trailers, not S02E02 or S02E03
3. **Check season detection**: `docker logs 800801-discord-bot | grep "Detected first episode"`
4. **Verify TMDb has season trailer**: Search on https://www.themoviedb.org/ (many series lack season-specific trailers)
5. **Check timing**: S02E01 must arrive AFTER suppression expires (24h after series added)

**Issue**: Filename still showing in notifications
1. Verify Notifiarr includes filename in embeds (check embed fields)
2. Check logs: `docker logs 800801-discord-bot | grep "Removing filename"`
3. Ensure bot has permission to delete and repost messages

**Issue**: Trailer not showing rich YouTube preview
1. Verify trailer sent as **separate message** (not in embed content)
2. Check Discord URL auto-embed settings (should be enabled by default)
3. Ensure URL is on its own line with newline before it

### Requests Channel Issues

**Issue**: Request link not auto-deleting after 30 seconds
1. Check bot logs: `docker logs 800801-discord-bot | grep "Request link"`
2. Verify message was detected: Look for "Rebranded request link" in logs
3. Check permissions: Bot needs "Manage Messages" in #requests channel
4. Async timing: May take slightly longer than 30s due to event loop

**Issue**: Fulfillment not replacing request message
1. **Check logs**: `docker logs 800801-discord-bot | grep -E "(Stored|fulfillment)"`
2. **Verify title extraction**: Should see `Stored request message for 'Title'`
3. **Check mapping file**: `docker exec 800801-discord-bot cat data/request_messages.json`
4. **Title mismatch**: Ensure embed description contains `I've added **Title** to the system`
5. **Orphaned request**: If original request deleted manually, fallback posts new message

**Issue**: Reply/mention not preserved in fulfillment
1. Verify Notifiarr fulfillment is sent as a reply (check Discord "Replying to...")
2. Check logs: Look for "Posted fulfillment as reply" or "preserving @mention"
3. Ensure bot has permission to mention users in #requests

**Issue**: Multiple request messages visible
1. Check `!rebrander` status - should show pending request count
2. Verify only one "Adding Movie" message exists per media
3. Check for errors in logs during fulfillment handling
4. Clean state: `docker exec 800801-discord-bot rm data/request_messages.json && docker restart 800801-discord-bot`

### Rate Limiting

Discord limits:
- Message deletions: ~5-10 per second
- Message edits: ~5-10 per second
- Avoid bulk operations in short time
- Bot uses asyncio for non-blocking operations

## 💾 Data Persistence & State Files

The bot maintains persistent state in the `data/` directory to survive restarts:

### State Files (all in `.gitignore`, auto-persist)

| File | Purpose | Details |
|------|---------|---------|
| `episode_suppressions.json` | TV series suppression tracking | Series name, timestamps, count; 24h auto-cleanup |
| `trailer_retries.json` | Movie trailer retry queue | Message IDs, titles, years; 3 attempts (1h, 3h, 7h) |
| `request_messages.json` | Request/fulfillment mapping (#requests) | Media title → message ID mapping; cleaned on fulfillment |

**Docker Volume**: Mount `./800801-discord-bot:/app` (includes data/)

**Backup**: `cp -r data/ ~/backups/discord-bot-data-$(date +%Y%m%d)/`

**Recovery** (if corrupted): `docker compose stop discord-bot && rm data/*.json && docker compose start discord-bot`

**Request Messages**: Stores pending media requests in #requests channel. When media becomes available, bot edits the original request message with fulfillment info, then removes from tracking. Orphaned entries (deleted messages) are handled gracefully with fallback to new message posting.

## 🔐 Security Notes

- **Never commit `.env` file** to git (already in `.gitignore`)
- **Never commit `data/` directory** to git (contains runtime state, already in `.gitignore`)
- Keep Discord token secret
- Keep TMDb API key private (default key is public but you should use your own)
- Readarr/Sonarr/Radarr API keys are local network only
- Consider role restrictions for admin commands

## 🚢 Docker Deployment (Optional)

Add to your [`docker-compose.yml`](../docker-compose.yml):

```yaml
  discord-bot:
    image: python:3.11-slim
    container_name: 800801-discord-bot
    restart: unless-stopped
    working_dir: /app
    volumes:
      - ./800801-discord-bot:/app
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - READARR_URL=http://readarr:8787
      - READARR_API_KEY=${READARR_API_KEY}
      - SONARR_URL=http://sonarr:8989
      - SONARR_API_KEY=${SONARR_API_KEY}
      - RADARR_URL=http://radarr:7878
      - RADARR_API_KEY=${RADARR_API_KEY}
    command: >
      sh -c "pip install -r requirements.txt && python bot.py"
    networks:
      - plex_network
    depends_on:
      - readarr
```

## 🧑‍💻 Development Guide for LLM Agents

### Common Code Patterns

**New config variable**: Add to config.py (default) → .env.example (docs) → README → use `config.VAR`

**New API client**: Create in `utils/` → timeout (5sec) → error logging → return None/dict on fail → init in cog

**Persistent state**: Define path in `__init__` → `_load_state()`/`_save_state()` → load on init → cleanup task

**Background task**: `await bot.wait_until_ready()` → while loop → `asyncio.sleep()` → `asyncio.create_task()` in `__init__`

**Access other cog**: `other_cog = self.bot.cogs.get('CogName')` → check if exists → call method

**Discord embeds**: Read: `embed = message.embeds[0]` → fields dict | Create: `discord.Embed()` → set_author/thumbnail

**Error handling**: try/except → `asyncio.TimeoutError`, `discord.HTTPException`, `Exception` → log & send user message

### Important Files to Understand

| File | Purpose | When to Modify |
|------|---------|----------------|
| [bot.py](bot.py) | Main entry point, loads cogs | Add new cogs to `cog_modules` list |
| [config.py](config.py) | Configuration management | Add new environment variables |
| [.env](.env) | Secrets and settings | Configure your instance (never commit!) |
| [cogs/\*.py](cogs/) | Feature modules | Add new features or modify existing ones |
| [utils/\*.py](utils/) | Shared utilities | Add new API clients or helper functions |

### Testing & Debugging

**Local**: `source venv/bin/activate && python3 bot.py` (stdout logs)
**Docker**: `docker compose up -d --build discord-bot && docker logs 800801-discord-bot -f`

**Debug mode**: `self.debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'`
**View state**: `docker exec 800801-discord-bot cat data/*.json | jq .`
**Test APIs**: `curl "https://api.themoviedb.org/3/search/movie?api_key=KEY&query=Matrix"`

## 📖 Related Documentation

- **Discord.py Documentation**: https://discordpy.readthedocs.io/
- **Discord.py Cogs**: https://discordpy.readthedocs.io/en/stable/ext/commands/cogs.html
- **TMDb API v3**: https://developer.themoviedb.org/docs/getting-started
- **Readarr API**: https://readarr.com/docs/api/
- **Sonarr API**: https://sonarr.tv/docs/api/
- **Radarr API**: https://radarr.video/docs/api/

## 🎉 Success Criteria

Bot is working correctly when:
1. ✅ Bot shows online in Discord server
2. ✅ `!readarr` returns Readarr version
3. ✅ `!searchbook test` returns book results
4. ✅ `!book <title>` adds book to Readarr Library
5. ✅ `!audiobook <title>` adds audiobook to Readarr Audiobooks
6. ✅ Book shows "Wanted" status in Readarr
7. ✅ Book automatically downloads via Prowlarr

## 🛣️ Roadmap

### High Priority (Implementation Plan Ready)
- [ ] **Phase 1**: Fix book request workflow (Readarr metadata search API)
- [ ] **Phase 2**: Add `!tv` command (Sonarr integration - port 8989)
- [ ] **Phase 3**: Add `!movie` command (Radarr integration - port 7878)

### Medium Priority
- [ ] Add admin cog (kick, ban, mute commands)
- [ ] Add fun cog (games, polls, etc.)
- [ ] Webhook notifications for downloads
- [ ] User preferences per Discord user

### Low Priority
- [ ] ISBN barcode scanning for books
- [ ] Integration with Anna's Archive

📋 **See Implementation Plan**: Detailed 3-phase plan available in project documentation folder.

---

**Status**: ✅ Modular Architecture Ready  
**Current Cogs**: Books, Media (partial)  
**Framework**: Discord.py with Cogs system  
**Author**: Tyler Crawford  
**Updated**: December 2024
