## Implementation Plan: Perplexity-Powered Discord Bot

### Code Review Summary

The provided implementation is solid and follows Discord.py best practices with a cog-based architecture. Your $5/month Pro API credit covers approximately 1,000 Sonar queries or 200 Sonar Pro queries. However, I've identified several improvements for production readiness. [docs.perplexity](https://docs.perplexity.ai/getting-started/models/models/sonar)

### Phase 1: Setup & Prerequisites

**1.1 API Configuration**
- Navigate to [Perplexity Settings → API](https://www.perplexity.ai/settings/api)
- Add payment method (required to unlock free $5 credit, no charges until exceeded) [glbgpt](https://www.glbgpt.com/hub/perplexity-api-cost-2025/)
- Generate and securely store API key
- Enable auto-top-up if expecting high usage

**1.2 Environment Setup**
```bash
pip install discord.py openai python-dotenv
```

**1.3 Environment Variables (.env file)**
```
DISCORD_BOT_TOKEN=your_discord_token
PERPLEXITY_API_KEY=pplx-xxxxx
TARGET_CHANNEL_ID=123456789012345678
MODEL_NAME=sonar
```

### Phase 2: Enhanced Implementation

**2.1 Improved Cog with Production Features**

Key improvements over original code:
- **Rate limiting protection** - Prevents API abuse [support-dev.discord](https://support-dev.discord.com/hc/en-us/articles/6223003921559-My-Bot-is-Being-Rate-Limited)
- **Error handling** - Graceful failures with user feedback
- **Message length handling** - Discord has 2000 char limits
- **Configurable system prompt** - Customizable assistant behavior
- **Cost tracking** - Monitor API usage
- **Cooldowns** - Prevent spam

**2.2 Enhanced Code Structure**
```python
import discord
from discord.ext import commands
from openai import OpenAI
import os
from datetime import datetime, timedelta
from collections import defaultdict

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", 0))
MODEL_NAME = os.getenv("MODEL_NAME", "sonar")

class PerplexitySearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = OpenAI(
            api_key=PERPLEXITY_API_KEY,
            base_url="https://api.perplexity.ai"
        )
        # Rate limiting: track requests per user
        self.user_cooldowns = defaultdict(lambda: datetime.min)
        self.cooldown_seconds = 10  # Adjust as needed
        
        # System prompt for consistent behavior
        self.system_prompt = (
            "You are a helpful assistant in a Discord server. "
            "Provide concise, accurate answers using web search. "
            "Keep responses under 1800 characters when possible. "
            "Include citations when relevant."
        )

    def check_cooldown(self, user_id):
        """Check if user is on cooldown"""
        now = datetime.now()
        last_request = self.user_cooldowns[user_id]
        if now - last_request < timedelta(seconds=self.cooldown_seconds):
            remaining = self.cooldown_seconds - (now - last_request).seconds
            return False, remaining
        return True, 0

    def split_message(self, text, max_length=1900):
        """Split long messages into chunks"""
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        while text:
            if len(text) <= max_length:
                chunks.append(text)
                break
            
            # Try to split at newline
            split_pos = text.rfind('\n', 0, max_length)
            if split_pos == -1:
                split_pos = max_length
            
            chunks.append(text[:split_pos])
            text = text[split_pos:].lstrip()
        
        return chunks

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bot's own messages
        if message.author == self.bot.user:
            return

        # Only respond in target channel
        if message.channel.id != TARGET_CHANNEL_ID:
            return

        # Ignore empty messages
        if not message.content or message.content.strip() == "":
            return

        # Check cooldown
        can_proceed, remaining = self.check_cooldown(message.author.id)
        if not can_proceed:
            await message.reply(
                f"⏳ Please wait {remaining}s before asking again.",
                mention_author=False,
                delete_after=5
            )
            return

        # Update cooldown
        self.user_cooldowns[message.author.id] = datetime.now()

        async with message.channel.typing():
            try:
                # Call Perplexity API
                response = self.client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": message.content}
                    ],
                    temperature=0.2,  # Lower for factual responses
                    max_tokens=1500   # Control response length
                )

                answer = response.choices[0].message.content
                
                # Split if too long
                chunks = self.split_message(answer)
                
                # Send first chunk as reply
                await message.reply(chunks[0], mention_author=False)
                
                # Send remaining chunks as follow-ups
                for chunk in chunks[1:]:
                    await message.channel.send(chunk)

            except Exception as e:
                error_msg = f"❌ Error: {str(e)[:100]}"
                await message.reply(error_msg, mention_author=False)
                # Log error for debugging
                print(f"[ERROR] {datetime.now()}: {str(e)}")

    @commands.command(name="setmodel")
    @commands.has_permissions(administrator=True)
    async def set_model(self, ctx, model: str):
        """Admin command to switch between sonar and sonar-pro"""
        valid_models = ["sonar", "sonar-pro"]
        if model.lower() in valid_models:
            global MODEL_NAME
            MODEL_NAME = model.lower()
            await ctx.send(f"✅ Model switched to: {MODEL_NAME}")
        else:
            await ctx.send(f"❌ Invalid model. Choose from: {', '.join(valid_models)}")

async def setup(bot):
    await bot.add_cog(PerplexitySearch(bot))
```

### Phase 3: Deployment Checklist

**3.1 Pre-Launch Testing**
- [ ] Test in a private channel first
- [ ] Verify API key is working
- [ ] Test rate limiting with rapid messages
- [ ] Test with long responses (>2000 chars)
- [ ] Test error handling (disconnect API key temporarily)
- [ ] Monitor API credit usage in Perplexity dashboard

**3.2 Configuration Decisions**

| Setting | Recommended Value | Rationale |
|---------|------------------|-----------|
| MODEL_NAME | `sonar` | 5x cheaper than sonar-pro, faster responses  [techcrunch](https://techcrunch.com/2025/01/21/perplexity-launches-sonar-an-api-for-ai-search/) |
| Cooldown | 10-15 seconds | Prevents spam, protects credits |
| Max Tokens | 1500 | Balances detail with cost |
| Temperature | 0.2 | Lower = more factual, less creative |

**3.3 Main Bot Integration**
```python
# In your main bot file (bot.py or main.py)
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True  # Required for on_message

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.load_extension("cogs.perplexity_search")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
```

### Phase 4: Monitoring & Optimization

**4.1 Usage Tracking**
- Monitor API usage at [Perplexity Settings → API](https://www.perplexity.ai/settings/api)
- Track: requests/day, average tokens, credit burn rate
- Set alerts at 80% credit consumption [glbgpt](https://www.glbgpt.com/hub/perplexity-api-cost-2025/)

**4.2 Cost Optimization**
- Start with `sonar` model ($1 per 1K requests) [techcrunch](https://techcrunch.com/2025/01/21/perplexity-launches-sonar-an-api-for-ai-search/)
- Upgrade to `sonar-pro` only if answer quality is insufficient
- Implement stricter cooldowns during peak hours
- Consider prefix commands (e.g., `!ask`) instead of all messages

**4.3 Performance Improvements**
- Add caching for repeated questions (optional)
- Implement conversation context (store last 5 messages)
- Add command to clear user cooldowns (admin only)

### Phase 5: Advanced Features (Optional)

- **Multi-channel support**: Remove TARGET_CHANNEL_ID restriction, use whitelist
- **Citation formatting**: Parse and format Perplexity citations as Discord embeds
- **Usage statistics**: Track queries per user, popular questions
- **Custom sources**: Use Perplexity's source customization API feature [techcrunch](https://techcrunch.com/2025/01/21/perplexity-launches-sonar-an-api-for-ai-search/)

### Security Considerations

- Never commit `.env` files to version control
- Restrict admin commands to specific roles
- Implement message logging for moderation
- Consider adding content filtering for inappropriate queries
- Set up Discord rate limit handling [support-dev.discord](https://support-dev.discord.com/hc/en-us/articles/6223003921559-My-Bot-is-Being-Rate-Limited)

This implementation plan provides a production-ready foundation with proper error handling, rate limiting, and cost controls while maintaining the simplicity of your original design. [docs.perplexity](https://docs.perplexity.ai/getting-started/models/models/sonar)