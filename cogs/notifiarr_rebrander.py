#!/usr/bin/env python3
"""
Notifiarr Rebrander Cog - Reposts Notifiarr messages in #general as the bot
Monitors messages from Notifiarr bot and reposts them with the bot's identity
Now includes automatic YouTube trailer links via Trailarr API!
"""
import discord
from discord.ext import commands
from config import config
import re
import asyncio
import json
from pathlib import Path
from typing import Optional

# Import Trailarr client and retry manager
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.trailarr_client import TrailarrClient
from utils.trailer_retry_manager import TrailerRetryManager


class NotifiarrRebrander(commands.Cog):
    """Rebrand Notifiarr posts in #general and #requests channels"""

    def __init__(self, bot):
        self.bot = bot
        self.target_bot_name = "Notifiarr"  # The primary bot to monitor
        self.rebrand_bot_names = ["notifiarr", "tautulli digest"]  # All bots/webhooks to rebrand
        self.target_channels = ["general", "requests"]  # The channels to monitor

        # Track request messages for editing when fulfilled (requests channel only)
        # Key: media title, Value: {'message_id': int, 'channel_id': int}
        self.request_messages = {}
        self.request_map_file = Path(__file__).parent.parent / "data" / "request_messages.json"
        self._load_request_map()

        # Initialize Trailarr client for YouTube trailer links
        if config.TRAILARR_ENABLED:
            self.trailarr_client = TrailarrClient(
                base_url=config.TRAILARR_URL,
                tmdb_api_key=config.TMDB_API_KEY
            )
            self.retry_manager = TrailerRetryManager(
                data_file=Path(__file__).parent.parent / "data" / "trailer_retries.json"
            )
            # Track which series have had trailer lookups attempted
            self.trailer_posted_series_file = Path(__file__).parent.parent / "data" / "trailer_posted_series.json"
            self.trailer_posted_series = {}
            self._load_trailer_posted_series()
            # Start background retry loop
            asyncio.create_task(self._retry_loop())
            print(f"🎬 Trailarr YouTube trailer integration enabled ({config.TRAILARR_URL})")
        else:
            self.trailarr_client = None
            self.retry_manager = None
            self.trailer_posted_series = {}
            print("ℹ️ Trailarr integration disabled")
    
    def _load_request_map(self):
        """Load request message map from file"""
        try:
            if self.request_map_file.exists():
                with open(self.request_map_file, 'r') as f:
                    self.request_messages = json.load(f)
                print(f"📂 Loaded {len(self.request_messages)} request message mappings")
        except Exception as e:
            print(f"⚠️ Error loading request map: {e}")
            self.request_messages = {}

    def _save_request_map(self):
        """Save request message map to file"""
        try:
            self.request_map_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.request_map_file, 'w') as f:
                json.dump(self.request_messages, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving request map: {e}")

    @staticmethod
    def _normalize_series_name(name: str) -> str:
        """
        Normalize series name for consistent tracker lookups.
        Mirrors EpisodeSuppressor._normalize_name() logic.
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

    def _load_trailer_posted_series(self):
        """Load trailer-posted series tracker from JSON file"""
        try:
            if self.trailer_posted_series_file.exists():
                with open(self.trailer_posted_series_file, 'r') as f:
                    self.trailer_posted_series = json.load(f)
                print(f"📂 Loaded {len(self.trailer_posted_series)} trailer-posted series")
        except Exception as e:
            print(f"⚠️ Error loading trailer posted series: {e}")
            self.trailer_posted_series = {}

    def _save_trailer_posted_series(self):
        """Save trailer-posted series tracker to JSON file"""
        try:
            self.trailer_posted_series_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.trailer_posted_series_file, 'w') as f:
                json.dump(self.trailer_posted_series, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving trailer posted series: {e}")

    def _is_series_trailer_attempted(self, series_name: str) -> bool:
        """Check if a trailer lookup has already been attempted for this series"""
        normalized = self._normalize_series_name(series_name)
        return normalized in self.trailer_posted_series

    def _mark_series_trailer_attempted(self, series_name: str):
        """Mark a series as having had a trailer lookup attempted"""
        from datetime import datetime
        normalized = self._normalize_series_name(series_name)
        self.trailer_posted_series[normalized] = {
            'title': series_name,
            'first_seen': datetime.utcnow().isoformat()
        }
        self._save_trailer_posted_series()
        print(f"📝 Marked '{series_name}' as trailer-attempted (key: '{normalized}')")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for Notifiarr messages in monitored channels and rebrand them"""
        # Ignore messages from ourselves
        if message.author == self.bot.user:
            return

        # Check if this is from Notifiarr bot
        if not self._is_notifiarr(message.author):
            return

        # Check if this is in a monitored channel
        if not self._is_monitored_channel(message.channel):
            return

        # Rebrand the message
        await self._rebrand_message(message)
    
    def _is_notifiarr(self, author):
        """Check if the message author is a bot/webhook we should rebrand"""
        if not author.bot:
            return False

        # Match by name or display name against all rebrand targets
        author_names = [author.name.lower(), author.display_name.lower()]
        return any(name in author_names for name in self.rebrand_bot_names)

    def _is_monitored_channel(self, channel):
        """Check if this is a monitored channel"""
        return channel.name.lower() in self.target_channels

    def _is_request_link_message(self, message):
        """Check if this is the initial request link message"""
        if not message.embeds:
            return False

        embed = message.embeds[0]
        title = (embed.title or "").lower()

        # Check for "Request Link" title
        return "request link" in title

    def _is_request_message(self, message):
        """Check if this is a media request message (Adding Movie/Show)"""
        if not message.embeds:
            return False

        embed = message.embeds[0]
        author_name = (embed.author.name if embed.author else "").lower()
        title = (embed.title or "").lower()

        # Check for "Media request" in embed author, but NOT "Request Link"
        return "media request" in author_name and "request link" not in title

    def _is_fulfillment_message(self, message):
        """Check if this is a request fulfillment message"""
        if not message.embeds:
            return False

        embed = message.embeds[0]
        author_name = (embed.author.name if embed.author else "").lower()

        # Check for "Requested media available" in embed author
        return "requested media available" in author_name

    def _extract_media_title(self, message):
        """Extract media title from embed for matching request to fulfillment"""
        if not message.embeds:
            return None

        embed = message.embeds[0]

        # The actual media title is in the description field for request messages
        # Look for patterns like "Thanks for giving me something to do [username]! I've added **Title** to the system."
        description = embed.description or ""

        # Try to extract title from description first
        # Pattern: "I've added **Title** to the system"
        title_match = re.search(r"I've added \*\*(.+?)\*\* to the system", description)
        if title_match:
            title = title_match.group(1)
        else:
            # Fallback to embed title
            title = embed.title or ""

        # Remove year from title if present (for matching)
        # "The Matrix (1999)" -> "The Matrix"
        title = re.sub(r'\s*\(\d{4}\)', '', title).strip()

        return title if title else None

    async def _retry_loop(self):
        """Background task to retry failed trailer lookups"""
        await self.bot.wait_until_ready()

        while True:
            await asyncio.sleep(600)  # Check every 10 minutes

            if not self.retry_manager:
                continue

            pending = self.retry_manager.get_pending_retries()
            for msg_id, retry in pending:
                await self._retry_trailer_lookup(msg_id, retry)

            # Periodic cleanup of very old retries
            self.retry_manager.cleanup_old_retries(max_age_hours=48)

    async def _retry_trailer_lookup(self, message_id: str, retry: dict):
        """Retry finding and adding trailer to existing message"""
        if not self.trailarr_client:
            return

        try:
            # Try to get YouTube URL from Trailarr
            youtube_url = self.trailarr_client.get_trailer_url(
                title=retry["title"],
                year=retry.get("year")
            )

            if youtube_url:
                # Success! Edit the original message
                channel = self.bot.get_channel(retry["channel_id"])
                if channel:
                    try:
                        message = await channel.fetch_message(int(message_id))
                        title_year = f"{retry['title']} ({retry.get('year')})" if retry.get('year') else retry['title']
                        new_content = (message.content or "") + f"\n\n🎬**Trailer**:\n{title_year}\n{youtube_url}"
                        await message.edit(content=new_content)

                        print(f"✓ Added trailer to message {message_id} (retry attempt {retry['attempt'] + 1})")
                        self.retry_manager.remove_retry(message_id)
                        return
                    except discord.NotFound:
                        # Message was deleted
                        print(f"ℹ️ Message {message_id} no longer exists, removing from retry queue")
                        self.retry_manager.remove_retry(message_id)
                        return
                    except discord.Forbidden:
                        print(f"⚠️ No permission to edit message {message_id}")
                        self.retry_manager.remove_retry(message_id)
                        return

            # No trailer found yet - increment attempt
            if not self.retry_manager.increment_attempt(message_id):
                print(f"⏹️ Giving up on trailer for '{retry['title']}'")

        except Exception as e:
            print(f"✗ Error in retry loop for {retry.get('title', 'Unknown')}: {e}")

    def _extract_media_info(self, message):
        """
        Extract media title, year, and type from Notifiarr embed
        Only for NEW movies and NEW series (not individual episodes)

        Returns:
            dict with title, year, media_type, season_number (for TV) or None
        """
        if not message.embeds:
            return None

        embed = message.embeds[0]
        author_name = embed.author.name if embed.author else ""

        # Check embed title and description for patterns
        # Notifiarr patterns:
        # Movies Added: "Movie Title (Year)"
        # Series Added: "Series Name" (no episode number)
        # Episode Added: "Series Name - S01E01" (has episode number - SKIP THIS)

        title_text = embed.title or ""
        description_text = embed.description or ""

        # Check for episode notifications (S##E## format)
        # For first episodes of new seasons (S02E01, S03E01), extract season info for trailers
        episode_match = re.search(r'S(\d+)E(\d+)', title_text, re.IGNORECASE)
        if episode_match:
            season_num = int(episode_match.group(1))
            episode_num = int(episode_match.group(2))

            # Only process first episode of seasons (S02E01, S03E01, etc.)
            # Skip S01E01 (that's handled by "Series Added" notification)
            if episode_num == 1 and season_num > 1:
                # Extract series name from title (remove season/episode info)
                series_name = re.sub(r'\s*\(S\d+E\d+\)', '', title_text).strip()

                print(f"🎬 Detected first episode of Season {season_num}: {series_name}")
                return {
                    'title': series_name,
                    'year': None,  # Usually not in episode notifications
                    'media_type': 'tv',
                    'season_number': season_num
                }
            elif season_num == 1 and not self._is_series_trailer_attempted(
                re.sub(r'\s*\(S\d+E\d+\)', '', title_text).strip()
            ):
                # First-ever S01 episode for an unseen series (Watchlistarr flow)
                series_name = re.sub(r'\s*\(S\d+E\d+\)', '', title_text).strip()

                print(f"🎬 Detected new series from S01 episode: {series_name} (S{season_num:02d}E{episode_num:02d})")
                return {
                    'title': series_name,
                    'year': None,
                    'media_type': 'tv',
                    'season_number': 1
                }
            else:
                # Not first episode of a new season, or trailer already attempted
                print(f"ℹ️ Skipping episode notification (S{season_num:02d}E{episode_num:02d}, not first of new season or trailer already attempted)")
                return None

        # Try to extract from title first
        # Pattern: "Title (Year)" for movies
        movie_match = re.match(r'^(.+?)\s*\((\d{4})\)', title_text)
        if movie_match:
            return {
                'title': movie_match.group(1).strip(),
                'year': int(movie_match.group(2)),
                'media_type': 'movie',
                'season_number': None
            }

        # If no year in title but title exists, check if it's a TV series
        # (series notifications typically don't have episode numbers)
        if title_text:
            # Try to extract year from description
            year_match = re.search(r'\((\d{4})\)', description_text)
            year = int(year_match.group(1)) if year_match else None

            # Check description, author, or footer for hints about media type
            # If description mentions "series" or "season", it's TV
            desc_lower = description_text.lower()
            title_lower = title_text.lower()
            author_lower = author_name.lower()

            if 'series' in desc_lower or 'season' in desc_lower or 'tv' in desc_lower or 'sonarr' in desc_lower or 'series' in author_lower:
                # Try to extract season information from description
                # Pattern: "Season 1", "Season 2", etc.
                season_match = re.search(r'season\s+(\d+)', description_text, re.IGNORECASE)
                season_number = int(season_match.group(1)) if season_match else None

                return {
                    'title': title_text.strip(),
                    'year': year,
                    'media_type': 'tv',
                    'season_number': season_number
                }

            # Default to movie if we have a year
            if year:
                return {
                    'title': title_text.strip(),
                    'year': year,
                    'media_type': 'movie',
                    'season_number': None
                }

        return None

    def _get_sonarr_series_year(self, series_title: str) -> Optional[int]:
        """
        Query Sonarr API to get the year for a TV series

        Args:
            series_title: The series title to look up

        Returns:
            Year as integer, or None if not found
        """
        try:
            import requests

            # Query Sonarr's series endpoint
            response = requests.get(
                f"{config.SONARR_URL}/api/v3/series",
                headers={"X-Api-Key": config.SONARR_API_KEY},
                timeout=5
            )

            if response.status_code != 200:
                return None

            series_list = response.json()

            # Find matching series (case-insensitive)
            for series in series_list:
                if series.get('title', '').lower() == series_title.lower():
                    # Extract year from first aired date
                    first_aired = series.get('firstAired')
                    if first_aired:
                        return int(first_aired[:4])  # Extract year from date string
                    return None

            return None

        except Exception as e:
            print(f"⚠️ Error querying Sonarr for '{series_title}': {e}")
            return None

    async def _is_bulk_add(self, series_name: str) -> bool:
        """
        Check if this TV series is currently being bulk-added (episode suppression active)

        Args:
            series_name: The series name to check

        Returns:
            True if series is in suppression (bulk-add in progress), False otherwise
        """
        try:
            # Get the episode_suppressor cog
            episode_suppressor = self.bot.get_cog('EpisodeSuppressor')
            if not episode_suppressor:
                return False

            # Check if series is in active suppression
            return episode_suppressor.is_suppressed(series_name)

        except Exception as e:
            print(f"⚠️ Error checking bulk-add status: {e}")
            return False

    def _is_episode_notification(self, message):
        """Check if this is an episode notification (S##E## pattern)"""
        if not message.embeds:
            return False

        embed = message.embeds[0]
        title_text = (embed.title or "")
        author_text = (embed.author.name if embed.author else "")

        # Check for episode pattern
        import re
        if re.search(r'S\d+E\d+', title_text, re.IGNORECASE):
            return True

        # Check for "New episode available" in author
        if "new episode available" in author_text.lower():
            return True

        return False

    def _extract_series_name_from_episode(self, message):
        """Extract series name from episode notification"""
        if not message.embeds:
            return None

        embed = message.embeds[0]
        title_text = embed.title or ""

        # Remove episode info: "Show - S01E01" or "Show (S01E01)" -> "Show"
        import re
        title_text = re.sub(r'\s*[-\(]?\s*S\d+E\d+.*$', '', title_text, flags=re.IGNORECASE)
        title_text = title_text.strip()

        return title_text if title_text else None

    async def _handle_request_link(self, original_message):
        """Handle request link message - rebrand, keep for 30s, then delete"""
        try:
            # Extract the message content and embeds
            content = original_message.content or None
            embeds = self._clean_embeds(original_message.embeds) if original_message.embeds else None

            if not content and not embeds:
                print(f"⚠️ Request link has no content or embeds, skipping")
                return

            # Post the rebranded message
            if embeds:
                new_message = await original_message.channel.send(content, embeds=embeds)
            elif content:
                new_message = await original_message.channel.send(content)
            else:
                return

            # Delete the original Notifiarr message
            await original_message.delete()

            print(f"📋 Rebranded request link, will auto-delete after 30 seconds")

            # Wait 30 seconds before deleting the rebranded message
            await asyncio.sleep(30)
            await new_message.delete()
            print(f"🗑️ Deleted request link message after 30 seconds")

        except discord.NotFound:
            print(f"⚠️ Request link message already deleted")
        except discord.Forbidden:
            print(f"✗ Missing permissions in #{original_message.channel.name}")
        except Exception as e:
            print(f"✗ Error handling request link: {e}")

    async def _handle_request(self, original_message):
        """Handle media request message (Adding Movie/Show) in #requests channel"""
        try:
            # Extract the message content and embeds
            content = original_message.content or None
            embeds = self._clean_embeds(original_message.embeds) if original_message.embeds else None

            if not content and not embeds:
                print(f"⚠️ Request message has no content or embeds, skipping")
                return

            # Post the rebranded message
            if embeds:
                new_message = await original_message.channel.send(content, embeds=embeds)
            elif content:
                new_message = await original_message.channel.send(content)
            else:
                return

            # Delete the original Notifiarr message
            await original_message.delete()

            # Store the message ID for later editing when fulfilled
            media_title = self._extract_media_title(original_message)
            if media_title and new_message:
                self.request_messages[media_title] = {
                    'message_id': new_message.id,
                    'channel_id': new_message.channel.id
                }
                self._save_request_map()
                print(f"📝 Stored request message for '{media_title}' (ID: {new_message.id})")

            print(f"✓ Rebranded request message in #{original_message.channel.name}")

        except discord.Forbidden:
            print(f"✗ Missing permissions in #{original_message.channel.name}")
        except Exception as e:
            print(f"✗ Error handling request message: {e}")

    async def _handle_fulfillment(self, original_message):
        """Handle media fulfillment message in #requests channel"""
        try:
            # Extract media title to find the original request message
            media_title = self._extract_media_title(original_message)
            if not media_title:
                print(f"⚠️ Could not extract media title from fulfillment message")
                # Fallback to normal rebranding
                await self._rebrand_message_normal(original_message)
                return

            # Look up the original request message
            request_info = self.request_messages.get(media_title)
            if not request_info:
                print(f"⚠️ No request message found for '{media_title}', posting as new message")
                # Fallback to normal rebranding
                await self._rebrand_message_normal(original_message)
                return

            # Get the original request message
            try:
                channel = self.bot.get_channel(request_info['channel_id'])
                if not channel:
                    print(f"⚠️ Channel not found for request message")
                    await self._rebrand_message_normal(original_message)
                    return

                request_message = await channel.fetch_message(request_info['message_id'])
            except discord.NotFound:
                print(f"⚠️ Original request message not found (may have been deleted)")
                # Remove from map and post as new
                del self.request_messages[media_title]
                self._save_request_map()
                await self._rebrand_message_normal(original_message)
                return

            # Extract fulfillment embeds and content
            embeds = self._clean_embeds(original_message.embeds) if original_message.embeds else None
            content = original_message.content or None

            # Check if the Notifiarr fulfillment message is a reply
            # If so, we want to create a new rebranded reply instead of editing
            if original_message.reference and original_message.reference.message_id:
                # Delete the original request message since we're posting a new reply
                await request_message.delete()

                # Post a new fulfillment message as a reply (preserving the mention)
                if embeds:
                    new_fulfillment = await channel.send(
                        content=content,
                        embeds=embeds,
                        reference=original_message.reference
                    )
                elif content:
                    new_fulfillment = await channel.send(
                        content=content,
                        reference=original_message.reference
                    )

                print(f"✓ Posted fulfillment as reply for '{media_title}' (preserving @mention)")
            else:
                # No reply - just edit the original request message as before
                if embeds:
                    await request_message.edit(content=content, embeds=embeds)
                    print(f"✓ Updated request message for '{media_title}' with fulfillment")
                else:
                    print(f"⚠️ Fulfillment message has no embeds")

            # Delete the original Notifiarr fulfillment message
            await original_message.delete()

            # Clean up the mapping
            del self.request_messages[media_title]
            self._save_request_map()

        except discord.Forbidden:
            print(f"✗ Missing permissions in #{original_message.channel.name}")
        except Exception as e:
            print(f"✗ Error handling fulfillment message: {e}")

    def _clean_embeds(self, embeds):
        """Clean embeds by removing filename field"""
        if not embeds:
            return None

        cleaned_embeds = []
        for embed in embeds:
            # Create new embed without filename field
            new_embed = discord.Embed(
                title=embed.title,
                description=embed.description,
                color=embed.color,
                url=embed.url
            )

            # Copy author
            if embed.author:
                new_embed.set_author(name=embed.author.name, icon_url=embed.author.icon_url)

            # Copy thumbnail
            if embed.thumbnail:
                new_embed.set_thumbnail(url=embed.thumbnail.url)

            # Copy image
            if embed.image:
                new_embed.set_image(url=embed.image.url)

            # Copy footer
            if embed.footer:
                new_embed.set_footer(text=embed.footer.text, icon_url=embed.footer.icon_url)

            # Copy fields except "Filename"
            if embed.fields:
                for field in embed.fields:
                    if field.name.lower() != 'filename':
                        new_embed.add_field(name=field.name, value=field.value, inline=field.inline)

            cleaned_embeds.append(new_embed)

        return cleaned_embeds

    async def _rebrand_message_normal(self, original_message):
        """Normal rebranding (for #general or fallback) - posts as new message"""
        # Extract the message content and embeds
        content = original_message.content or None
        embeds = self._clean_embeds(original_message.embeds) if original_message.embeds else None

        if not content and not embeds:
            print(f"⚠️ Message has no content or embeds, skipping")
            return

        # Post the rebranded message
        if embeds:
            await original_message.channel.send(content, embeds=embeds)
        elif content:
            await original_message.channel.send(content)

        # Delete the original Notifiarr message
        await original_message.delete()

        print(f"✓ Rebranded message in #{original_message.channel.name}")

    async def _rebrand_message(self, original_message):
        """Delete original Notifiarr message and repost as bot with YouTube trailer link"""
        try:
            # Special handling for #requests channel
            if original_message.channel.name.lower() == "requests":
                # Check if this is a request link message (keep for 30s)
                if self._is_request_link_message(original_message):
                    await self._handle_request_link(original_message)
                    return
                # Check if this is a fulfillment message
                elif self._is_fulfillment_message(original_message):
                    await self._handle_fulfillment(original_message)
                    return
                # Check if this is a request message (Adding Movie/Show)
                elif self._is_request_message(original_message):
                    await self._handle_request(original_message)
                    return

            # Check if this is an episode notification that should be suppressed
            if self._is_episode_notification(original_message):
                series_name = self._extract_series_name_from_episode(original_message)
                print(f"🔍 DEBUG: Detected episode notification, extracted series name: '{series_name}'")
                if series_name:
                    # Check with episode suppressor if this series is suppressed
                    episode_suppressor = self.bot.get_cog('EpisodeSuppressor')
                    if episode_suppressor:
                        is_suppressed = episode_suppressor.is_suppressed(series_name)
                        print(f"🔍 DEBUG: Is '{series_name}' suppressed? {is_suppressed}")
                        print(f"🔍 DEBUG: Active suppressions: {list(episode_suppressor.suppressions.keys())}")
                        if is_suppressed:
                            # This episode should be suppressed - delete original and don't rebrand
                            try:
                                await original_message.delete()
                                print(f"🗑️ Suppressed episode notification for '{series_name}' (not rebranding)")

                                # Increment suppression counter
                                if series_name in episode_suppressor.suppressions:
                                    episode_suppressor.suppressions[series_name]['suppressed_count'] += 1
                                    episode_suppressor._save_suppressions()
                            except Exception as e:
                                print(f"⚠️ Error suppressing episode: {e}")
                            return  # Don't rebrand this message
                    else:
                        print(f"⚠️ DEBUG: EpisodeSuppressor cog not found!")

            # Extract the message content and embeds
            content = original_message.content or None
            embeds = self._clean_embeds(original_message.embeds) if original_message.embeds else None

            if not content and not embeds:
                # If there's neither content nor embeds, skip reposting
                print(f"⚠️ Notifiarr message has no content or embeds, skipping repost")
                return

            # Try to find YouTube trailer URL via Trailarr
            trailer_url = None
            trailer_title = None  # Store the formatted title for the trailer message
            media_info = self._extract_media_info(original_message)

            if media_info and self.trailarr_client:
                if media_info['media_type'] == 'movie':
                    # Movie trailer logic
                    print(f"🔍 Looking for movie trailer: {media_info['title']} ({media_info['year']})")

                    trailer_url = self.trailarr_client.get_trailer_url(
                        title=media_info['title'],
                        year=media_info['year']
                    )

                    if trailer_url:
                        # Store the formatted title for movies with bold formatting (matches TV series)
                        if media_info.get('year'):
                            trailer_title = f"**{media_info['title']} ({media_info['year']})**"
                        else:
                            trailer_title = f"**{media_info['title']}**"
                        content = (content or "") + f"\n\n🎬**Trailer**:\n{media_info['title']} ({media_info['year']})\n{trailer_url}"
                        print(f"✓ Found movie trailer: {trailer_url}")

                elif media_info['media_type'] == 'tv':
                    # TV series trailer logic
                    series_title = media_info['title']
                    season_number = media_info.get('season_number')

                    # Check if this is a "Series Added" notification (not an episode)
                    embed = original_message.embeds[0] if original_message.embeds else None
                    author_name = embed.author.name if embed and embed.author else ""
                    is_series_add = 'series added' in author_name.lower()

                    # Check if this is a bulk-add (episode suppression active)
                    is_bulk = await self._is_bulk_add(series_title)

                    # Trailer logic:
                    # - Series Added notification: Show trailer even during suppression
                    # - S02E01+ (first episodes of new seasons): Only show if NOT during suppression
                    # - Other episodes: Already filtered out by _extract_media_info

                    if is_bulk and not is_series_add:
                        # During suppression, only show trailer for initial "Series Added"
                        print(f"ℹ️ Skipping trailer for '{series_title}' S{season_number:02d} (suppression active - trailers only after 24h)")
                    else:
                        # Not a bulk-add - show trailer
                        if season_number == 1 or season_number is None:
                            # New series (S01) - try season 1 trailer, fallback to series trailer
                            print(f"🔍 Looking for new series trailer: {series_title} ({media_info.get('year')})")

                            trailer_url = self.trailarr_client.get_tv_trailer_url(
                                title=series_title,
                                year=media_info.get('year'),
                                season_number=1  # Try S01 trailer first, will fallback to series
                            )

                            if trailer_url:
                                # Get year from Sonarr for proper formatting
                                series_year = self._get_sonarr_series_year(series_title)
                                # Format: **Title (Year)**\nSeason 1
                                if series_year:
                                    trailer_title = f"**{series_title} ({series_year})**\nSeason 1"
                                else:
                                    trailer_title = f"**{series_title}**\nSeason 1"
                                content = (content or "") + f"\n\n🎬**Trailer**:\n{series_title}\n{trailer_url}"
                                print(f"✓ Found series trailer: {trailer_url}")

                            # Mark series as attempted regardless of whether trailer was found
                            # Prevents duplicate lookups from subsequent S01 episodes
                            self._mark_series_trailer_attempted(series_title)

                        elif season_number and season_number > 1:
                            # New season (S02+) - try season-specific trailer, NO fallback
                            print(f"🔍 Looking for season {season_number} trailer: {series_title}")

                            # Try season-specific trailer only (no series fallback for S02+)
                            season_trailer = self.trailarr_client._get_season_trailer(
                                series_id=None,  # We'll need to get this first
                                season_number=season_number,
                                series_title=series_title
                            )

                            # Actually, we need to search for the series first to get the ID
                            # Let's use get_tv_trailer_url but only accept season-specific results
                            trailer_url = await self._get_season_only_trailer(
                                title=series_title,
                                year=media_info.get('year'),
                                season_number=season_number
                            )

                            if trailer_url:
                                # Get year from Sonarr for proper formatting
                                series_year = self._get_sonarr_series_year(series_title)
                                # Format: **Title (Year)**\nSeason X
                                if series_year:
                                    trailer_title = f"**{series_title} ({series_year})**\nSeason {season_number}"
                                else:
                                    trailer_title = f"**{series_title}**\nSeason {season_number}"
                                content = (content or "") + f"\n\n🎬**Trailer**:\n{series_title} - Season {season_number}\n{trailer_url}"
                                print(f"✓ Found season {season_number} trailer: {trailer_url}")
                            else:
                                print(f"ℹ️ No season {season_number} trailer found for '{series_title}' (skipping)")

            # Post the rebranded message
            # If we have a trailer URL, send it as a separate message for rich preview
            new_message = None
            trailer_message = None

            # Check if content has a trailer URL
            has_trailer = trailer_url and "🎬" in (content or "")

            if has_trailer and embeds:
                # Split: Send embed with content (minus trailer), then trailer separately
                # Extract the trailer part from content
                content_parts = (content or "").split("\n\n🎬")
                main_content = content_parts[0] if content_parts else content

                # Send main message with embed
                new_message = await original_message.channel.send(main_content, embeds=embeds)

                # Send trailer as plain text for playable video with bold title
                # Use trailer_title if it was set during trailer lookup, otherwise build from media_info
                if trailer_title:
                    # trailer_title was set when we found the trailer - use it directly (already formatted)
                    trailer_message = await original_message.channel.send(f"{trailer_title}\n{trailer_url}")
                elif media_info:
                    # Fallback: build title from media_info
                    title_with_year = f"{media_info['title']} ({media_info['year']})" if media_info.get('year') else media_info['title']
                    if media_info['media_type'] == 'tv' and media_info.get('season_number'):
                        trailer_message = await original_message.channel.send(f"**{title_with_year} - Season {media_info['season_number']}**\n{trailer_url}")
                    else:
                        trailer_message = await original_message.channel.send(f"**{title_with_year}**\n{trailer_url}")
                else:
                    # No metadata available - just send URL
                    trailer_message = await original_message.channel.send(f"{trailer_url}")

            elif embeds:
                new_message = await original_message.channel.send(content, embeds=embeds)
            elif content:
                new_message = await original_message.channel.send(content)

            # Delete the original Notifiarr message
            await original_message.delete()

            # If no trailer found initially, add to retry queue
            if media_info and not trailer_url and new_message and self.retry_manager:
                # Only add movies to retry queue for now (TV trailers are more complex)
                if media_info['media_type'] == 'movie':
                    self.retry_manager.add_retry(
                        message_id=new_message.id,
                        title=media_info['title'],
                        year=media_info.get('year'),
                        channel_id=new_message.channel.id
                    )
                    print(f"📝 Added '{media_info['title']}' to retry queue")

            trailer_status = "with trailer 🎬" if trailer_url else ""
            print(f"✓ Rebranded Notifiarr message {trailer_status} in #{original_message.channel.name}")

        except discord.Forbidden:
            # Bot doesn't have permission to delete messages
            print(f"✗ Missing permissions to delete Notifiarr message in #{original_message.channel.name}")
            print(f"  Please ensure bot has 'Manage Messages' permission")

        except Exception as e:
            print(f"✗ Error rebranding Notifiarr message: {e}")

    async def _get_season_only_trailer(self, title: str, year: Optional[int], season_number: int) -> Optional[str]:
        """
        Get season-specific trailer ONLY (no series fallback for S02+)

        Args:
            title: TV series title
            year: First air year
            season_number: Season number

        Returns:
            YouTube URL for season trailer or None
        """
        try:
            # Search for the series to get TMDb ID
            search_params = {
                'api_key': self.trailarr_client.tmdb_api_key,
                'query': title,
                'language': 'en-US'
            }
            if year:
                search_params['first_air_date_year'] = year

            search_response = self.trailarr_client.session.get(
                f"{self.trailarr_client.tmdb_base_url}/search/tv",
                params=search_params,
                timeout=5
            )

            if search_response.status_code != 200:
                return None

            results = search_response.json().get('results', [])
            if not results:
                return None

            series_id = results[0].get('id')
            series_title = results[0].get('name', title)

            # Get season-specific trailer ONLY
            return self.trailarr_client._get_season_trailer(series_id, season_number, series_title)

        except Exception as e:
            print(f"⚠️ Error getting season-only trailer: {e}")
            return None
    
    @commands.command(name='rebrander')
    async def rebrander_status(self, ctx):
        """Show Notifiarr rebrander status

        Usage: !rebrander
        """
        status = f"**Notifiarr Rebrander Status**\n"
        status += f"✅ Monitoring: `{self.target_bot_name}` bot\n"
        status += f"✅ Target channels: {', '.join([f'`#{ch}`' for ch in self.target_channels])}\n"
        status += f"✅ Action: Delete original → Repost as bot\n"
        status += f"   • #general: New message with trailer 🎬\n"
        status += f"   • #requests: Edit request with fulfillment (1 msg total)\n"
        status += f"📝 Pending requests: {len(self.request_messages)}\n"

        # Trailarr status
        if self.trailarr_client:
            health = self.trailarr_client.health_check()
            if health:
                status += f"✅ Trailarr: Connected ({config.TRAILARR_URL})\n"
            else:
                status += f"⚠️ Trailarr: Cannot connect to {config.TRAILARR_URL}\n"

            # Retry queue status
            if self.retry_manager:
                retry_count = self.retry_manager.get_retry_count()
                if retry_count > 0:
                    status += f"📝 Pending trailer retries: {retry_count}\n"
                else:
                    status += f"✅ No pending trailer retries\n"
        else:
            status += f"ℹ️ Trailarr: Disabled\n"

        # Check if bot has required permissions in monitored channels
        status += f"\n**Channel Permissions:**\n"
        for channel_name in self.target_channels:
            channel = discord.utils.get(ctx.guild.channels, name=channel_name)
            if channel:
                permissions = channel.permissions_for(ctx.guild.me)
                if permissions.manage_messages:
                    status += f"✅ #{channel_name}: OK (Manage Messages)\n"
                else:
                    status += f"⚠️ #{channel_name}: Missing 'Manage Messages'\n"
            else:
                status += f"⚠️ #{channel_name}: Channel not found\n"

        await ctx.send(status)

    @commands.command(name='addtrailer')
    @commands.has_permissions(manage_messages=True)
    async def add_trailer_test(self, ctx, message_id: str = None, title: str = None, year: int = None):
        """Test command: Add trailer to an existing message (Admin only)

        Usage:
            !addtrailer <message_id> <title> [year]

        Examples:
            !addtrailer 1234567890 "The Matrix" 1999
            !addtrailer 1234567890 "Inception"

        Note: Right-click a message and "Copy Message ID" (requires Developer Mode enabled)
        """
        if not self.trailarr_client:
            await ctx.send("❌ Trailarr integration is disabled")
            return

        if not message_id or not title:
            await ctx.send("❌ Usage: `!addtrailer <message_id> <title> [year]`\n"
                          "Example: `!addtrailer 1234567890 \"The Matrix\" 1999`")
            return

        try:
            # Fetch the message
            target_message = await ctx.channel.fetch_message(int(message_id))
        except discord.NotFound:
            await ctx.send(f"❌ Message {message_id} not found in this channel")
            return
        except ValueError:
            await ctx.send(f"❌ Invalid message ID: {message_id}")
            return
        except Exception as e:
            await ctx.send(f"❌ Error fetching message: {e}")
            return

        # Check if message is from the bot
        if target_message.author.id != self.bot.user.id:
            await ctx.send(f"⚠️ Message is from {target_message.author.name}, not the bot. "
                          f"Can only edit bot's own messages.")
            return

        # Send status
        status_msg = await ctx.send(f"🔍 Looking for trailer: {title} ({year or 'no year'})")

        # Query Trailarr for trailer
        youtube_url = self.trailarr_client.get_trailer_url(title=title, year=year)

        if not youtube_url:
            await status_msg.edit(content=f"❌ No trailer found for '{title}' ({year or 'no year'})")
            return

        # Add trailer to message
        try:
            title_year = f"{title} ({year})" if year else title
            new_content = (target_message.content or "") + f"\n\n🎬**Trailer**:\n{title_year}\n{youtube_url}"
            await target_message.edit(content=new_content)
            await status_msg.edit(content=f"✅ Added trailer to message!\n🎬 {youtube_url}")
            print(f"✓ Test: Added trailer to message {message_id}: {youtube_url}")
        except discord.Forbidden:
            await status_msg.edit(content=f"❌ No permission to edit that message")
        except Exception as e:
            await status_msg.edit(content=f"❌ Error editing message: {e}")


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(NotifiarrRebrander(bot))
