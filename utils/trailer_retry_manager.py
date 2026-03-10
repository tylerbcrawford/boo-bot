#!/usr/bin/env python3
"""
Trailer Retry Manager - Manages retry queue for movies without immediate trailer availability
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Tuple, Dict


class TrailerRetryManager:
    """Manages retry queue for trailer lookups that didn't find results immediately"""

    def __init__(self, data_file: Path):
        """
        Initialize retry manager

        Args:
            data_file: Path to JSON file for persisting retry state
        """
        self.data_file = Path(data_file)
        self.retries = {}  # {message_id: {title, year, attempt, next_retry, created_at, channel_id}}
        self.max_retries = 3
        # Retry schedule: 1h, 3h total, 7h total
        self.retry_intervals = [3600, 7200, 14400]  # seconds
        self._load()

    def _load(self):
        """Load retry state from JSON file"""
        if not self.data_file.exists():
            print(f"ℹ️ Trailer retry state file not found, starting fresh")
            return

        try:
            with open(self.data_file, 'r') as f:
                self.retries = json.load(f)
            print(f"✓ Loaded {len(self.retries)} pending trailer retries from disk")
        except json.JSONDecodeError as e:
            print(f"⚠️ Corrupted trailer retry state file, starting fresh: {e}")
            self.retries = {}
        except Exception as e:
            print(f"⚠️ Error loading trailer retry state: {e}")
            self.retries = {}

    def _save(self):
        """Save retry state to JSON file (atomic write)"""
        try:
            # Ensure parent directory exists
            self.data_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to temporary file first (atomic write)
            temp_file = self.data_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.retries, f, indent=2, ensure_ascii=False)

            # Rename to actual file (atomic on POSIX systems)
            temp_file.replace(self.data_file)

        except Exception as e:
            print(f"✗ Error saving trailer retry state: {e}")

    def add_retry(self, message_id: int, title: str, year: Optional[int], channel_id: int):
        """
        Add a message to the retry queue

        Args:
            message_id: Discord message ID to edit when trailer is found
            title: Movie title
            year: Release year (optional)
            channel_id: Discord channel ID where message was posted
        """
        now = datetime.utcnow()
        next_retry = now + timedelta(seconds=self.retry_intervals[0])

        self.retries[str(message_id)] = {
            "title": title,
            "year": year,
            "channel_id": channel_id,
            "attempt": 0,
            "next_retry": next_retry.isoformat(),
            "created_at": now.isoformat()
        }

        self._save()
        print(f"📝 Added '{title}' to trailer retry queue (message {message_id})")

    def get_pending_retries(self) -> List[Tuple[str, Dict]]:
        """
        Get all retries that are due for retry now

        Returns:
            List of (message_id, retry_data) tuples
        """
        now = datetime.utcnow()
        pending = []

        for msg_id, retry in self.retries.items():
            try:
                next_retry = datetime.fromisoformat(retry["next_retry"])
                if now >= next_retry:
                    pending.append((msg_id, retry))
            except (ValueError, KeyError) as e:
                print(f"⚠️ Invalid retry data for message {msg_id}: {e}")
                continue

        return pending

    def increment_attempt(self, message_id: str) -> bool:
        """
        Increment retry attempt counter

        Args:
            message_id: Message ID to increment

        Returns:
            True if another retry is scheduled, False if max retries reached
        """
        if message_id not in self.retries:
            return False

        retry = self.retries[message_id]
        retry["attempt"] += 1

        if retry["attempt"] >= self.max_retries:
            # Max retries reached - give up
            print(f"⏹️ Max retries ({self.max_retries}) reached for '{retry['title']}' - giving up")
            del self.retries[message_id]
            self._save()
            return False

        # Schedule next retry
        now = datetime.utcnow()
        next_retry = now + timedelta(seconds=self.retry_intervals[retry["attempt"]])
        retry["next_retry"] = next_retry.isoformat()

        self._save()

        # Calculate hours until next retry
        hours_until = self.retry_intervals[retry["attempt"]] / 3600
        print(f"🔄 Retry {retry['attempt'] + 1}/{self.max_retries} scheduled for '{retry['title']}' in {hours_until:.1f}h")

        return True

    def remove_retry(self, message_id: str):
        """
        Remove a retry from the queue (successful or cancelled)

        Args:
            message_id: Message ID to remove
        """
        if message_id in self.retries:
            title = self.retries[message_id].get('title', 'Unknown')
            del self.retries[message_id]
            self._save()
            print(f"✓ Removed '{title}' from retry queue")

    def get_retry_count(self) -> int:
        """
        Get number of pending retries

        Returns:
            Count of pending retries
        """
        return len(self.retries)

    def cleanup_old_retries(self, max_age_hours: int = 48):
        """
        Remove retries older than specified age

        Args:
            max_age_hours: Maximum age in hours before cleanup
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=max_age_hours)
        removed = 0

        # Create list of keys to remove (can't modify dict during iteration)
        to_remove = []

        for msg_id, retry in self.retries.items():
            try:
                created_at = datetime.fromisoformat(retry["created_at"])
                if created_at < cutoff:
                    to_remove.append(msg_id)
            except (ValueError, KeyError):
                # Invalid data - remove it
                to_remove.append(msg_id)

        for msg_id in to_remove:
            del self.retries[msg_id]
            removed += 1

        if removed > 0:
            self._save()
            print(f"🧹 Cleaned up {removed} old trailer retries (older than {max_age_hours}h)")

    def get_status(self) -> str:
        """
        Get human-readable status of retry queue

        Returns:
            Status string
        """
        if not self.retries:
            return "No pending trailer retries"

        lines = [f"Pending trailer retries: {len(self.retries)}"]

        for msg_id, retry in list(self.retries.items())[:5]:  # Show first 5
            try:
                next_retry = datetime.fromisoformat(retry["next_retry"])
                now = datetime.utcnow()
                time_until = next_retry - now

                if time_until.total_seconds() > 0:
                    hours = time_until.total_seconds() / 3600
                    status = f"next retry in {hours:.1f}h"
                else:
                    status = "due now"

                lines.append(f"  - {retry['title']} ({retry['year']}) - attempt {retry['attempt'] + 1}/{self.max_retries} - {status}")
            except (ValueError, KeyError):
                lines.append(f"  - Message {msg_id} (invalid data)")

        if len(self.retries) > 5:
            lines.append(f"  ... and {len(self.retries) - 5} more")

        return "\n".join(lines)
