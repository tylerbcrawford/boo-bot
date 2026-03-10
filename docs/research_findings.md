# Discord Bot Readarr Integration - Bug Analysis & Fixes

## Overview
Your Discord bot for managing media requests has a **critical bug in the Readarr API integration** that prevents books from being added successfully. The issue stems from incorrect foreign ID formats and API payload structure.

---

## Critical Bug: Invalid Readarr Foreign IDs

### Current Problem (Lines in `utils/api_clients.py`)

```python
# ❌ WRONG - This is what your code currently does:
foreign_book_id = f"google-{google_id}"
foreign_author_id = f"google-author-{book_data['authors']}"
```

**Why This Fails:**
- Readarr's BookInfo metadata provider uses **GoodReads IDs**, not Google Book IDs
- Invalid foreign IDs like `google-12345` are rejected by Readarr
- The error appears as: `"Book with Foreign Id google-12345 was not found"`
- Readarr cannot link books without valid GoodReads IDs from its metadata database

### Root Cause Analysis

Readarr's metadata sources include:
- **GoodReads** (Primary - uses numeric IDs like `123456`)
- **Google Books** (Alternative - uses alphanumeric IDs)
- **MusicBrainz** (Books extension)

When you provide `google-{id}`, Readarr tries to validate against GoodReads database and fails because:
1. It doesn't recognize the `google-` prefix format
2. The ID doesn't exist in GoodReads
3. Validation rejects the entire book addition request

---

## Solution: Use Readarr API Search Endpoint

### Recommended Fix

Instead of manually constructing foreign IDs from external sources, use Readarr's **native search endpoint** to get validated metadata:

```python
# ✅ CORRECT APPROACH:
# 1. Search Readarr's metadata database directly
# 2. Let Readarr provide the correct foreign IDs
# 3. Use those IDs in the add request

def search_book(self, query: str) -> Dict:
    """Search Readarr's metadata database for books"""
    try:
        response = requests.get(
            f"{self.url}/api/v1/search",
            headers=self.headers,
            params={"term": query, "type": "book"},  # Search for books specifically
            timeout=10
        )
        
        if response.status_code == 200:
            results = response.json()
            # Results contain foreignBookId from Readarr's database
            return {
                'success': True,
                'books': results  # Each book has correct foreignBookId
            }
        return {'success': False, 'error': f'HTTP {response.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

### API Endpoint Details

**Readarr Search Endpoint:**
- **URL:** `GET /api/v1/search?term={query}&type=book`
- **Returns:** List of books with metadata including:
  - `foreignBookId` (GoodReads ID, validated by Readarr)
  - `author` (with foreignAuthorId)
  - `title`, `publisher`, `year`
  - Full metadata for adding

**Example Response:**
```json
[
  {
    "foreignBookId": "95834",
    "title": "The Name of the Wind",
    "author": {
      "foreignAuthorId": "2617048",
      "authorName": "Patrick Rothfuss"
    },
    "year": 2007,
    "publisher": "Tor Books",
    "overview": "..."
  }
]
```

---

## Current Code Issues Breakdown

### Issue 1: Wrong Foreign ID Format
**File:** `utils/api_clients.py`, Line ~35-37

```python
# ❌ Current code:
google_id = book_data.get('googleBooksId', 'unknown')
foreign_book_id = f"google-{google_id}"  # Creates invalid ID
foreign_author_id = f"google-author-{book_data['authors']}"  # Wrong format
```

**Fix:** Use Readarr's search API instead (see above)

### Issue 2: Missing Required Fields for Readarr API
**File:** `utils/api_clients.py`, Line ~39-60

Readarr v0.3+ requires specific fields that your current code may not include:

```python
# ✅ Correct minimal payload for Readarr:
readarr_payload = {
    "foreignBookId": "95834",  # From Readarr search - REQUIRED
    "title": "The Name of the Wind",
    "author": {
        "foreignAuthorId": "2617048",  # From Readarr search - REQUIRED
        "authorName": "Patrick Rothfuss",
        "qualityProfileId": 1,
        "metadataProfileId": 1,
        "rootFolderPath": "/data/books/user1/ebooks",
        "monitored": True
    },
    "editions": [
        {
            "title": "The Name of the Wind",
            "foreignEditionId": "95834-1",  # Edition-specific ID
            "monitored": True,
            "manualAdd": True
        }
    ],
    "monitored": True,
    "addOptions": {
        "searchForNewBook": True
    }
}
```

### Issue 3: Book Search Falls Back to OpenLibrary
**File:** `cogs/books.py`, Line ~40-50

Your code tries Google Books first, then OpenLibrary. But these sources don't provide Readarr-compatible IDs:

```python
# ❌ Current approach:
books = search_google_books(query)
if not books:
    books = search_openlibrary(title, author)  # Both provide wrong IDs

# ✅ Better approach:
# Use Readarr search directly as primary source
books = self.readarr.search_book(query)
if not books:
    # Optionally fall back to manual search + user confirmation
    books = search_google_books(query)
