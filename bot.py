#!/usr/bin/env python3
"""
Boo Bot - Modular Discord bot for media server management
Features: Book management (Readarr), Media management (Sonarr/Radarr), and more
"""
import discord
from discord.ext import commands
import asyncio
import sys
from pathlib import Path

from config import config


# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=config.COMMAND_PREFIX, intents=intents)


@bot.event
async def on_ready():
    """Bot startup event"""
    print(f'╔═══════════════════════════════════════════════════════════╗')
    print(f'║  Boo Bot - Ready                                          ║')
    print(f'╚═══════════════════════════════════════════════════════════╝')
    print(f'Bot User: {bot.user}')
    print(f'Bot ID: {bot.user.id}')
    print(f'Command Prefix: {config.COMMAND_PREFIX}')
    print(f'Connected to {len(bot.guilds)} guild(s)')
    print(f'─────────────────────────────────────────────────────────────')
    print(f'Loaded Cogs:')
    for cog in bot.cogs:
        print(f'  ✓ {cog}')
    print(f'─────────────────────────────────────────────────────────────')
    print(f'Ready to receive commands!')
    print()


@bot.event
async def on_message(message):
    """Process commands from humans and whitelisted bots"""
    # Default discord.py behavior skips all bot messages.
    # Allow whitelisted bot IDs (e.g., MCP bot for testing).
    if message.author.bot:
        if message.author.id not in config.ALLOWED_BOT_IDS:
            return
    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    """Global error handler"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ Unknown command. Type `{config.COMMAND_PREFIX}help` for available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument. Use `{config.COMMAND_PREFIX}help {ctx.command}` for usage.")
    elif isinstance(error, commands.CommandInvokeError):
        await ctx.send(f"❌ Error executing command: {error.original}")
        print(f"Command error in {ctx.command}: {error.original}")
    else:
        await ctx.send(f"❌ An error occurred: {error}")
        print(f"Unhandled error: {error}")


async def load_cogs():
    """Load all cog modules"""
    cogs_dir = Path(__file__).parent / 'cogs'
    
    # List of cogs to load (add new cogs here)
    cog_modules = [
        'cogs.books',               # Book management via Readarr
        'cogs.media',               # TV/Movie management via Sonarr/Radarr
        'cogs.notifiarr_rebrander', # Rebrand Notifiarr posts in #general with YouTube trailers
        'cogs.episode_suppressor',  # Suppress episode notifications after new series added
        'cogs.readarr_manual_import',  # Detect manual Readarr imports and notify
        'cogs.perplexity_search',      # AI-powered search in #perplexity channel
        # Add more cogs here as you create them:
        # 'cogs.admin',  # Admin/moderation commands
        # 'cogs.fun',    # Fun/social commands
        # 'cogs.utils',  # Utility commands
    ]
    
    for cog in cog_modules:
        try:
            await bot.load_extension(cog)
            print(f'✓ Loaded: {cog}')
        except Exception as e:
            print(f'✗ Failed to load {cog}: {e}')


async def main():
    """Main bot entry point"""
    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print(f"Please check your .env file and ensure all required values are set.")
        sys.exit(1)
    
    # Load cogs
    print("Loading cogs...")
    await load_cogs()
    print()
    
    # Start bot
    try:
        await bot.start(config.DISCORD_TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid Discord token! Please check your .env file.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ Shutting down bot...")
        await bot.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Bot stopped by user")
        sys.exit(0)
