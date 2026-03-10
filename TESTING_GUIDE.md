# Discord Bot - Manual Testing Guide

This guide provides comprehensive test cases for all book-related commands in the Discord bot.

## Prerequisites

- Bot must be running and connected to Discord
- You must be in the `#requests` channel (commands only work there)
- All 4 Readarr instances must be accessible

## Test Environment Status

✅ All 4 Readarr instances are connected and working:
- `readarr` (eBooks 1) - Port 8787
- `readarr-audio` (Audiobooks 1) - Port 8788
- `readarr2` (eBooks 2) - Port 8789
- `readarr-audio2` (Audiobooks 2) - Port 8790

## Command Overview

| Command | Instance | Type | Description |
|---------|----------|------|-------------|
| `!book` | readarr | eBook | Add book to first eBooks instance |
| `!audiobook` | readarr-audio | Audiobook | Add audiobook to first audiobooks instance |
| `!book2` | readarr2 | eBook | Add book to second eBooks instance |
| `!audiobook2` | readarr-audio2 | Audiobook | Add audiobook to second audiobooks instance |
| `!searchbook` | N/A | Search only | Search without adding |
| `!readarr` | readarr | Status | Test connection |

---

## Test Cases

### Test 1: Standard Format (Title by Author)

This is the recommended format for all commands.

#### !book

```
!book The Name of the Wind by Patrick Rothfuss
!book 1984 by George Orwell
!book The Hobbit by J.R.R. Tolkien
```

**Expected behavior:**
- Bot searches Google Books
- If single result: Adds directly to Readarr (eBooks 1)
- If multiple results: Shows numbered list with reactions
- Success message confirms addition

#### !audiobook

```
!audiobook Project Hail Mary by Andy Weir
!audiobook The Midnight Library by Matt Haig
```

**Expected behavior:**
- Bot searches Google Books
- Adds to Readarr-Audio (Audiobooks 1)
- Same interactive selection as !book

#### !book2

```
!book2 Dune by Frank Herbert
!book2 Foundation by Isaac Asimov
```

**Expected behavior:**
- Bot searches Google Books
- Adds to Readarr2 (eBooks 2)
- Confirms "Successfully added to Readarr2!"

#### !audiobook2

```
!audiobook2 Sapiens by Yuval Noah Harari
!audiobook2 Educated by Tara Westover
```

**Expected behavior:**
- Bot searches Google Books
- Adds to Readarr-Audio2 (Audiobooks 2)
- Confirms "Successfully added to Readarr-Audio2!"

---

### Test 2: Title Only (No Author)

Commands should still work without the "by Author" part.

```
!book The Martian
!audiobook Harry Potter
!book2 Twilight
!audiobook2 The Hunger Games
```

**Expected behavior:**
- Bot searches using title only
- May return more results (less specific)
- Interactive selection still works

---

### Test 3: Multiple Word Titles

```
!book The Lord of the Rings by J.R.R. Tolkien
!audiobook The Hitchhiker's Guide to the Galaxy by Douglas Adams
!book2 A Song of Ice and Fire by George R.R. Martin
!audiobook2 The Way of Kings by Brandon Sanderson
```

**Expected behavior:**
- Handles long titles correctly
- Parses "by" separator properly

---

### Test 4: Special Characters

```
!book IT by Stephen King
!audiobook Alice's Adventures in Wonderland by Lewis Carroll
!book2 Ender's Game by Orson Scott Card
```

**Expected behavior:**
- Handles apostrophes correctly
- Searches work with special characters

---

### Test 5: Interactive Selection (Multiple Results)

Use ambiguous queries to trigger multiple results:

```
!book Foundation
!audiobook The Stand
```

**Expected behavior:**
- Shows embed with 1-5 numbered results
- Adds reactions (1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣)
- Waits 60 seconds for user reaction
- Adds selected book
- Timeout after 60 seconds shows "Selection timed out"

---

### Test 6: No Results Found

Use non-existent or very obscure titles:

```
!book asdfasdfasdf by nonexistent
!audiobook zzzzzzzzzz
```

**Expected behavior:**
- First tries Google Books
- Then tries OpenLibrary
- Shows "Could not find any books matching: ..."

---

### Test 7: Search Command (No Adding)

```
!searchbook The Great Gatsby
!searchbook Moby Dick by Herman Melville
```

**Expected behavior:**
- Shows search results in embed
- Does NOT add to any Readarr instance
- Shows: Title, Author, Year, ISBN

