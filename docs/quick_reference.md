# Quick Reference - Readarr API & Python Best Practices

## The Core Problem (In 30 Seconds)

Your bot creates invalid book IDs: `google-12345`
Readarr expects: `95834` (GoodReads format from its database)
**Result:** Books fail to add with validation errors

## The Core Solution (In 30 Seconds)

```python
# ❌ OLD WAY (BROKEN)
foreign_book_id = f"google-{google_id}"  # Creates google-95834, invalid!

# ✅ NEW WAY (WORKS)
search_result = readarr.search_book("The Name of the Wind")
# Returns: {..., 'foreignBookId': '95834', ...}
# Now foreignBookId is already correct from Readarr's database
```

---

## Readarr API Endpoints You Need

### Search for Books
```
GET /api/v1/search?term={query}&type=book
Headers: X-Api-Key: {api_key}

Response:
[
  {
    "foreignBookId": "95834",           # ← USE THIS (not custom-formatted)
    "title": "The Name of the Wind",
    "author": {
      "foreignAuthorId": "1234567",     # ← USE THIS TOO
      "authorName": "Patrick Rothfuss"
    },
    "year": 2007,
    "overview": "...",
    "images": [...]
  }
]
```

### Add a Book
```
POST /api/v1/book
Headers: X-Api-Key: {api_key}
Body:
{
  "foreignBookId": "95834",             # ← From search results
  "title": "The Name of the Wind",
  "author": {
    "foreignAuthorId": "1234567",       # ← From search results
    "authorName": "Patrick Rothfuss",
    "qualityProfileId": 1,
    "metadataProfileId": 1,
    "rootFolderPath": "/data/books/user1/ebooks"
  },
  "editions": [{
    "title": "The Name of the Wind",
    "foreignEditionId": "95834-1",      # ← Derived from book ID
    "monitored": true,
    "manualAdd": true
  }],
  "addOptions": { "searchForNewBook": true }
}

Response:
{
  "id": 1,
  "foreignBookId": "95834",
  "title": "The Name of the Wind",
  ...
}
```

---

## Python HTTP Error Handling Pattern

### Bad (What You Might Have)
```python
try:
    response = requests.get(url)
    return response.json()
except Exception as e:
    print(f"Error: {e}")
```
❌ Catches too much, hides real issues

### Good
```python
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()  # Raise 4xx/5xx as exceptions
    return response.json()

except requests.Timeout:
    return {'success': False, 'error': 'Request timeout'}

except requests.ConnectionError:
    return {'success': False, 'error': 'Cannot connect to server'}

except requests.HTTPError as e:
    # Parse error details from response
    try:
        error_data = e.response.json()
        error_msg = error_data.get('message', str(e))
    except:
        error_msg = str(e)
    return {'success': False, 'error': error_msg}

except Exception as e:
    return {'success': False, 'error': f'Unexpected: {str(e)}'}
```
✅ Handles specific cases, clear error messages

---

## Discord.py Async/Await Pattern

### Waiting for User Interaction
```python
def check(reaction, user):
    """Callback to validate reaction"""
    return (
        user == ctx.author and  # Only author can react
        str(reaction.emoji) in ['1️⃣', '2️⃣', '3️⃣']  # Valid reactions
    )

try:
    # Wait for reaction with 60-second timeout
    reaction, user = await self.bot.wait_for(
        'reaction_add',
        timeout=60.0,
        check=check
    )
    # User reacted - continue processing
    selected_idx = ['1️⃣', '2️⃣', '3️⃣'].index(str(reaction.emoji))
    
except asyncio.TimeoutError:
    # No reaction within 60 seconds
    await ctx.send("⏱️ Timed out")
```

---

## Common Readarr API Field Reference

| Field | Type | Required | Example | Notes |
|-------|------|----------|---------|-------|
| foreignBookId | string | YES | "95834" | GoodReads ID from search |
| title | string | YES | "The Name of the Wind" | Book title |
| author.foreignAuthorId | string | YES | "1234567" | GoodReads author ID from search |
| author.authorName | string | YES | "Patrick Rothfuss" | Author name |
| author.qualityProfileId | int | YES | 1 | Get from `/api/v1/qualityprofile` |
| author.metadataProfileId | int | YES | 1 | Get from `/api/v1/metadataprofile` |
| author.rootFolderPath | string | YES | "/data/books/user1/ebooks" | Get from `/api/v1/rootfolder` |
| editions[].foreignEditionId | string | YES | "95834-1" | Derived from book ID |
| editions[].monitored | bool | YES | true | Monitor this edition |
| addOptions.searchForNewBook | bool | NO | true | Search for the book after adding |

---

