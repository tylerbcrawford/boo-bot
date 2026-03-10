#!/usr/bin/env python3
"""Perplexity AI Search — responds to all messages in #perplexity with web-sourced answers"""
import re
import requests as http_requests
from datetime import datetime, timedelta
from collections import defaultdict

import discord
from discord.ext import commands

from config import config


class PerplexitySearch(commands.Cog):
    """Listens in #perplexity and replies with Perplexity Sonar answers."""

    API_URL = "https://api.perplexity.ai/chat/completions"

    def __init__(self, bot):
        self.bot = bot
        self.user_cooldowns = defaultdict(lambda: datetime.min)
        self.system_prompt = (
            "You are a knowledgeable assistant in a Discord server. "
            "Answer in exactly 2-3 short paragraphs — never more. "
            "Be direct — no filler, preamble, or closing advice. "
            "Prefer recent sources. Do NOT use inline citations like [1] or [2] in your text. "
            "Use **bold** for key terms. Use bullet lists only when comparing options. "
            "Never include a sources/references section or character counts — sources are appended automatically."
        )

    def _is_search_channel(self, channel):
        return channel.name == config.PERPLEXITY_CHANNEL_NAME

    def _check_cooldown(self, user_id):
        now = datetime.now()
        last = self.user_cooldowns[user_id]
        remaining = config.PERPLEXITY_COOLDOWN_SECONDS - (now - last).total_seconds()
        if remaining > 0:
            return False, int(remaining)
        return True, 0

    def _call_api(self, query):
        """POST to Perplexity chat/completions. Returns (answer, citations) or raises."""
        resp = http_requests.post(
            self.API_URL,
            headers={
                "Authorization": f"Bearer {config.PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.PERPLEXITY_MODEL,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": query},
                ],
                "max_tokens": 768,
                "temperature": 0.2,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
        citations = data.get("citations", [])
        return answer, citations

    def _clean_answer(self, answer):
        """Strip model-generated source lists, char counts, inline citations, and trailing noise."""
        # Remove any "Sources:", "References:", etc. section the model adds
        answer = re.split(r'\n+\*{0,2}(?:Sources|References|Links)\*{0,2}[\s:]*\n', answer, flags=re.IGNORECASE)[0]
        # Remove inline citations like [1], [2][3], [1, 2]
        answer = re.sub(r'\[[\d,\s]+\]', '', answer)
        # Remove char count comments like "(748 chars)"
        answer = re.sub(r'\(\d+ chars?\)', '', answer)
        # Clean up double spaces left behind
        answer = re.sub(r'  +', ' ', answer)
        return answer.rstrip()

    def _format_response(self, answer, citations, max_sources=5):
        """Clean answer and append numbered source URLs, capped at max_sources."""
        answer = self._clean_answer(answer)
        if not citations:
            return answer
        sources = "\n\n**Sources:**\n"
        for i, url in enumerate(citations[:max_sources], 1):
            sources += f"[{i}] <{url}>\n"
        return answer + sources

    def _split_message(self, text, max_len=1900):
        """Split text into chunks that fit Discord's 2000-char limit."""
        if len(text) <= max_len:
            return [text]
        chunks = []
        while text:
            if len(text) <= max_len:
                chunks.append(text)
                break
            split_pos = text.rfind("\n", 0, max_len)
            if split_pos == -1:
                split_pos = max_len
            chunks.append(text[:split_pos])
            text = text[split_pos:].lstrip()
        return chunks

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if not self._is_search_channel(message.channel):
            return
        if not message.content or not message.content.strip():
            return
        if not config.PERPLEXITY_API_KEY:
            return

        can_proceed, remaining = self._check_cooldown(message.author.id)
        if not can_proceed:
            await message.reply(
                f"⏳ Please wait {remaining}s before asking again.",
                mention_author=False,
                delete_after=5,
            )
            return

        self.user_cooldowns[message.author.id] = datetime.now()

        thinking_msg = await message.reply(
            "🔍 Searching the web...", mention_author=False
        )

        try:
            answer, citations = self._call_api(message.content)
            formatted = self._format_response(answer, citations)
            chunks = self._split_message(formatted)
            await thinking_msg.edit(content=chunks[0])
            for chunk in chunks[1:]:
                await message.channel.send(chunk)
        except http_requests.HTTPError as e:
            status = e.response.status_code if e.response else "?"
            print(f"[Perplexity] HTTP {status}: {e}")
            await thinking_msg.edit(
                content=f"❌ Search failed (HTTP {status}). Try again later."
            )
        except Exception as e:
            print(f"[Perplexity] Error: {e}")
            await thinking_msg.edit(
                content="❌ Something went wrong. Try again later."
            )


async def setup(bot):
    await bot.add_cog(PerplexitySearch(bot))
