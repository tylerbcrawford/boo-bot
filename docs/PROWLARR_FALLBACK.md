# Prowlarr Fallback - Discord Bot Integration

**Status:** ✅ Active (Integrated Feb 10, 2026)

## Overview

The Discord bot now automatically falls back to Prowlarr when Readarr can't find book metadata. This is especially useful for very new books that haven't been indexed in GoodReads yet.

## How It Works

```
User: !book Strangers by Belle Burden
  ↓
Bot searches Readarr (GoodReads metadata)
  ↓
Found? → Add to Readarr + trigger search ✅
  ↓
No results? → Automatically try Prowlarr fallback
  ↓
Search Prowlarr indexers for EPUB
  ↓
Found? → Download file + add to Readarr ✅
  ↓
Not found? → Try to add to Readarr anyway
  ↓
If metadata exists → Monitor in Readarr (Anna's Archive will catch it) ✅
If no metadata → Complete failure (try different search) ❌
```

## Three-Tier Fallback System

**Tier 1: Readarr (GoodReads)**
- Metadata-based search
- Triggers Prowlarr indexer search
- Success: Book added, monitored, searched

**Tier 2: Prowlarr (Torrents/Usenet)**
- Direct file search when Tier 1 fails
- Downloads immediately if found
- Success: File downloaded + monitored in Readarr

**Tier 3: Anna's Archive (Automated)**
- Triggered when book monitored but no file
- Runs every 12 hours via cron
- Success: Downloads within 12-18 hours

## Commands

### Standard Commands (with fallback)
- `!book Title by Author` - User 1 ebooks
- `!book2 Title by Author` - User 2 ebooks

### Example Usage

**Scenario 1: Prowlarr finds file**
```
User: !book Strangers by Belle Burden
Bot:  🔍 Searching for: Strangers by Belle Burden
Bot:  ❌ Readarr found no metadata. Trying Prowlarr fallback...
Bot:  ✅ Book downloaded via Prowlarr!
      📚 Belle Burden - Strangers A Memoir of Marriage
      💾 Size: 1.6M
      📥 Source: altHUB (usenet)
      📂 Calibre will auto-import shortly (Added to Readarr for monitoring)
```

**Scenario 2: Prowlarr fails, but metadata exists**
```
User: !book Obscure Book Title by Unknown Author
Bot:  🔍 Searching for: Obscure Book Title by Unknown Author
Bot:  ❌ Readarr found no metadata. Trying Prowlarr fallback...
Bot:  ❌ Prowlarr found no results
Bot:  ✅ Added Obscure Book Title to Readarr for monitoring
      📅 Anna's Archive will try to download within 12 hours
```

**Scenario 3: Complete failure (no metadata anywhere)**
```
User: !book asdfghjkl by qwertyuiop
Bot:  🔍 Searching for: asdfghjkl by qwertyuiop
Bot:  ❌ Readarr found no metadata. Trying Prowlarr fallback...
Bot:  ❌ Complete failure - no results found:
      • Readarr (GoodReads): No metadata
      • Prowlarr (indexers): No files
      • Cannot monitor in Readarr without metadata
      Try a different search term or check the title/author spelling
```

## Technical Details

**Implementation:** `cogs/books.py` lines 33-92

**Fallback Method:** `_prowlarr_fallback_search(title, author)`
- Calls the Prowlarr fallback script (configured via `PROWLARR_FALLBACK_SCRIPT` env var)
- Runs asynchronously with 6-minute timeout
- Parses JSON response from script
- Returns formatted Discord message

**Smart Download Routing:**
- MAM torrents → qbittorrent-mam (no VPN)
- Other torrents → qbittorrent-vpn
- Usenet → NZBGet

**Query Parsing:**
- Supports "Title by Author" format
- Falls back to title-only search if no "by" found
- Script handles author/title extraction from results

## When Fallback Triggers

- Very new books (2026 releases not yet in GoodReads)
- Self-published books
- Books with non-standard metadata
- Foreign language books not in GoodReads

## Testing

Test with a very new book:
```
!book Half His Age by Jennette McCurdy
```

Should trigger Prowlarr fallback if not in GoodReads yet.

## Error Handling

**Readarr fails, Prowlarr succeeds:**
- User gets book via Prowlarr
- Success message with source details

**Both fail:**
- User gets error message from Prowlarr
- Common errors: "No results found", "Download timeout"

**Script errors:**
- Caught and reported to user
- Bot logs error for debugging

## Future Enhancements

Potential improvements:
- [ ] Add Prowlarr fallback to audiobook commands
- [ ] Support manual indexer selection
- [ ] Add quality/size preferences
- [ ] Retry failed downloads automatically
- [ ] Support PDF/MOBI formats

## Notes

- Only EPUB format supported (script limitation)
- 6-minute timeout for downloads
- Downloads placed in `/media/tyler/8TB/media/books/user1/ebooks/`
- Calibre auto-imports on next scan
- Script output logged to Discord for transparency

---

**Script:** Configured via `PROWLARR_FALLBACK_SCRIPT` env var (default: `/opt/scripts/prowlarr-book-fallback.sh`)
**Bot Code:** `cogs/books.py`
