"""
Books Cog - Commands for managing books via Readarr

Uses Readarr's own lookup endpoint which searches GoodReads for proper metadata.
Falls back to Prowlarr direct search when Readarr can't find metadata.
"""
import discord
from discord.ext import commands
from typing import Optional
import subprocess
import json
import asyncio
import os

from config import config
from utils.api_clients import ReadarrClient

# Prowlarr fallback script path (override via PROWLARR_FALLBACK_SCRIPT env var)
PROWLARR_FALLBACK_SCRIPT = os.getenv(
    'PROWLARR_FALLBACK_SCRIPT',
    '/opt/scripts/prowlarr-book-fallback.sh'
)


class Books(commands.Cog):
    """Book management commands using Readarr"""

    def __init__(self, bot):
        self.bot = bot
        self.readarr = ReadarrClient(config.READARR_URL, config.READARR_API_KEY)
        self.readarr_audiobooks = ReadarrClient(
            config.READARR_AUDIOBOOK_URL,
            config.READARR_AUDIOBOOK_API_KEY
        )
        self.readarr2 = ReadarrClient(config.READARR2_URL, config.READARR2_API_KEY)
        self.readarr_audio2 = ReadarrClient(
            config.READARR_AUDIO2_URL,
            config.READARR_AUDIO2_API_KEY
        )

    def _is_requests_channel(self, ctx):
        """Check if command is used in the designated requests channel"""
        return ctx.channel.name.lower() == config.REQUESTS_CHANNEL_NAME.lower()

    async def _prowlarr_fallback_search(self, title: str, author: Optional[str] = None) -> dict:
        """
        Fallback book search using Prowlarr when Readarr fails.
        Calls the prowlarr-book-fallback.sh script.

        Args:
            title: Book title
            author: Author name (optional)

        Returns:
            dict: Result with success, author, title, path, etc.
        """
        script_path = PROWLARR_FALLBACK_SCRIPT

        # Build command
        if author:
            cmd = [script_path, title, author]
        else:
            cmd = [script_path, title]

        try:
            # Run script asynchronously
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for completion with 6 minute timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=360.0
            )

            if process.returncode == 0:
                # Parse JSON from last line of output
                lines = stdout.decode().strip().split('\n')
                json_output = lines[-1]
                return json.loads(json_output)
            else:
                return {
                    "success": False,
                    "error": stderr.decode().strip() or "Unknown error"
                }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Download timeout (>6 minutes)"
            }
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Failed to parse script output"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @commands.command(name='book', help='Add a book to Readarr. Usage: !book Title by Author')
    async def book(self, ctx, *, query: str):
        """
        Main command: !book Taipei by Tao Lin
        Uses Readarr's native GoodReads search for accurate results.
        """
        # Check if command is used in the correct channel
        if not self._is_requests_channel(ctx):
            await ctx.send(f"❌ This command can only be used in the #{config.REQUESTS_CHANNEL_NAME} channel.")
            return

        await ctx.send(f"🔍 Searching for: **{query}**")

        # Use Readarr's native search (GoodReads)
        books = self.readarr.search_books(query)

        if not books:
            # Prowlarr fallback - try direct file search
            await ctx.send(f"❌ Readarr found no metadata. Trying Prowlarr fallback...")

            # Try to parse "Title by Author" format
            title = query
            author = None
            if " by " in query.lower():
                parts = query.split(" by ", 1)
                title = parts[0].strip()
                author = parts[1].strip() if len(parts) > 1 else None

            result = await self._prowlarr_fallback_search(title, author)

            if result["success"]:
                # Prowlarr download succeeded - now try to add to Readarr for monitoring
                # Search again with better query now that we know exact title/author
                search_query = f"{result['title']} by {result['author']}"
                books_retry = self.readarr.search_books(search_query)

                if books_retry:
                    # Found metadata! Add to Readarr for monitoring
                    add_result = self.readarr.add_book_with_cleanup(
                        books_retry[0],
                        config.READARR_ROOT_FOLDER,
                        config.READARR_QUALITY_PROFILE_ID,
                        config.READARR_METADATA_PROFILE_ID
                    )
                    monitor_msg = " (Added to Readarr for monitoring)" if add_result.get('success') else ""
                else:
                    monitor_msg = " (⚠️ No metadata - not monitored in Readarr)"

                await ctx.send(
                    f"✅ Book downloaded via Prowlarr!\n"
                    f"📚 **{result['author']}** - **{result['title']}**\n"
                    f"💾 Size: {result['size']}\n"
                    f"📥 Source: {result['indexer']} ({result['protocol']})\n"
                    f"📂 Calibre will auto-import shortly{monitor_msg}"
                )
            else:
                # Both Readarr and Prowlarr failed - try one more search to add to Readarr anyway
                # This way Anna's Archive automation can catch it later
                search_query = f"{title} by {author}" if author else title
                books_retry = self.readarr.search_books(search_query)

                if books_retry:
                    # Found metadata - add to Readarr for monitoring (Anna's Archive will download later)
                    add_result = self.readarr.add_book_with_cleanup(
                        books_retry[0],
                        config.READARR_ROOT_FOLDER,
                        config.READARR_QUALITY_PROFILE_ID,
                        config.READARR_METADATA_PROFILE_ID
                    )

                    if add_result.get('success'):
                        await ctx.send(
                            f"❌ Prowlarr found no results\n"
                            f"✅ Added **{books_retry[0]['title']}** to Readarr for monitoring\n"
                            f"📅 Anna's Archive will try to download within 12 hours"
                        )
                    else:
                        await ctx.send(
                            f"❌ Prowlarr found no results\n"
                            f"⚠️ Could not add to Readarr: {add_result.get('error', 'Unknown error')}"
                        )
                else:
                    # No metadata anywhere - truly can't help
                    await ctx.send(
                        f"❌ Complete failure - no results found:\n"
                        f"• Readarr (GoodReads): No metadata\n"
                        f"• Prowlarr (indexers): No files\n"
                        f"• Cannot monitor in Readarr without metadata\n"
                        f"Try a different search term or check the title/author spelling"
                    )
            return

        # Show results
        if len(books) == 1:
            # Only one result, add it directly
            book = books[0]
            await ctx.send(f"📚 Found: **{book['title']}**")

            result = self.readarr.add_book_with_cleanup(
                book,
                config.READARR_ROOT_FOLDER,
                config.READARR_QUALITY_PROFILE_ID,
                config.READARR_METADATA_PROFILE_ID
            )

            if result['success']:
                stats = result.get('cleanup_stats', {})
                msg = f"✅ Successfully added to Readarr!"
                if stats.get('search_triggered'):
                    msg += " Search triggered."
                if stats.get('books_unmonitored', 0) > 0:
                    msg += f" (Cleaned up {stats['books_unmonitored']} other book(s) by this author)"
                await ctx.send(msg)
            else:
                await ctx.send(f"❌ Failed to add to Readarr: {result['error']}")

        else:
            # Multiple results, let user choose
            embed = discord.Embed(
                title="📚 Multiple results found",
                description="React with the number to add that book:",
                color=discord.Color.blue()
            )

            for idx, book in enumerate(books[:5], 1):
                # Extract year from releaseDate (format: "2011-01-01T13:00:00Z")
                release_date = book.get('releaseDate', '')
                year = release_date[:4] if release_date else 'Unknown'
                # Use authorTitle or extract from it
                author_info = book.get('authorTitle', '').split(book.get('title', ''))[0].strip()
                embed.add_field(
                    name=f"{idx}. {book['title']}",
                    value=f"by {author_info} ({year})",
                    inline=False
                )

            message = await ctx.send(embed=embed)

            # Add number reactions
            reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
            for i in range(min(len(books), 5)):
                await message.add_reaction(reactions[i])

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in reactions[:len(books)]

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                # Get selected book
                selected_idx = reactions.index(str(reaction.emoji))
                selected_book = books[selected_idx]

                await ctx.send(f"Adding: **{selected_book['title']}**")

                result = self.readarr.add_book_with_cleanup(
                    selected_book,
                    config.READARR_ROOT_FOLDER,
                    config.READARR_QUALITY_PROFILE_ID,
                    config.READARR_METADATA_PROFILE_ID
                )

                if result['success']:
                    stats = result.get('cleanup_stats', {})
                    msg = f"✅ Successfully added to Readarr!"
                    if stats.get('search_triggered'):
                        msg += " Search triggered."
                    if stats.get('books_unmonitored', 0) > 0:
                        msg += f" (Cleaned up {stats['books_unmonitored']} other book(s) by this author)"
                    await ctx.send(msg)
                else:
                    await ctx.send(f"❌ Failed to add: {result['error']}")

            except TimeoutError:
                await ctx.send("⏱️ Selection timed out.")

    @commands.command(name='audiobook', help='Add an audiobook to Readarr. Usage: !audiobook Title by Author')
    async def audiobook(self, ctx, *, query: str):
        """
        Add audiobook command: !audiobook The Name of the Wind by Patrick Rothfuss
        Uses Readarr-Audio's native GoodReads search.
        """
        # Check if command is used in the correct channel
        if not self._is_requests_channel(ctx):
            await ctx.send(f"❌ This command can only be used in the #{config.REQUESTS_CHANNEL_NAME} channel.")
            return

        await ctx.send(f"🔍 Searching for audiobook: **{query}**")

        # Use Readarr-Audio's native search (GoodReads)
        books = self.readarr_audiobooks.search_books(query)

        if not books:
            await ctx.send(f"❌ Could not find any audiobooks matching: **{query}**")
            return

        # Show results
        if len(books) == 1:
            # Only one result, add it directly
            book = books[0]
            await ctx.send(f"🎧 Found audiobook: **{book['title']}**")

            result = self.readarr_audiobooks.add_book_with_cleanup(
                book,
                config.READARR_AUDIOBOOK_ROOT_FOLDER,
                config.READARR_AUDIOBOOK_QUALITY_PROFILE_ID,
                config.READARR_AUDIOBOOK_METADATA_PROFILE_ID
            )

            if result['success']:
                stats = result.get('cleanup_stats', {})
                msg = f"✅ Successfully added audiobook to Readarr!"
                if stats.get('search_triggered'):
                    msg += " Search triggered."
                if stats.get('books_unmonitored', 0) > 0:
                    msg += f" (Cleaned up {stats['books_unmonitored']} other book(s) by this author)"
                await ctx.send(msg)
            else:
                await ctx.send(f"❌ Failed to add audiobook to Readarr: {result['error']}")

        else:
            # Multiple results, let user choose
            embed = discord.Embed(
                title="🎧 Multiple audiobook results found",
                description="React with the number to add that audiobook:",
                color=discord.Color.blue()
            )

            for idx, book in enumerate(books[:5], 1):
                release_date = book.get('releaseDate', '')
                year = release_date[:4] if release_date else 'Unknown'
                author_info = book.get('authorTitle', '').split(book.get('title', ''))[0].strip()
                embed.add_field(
                    name=f"{idx}. {book['title']}",
                    value=f"by {author_info} ({year})",
                    inline=False
                )

            message = await ctx.send(embed=embed)

            # Add number reactions
            reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
            for i in range(min(len(books), 5)):
                await message.add_reaction(reactions[i])

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in reactions[:len(books)]

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                # Get selected book
                selected_idx = reactions.index(str(reaction.emoji))
                selected_book = books[selected_idx]

                await ctx.send(f"Adding audiobook: **{selected_book['title']}**")

                result = self.readarr_audiobooks.add_book_with_cleanup(
                    selected_book,
                    config.READARR_AUDIOBOOK_ROOT_FOLDER,
                    config.READARR_AUDIOBOOK_QUALITY_PROFILE_ID,
                    config.READARR_AUDIOBOOK_METADATA_PROFILE_ID
                )

                if result['success']:
                    stats = result.get('cleanup_stats', {})
                    msg = f"✅ Successfully added audiobook to Readarr!"
                    if stats.get('search_triggered'):
                        msg += " Search triggered."
                    if stats.get('books_unmonitored', 0) > 0:
                        msg += f" (Cleaned up {stats['books_unmonitored']} other book(s) by this author)"
                    await ctx.send(msg)
                else:
                    await ctx.send(f"❌ Failed to add audiobook: {result['error']}")

            except TimeoutError:
                await ctx.send("⏱️ Selection timed out.")

    @commands.command(name='book2', help='Add a book to Readarr2. Usage: !book2 Title by Author')
    async def book2(self, ctx, *, query: str):
        """
        Add book to readarr2 instance: !book2 Taipei by Tao Lin
        Uses Readarr2's native GoodReads search.
        """
        # Check if command is used in the correct channel
        if not self._is_requests_channel(ctx):
            await ctx.send(f"❌ This command can only be used in the #{config.REQUESTS_CHANNEL_NAME} channel.")
            return

        await ctx.send(f"🔍 Searching for: **{query}**")

        # Use Readarr2's native search (GoodReads)
        books = self.readarr2.search_books(query)

        if not books:
            # Prowlarr fallback - try direct file search
            await ctx.send(f"❌ Readarr2 found no metadata. Trying Prowlarr fallback...")

            # Try to parse "Title by Author" format
            title = query
            author = None
            if " by " in query.lower():
                parts = query.split(" by ", 1)
                title = parts[0].strip()
                author = parts[1].strip() if len(parts) > 1 else None

            result = await self._prowlarr_fallback_search(title, author)

            if result["success"]:
                # Prowlarr download succeeded - now try to add to Readarr2 for monitoring
                search_query = f"{result['title']} by {result['author']}"
                books_retry = self.readarr2.search_books(search_query)

                if books_retry:
                    # Found metadata! Add to Readarr2 for monitoring
                    add_result = self.readarr2.add_book_with_cleanup(
                        books_retry[0],
                        config.READARR2_ROOT_FOLDER,
                        config.READARR2_QUALITY_PROFILE_ID,
                        config.READARR2_METADATA_PROFILE_ID
                    )
                    monitor_msg = " (Added to Readarr2 for monitoring)" if add_result.get('success') else ""
                else:
                    monitor_msg = " (⚠️ No metadata - not monitored in Readarr2)"

                await ctx.send(
                    f"✅ Book downloaded via Prowlarr!\n"
                    f"📚 **{result['author']}** - **{result['title']}**\n"
                    f"💾 Size: {result['size']}\n"
                    f"📥 Source: {result['indexer']} ({result['protocol']})\n"
                    f"📂 Calibre will auto-import shortly{monitor_msg}"
                )
            else:
                # Both Readarr2 and Prowlarr failed - try to add to Readarr2 anyway for Anna's Archive
                search_query = f"{title} by {author}" if author else title
                books_retry = self.readarr2.search_books(search_query)

                if books_retry:
                    # Found metadata - add to Readarr2 for monitoring
                    add_result = self.readarr2.add_book_with_cleanup(
                        books_retry[0],
                        config.READARR2_ROOT_FOLDER,
                        config.READARR2_QUALITY_PROFILE_ID,
                        config.READARR2_METADATA_PROFILE_ID
                    )

                    if add_result.get('success'):
                        await ctx.send(
                            f"❌ Prowlarr found no results\n"
                            f"✅ Added **{books_retry[0]['title']}** to Readarr2 for monitoring\n"
                            f"📅 Anna's Archive will try to download within 12 hours"
                        )
                    else:
                        await ctx.send(
                            f"❌ Prowlarr found no results\n"
                            f"⚠️ Could not add to Readarr2: {add_result.get('error', 'Unknown error')}"
                        )
                else:
                    # No metadata anywhere
                    await ctx.send(
                        f"❌ Complete failure - no results found:\n"
                        f"• Readarr2 (GoodReads): No metadata\n"
                        f"• Prowlarr (indexers): No files\n"
                        f"• Cannot monitor in Readarr2 without metadata\n"
                        f"Try a different search term or check the title/author spelling"
                    )
            return

        # Show results
        if len(books) == 1:
            # Only one result, add it directly
            book = books[0]
            await ctx.send(f"📚 Found: **{book['title']}**")

            result = self.readarr2.add_book_with_cleanup(
                book,
                config.READARR2_ROOT_FOLDER,
                config.READARR2_QUALITY_PROFILE_ID,
                config.READARR2_METADATA_PROFILE_ID
            )

            if result['success']:
                stats = result.get('cleanup_stats', {})
                msg = f"✅ Successfully added to Readarr2!"
                if stats.get('search_triggered'):
                    msg += " Search triggered."
                if stats.get('books_unmonitored', 0) > 0:
                    msg += f" (Cleaned up {stats['books_unmonitored']} other book(s) by this author)"
                await ctx.send(msg)
            else:
                await ctx.send(f"❌ Failed to add to Readarr2: {result['error']}")

        else:
            # Multiple results, let user choose
            embed = discord.Embed(
                title="📚 Multiple results found",
                description="React with the number to add that book:",
                color=discord.Color.blue()
            )

            for idx, book in enumerate(books[:5], 1):
                release_date = book.get('releaseDate', '')
                year = release_date[:4] if release_date else 'Unknown'
                author_info = book.get('authorTitle', '').split(book.get('title', ''))[0].strip()
                embed.add_field(
                    name=f"{idx}. {book['title']}",
                    value=f"by {author_info} ({year})",
                    inline=False
                )

            message = await ctx.send(embed=embed)

            # Add number reactions
            reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
            for i in range(min(len(books), 5)):
                await message.add_reaction(reactions[i])

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in reactions[:len(books)]

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                # Get selected book
                selected_idx = reactions.index(str(reaction.emoji))
                selected_book = books[selected_idx]

                await ctx.send(f"Adding: **{selected_book['title']}**")

                result = self.readarr2.add_book_with_cleanup(
                    selected_book,
                    config.READARR2_ROOT_FOLDER,
                    config.READARR2_QUALITY_PROFILE_ID,
                    config.READARR2_METADATA_PROFILE_ID
                )

                if result['success']:
                    stats = result.get('cleanup_stats', {})
                    msg = f"✅ Successfully added to Readarr2!"
                    if stats.get('search_triggered'):
                        msg += " Search triggered."
                    if stats.get('books_unmonitored', 0) > 0:
                        msg += f" (Cleaned up {stats['books_unmonitored']} other book(s) by this author)"
                    await ctx.send(msg)
                else:
                    await ctx.send(f"❌ Failed to add: {result['error']}")

            except TimeoutError:
                await ctx.send("⏱️ Selection timed out.")

    @commands.command(name='audiobook2', help='Add an audiobook to Readarr-Audio2. Usage: !audiobook2 Title by Author')
    async def audiobook2(self, ctx, *, query: str):
        """
        Add audiobook to readarr-audio2 instance: !audiobook2 The Name of the Wind by Patrick Rothfuss
        Uses Readarr-Audio2's native GoodReads search.
        """
        # Check if command is used in the correct channel
        if not self._is_requests_channel(ctx):
            await ctx.send(f"❌ This command can only be used in the #{config.REQUESTS_CHANNEL_NAME} channel.")
            return

        await ctx.send(f"🔍 Searching for audiobook: **{query}**")

        # Use Readarr-Audio2's native search (GoodReads)
        books = self.readarr_audio2.search_books(query)

        if not books:
            await ctx.send(f"❌ Could not find any audiobooks matching: **{query}**")
            return

        # Show results
        if len(books) == 1:
            # Only one result, add it directly
            book = books[0]
            await ctx.send(f"🎧 Found audiobook: **{book['title']}**")

            result = self.readarr_audio2.add_book_with_cleanup(
                book,
                config.READARR_AUDIO2_ROOT_FOLDER,
                config.READARR_AUDIO2_QUALITY_PROFILE_ID,
                config.READARR_AUDIO2_METADATA_PROFILE_ID
            )

            if result['success']:
                stats = result.get('cleanup_stats', {})
                msg = f"✅ Successfully added audiobook to Readarr-Audio2!"
                if stats.get('search_triggered'):
                    msg += " Search triggered."
                if stats.get('books_unmonitored', 0) > 0:
                    msg += f" (Cleaned up {stats['books_unmonitored']} other book(s) by this author)"
                await ctx.send(msg)
            else:
                await ctx.send(f"❌ Failed to add audiobook to Readarr-Audio2: {result['error']}")

        else:
            # Multiple results, let user choose
            embed = discord.Embed(
                title="🎧 Multiple audiobook results found",
                description="React with the number to add that audiobook:",
                color=discord.Color.blue()
            )

            for idx, book in enumerate(books[:5], 1):
                release_date = book.get('releaseDate', '')
                year = release_date[:4] if release_date else 'Unknown'
                author_info = book.get('authorTitle', '').split(book.get('title', ''))[0].strip()
                embed.add_field(
                    name=f"{idx}. {book['title']}",
                    value=f"by {author_info} ({year})",
                    inline=False
                )

            message = await ctx.send(embed=embed)

            # Add number reactions
            reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
            for i in range(min(len(books), 5)):
                await message.add_reaction(reactions[i])

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in reactions[:len(books)]

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                # Get selected book
                selected_idx = reactions.index(str(reaction.emoji))
                selected_book = books[selected_idx]

                await ctx.send(f"Adding audiobook: **{selected_book['title']}**")

                result = self.readarr_audio2.add_book_with_cleanup(
                    selected_book,
                    config.READARR_AUDIO2_ROOT_FOLDER,
                    config.READARR_AUDIO2_QUALITY_PROFILE_ID,
                    config.READARR_AUDIO2_METADATA_PROFILE_ID
                )

                if result['success']:
                    stats = result.get('cleanup_stats', {})
                    msg = f"✅ Successfully added audiobook to Readarr-Audio2!"
                    if stats.get('search_triggered'):
                        msg += " Search triggered."
                    if stats.get('books_unmonitored', 0) > 0:
                        msg += f" (Cleaned up {stats['books_unmonitored']} other book(s) by this author)"
                    await ctx.send(msg)
                else:
                    await ctx.send(f"❌ Failed to add audiobook: {result['error']}")

            except TimeoutError:
                await ctx.send("⏱️ Selection timed out.")

    @commands.command(name='searchbook', help='Search for a book without adding. Usage: !searchbook query')
    async def searchbook(self, ctx, *, query: str):
        """Search only, don't add. Uses Readarr's GoodReads search."""
        await ctx.send(f"🔍 Searching for: **{query}**")

        books = self.readarr.search_books(query)

        if not books:
            await ctx.send(f"❌ No results found for: **{query}**")
            return

        embed = discord.Embed(
            title="📚 Search Results (GoodReads)",
            description=f"Found {len(books)} book(s)",
            color=discord.Color.green()
        )

        for idx, book in enumerate(books[:5], 1):
            release_date = book.get('releaseDate', '')
            year = release_date[:4] if release_date else 'Unknown'
            author_info = book.get('authorTitle', '').split(book.get('title', ''))[0].strip()
            rating = book.get('ratings', {}).get('value', 'N/A')

            embed.add_field(
                name=f"{idx}. {book['title']}",
                value=f"by {author_info} ({year})\nRating: {rating}/5 | GoodReads ID: {book.get('foreignBookId', 'N/A')}",
                inline=False
            )

        await ctx.send(embed=embed)
    
    @commands.command(name='readarr', help='Check Readarr connection status')
    async def readarr_status(self, ctx):
        """Test Readarr API connection"""
        result = self.readarr.test_connection()
        
        if result['success']:
            version = result['data'].get('version', 'unknown')
            await ctx.send(f"✅ Connected to Readarr {version}")
        else:
            await ctx.send(f"❌ Cannot connect to Readarr: {result['error']}")


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(Books(bot))
