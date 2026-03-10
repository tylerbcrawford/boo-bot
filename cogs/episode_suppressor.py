#!/usr/bin/env python3
"""
Episode Suppressor Cog - Automatically suppress episode notifications after new series added
Prevents channel flooding when bulk-adding TV series with many seasons/episodes
"""
import discord
from discord.ext import commands
from config import config
import asyncio
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Union


class EpisodeSuppressor(commands.Cog):
    """Suppress episode notifications for 24h after new series added"""

    def __init__(self, bot):
        self.bot = bot
        self.target_bot_name = "Notifiarr"  # Bot to monitor
        self.target_channel = config.EPISODE_SUPPRESSION_CHANNEL  # Channel to monitor
        self.suppression_duration = config.EPISODE_SUPPRESSION_HOURS * 3600  # Convert to seconds

        # State file for persistent storage
        self.data_file = Path(__file__).parent.parent / "data" / "episode_suppressions.json"

        # In-memory cache: {series_name: {added_at, expires_at, suppressed_count, status}}
        self.suppressions = {}

        # Track seen seasons: {series_name: [1, 2, 3, ...]}
        self.seen_seasons = {}

        # Track recent episodes for rapid-fire detection: [{series, season, episode, timestamp}, ...]
        self.recent_episodes = []
        self.rapid_fire_window = 300  # 5 minutes in seconds
        self.rapid_fire_threshold = 3  # 3+ episodes triggers suppression

        # Load existing suppressions from disk
        self._load_suppressions()

        # Start background cleanup task
        asyncio.create_task(self._cleanup_loop())

        print(f"📺 Episode Suppressor initialized - monitoring #{self.target_channel}")
        print(f"   Suppression window: {config.EPISODE_SUPPRESSION_HOURS}h")
        print(f"   🆕 New season detection: ENABLED")
        print(f"   ⚡ Rapid-fire detection: {self.rapid_fire_threshold}+ episodes in {self.rapid_fire_window//60} minutes")

    def _load_suppressions(self):
        """Load suppression state from JSON file"""
        if not self.data_file.exists():
            print(f"ℹ️ No existing episode suppression state found")
            return

        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                self.suppressions = data.get('suppressions', {})
                self.seen_seasons = data.get('seen_seasons', {})

            # Clean up any expired suppressions on load
            self._cleanup_expired()

            active_count = len([s for s in self.suppressions.values() if s.get('status') == 'active'])
            season_count = sum(len(seasons) for seasons in self.seen_seasons.values())
            print(f"✓ Loaded {active_count} active episode suppressions from disk")
            print(f"✓ Loaded {len(self.seen_seasons)} series with {season_count} tracked seasons")

        except json.JSONDecodeError as e:
            print(f"⚠️ Corrupted suppression state file, starting fresh: {e}")
            self.suppressions = {}
            self.seen_seasons = {}
        except Exception as e:
            print(f"⚠️ Error loading suppression state: {e}")
            self.suppressions = {}
            self.seen_seasons = {}

    def _save_suppressions(self):
        """Save suppression state to JSON file (atomic write)"""
        try:
            # Ensure parent directory exists
            self.data_file.parent.mkdir(parents=True, exist_ok=True)

            # Prepare data structure
            data = {
                "suppressions": self.suppressions,
                "seen_seasons": self.seen_seasons,
                "last_cleanup": datetime.utcnow().isoformat()
            }

            # Atomic write (write to temp, then rename)
            temp_file = self.data_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            temp_file.replace(self.data_file)

        except Exception as e:
            print(f"✗ Error saving suppression state: {e}")

    def _cleanup_expired(self):
        """Remove expired suppressions from memory"""
        now = datetime.utcnow()
        expired = []

        for series_name, suppression in self.suppressions.items():
            try:
                expires_at = datetime.fromisoformat(suppression["expires_at"])
                if now >= expires_at:
                    expired.append(series_name)
            except (ValueError, KeyError):
                # Invalid data - mark for removal
                expired.append(series_name)

        for series_name in expired:
            count = self.suppressions[series_name].get('suppressed_count', 0)
            del self.suppressions[series_name]
            if count > 0:
                print(f"⏱️ Suppression expired for '{series_name}' ({count} episodes suppressed)")

        if expired:
            self._save_suppressions()

    async def _cleanup_loop(self):
        """Background task to periodically clean up expired suppressions"""
        await self.bot.wait_until_ready()

        while True:
            await asyncio.sleep(3600)  # Run every hour
            self._cleanup_expired()

    def _normalize_name(self, name: str) -> str:
        """
        Normalize series name for fuzzy matching

        Handles variations like:
        - "The Walking Dead" vs "Walking Dead" (articles)
        - "Grey's Anatomy" vs "Greys Anatomy" (apostrophes)
        - "Show (2020)" vs "Show" (years)

        Args:
            name: Series name to normalize

        Returns:
            Normalized lowercase name without articles, punctuation, or years
        """
        if not name:
            return ""

        normalized = name.lower()

        # Remove common articles
        normalized = re.sub(r'^(the|a|an)\s+', '', normalized)

        # Remove year in parentheses: "Show (2020)" -> "show"
        normalized = re.sub(r'\s*\(\d{4}\)\s*$', '', normalized)

        # Remove punctuation (apostrophes, colons, etc.)
        normalized = re.sub(r"['\"\-:,!?]", '', normalized)

        # Collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def is_suppressed(self, series_name: str) -> bool:
        """
        Check if a series is currently in suppression (bulk-add in progress)

        Uses normalized matching to handle variations in series names:
        - "The Walking Dead" matches "Walking Dead"
        - "Grey's Anatomy" matches "Greys Anatomy"
        - "Show (2020)" matches "Show"

        Args:
            series_name: The series name to check

        Returns:
            True if series is actively suppressed, False otherwise
        """
        normalized_query = self._normalize_name(series_name)

        # Check all active suppressions with normalized matching
        for stored_name in list(self.suppressions.keys()):
            if self._normalize_name(stored_name) == normalized_query:
                suppression = self.suppressions[stored_name]

                # Check if suppression is still active
                try:
                    expires_at = datetime.fromisoformat(suppression["expires_at"])
                    now = datetime.utcnow()

                    if now >= expires_at:
                        # Expired - clean it up
                        del self.suppressions[stored_name]
                        self._save_suppressions()
                        return False

                    # Still active
                    return suppression.get('status') == 'active'

                except (ValueError, KeyError):
                    # Invalid data - remove it
                    del self.suppressions[stored_name]
                    self._save_suppressions()
                    return False

        # No matching suppression found
        return False

    def _is_notifiarr_bot(self, author):
        """Check if message author is Notifiarr or Boo Bot (rebranded Notifiarr)"""
        if not author.bot:
            return False

        # Check for Notifiarr (original)
        if (author.name.lower() == self.target_bot_name.lower() or
                author.display_name.lower() == self.target_bot_name.lower()):
            return True

        # Check for Boo Bot (rebranded Notifiarr messages)
        if (author.name.lower() == "boo bot" or
                author.display_name.lower() == "boo bot"):
            return True

        return False

    def _is_target_channel(self, channel):
        """Check if this is the target channel"""
        return channel.name.lower() == self.target_channel.lower()

    def _extract_series_name(self, message):
        """
        Extract normalized series name from Notifiarr embed

        Returns:
            str: "Show Name" or "Show Name (Year)" or None
        """
        if not message.embeds:
            return None

        embed = message.embeds[0]
        title_text = embed.title or ""

        # Remove episode info: "Show - S01E01" or "Show (S01E01)" -> "Show"
        title_text = re.sub(r'\s*[-\(]?\s*S\d+E\d+.*$', '', title_text, flags=re.IGNORECASE)

        # Remove action text: "added to Sonarr", "imported", etc.
        title_text = re.sub(r'\s*(?:added|imported|grabbed).*$', '', title_text, flags=re.IGNORECASE)

        # Try to preserve year if present: "Show (2024)"
        # This helps distinguish reboots/remakes
        title_text = title_text.strip()

        return title_text if title_text else None

    def _is_new_content_notification(self, message):
        """
        Check if this is a 'new series added' OR 'new season' notification

        Returns:
            bool: True if this is a new series or new season notification
        """
        if not message.embeds:
            return False

        embed = message.embeds[0]
        title_text = (embed.title or "").lower()
        description_text = (embed.description or "").lower()
        author_text = (embed.author.name if embed.author else "").lower()

        # Combine all text for pattern matching
        combined_text = f"{title_text} {description_text} {author_text}"

        # CRITICAL FIX: Check for first episode of NEW seasons (S02E01, S03E01, etc.)
        # These should trigger suppression even though they have episode numbers
        first_episode_match = re.search(r'S(\d+)E01\b', combined_text, re.IGNORECASE)
        if first_episode_match:
            season_num = int(first_episode_match.group(1))
            # S02E01 or higher = first episode of a new season
            if season_num >= 2:
                print(f"🎯 Detected first episode of Season {season_num} (new season trigger)")
                return True

        # Check for other episode patterns (S##E## but not E01)
        # These should NOT trigger season suppression
        if re.search(r'S\d+E(?!01\b)\d+', combined_text, re.IGNORECASE):
            return False

        # Look for patterns indicating series addition OR new season
        series_patterns = [
            # Existing patterns for new SERIES
            r'added\s+to\s+sonarr',
            r'series\s+added',
            r'new\s+series',
            r'imported\s+to\s+sonarr',
            r'series\s+imported',
            r'new\s+show',
            r'show\s+added',
            # NEW patterns for new SEASONS (fixes Bridgerton bug)
            r'season\s+\d+',           # "Season 4", "Season 12"
            r'new\s+season',           # "New Season"
            r's\d{2}\s+premiere'       # "S04 Premiere"
        ]

        for pattern in series_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                print(f"🎯 Detected new series notification: pattern '{pattern}' matched")
                return True

        return False

    def _is_episode_notification(self, message):
        """
        Check if this is an 'episode added' notification

        Returns:
            bool: True if this is an episode notification
        """
        if not message.embeds:
            return False

        embed = message.embeds[0]
        title_text = (embed.title or "")
        description_text = (embed.description or "")
        author_text = (embed.author.name if embed.author else "")

        # Combine all text for checking
        combined_text = f"{title_text} {description_text} {author_text}"

        # Check for "New episode available" in author (Boo Bot format)
        if "new episode available" in author_text.lower():
            return True

        # Must contain episode pattern (S##E## or E##)
        if re.search(r'[SE]\d{2,}', combined_text, re.IGNORECASE):
            # And should mention "added", "imported", "grabbed", or "episode"
            episode_patterns = [
                r'added',
                r'imported',
                r'grabbed',
                r'episode',
                r'available'
            ]

            for pattern in episode_patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    return True

        return False

    async def _auto_delete_cleanup_messages(self, command_msg, status_msg, delay: int = 300):
        """
        Auto-delete cleanup command and bot response after delay

        Args:
            command_msg: The user's command message
            status_msg: The bot's status/response message
            delay: Seconds to wait before deletion (default: 300 = 5 minutes)
        """
        try:
            await asyncio.sleep(delay)

            # Delete user's command message
            try:
                await command_msg.delete()
                print(f"🗑️ Auto-deleted cleanup command after {delay}s")
            except discord.NotFound:
                # Message already deleted
                pass
            except Exception as e:
                print(f"⚠️ Could not delete command message: {e}")

            # Delete bot's status message
            try:
                await status_msg.delete()
                print(f"🗑️ Auto-deleted cleanup status message after {delay}s")
            except discord.NotFound:
                # Message already deleted
                pass
            except Exception as e:
                print(f"⚠️ Could not delete status message: {e}")

        except Exception as e:
            print(f"⚠️ Error in auto-delete cleanup: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for Notifiarr messages in target channel"""
        # Check if in target channel first
        if not self._is_target_channel(message.channel):
            return

        # Check if from Notifiarr bot OR our own bot (rebranded messages)
        is_from_bot = message.author == self.bot.user
        is_from_notifiarr = self._is_notifiarr_bot(message.author)

        if not is_from_bot and not is_from_notifiarr:
            return

        # Debug logging
        if message.embeds:
            embed = message.embeds[0]
            author_type = "Boo Bot (rebranded)" if is_from_bot else "Notifiarr (original)"
            print(f"🔍 Checking message - Title: '{embed.title}' | Author: '{embed.author.name if embed.author else 'N/A'}' | Type: {author_type}")

        # Check if new series or new season notification
        if self._is_new_content_notification(message):
            await self._handle_new_series(message)
        # Check if episode notification
        elif self._is_episode_notification(message):
            await self._handle_episode_notification(message)

    async def _handle_new_series(self, message):
        """Handle new series added notification - start suppression"""
        series_name = self._extract_series_name(message)
        if not series_name:
            return

        await self._start_suppression(series_name, "new series/season notification")

    async def _start_suppression(self, series_name: str, reason: str):
        """Start suppression for a series"""
        # Don't restart if already suppressed
        if series_name in self.suppressions:
            suppression = self.suppressions[series_name]
            try:
                expires_at = datetime.fromisoformat(suppression["expires_at"])
                if datetime.utcnow() < expires_at:
                    print(f"ℹ️ '{series_name}' already suppressed, skipping restart")
                    return
            except (ValueError, KeyError):
                pass

        # Start suppression
        now = datetime.utcnow()
        expires = now + timedelta(seconds=self.suppression_duration)

        self.suppressions[series_name] = {
            "added_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "suppressed_count": 0,
            "status": "active"
        }

        self._save_suppressions()

        hours = self.suppression_duration / 3600
        print(f"🔕 Started episode suppression for '{series_name}' ({hours:.0f}h) - Reason: {reason}")

    def _check_new_season_detection(self, series_name: str, season_num: int) -> bool:
        """
        Check if this is a NEW season we haven't seen before (Option 1)

        Returns True if:
        - This series has been tracked before
        - This season number hasn't been seen yet
        - Season number >= 2 (Season 1 is normal series add)
        """
        if season_num < 2:
            return False

        # Get normalized name for tracking
        normalized_name = self._normalize_name(series_name)

        # Get seen seasons for this series
        seen = self.seen_seasons.get(normalized_name, [])

        # If we've seen this season before, not new
        if season_num in seen:
            return False

        # If we've NEVER seen this series, it's not a "new season" - it's a new series
        # (Let the regular "new series" detection handle it)
        if not seen:
            # But still track this season so future episodes are caught
            self.seen_seasons[normalized_name] = [season_num]
            self._save_suppressions()
            return False

        # We've seen this series before but NOT this season = NEW SEASON!
        print(f"🆕 Detected NEW season: '{series_name}' Season {season_num} (previously seen: {seen})")

        # Track this new season
        self.seen_seasons[normalized_name].append(season_num)
        self._save_suppressions()

        return True

    def _check_rapid_fire_detection(self, series_name: str, season_num: int, episode_num: int) -> bool:
        """
        Check for rapid-fire bulk import (Option 2)

        Returns True if 3+ episodes from same season within 5 minutes
        """
        now = datetime.utcnow()
        normalized_name = self._normalize_name(series_name)

        # Add this episode to recent list
        self.recent_episodes.append({
            "series": normalized_name,
            "season": season_num,
            "episode": episode_num,
            "timestamp": now.isoformat()
        })

        # Clean up old episodes (older than 5 minutes)
        cutoff = now - timedelta(seconds=self.rapid_fire_window)
        self.recent_episodes = [
            ep for ep in self.recent_episodes
            if datetime.fromisoformat(ep["timestamp"]) > cutoff
        ]

        # Count episodes from this series/season in the last 5 minutes
        matching = [
            ep for ep in self.recent_episodes
            if ep["series"] == normalized_name and ep["season"] == season_num
        ]

        if len(matching) >= self.rapid_fire_threshold:
            episodes = sorted(set(ep["episode"] for ep in matching))
            print(f"⚡ Detected rapid-fire import: '{series_name}' S{season_num:02d} "
                  f"({len(matching)} episodes in {self.rapid_fire_window//60}min: E{episodes[0]}-E{episodes[-1]})")
            return True

        return False

    async def _handle_episode_notification(self, message):
        """Handle episode added notification - delete if suppressed

        This handles BOTH original Notifiarr messages AND rebranded Boo Bot messages.
        For original Notifiarr messages: don't delete (let rebrander handle)
        For rebranded Boo Bot messages: delete if suppressed
        """
        series_name = self._extract_series_name(message)
        if not series_name:
            return

        # Extract episode info (S##E##)
        embed = message.embeds[0] if message.embeds else None
        if not embed:
            return

        title_text = (embed.title or "").lower()
        episode_match = re.search(r'S(\d+)E(\d+)', title_text, re.IGNORECASE)

        if episode_match:
            season_num = int(episode_match.group(1))
            episode_num = int(episode_match.group(2))

            # NEW DETECTION LOGIC
            # Option 1: Check if this is a NEW season we haven't seen before
            if self._check_new_season_detection(series_name, season_num):
                await self._start_suppression(series_name, f"new season {season_num} detected")

            # Option 2: Check for rapid-fire episode detection
            if self._check_rapid_fire_detection(series_name, season_num, episode_num):
                await self._start_suppression(series_name, f"rapid-fire bulk import detected (S{season_num:02d})")

            # Always track seen seasons (for future detection)
            normalized_name = self._normalize_name(series_name)
            if normalized_name not in self.seen_seasons:
                self.seen_seasons[normalized_name] = []
            if season_num not in self.seen_seasons[normalized_name]:
                self.seen_seasons[normalized_name].append(season_num)
                self.seen_seasons[normalized_name].sort()
                # Only save if we added a new season (avoid excessive writes)
                if len(self.seen_seasons[normalized_name]) > 1:
                    self._save_suppressions()

        # Check if this series is currently suppressed
        if series_name in self.suppressions:
            suppression = self.suppressions[series_name]

            # Check if still within suppression window
            try:
                expires_at = datetime.fromisoformat(suppression["expires_at"])
                now = datetime.utcnow()

                if now < expires_at:
                    # Still suppressed
                    # Only delete if this is a REBRANDED message from our bot (Boo Bot)
                    # Let the original Notifiarr message be handled by the rebrander
                    if message.author != self.bot.user:
                        # This is the original Notifiarr message - don't delete it
                        # Just track that we'll need to suppress the rebranded version
                        print(f"⏭️ Skipping suppression of original Notifiarr message for '{series_name}' (will suppress rebranded version)")
                        return

                    # This is the rebranded "Boo Bot" message - delete it!
                    try:
                        await message.delete()
                        suppression["suppressed_count"] += 1
                        self._save_suppressions()

                        # Log suppression
                        count = suppression['suppressed_count']
                        time_remaining = (expires_at - now).total_seconds() / 3600
                        print(f"🗑️ Suppressed episode notification for '{series_name}' "
                              f"(#{count}, {time_remaining:.1f}h remaining)")

                    except discord.Forbidden:
                        print(f"✗ Missing permission to delete episode notification for '{series_name}'")
                    except discord.NotFound:
                        # Message was already deleted
                        print(f"⚠️ Episode notification for '{series_name}' was already deleted")
                    except Exception as e:
                        print(f"✗ Error deleting episode notification: {e}")
                else:
                    # Expired - clean up
                    count = suppression.get('suppressed_count', 0)
                    del self.suppressions[series_name]
                    self._save_suppressions()
                    if count > 0:
                        print(f"⏱️ Suppression expired for '{series_name}' ({count} episodes suppressed)")

            except (ValueError, KeyError) as e:
                print(f"⚠️ Invalid suppression data for '{series_name}': {e}")
                # Clean up invalid data
                del self.suppressions[series_name]
                self._save_suppressions()

    @commands.command(name='suppressions')
    @commands.has_permissions(manage_messages=True)
    async def show_suppressions(self, ctx):
        """Show active episode suppressions (Admin only)

        Usage: !suppressions
        """
        if not self.suppressions:
            await ctx.send("✅ No active episode suppressions")
            return

        # Filter to only active suppressions
        now = datetime.utcnow()
        active = []

        for series_name, suppression in self.suppressions.items():
            try:
                expires_at = datetime.fromisoformat(suppression["expires_at"])
                if now < expires_at:
                    time_remaining = expires_at - now
                    active.append((series_name, suppression, time_remaining))
            except (ValueError, KeyError):
                continue

        if not active:
            await ctx.send("✅ No active episode suppressions")
            return

        # Create embed
        embed = discord.Embed(
            title="📺 Active Episode Suppressions",
            description=f"Showing {len(active)} active suppression(s)",
            color=discord.Color.blue()
        )

        for series_name, suppression, time_remaining in active[:10]:  # Limit to 10
            hours = time_remaining.total_seconds() / 3600
            count = suppression.get('suppressed_count', 0)

            value = f"⏱️ **Time remaining**: {hours:.1f}h\n"
            value += f"🗑️ **Episodes suppressed**: {count}\n"

            added_at = datetime.fromisoformat(suppression['added_at'])
            value += f"📅 **Started**: {added_at.strftime('%Y-%m-%d %H:%M UTC')}"

            embed.add_field(
                name=f"📺 {series_name}",
                value=value,
                inline=False
            )

        if len(active) > 10:
            embed.set_footer(text=f"... and {len(active) - 10} more")

        await ctx.send(embed=embed)

    @commands.command(name='cleanup')
    @commands.has_permissions(manage_messages=True)
    async def manual_cleanup(self, ctx, action: str = None, show_name: str = None, hours: Union[int, str] = None):
        """Manually manage episode suppressions (Admin only)

        Usage:
            !cleanup episodes "Show Name" 24  - Suppress episodes for 24 hours
            !cleanup purge "Show Name" 100    - Delete last 100 episode notifications for a show
            !cleanup purge all 100            - Delete last 100 episode notifications for all shows
            !cleanup clear "Show Name"        - Remove suppression for specific show
            !cleanup clear all                - Remove all suppressions

        Examples:
            !cleanup episodes "Breaking Bad" 24
            !cleanup purge "Breaking Bad" 100
            !cleanup purge all 200
            !cleanup clear "The Wire"
            !cleanup clear all
        """
        if not action:
            await ctx.send("❌ Usage: `!cleanup episodes <show_name> <hours>`, `!cleanup purge <show_name> <limit>`, or `!cleanup clear <show_name|all>`")
            return

        action = action.lower()

        if action == "purge":
            # Retroactively delete episode notifications from channel history
            if not show_name:
                await ctx.send("❌ Usage: `!cleanup purge <show_name|all> <limit>`\n"
                               "Example: `!cleanup purge \"Breaking Bad\" 100`")
                return

            # Parse limit (reuse hours parameter as limit)
            if hours is None:
                limit = 100  # Default
            else:
                try:
                    limit = int(hours)
                except (ValueError, TypeError):
                    await ctx.send("❌ Limit must be a number between 1 and 500")
                    return

            if limit < 1 or limit > 500:
                await ctx.send("❌ Limit must be between 1 and 500")
                return

            # Send confirmation message
            status_msg = await ctx.send(f"🔍 Scanning last {limit} messages for episode notifications...")

            deleted_count = 0
            try:
                # Scan channel history
                async for message in ctx.channel.history(limit=limit):
                    # Skip if not from Notifiarr bot
                    if not self._is_notifiarr_bot(message.author):
                        continue

                    # Check if it's an episode notification
                    if not self._is_episode_notification(message):
                        continue

                    # Extract series name
                    series_name = self._extract_series_name(message)
                    if not series_name:
                        continue

                    # Check if we should delete this episode
                    if show_name.lower() == "all" or show_name.lower() in series_name.lower():
                        try:
                            await message.delete()
                            deleted_count += 1
                            print(f"🗑️ Purged episode notification for '{series_name}'")
                        except discord.Forbidden:
                            await status_msg.edit(content=f"✗ Missing permission to delete messages")
                            return
                        except Exception as e:
                            print(f"⚠️ Error deleting message: {e}")
                            continue

                # Update status message with results
                await status_msg.edit(content=f"✅ Purged {deleted_count} episode notification(s) for '{show_name}' from last {limit} messages")
                print(f"✓ Retroactive purge complete: {deleted_count} episodes deleted")

                # Schedule auto-deletion of command and response after 5 minutes
                asyncio.create_task(self._auto_delete_cleanup_messages(ctx.message, status_msg, delay=300))

            except Exception as e:
                await status_msg.edit(content=f"✗ Error during purge: {e}")
                print(f"✗ Purge error: {e}")

                # Still schedule cleanup even on error
                asyncio.create_task(self._auto_delete_cleanup_messages(ctx.message, status_msg, delay=300))

        elif action == "episodes":
            # Add/extend suppression
            if not show_name or hours is None:
                await ctx.send("❌ Usage: `!cleanup episodes <show_name> <hours>`\n"
                               "Example: `!cleanup episodes \"Breaking Bad\" 24`")
                return

            # Convert hours to int
            try:
                hours_int = int(hours)
            except (ValueError, TypeError):
                await ctx.send("❌ Hours must be a number between 1 and 168 (1 week)")
                return

            if hours_int < 1 or hours_int > 168:  # Max 1 week
                await ctx.send("❌ Hours must be between 1 and 168 (1 week)")
                return

            now = datetime.utcnow()
            expires = now + timedelta(hours=hours_int)

            if show_name.lower() == "all":
                await ctx.send(f"⚠️ This will suppress ALL episode notifications for {hours_int}h. "
                               "This is rarely what you want. Use a specific show name instead.")
                return

            # Add or extend suppression
            self.suppressions[show_name] = {
                "added_at": now.isoformat(),
                "expires_at": expires.isoformat(),
                "suppressed_count": self.suppressions.get(show_name, {}).get('suppressed_count', 0),
                "status": "active"
            }
            self._save_suppressions()

            await ctx.send(f"✅ Suppressing episode notifications for '{show_name}' for {hours_int}h")
            print(f"📝 Manual suppression added: '{show_name}' for {hours_int}h")

        elif action == "clear":
            # Remove suppression
            if not show_name:
                await ctx.send("❌ Usage: `!cleanup clear <show_name|all>`")
                return

            if show_name.lower() == "all":
                count = len(self.suppressions)
                self.suppressions = {}
                self._save_suppressions()
                await ctx.send(f"✅ Cleared {count} suppression(s)")
                print(f"🗑️ All suppressions cleared manually")
            else:
                if show_name in self.suppressions:
                    count = self.suppressions[show_name].get('suppressed_count', 0)
                    del self.suppressions[show_name]
                    self._save_suppressions()
                    await ctx.send(f"✅ Cleared suppression for '{show_name}' ({count} episodes were suppressed)")
                    print(f"🗑️ Suppression cleared: '{show_name}'")
                else:
                    await ctx.send(f"❌ No suppression found for '{show_name}'")

        else:
            await ctx.send(f"❌ Unknown action '{action}'. Use 'episodes' or 'clear'")


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(EpisodeSuppressor(bot))