```

---

## Implementation Steps

### Phase 1: Add Readarr Search Method

**File: `utils/api_clients.py`**

Add this method to `ReadarrClient` class:

```python
def search_book(self, query: str) -> Dict:
    """Search Readarr's metadata database
    
    Args:
        query: Book title, author, or ISBN to search
        
    Returns:
        Dict with 'success' and 'books' (or 'error')
    """
    try:
        response = requests.get(
            f"{self.url}/api/v1/search",
            headers=self.headers,
            params={"term": query, "type": "book"},
            timeout=10
        )
        
        if response.status_code == 200:
            books = response.json()
            return {
                'success': True,
                'books': books,
                'count': len(books)
            }
        elif response.status_code == 404:
            return {'success': True, 'books': [], 'count': 0}
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text}'
            }
    except requests.Timeout:
        return {'success': False, 'error': 'Request timeout - Readarr unresponsive'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

### Phase 2: Update `add_book` Method

**File: `utils/api_clients.py`**

Replace current `add_book()` with:

```python
def add_book(self, book_data: Dict, root_folder: str, quality_profile_id: int,
             metadata_profile_id: int, monitored: bool = True) -> Dict:
    """Add book to Readarr using validated metadata
    
    Args:
        book_data: Book info from search_book() response
                   Must contain foreignBookId and author.foreignAuthorId
        root_folder: Root folder path for storing books
        quality_profile_id: Quality profile ID
        metadata_profile_id: Metadata profile ID
        
    Returns:
        Dict with 'success' and 'data' (or 'error')
    """
    # Validate required fields from Readarr search
    if 'foreignBookId' not in book_data:
        return {'success': False, 'error': 'Missing foreignBookId - use search_book() first'}
    
    if 'author' not in book_data or 'foreignAuthorId' not in book_data.get('author', {}):
        return {'success': False, 'error': 'Missing author foreignAuthorId'}
    
    # Build payload with validated IDs from Readarr
    payload = {
        "monitored": monitored,
        "foreignBookId": book_data['foreignBookId'],
        "title": book_data.get('title', ''),
        "editions": [
            {
                "title": book_data.get('title', ''),
                "foreignEditionId": f"{book_data['foreignBookId']}-1",
                "monitored": monitored,
                "manualAdd": True
            }
        ],
        "author": {
            "authorName": book_data['author'].get('authorName', ''),
            "foreignAuthorId": book_data['author']['foreignAuthorId'],
            "qualityProfileId": quality_profile_id,
            "metadataProfileId": metadata_profile_id,
            "rootFolderPath": root_folder,
            "monitored": monitored,
            "addOptions": {
                "searchForNewBook": True
            }
        },
        "addOptions": {
            "searchForNewBook": True
        }
    }
    
    # Add optional fields if available
    if 'overview' in book_data:
        payload['overview'] = book_data['overview']
    if 'year' in book_data:
        payload['releaseDate'] = f"{book_data['year']}-01-01"
    if 'images' in book_data:
        payload['images'] = book_data['images']
    
    try:
        response = requests.post(
            f"{self.url}/api/v1/book",
            json=payload,
            headers=self.headers,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            return {'success': True, 'data': response.json()}
        else:
            error_msg = response.text
            try:
                error_data = response.json()
                if isinstance(error_data, list):
                    error_msg = error_data.get('errorMessage', error_msg)
                elif 'message' in error_data:
                    error_msg = error_data['message']
            except:
                pass
            return {'success': False, 'error': f'HTTP {response.status_code}: {error_msg}'}
    
    except requests.Timeout:
        return {'success': False, 'error': 'Request timeout'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

### Phase 3: Update Book Command in Cog

**File: `cogs/books.py`**

Update the `book()` command to use new search method:

```python
@commands.command(name='book', help='Add a book to Readarr')
async def book(self, ctx, *, query: str):
    if not self._is_requests_channel(ctx):
        await ctx.send(f"❌ Use this command in #{config.REQUESTS_CHANNEL_NAME}")
        return
    
    await ctx.send(f"🔍 Searching for: **{query}**")
    
    # Use Readarr search endpoint (primary source)
    search_result = self.readarr.search_book(query)
    
    if not search_result['success']:
        await ctx.send(f"❌ Search failed: {search_result['error']}")
        return
    
    books = search_result.get('books', [])
    
    if not books:
        await ctx.send(f"❌ No books found for: **{query}**")
        return
    
    # Single result - add directly
    if len(books) == 1:
        book = books[0]
        await ctx.send(f"📚 Found: **{book['title']}** by {book['author']['authorName']}")
        
        add_result = self.readarr.add_book(
            book,
            config.READARR_ROOT_FOLDER,
            config.READARR_QUALITY_PROFILE_ID,
            config.READARR_METADATA_PROFILE_ID
        )
        
        if add_result['success']:
            await ctx.send("✅ Successfully added to Readarr!")
        else:
            await ctx.send(f"❌ Failed: {add_result['error']}")
    
    # Multiple results - show choices
    else:
        embed = discord.Embed(
            title="📚 Multiple results found",
            description="React to select the book:",
            color=discord.Color.blue()
        )
        
        for idx, book in enumerate(books[:5], 1):
            embed.add_field(
                name=f"{idx}. {book['title']}",
                value=f"by {book['author']['authorName']} ({book.get('year', '?')})",
                inline=False
            )
        
        message = await ctx.send(embed=embed)
        
        reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
        for i in range(min(len(books), 5)):
            await message.add_reaction(reactions[i])
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in reactions[:len(books)]
        
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
            selected_idx = reactions.index(str(reaction.emoji))
            selected_book = books[selected_idx]
            
            await ctx.send(f"Adding: **{selected_book['title']}**")
            
            add_result = self.readarr.add_book(
                selected_book,
                config.READARR_ROOT_FOLDER,
                config.READARR_QUALITY_PROFILE_ID,
                config.READARR_METADATA_PROFILE_ID
            )
            
            if add_result['success']:
                await ctx.send("✅ Successfully added to Readarr!")
            else:
                await ctx.send(f"❌ Failed: {add_result['error']}")
        
        except TimeoutError:
            await ctx.send("⏱️ Selection timed out")
```

---

## Readarr API Reference

### Search Endpoint
```
GET /api/v1/search
Query Parameters:
  - term (required): Book title, author, or ISBN
  - type: "book" (filter results to books only)

Response: Array of books with metadata
```

### Add Book Endpoint
```
POST /api/v1/book
Body: Book payload with foreignBookId and author.foreignAuthorId
Headers: X-Api-Key: {api_key}

Response: Created book object or error
```

### Key Field Requirements
- **foreignBookId**: GoodReads ID (from search results)
- **author.foreignAuthorId**: GoodReads author ID
- **author.qualityProfileId**: Valid profile ID
- **author.metadataProfileId**: Valid profile ID
- **author.rootFolderPath**: Valid directory path

---

## Testing Your Fix

### Test 1: Verify Search Works
```bash
curl -H "X-Api-Key: YOUR_API_KEY" \
  "http://localhost:8787/api/v1/search?term=The%20Name%20of%20the%20Wind&type=book"
```

### Test 2: Check Command
In Discord #requests channel:
```
!book The Name of the Wind
```

Should show valid search results with author names and years.

### Test 3: Verify Book Added
After adding, check Readarr UI:
1. Books → Library
2. Search for the book by title
3. Status should be "Wanted"

---

## Python Error Handling Best Practices

### Current Issues:
1. No timeout handling for slow Readarr responses
2. No retry logic for transient failures
3. Bare `except Exception` catches too much

### Improvements to Add:

```python
import asyncio
from requests.exceptions import Timeout, ConnectionError, RequestException

class ReadarrClient:
    def __init__(self, url: str, api_key: str, timeout: int = 10):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.headers = {'X-Api-Key': api_key}
        self.timeout = timeout
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Unified request handler with error handling"""
        url = f"{self.url}/api/v1/{endpoint}"
        
        # Merge defaults with provided kwargs
        request_kwargs = {
            'headers': self.headers,
            'timeout': self.timeout,
            **kwargs
        }
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, **request_kwargs)
            elif method.upper() == 'POST':
                response = requests.post(url, **request_kwargs)
            elif method.upper() == 'PUT':
                response = requests.put(url, **request_kwargs)
            else:
                return {'success': False, 'error': f'Unknown method: {method}'}
            
            response.raise_for_status()  # Raise for 4xx/5xx
            return {'success': True, 'data': response.json() if response.text else {}}
        
        except Timeout:
            return {'success': False, 'error': 'Request timeout - Readarr is unresponsive'}
        except ConnectionError:
            return {'success': False, 'error': f'Connection error - Cannot reach {self.url}'}
        except requests.HTTPError as e:
            error_msg = str(e)
            try:
                error_data = e.response.json()
                if isinstance(error_data, list) and error_data:
                    error_msg = error_data.get('errorMessage', error_msg)
            except:
                pass
            return {'success': False, 'error': f'HTTP error: {error_msg}'}
        except Exception as e:
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}
```

---

## Summary of Bugs & Fixes

| Bug | Location | Current | Fix |
|-----|----------|---------|-----|
| Invalid foreign IDs | `api_clients.py:36-37` | `google-{id}` format | Use Readarr's search API |
| Wrong metadata source | `books.py:40-50` | Google Books + OpenLibrary | Use Readarr's native search |
| Missing error handling | `api_clients.py:60+` | Generic error messages | Specific exception types |
| No timeout handling | `api_clients.py` | Default timeout | Explicit timeout + retry logic |
| Invalid payload structure | `api_clients.py:39-60` | Manual ID construction | Use search results directly |

---

## Next Steps

1. **Implement Phase 1**: Add `search_book()` method to `ReadarrClient`
2. **Implement Phase 2**: Replace `add_book()` with validated version
3. **Implement Phase 3**: Update book command to use new methods
4. **Test locally**: Run bot and test `!book` command
5. **Deploy**: Push to Docker and verify in Discord
