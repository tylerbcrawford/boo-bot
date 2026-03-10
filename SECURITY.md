# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Boo Bot, please report it responsibly.

**Preferred:** Open a [GitHub Security Advisory](https://github.com/tylerbcrawford/boo-bot/security/advisories/new) or create a private issue.

**Please do not** open a public issue for security vulnerabilities.

## What to Report

- Discord token exposure or leakage
- API key exposure (Readarr, Sonarr, Radarr, TMDb, Perplexity)
- Command injection or privilege escalation
- Unauthorized access to bot commands or data
- Dependency vulnerabilities with known exploits

## Credential Handling

Boo Bot handles several API keys and tokens. These are:

- Stored only in the `.env` file (gitignored)
- Loaded via environment variables at startup
- Never logged, echoed, or written to output files
- Never exposed in Discord messages or embeds

If you find a case where a credential is inadvertently exposed, please report it immediately.

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest  | Yes       |