---

### Test 8: Connection Status

```
!readarr
```

**Expected behavior:**
- Tests connection to first Readarr instance
- Shows "Connected to Readarr {version}"
- OR shows connection error

---

### Test 9: Channel Restriction

Try commands outside of `#requests` channel:

```
# In #general or any other channel:
!book Test Book
```

**Expected behavior:**
- Bot responds: "❌ This command can only be used in the #requests channel."

---

### Test 10: Error Handling

#### Already Added Book

```
!book The Name of the Wind by Patrick Rothfuss
# Wait for it to add
# Try again:
!book The Name of the Wind by Patrick Rothfuss
```

**Expected behavior:**
- May show "already in library" error from Readarr
- Or adds again (depending on Readarr settings)

#### API Connection Failure

If Readarr is down or unreachable:

```
!book Any Book Title
```

**Expected behavior:**
- Shows "Failed to add to Readarr: {error}"
- Error message includes connection details

---

## Test Verification Checklist

After testing each command, verify:

- [ ] Bot responds promptly (< 5 seconds for search)
- [ ] Search results are relevant
- [ ] Interactive selection works (reactions appear)
- [ ] Book is added to correct Readarr instance
- [ ] Success/error messages are clear
- [ ] Timeout behavior works correctly
- [ ] Channel restriction is enforced
- [ ] Multiple users can use commands simultaneously

---

## Readarr Instance Verification

After adding books, verify they appear in the correct Readarr instance:

1. **Readarr (eBooks 1)**: http://localhost:8787
   - Check for books added with `!book`

2. **Readarr-Audio (Audiobooks 1)**: http://localhost:8788
   - Check for books added with `!audiobook`

3. **Readarr2 (eBooks 2)**: http://localhost:8789
   - Check for books added with `!book2`

4. **Readarr-Audio2 (Audiobooks 2)**: http://localhost:8790
   - Check for books added with `!audiobook2`

---

## Automated API Connection Test

Run this script to verify all Readarr instances are accessible:

```bash
source venv/bin/activate
python test_readarr_connections.py
```

**Expected output:**
```
✅ PASS - readarr
✅ PASS - readarr-audio
✅ PASS - readarr2
✅ PASS - readarr-audio2

Total: 4 | Passed: 4 | Failed: 0
```

---

## Common Issues & Solutions

### Issue: "Command not found"
**Solution:** Check bot is running with `docker ps | grep discord-bot`

### Issue: "Channel restriction error"
**Solution:** Ensure you're in the #requests channel

### Issue: "API connection failed"
**Solution:**
1. Check Readarr instance is running: `docker ps | grep readarr`
2. Verify API key is correct in `.env`
3. Run connection test script

### Issue: "No search results"
**Solution:**
- Try different spelling
- Include author name
- Check Google Books API is accessible

### Issue: Interactive selection timeout
**Solution:**
- React within 60 seconds
- Click on the number emoji corresponding to your choice

---

## Advanced Testing

### Concurrent Users

Have multiple users run commands simultaneously:
```
User 1: !book Book A
User 2: !book2 Book B
User 3: !audiobook Book C
```

**Expected:** All commands should work independently

### Rate Limiting

Send commands rapidly:
```
!book Book1
!book Book2
!book Book3
```

**Expected:** All should be processed, may queue

### Long Running Operations

Use books that trigger fallback to OpenLibrary (obscure titles):
```
!book very obscure title that doesnt exist
```

**Expected:** Tries Google Books → Falls back to OpenLibrary → Shows no results

---

## Test Results Template

Use this to track your testing:

```
Date: _______________
Tester: _______________

Test Results:
[ ] Test 1: Standard Format - PASS/FAIL
[ ] Test 2: Title Only - PASS/FAIL
[ ] Test 3: Multiple Word Titles - PASS/FAIL
[ ] Test 4: Special Characters - PASS/FAIL
[ ] Test 5: Interactive Selection - PASS/FAIL
[ ] Test 6: No Results - PASS/FAIL
[ ] Test 7: Search Command - PASS/FAIL
[ ] Test 8: Connection Status - PASS/FAIL
[ ] Test 9: Channel Restriction - PASS/FAIL
[ ] Test 10: Error Handling - PASS/FAIL

Notes:
_________________________________
_________________________________
```

---

## Summary

All commands have been implemented and tested for syntax/API connectivity. Manual Discord testing is required to verify end-to-end functionality with real user interactions.

**Status: Ready for Discord Testing** ✅
