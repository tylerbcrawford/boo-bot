#!/usr/bin/env python3
"""
Configuration management for Discord bot
Loads settings from environment variables
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Bot configuration from environment variables"""
    
    # Discord
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    COMMAND_PREFIX = os.getenv('COMMAND_PREFIX', '!')
    
    # Readarr (Regular Books)
    READARR_URL = os.getenv('READARR_URL', 'http://localhost:8787')
    READARR_API_KEY = os.getenv('READARR_API_KEY', '')
    READARR_ROOT_FOLDER = os.getenv('ROOT_FOLDER_PATH', '/data/books/user1/ebooks')
    READARR_QUALITY_PROFILE_ID = int(os.getenv('QUALITY_PROFILE_ID', '1'))
    READARR_METADATA_PROFILE_ID = int(os.getenv('METADATA_PROFILE_ID', '1'))

    # Readarr (Audiobooks - First Instance)
    READARR_AUDIOBOOK_URL = os.getenv('READARR_AUDIOBOOK_URL', 'http://localhost:8787')
    READARR_AUDIOBOOK_API_KEY = os.getenv('READARR_AUDIOBOOK_API_KEY', '')
    READARR_AUDIOBOOK_ROOT_FOLDER = os.getenv('READARR_AUDIOBOOK_ROOT_FOLDER', '/data/books/user1/audiobooks')
    READARR_AUDIOBOOK_QUALITY_PROFILE_ID = int(os.getenv('READARR_AUDIOBOOK_QUALITY_PROFILE_ID', '1'))
    READARR_AUDIOBOOK_METADATA_PROFILE_ID = int(os.getenv('READARR_AUDIOBOOK_METADATA_PROFILE_ID', '1'))

    # Readarr2 (Second Ebooks Instance)
    READARR2_URL = os.getenv('READARR2_URL', 'http://localhost:8787')
    READARR2_API_KEY = os.getenv('READARR2_API_KEY', '')
    READARR2_ROOT_FOLDER = os.getenv('READARR2_ROOT_FOLDER', '/data/books/user2/ebooks')
    READARR2_QUALITY_PROFILE_ID = int(os.getenv('READARR2_QUALITY_PROFILE_ID', '1'))
    READARR2_METADATA_PROFILE_ID = int(os.getenv('READARR2_METADATA_PROFILE_ID', '1'))

    # Readarr-Audio2 (Second Audiobooks Instance)
    READARR_AUDIO2_URL = os.getenv('READARR_AUDIO2_URL', 'http://localhost:8787')
    READARR_AUDIO2_API_KEY = os.getenv('READARR_AUDIO2_API_KEY', '')
    READARR_AUDIO2_ROOT_FOLDER = os.getenv('READARR_AUDIO2_ROOT_FOLDER', '/data/books/user2/audiobooks')
    READARR_AUDIO2_QUALITY_PROFILE_ID = int(os.getenv('READARR_AUDIO2_QUALITY_PROFILE_ID', '1'))
    READARR_AUDIO2_METADATA_PROFILE_ID = int(os.getenv('READARR_AUDIO2_METADATA_PROFILE_ID', '1'))
    
    # Sonarr (TV Shows)
    SONARR_URL = os.getenv('SONARR_URL', 'http://localhost:8989')
    SONARR_API_KEY = os.getenv('SONARR_API_KEY', '')
    SONARR_ROOT_FOLDER = os.getenv('SONARR_ROOT_FOLDER', '/tv')
    SONARR_QUALITY_PROFILE_ID = int(os.getenv('SONARR_QUALITY_PROFILE_ID', '1'))

    # Radarr (Movies)
    RADARR_URL = os.getenv('RADARR_URL', 'http://localhost:7878')
    RADARR_API_KEY = os.getenv('RADARR_API_KEY', '')
    RADARR_ROOT_FOLDER = os.getenv('RADARR_ROOT_FOLDER', '/movies')
    RADARR_QUALITY_PROFILE_ID = int(os.getenv('RADARR_QUALITY_PROFILE_ID', '1'))
    
    # Media Request Channel
    REQUESTS_CHANNEL_NAME = os.getenv('REQUESTS_CHANNEL_NAME', 'requests')

    # Allowed Bot IDs (comma-separated) — bots whose messages should be processed as commands
    # Useful for MCP bot testing. Leave empty to only accept human commands (default).
    ALLOWED_BOT_IDS = [
        int(bid.strip()) for bid in os.getenv('ALLOWED_BOT_IDS', '').split(',')
        if bid.strip().isdigit()
    ]

    # Trailarr Configuration (YouTube trailer integration)
    TRAILARR_URL = os.getenv('TRAILARR_URL', 'http://trailarr:7889')
    TRAILARR_ENABLED = os.getenv('TRAILARR_ENABLED', 'true').lower() == 'true'

    # TMDb API Configuration (for YouTube trailer lookups)
    # Get your API key from https://www.themoviedb.org/settings/api
    TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')

    # Episode Suppressor Configuration
    EPISODE_SUPPRESSION_HOURS = int(os.getenv('EPISODE_SUPPRESSION_HOURS', '24'))
    EPISODE_SUPPRESSION_CHANNEL = os.getenv('EPISODE_SUPPRESSION_CHANNEL', 'general')

    # Manual Import Notifier Configuration
    MANUAL_IMPORT_POLL_INTERVAL = int(os.getenv('MANUAL_IMPORT_POLL_INTERVAL', '60'))
    MANUAL_IMPORT_CHANNEL = os.getenv('MANUAL_IMPORT_CHANNEL', 'general')

    # Perplexity AI Search
    PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY', '')
    PERPLEXITY_CHANNEL_NAME = os.getenv('PERPLEXITY_CHANNEL_NAME', 'perplexity')
    PERPLEXITY_MODEL = os.getenv('PERPLEXITY_MODEL', 'sonar')
    PERPLEXITY_COOLDOWN_SECONDS = int(os.getenv('PERPLEXITY_COOLDOWN_SECONDS', '10'))

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.DISCORD_TOKEN or cls.DISCORD_TOKEN == 'YOUR_DISCORD_BOT_TOKEN_HERE':
            raise ValueError(
                "DISCORD_TOKEN not set! Please add your Discord bot token to .env file"
            )
        if not cls.PERPLEXITY_API_KEY:
            print("⚠️  PERPLEXITY_API_KEY not set — #perplexity channel disabled")
        return True


# Global config instance
config = Config()