## Testing Readarr API Directly

### Test Connection
```bash
curl -H "X-Api-Key: YOUR_API_KEY" \
  "http://localhost:8787/api/v1/system/status"

# Response (success):
# {"version":"0.3.14.123","appName":"Readarr",...}
```

### Test Search
```bash
curl -H "X-Api-Key: YOUR_API_KEY" \
  "http://localhost:8787/api/v1/search?term=Dune&type=book"

# Response (success):
# [{"foreignBookId":"1","title":"Dune",...}]
```

### Test Add (will actually add the book!)
```bash
curl -X POST -H "X-Api-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "foreignBookId": "95834",
    "title": "The Name of the Wind",
    "author": {
      "foreignAuthorId": "1234567",
      "authorName": "Patrick Rothfuss",
      "qualityProfileId": 1,
      "metadataProfileId": 1,
      "rootFolderPath": "/data/books/user1/ebooks"
    },
    "editions": [{
      "foreignEditionId": "95834-1",
      "title": "The Name of the Wind",
      "monitored": true,
      "manualAdd": true
    }],
    "addOptions": {"searchForNewBook": true}
  }' \
  "http://localhost:8787/api/v1/book"
```

---

## Code Structure: Before vs After

### Before (Broken)
```
Google Books API
      ↓
Custom ID: google-95834  ← INVALID
      ↓
POST to Readarr
      ↓
❌ Validation fails: "Unknown foreign ID"
```

### After (Fixed)
```
Search Readarr API
      ↓
Get valid ID: foreignBookId = "95834"  ← VALIDATED
      ↓
POST to Readarr with correct ID
      ↓
✅ Book added successfully
```

---

## Files to Modify

1. **`utils/api_clients.py`** - Add `search_book()` method, fix `add_book()` method
2. **`cogs/books.py`** - Update `book()` command to use search endpoint
3. **`cogs/books.py`** - Update `audiobook()` command similarly

---

## Method Signatures

### New Method to Add
```python
def search_book(self, query: str) -> Dict:
    """Returns: {'success': bool, 'books': [...], 'error': str}"""
```

### Updated Method
```python
def add_book(self, book_data: Dict, root_folder: str, 
             quality_profile_id: int, metadata_profile_id: int,
             monitored: bool = True) -> Dict:
    """Returns: {'success': bool, 'data': dict, 'error': str}"""
```

---

## Debugging Tips

### Check What Readarr Returns
```python
import json
search_result = readarr.search_book("Dune")
print(json.dumps(search_result, indent=2))

# Look for:
# - foreignBookId (should be numeric)
# - author.foreignAuthorId (should be numeric)
# - NO "google-" prefix
```

### Check Readarr Logs
```bash
# Docker
docker logs 800801-discord-bot | grep -i "readarr\|book\|error"

# Or in Readarr UI: System → Logs
```

### Simulate API Call
```python
import requests

url = "http://localhost:8787/api/v1/search"
params = {"term": "Dune", "type": "book"}
headers = {"X-Api-Key": "your_key"}

response = requests.get(url, params=params, headers=headers, timeout=10)
print(f"Status: {response.status_code}")
print(f"Result: {response.json()}")
```

---

## Performance Tips

1. **Add timeout to all requests**: `timeout=10`
2. **Use appropriate HTTP methods**: GET for queries, POST for adds
3. **Batch operations**: Don't make 100 API calls in a loop
4. **Cache search results**: Don't search for same book twice
5. **Use Discord embeds**: Don't spam raw text

---

## Security Notes

- **Never log API keys**: `api_key = "abc123"  # ← DON'T PUT IN LOGS`
- **Use .env files**: Store secrets in environment variables only
- **Validate user input**: Check query is reasonable length before searching
- **Handle errors gracefully**: Don't expose stack traces to users

---

## Summary Checklist

- [ ] Understand: Google IDs ≠ GoodReads IDs
- [ ] Learn: Use Readarr's `/api/v1/search` endpoint
- [ ] Code: Add `search_book()` method
- [ ] Code: Fix `add_book()` to use search results
- [ ] Code: Update bot commands to use search
- [ ] Test: Verify search returns valid IDs
- [ ] Test: Verify book addition works
- [ ] Deploy: Push to production
- [ ] Monitor: Watch logs for any errors

---

## Still Stuck?

Check these in order:
1. Is your Readarr instance running? `docker ps | grep readarr`
2. Is your API key correct? `echo $READARR_API_KEY`
3. Can you curl the search endpoint manually? (see testing section)
4. Do the search results include `foreignBookId`?
5. Are you using the ID exactly as returned?

If still issues: Enable debug logging and check bot logs for exact error message from Readarr.
