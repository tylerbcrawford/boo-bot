"""
Media Cog - Commands for managing TV shows and movies via Sonarr/Radarr
"""
import discord
from discord.ext import commands
import asyncio

from config import config
from utils.api_clients import SonarrClient, RadarrClient

REACTIONS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']


class Media(commands.Cog):
    """TV Show and Movie management commands"""

    def __init__(self, bot):
        self.bot = bot
        self.sonarr = SonarrClient(config.SONARR_URL, config.SONARR_API_KEY) if config.SONARR_API_KEY else None
        self.radarr = RadarrClient(config.RADARR_URL, config.RADARR_API_KEY) if config.RADARR_API_KEY else None

    def _is_requests_channel(self, ctx):
        """Check if command is used in the designated requests channel"""
        return ctx.channel.name.lower() == config.REQUESTS_CHANNEL_NAME.lower()

    def _get_poster_url(self, images):
        """Extract poster URL from image array"""
        for img in (images or []):
            if img.get('coverType') == 'poster' and img.get('remoteUrl'):
                return img['remoteUrl']
        return None

    @commands.command(name='sonarr', help='Check Sonarr connection status')
    async def sonarr_status(self, ctx):
        """Test Sonarr API connection"""
        if not self.sonarr:
            await ctx.send("⚠️ Sonarr not configured. Add SONARR_API_KEY to .env file")
            return

        result = self.sonarr.test_connection()

        if result['success']:
            version = result['data'].get('version', 'unknown')
            await ctx.send(f"✅ Connected to Sonarr {version}")
        else:
            await ctx.send(f"❌ Cannot connect to Sonarr: {result['error']}")

    @commands.command(name='radarr', help='Check Radarr connection status')
    async def radarr_status(self, ctx):
        """Test Radarr API connection"""
        if not self.radarr:
            await ctx.send("⚠️ Radarr not configured. Add RADARR_API_KEY to .env file")
            return

        result = self.radarr.test_connection()

        if result['success']:
            version = result['data'].get('version', 'unknown')
            await ctx.send(f"✅ Connected to Radarr {version}")
        else:
            await ctx.send(f"❌ Cannot connect to Radarr: {result['error']}")

    @commands.command(name='tv', help='Request a TV show. Usage: !tv Breaking Bad')
    async def tv(self, ctx, *, query: str):
        """Search for and add a TV show to Sonarr"""
        if not self._is_requests_channel(ctx):
            await ctx.send(f"❌ This command can only be used in the #{config.REQUESTS_CHANNEL_NAME} channel.")
            return

        if not self.sonarr:
            await ctx.send("⚠️ Sonarr not configured. Add SONARR_API_KEY to .env file")
            return

        await ctx.send(f"🔍 Searching for TV show: **{query}**")

        results = self.sonarr.search_series(query)

        if not results:
            await ctx.send(f"❌ No TV shows found for: **{query}**\nTry a different search term.")
            return

        if len(results) == 1:
            # Single result — add directly
            series = results[0]
            title = series.get('title', 'Unknown')
            year = series.get('year', '')
            label = f"**{title}** ({year})" if year else f"**{title}**"
            await ctx.send(f"📺 Found: {label}")

            result = self.sonarr.add_series(
                series,
                config.SONARR_ROOT_FOLDER,
                config.SONARR_QUALITY_PROFILE_ID
            )

            if result['success']:
                await ctx.send(f"✅ Added to Sonarr! All seasons will be monitored and searched.")
            elif result.get('already_exists'):
                await ctx.send(f"📺 {label} is already in your library!")
            else:
                await ctx.send(f"❌ Failed to add: {result['error']}")
            return

        # Multiple results — show embed with reactions
        embed = discord.Embed(
            title="📺 Multiple TV shows found",
            description="React with a number to add that show:",
            color=discord.Color.blue()
        )

        poster_url = self._get_poster_url(results[0].get('images', []))
        if poster_url:
            embed.set_thumbnail(url=poster_url)

        for idx, series in enumerate(results[:5], 1):
            title = series.get('title', 'Unknown')
            year = series.get('year', '')
            network = series.get('network', '')
            seasons = series.get('seasonCount', 0)
            overview = series.get('overview', 'No description available.')

            name = f"{idx}. {title} ({year})" if year else f"{idx}. {title}"
            parts = []
            if network:
                parts.append(network)
            parts.append(f"{seasons} season(s)")
            value = f"{'  '.join(parts)}\n{overview[:120]}{'...' if len(overview) > 120 else ''}"

            embed.add_field(name=name, value=value, inline=False)

        message = await ctx.send(embed=embed)

        for i in range(min(len(results), 5)):
            await message.add_reaction(REACTIONS[i])

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in REACTIONS[:min(len(results), 5)]
                and reaction.message.id == message.id
            )

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
            selected_idx = REACTIONS.index(str(reaction.emoji))
            series = results[selected_idx]
            title = series.get('title', 'Unknown')
            year = series.get('year', '')
            label = f"**{title}** ({year})" if year else f"**{title}**"

            await ctx.send(f"Adding: {label}")

            result = self.sonarr.add_series(
                series,
                config.SONARR_ROOT_FOLDER,
                config.SONARR_QUALITY_PROFILE_ID
            )

            if result['success']:
                await ctx.send(f"✅ Added to Sonarr! All seasons will be monitored and searched.")
            elif result.get('already_exists'):
                await ctx.send(f"📺 {label} is already in your library!")
            else:
                await ctx.send(f"❌ Failed to add: {result['error']}")

        except asyncio.TimeoutError:
            await ctx.send("⏱️ Selection timed out.")

    @commands.command(name='movie', help='Request a movie. Usage: !movie Inception')
    async def movie(self, ctx, *, query: str):
        """Search for and add a movie to Radarr"""
        if not self._is_requests_channel(ctx):
            await ctx.send(f"❌ This command can only be used in the #{config.REQUESTS_CHANNEL_NAME} channel.")
            return

        if not self.radarr:
            await ctx.send("⚠️ Radarr not configured. Add RADARR_API_KEY to .env file")
            return

        await ctx.send(f"🔍 Searching for movie: **{query}**")

        results = self.radarr.search_movies(query)

        if not results:
            await ctx.send(f"❌ No movies found for: **{query}**\nTry a different search term or include the year.")
            return

        if len(results) == 1:
            # Single result — add directly
            movie = results[0]
            title = movie.get('title', 'Unknown')
            year = movie.get('year', '')
            label = f"**{title}** ({year})" if year else f"**{title}**"
            await ctx.send(f"🎬 Found: {label}")

            result = self.radarr.add_movie(
                movie,
                config.RADARR_ROOT_FOLDER,
                config.RADARR_QUALITY_PROFILE_ID
            )

            if result['success']:
                await ctx.send(f"✅ Added to Radarr! Download will start when a release is available.")
            elif result.get('already_exists'):
                await ctx.send(f"🎬 {label} is already in your library!")
            else:
                await ctx.send(f"❌ Failed to add: {result['error']}")
            return

        # Multiple results — show embed with reactions
        embed = discord.Embed(
            title="🎬 Multiple movies found",
            description="React with a number to add that movie:",
            color=discord.Color.blue()
        )

        poster_url = self._get_poster_url(results[0].get('images', []))
        if poster_url:
            embed.set_thumbnail(url=poster_url)

        for idx, movie in enumerate(results[:5], 1):
            title = movie.get('title', 'Unknown')
            year = movie.get('year', '')
            runtime = movie.get('runtime', 0)
            overview = movie.get('overview', 'No description available.')

            name = f"{idx}. {title} ({year})" if year else f"{idx}. {title}"
            parts = []
            if runtime:
                parts.append(f"{runtime}min")
            parts.append(overview[:120] + ('...' if len(overview) > 120 else ''))
            value = '\n'.join(parts) if len(parts) > 1 else parts[0]

            embed.add_field(name=name, value=value, inline=False)

        message = await ctx.send(embed=embed)

        for i in range(min(len(results), 5)):
            await message.add_reaction(REACTIONS[i])

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in REACTIONS[:min(len(results), 5)]
                and reaction.message.id == message.id
            )

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
            selected_idx = REACTIONS.index(str(reaction.emoji))
            movie = results[selected_idx]
            title = movie.get('title', 'Unknown')
            year = movie.get('year', '')
            label = f"**{title}** ({year})" if year else f"**{title}**"

            await ctx.send(f"Adding: {label}")

            result = self.radarr.add_movie(
                movie,
                config.RADARR_ROOT_FOLDER,
                config.RADARR_QUALITY_PROFILE_ID
            )

            if result['success']:
                await ctx.send(f"✅ Added to Radarr! Download will start when a release is available.")
            elif result.get('already_exists'):
                await ctx.send(f"🎬 {label} is already in your library!")
            else:
                await ctx.send(f"❌ Failed to add: {result['error']}")

        except asyncio.TimeoutError:
            await ctx.send("⏱️ Selection timed out.")


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(Media(bot))
