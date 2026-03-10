#!/usr/bin/env python3
"""
Readarr Manual Import Notifier Cog

Polls all Readarr instances for manual imports (bookFileImported events without
a downloadId) and sends Discord notifications to #general matching the Notifiarr
embed style.

Readarr does not fire webhooks for manual imports (confirmed by Notifiarr dev,
Readarr is EOL since June 2025). Automatic imports continue to flow through
Notifiarr → Discord normally. This cog fills that gap.
"""
import discord
from discord.ext import commands
from config import config
import asyncio
import json
import requests
from datetime import datetime
from pathlib import Path


# Readarr icon for embed author line
READARR_ICON_URL = "https://raw.githubusercontent.com/Readarr/Readarr/develop/Logo/128.png"


class ReadarrManualImport(commands.Cog):
    """Detect manual Readarr imports and send Discord notifications"""

    def __init__(self, bot):
        self.bot = bot
        self.target_channel = config.MANUAL_IMPORT_CHANNEL
        self.poll_interval = config.MANUAL_IMPORT_POLL_INTERVAL

        # State file for tracking last seen history IDs per instance
        self.state_file = Path(__file__).parent.parent / "data" / "manual_import_state.json"

        # {instance_label: last_seen_history_id}
        self.state = {}

        # Build instance list from config
        self.instances = self._build_instance_list()

        # Load persisted state
        self._load_state()

        # Start background poll loop
        self._poll_task = asyncio.create_task(self._poll_loop())

        print(f"📚 Readarr Manual Import Notifier initialized")
        print(f"   Polling {len(self.instances)} instance(s) every {self.poll_interval}s")
        print(f"   Target channel: #{self.target_channel}")
        for inst in self.instances:
            print(f"   • {inst['label']} → {inst['url']}")

    def _build_instance_list(self):
        """Build list of all Readarr instances from config, skipping empty API keys"""
        candidates = [
            {
                "label": "Readarr (Ebooks)",
                "url": config.READARR_URL,
                "api_key": config.READARR_API_KEY,
            },
            {
                "label": "Readarr (Audiobooks)",
                "url": config.READARR_AUDIOBOOK_URL,
                "api_key": config.READARR_AUDIOBOOK_API_KEY,
            },
            {
                "label": "Readarr2 (Ebooks)",
                "url": config.READARR2_URL,
                "api_key": config.READARR2_API_KEY,
            },
            {
                "label": "Readarr-Audio2 (Audiobooks)",
                "url": config.READARR_AUDIO2_URL,
                "api_key": config.READARR_AUDIO2_API_KEY,
            },
        ]

        instances = []
        for c in candidates:
            # Skip instances with empty/placeholder API keys
            if not c["api_key"] or c["api_key"].startswith("your_"):
                continue
            instances.append(c)

        return instances

    def _load_state(self):
        """Load last seen history IDs from JSON file"""
        if not self.state_file.exists():
            print(f"ℹ️ No existing manual import state found — will seed on first poll")
            return

        try:
            with open(self.state_file, "r") as f:
                self.state = json.load(f)
            print(f"✓ Loaded manual import state for {len(self.state)} instance(s)")
        except json.JSONDecodeError as e:
            print(f"⚠️ Corrupted manual import state file, starting fresh: {e}")
            self.state = {}
        except Exception as e:
            print(f"⚠️ Error loading manual import state: {e}")
            self.state = {}

    def _save_state(self):
        """Save state to JSON file (atomic write)"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(self.state, f, indent=2)

            temp_file.replace(self.state_file)
        except Exception as e:
            print(f"✗ Error saving manual import state: {e}")

    async def _poll_loop(self):
        """Background task: poll all instances every POLL_INTERVAL seconds"""
        await self.bot.wait_until_ready()

        # Small startup delay to let other cogs finish init
        await asyncio.sleep(5)

        while True:
            for instance in self.instances:
                try:
                    await self._poll_instance(instance)
                except Exception as e:
                    print(f"⚠️ Error polling {instance['label']}: {e}")

            await asyncio.sleep(self.poll_interval)

    async def _poll_instance(self, instance):
        """Poll a single Readarr instance for new manual imports"""
        label = instance["label"]

        # Fetch history from API (sync requests wrapped in to_thread)
        history = await self._fetch_history(instance)
        if history is None:
            return

        records = history.get("records", [])
        if not records:
            return

        # Seed initial state on first run — don't replay old imports
        if label not in self.state:
            max_id = max(r["id"] for r in records)
            self.state[label] = max_id
            self._save_state()
            print(f"🌱 Seeded {label}: last_seen_id = {max_id}")
            return

        last_seen_id = self.state[label]

        # Filter for new manual imports
        manual_imports = self._filter_manual_imports(records, last_seen_id)

        if not manual_imports:
            return

        # Find the channel
        channel = discord.utils.get(
            self.bot.get_all_channels(), name=self.target_channel
        )
        if not channel:
            print(f"⚠️ Channel #{self.target_channel} not found, skipping notifications")
            return

        # Send notifications for each new manual import
        for record in manual_imports:
            try:
                embed = self._build_notification_embed(record, label)
                await channel.send(embed=embed)
                book_title = record.get("book", {}).get("title", record.get("sourceTitle", "Unknown"))
                print(f"📚 Notified manual import: '{book_title}' via {label}")
            except Exception as e:
                print(f"⚠️ Failed to send notification for record {record['id']}: {e}")

        # Update last seen ID to the highest we processed
        new_max_id = max(r["id"] for r in manual_imports)
        if new_max_id > self.state.get(label, 0):
            self.state[label] = new_max_id
            self._save_state()

    async def _fetch_history(self, instance):
        """Fetch recent history from a Readarr instance (async-wrapped sync request)"""
        url = f"{instance['url']}/api/v1/history"
        params = {
            "pageSize": 50,
            "sortKey": "date",
            "sortDirection": "descending",
            "includeBook": "true",
            "includeAuthor": "true",
            "apikey": instance["api_key"],
        }

        try:
            response = await asyncio.to_thread(
                requests.get, url, params=params, timeout=15
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            print(f"⚠️ Cannot reach {instance['label']} at {instance['url']} — skipping")
            return None
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout polling {instance['label']} — skipping")
            return None
        except requests.exceptions.HTTPError as e:
            print(f"⚠️ HTTP error from {instance['label']}: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Unexpected error fetching history from {instance['label']}: {e}")
            return None

    def _filter_manual_imports(self, records, last_seen_id):
        """
        Filter history records to only new manual imports.

        Manual imports = bookFileImported events WITHOUT a downloadId.
        Automatic imports come through a download client and always have a downloadId.
        """
        manual = []
        for rec in records:
            # Only newer records
            if rec["id"] <= last_seen_id:
                continue

            # Only import events
            if rec.get("eventType") != "bookFileImported":
                continue

            # Skip automatic imports (have a downloadId)
            if rec.get("downloadId"):
                continue

            manual.append(rec)

        # Sort oldest first so notifications appear in chronological order
        manual.sort(key=lambda r: r["id"])
        return manual

    def _build_notification_embed(self, record, instance_label):
        """
        Build a Discord embed matching Notifiarr's book notification style.

        Notifiarr format:
        - Author line: "New book available - Readarr - {instance}"
        - Title: book title (with year if available)
        - Fields: Pages, Author, Rating (inline)
        - Thumbnail: book cover
        - Color: Readarr teal
        """
        book = record.get("book", {})
        author = record.get("author", {})

        # Book title with year
        title = book.get("title", record.get("sourceTitle", "Unknown"))
        release_date = book.get("releaseDate")
        if release_date:
            try:
                year = datetime.fromisoformat(release_date.replace("Z", "+00:00")).year
                title = f"{title} ({year})"
            except (ValueError, AttributeError):
                pass

        # Build embed
        embed = discord.Embed(
            title=title,
            color=discord.Color.from_rgb(74, 144, 226),  # Readarr blue
        )

        # Author line matching Notifiarr style
        embed.set_author(
            name=f"New book available - {instance_label}",
            icon_url=READARR_ICON_URL,
        )

        # Book cover thumbnail
        images = book.get("images", [])
        if images:
            # Prefer the cover image with a remote URL
            cover_url = None
            for img in images:
                if img.get("coverType") == "cover":
                    cover_url = img.get("url", "")
                    break
            if not cover_url and images:
                cover_url = images[0].get("url", "")

            if cover_url and cover_url.startswith("http"):
                embed.set_thumbnail(url=cover_url)

        # Inline fields matching Notifiarr: Pages, Author, Rating
        page_count = book.get("pageCount", 0)
        if page_count:
            embed.add_field(name="Pages", value=str(page_count), inline=True)

        author_name = author.get("authorName", "Unknown")
        embed.add_field(name="Author", value=author_name, inline=True)

        ratings = book.get("ratings", {})
        rating_value = ratings.get("value", 0)
        if rating_value:
            embed.add_field(name="Rating", value=f"{rating_value:.2f}", inline=True)

        # Quality info as footer
        quality_name = record.get("quality", {}).get("quality", {}).get("name", "")
        if quality_name:
            embed.set_footer(text=f"Format: {quality_name}")

        return embed

    @commands.command(name="manualimports")
    @commands.has_permissions(manage_messages=True)
    async def show_manual_imports(self, ctx):
        """Show status of manual import tracking (Admin only)

        Usage: !manualimports
        """
        if not self.instances:
            await ctx.send("⚠️ No Readarr instances configured")
            return

        embed = discord.Embed(
            title="📚 Readarr Manual Import Tracker",
            description=f"Polling {len(self.instances)} instance(s) every {self.poll_interval}s",
            color=discord.Color.from_rgb(74, 144, 226),
        )

        for instance in self.instances:
            label = instance["label"]
            last_id = self.state.get(label, "not seeded")
            status = "✅ Tracking" if label in self.state else "🌱 Awaiting first poll"

            embed.add_field(
                name=label,
                value=f"Status: {status}\nLast seen ID: `{last_id}`",
                inline=False,
            )

        embed.set_footer(text=f"Target channel: #{self.target_channel}")
        await ctx.send(embed=embed)

    def cog_unload(self):
        """Cancel background task on cog unload"""
        if hasattr(self, "_poll_task"):
            self._poll_task.cancel()


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(ReadarrManualImport(bot))
