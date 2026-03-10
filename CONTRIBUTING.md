# Contributing to Boo Bot

Thanks for your interest in contributing! This guide covers everything you need to get started.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/boo-bot.git
   cd boo-bot
   ```
3. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Set up your environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   # Add your DISCORD_TOKEN and API keys to .env
   ```

## Development Workflow

### Running Locally

```bash
source venv/bin/activate
python3 bot.py
```

The bot prints a startup banner listing loaded cogs and connected guilds.

### Project Structure

- **`bot.py`** — Entry point, cog loader, error handling
- **`config.py`** — Configuration from environment variables
- **`cogs/`** — Feature modules (each cog is independent)
- **`utils/`** — Shared API clients and helpers
- **`data/`** — Runtime state files (gitignored)

### Adding a New Cog

1. Create `cogs/your_cog.py` with a class extending `commands.Cog`
2. Add a `setup(bot)` function at the bottom
3. Add the module path to `cog_modules` in `bot.py`
4. Test: `python3 -m py_compile cogs/your_cog.py`

### Code Style

- **Python**: Follow PEP 8. Use type hints for function signatures.
- Use `asyncio.to_thread` for blocking HTTP calls — never block the event loop.
- JSON state files use atomic writes (write to temp, then rename).
- API clients return structured results with success/error/already-exists types.

## Pull Requests

1. **Keep PRs focused** — one feature or fix per PR
2. **Write a clear description** — explain what changed and why
3. **Test your changes** — verify the cog loads and commands work
4. **Update docs** if your change affects commands, configuration, or `.env.example`

### PR Title Format

```
feat: add new feature
fix: resolve specific bug
docs: update documentation
refactor: code restructuring (no behavior change)
```

## Reporting Issues

- **Bug reports**: Include steps to reproduce, expected vs actual behavior, and Python/OS version
- **Feature requests**: Describe the use case and why it would be valuable
- **Questions**: Open an issue with the `question` label

## Architecture Notes

- Each cog is isolated and can be hot-reloaded without restarting the bot
- Cross-cog communication uses `bot.cogs['Name']` (e.g., the rebrander checks the suppressor)
- State is persisted in `data/` as JSON with atomic writes for crash safety
- All API calls go through shared clients in `utils/` with unified error handling

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
