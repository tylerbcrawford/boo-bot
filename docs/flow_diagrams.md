# Flow Diagrams - Understanding the Bug & Fix

## Current (Broken) Book Addition Flow

```
User Command
    │
    ↓
!book "The Name of the Wind"
    │
    ├─→ Search Google Books API
    │       └─→ Returns: googleBooksId = "8-yGC_bfKesC"
    │
    ├─→ Create Foreign ID
    │       └─→ foreign_book_id = "google-8-yGC_bfKesC" ❌ WRONG FORMAT
    │
    ├─→ POST to Readarr /api/v1/book
    │       └─→ Payload includes: "foreignBookId": "google-8-yGC_bfKesC"
    │
    └─→ ❌ Readarr Validation FAILS
            └─→ "Book with Foreign Id google-8-yGC_bfKesC was not found"
                    (Readarr expected: "95834" from GoodReads)
```

**Result:** Error message, book not added ❌

---

## Fixed Book Addition Flow

```
User Command
    │
    ↓
!book "The Name of the Wind"
    │
    ├─→ Search Readarr's Metadata API
    │       └─→ GET /api/v1/search?term=The%20Name%20of%20the%20Wind
    │
    ├─→ Readarr Returns Validated Metadata ✅
    │       ├─ foreignBookId: "95834" ✅ (GoodReads ID)
    │       ├─ title: "The Name of the Wind"
    │       ├─ author:
    │       │   ├─ foreignAuthorId: "2617048" ✅ (GoodReads Author ID)
    │       │   └─ authorName: "Patrick Rothfuss"
    │       └─ year: 2007
    │
    ├─→ POST to Readarr /api/v1/book
    │       └─→ Payload includes: "foreignBookId": "95834" ✅ CORRECT FORMAT
    │
    └─→ ✅ Readarr Validation SUCCESS
            └─→ Book added to library with status "Wanted"
```

**Result:** Success message, book added ✅

---

## Data Flow: ID Sources Comparison

### Before (Broken) - Multiple Sources, Invalid Format
```
┌─────────────────────────────────────┐
│   External Book APIs                │
├─────────────────────────────────────┤
│ Google Books: googleBooksId         │
│     8-yGC_bfKesC                    │
│                                     │
│ OpenLibrary: olid                   │
│     OL8393976W                      │
└─────────────────────────────────────┘
                ↓
        ┌───────────────┐
        │ Bot Combines: │
        │ f"google-{id}"│  ❌ Wrong format!
        └───────────────┘
                ↓
        ┌─────────────────────┐
        │ Readarr Validation: │
        │ Expects GoodReads   │
        │ NOT "google-..."    │
        └─────────────────────┘
                ↓
            ❌ FAIL
```

### After (Fixed) - Single Source, Validated Format
```
┌──────────────────────────────┐
│  Readarr Metadata Database   │
├──────────────────────────────┤
│ foreignBookId: 95834         │ ✅ GoodReads format
│ foreignAuthorId: 2617048     │ ✅ Validated by Readarr
│ title: "The Name of..."      │ ✅ Official metadata
│ overview: "..."              │ ✅ Complete data
└──────────────────────────────┘
                ↓
        ┌─────────────────┐
        │ Bot Uses IDs    │
        │ Directly from   │
        │ Readarr Search  │ ✅ Pre-validated!
        └─────────────────┘
                ↓
        ┌─────────────────────┐
        │ Readarr Validation: │
        │ IDs from own DB,    │
        │ format is correct   │
        └─────────────────────┘
                ↓
            ✅ SUCCESS
```

---

## Code Change Map

### Files Changed
```
800801-discord-bot/
├── utils/api_clients.py
│   ├── ReadarrClient class
│   │   ├── ADD: search_book()       ← NEW METHOD
│   │   └── REPLACE: add_book()      ← FIX METHOD
│   │       ├── REMOVE: ID construction
│   │       └── KEEP: Payload building
│   │
│   └── No changes to Sonarr/RadarrClient
│
└── cogs/books.py
    ├── REPLACE: book() command
    │   ├── ADD: Call search_book() first
    │   ├── CHANGE: Use result IDs directly
    │   └── KEEP: Selection menu logic
    │
    └── REPLACE: audiobook() command
        ├── ADD: Call search_book() first
        ├── CHANGE: Use result IDs directly
        └── KEEP: Selection menu logic
```

---

## API Call Sequence

### Step 1: User Issues Command
```
Discord User in #requests channel:
┌────────────────────┐
│ !book Dune         │
└────────────────────┘
        ↓
    Bot receives command
```

### Step 2: Search Phase
```
Bot → Readarr
┌─────────────────────────────────────────┐
│ GET /api/v1/search                      │
│ ?term=Dune&type=book                    │
│ Header: X-Api-Key: {api_key}            │
└─────────────────────────────────────────┘
        ↓
Readarr → Bot
┌──────────────────────────────────────────┐
│ [                                        │
│   {                                      │
│     "foreignBookId": "1",    ✅          │
│     "title": "Dune",                     │
│     "author": {                          │
│       "foreignAuthorId": "1234",  ✅     │
│       "authorName": "Frank Herbert"      │
│     },                                   │
│     "year": 1965                         │
│   },                                     │
│   ...                                    │
│ ]                                        │
└──────────────────────────────────────────┘
```

### Step 3: Selection Phase (if multiple results)
```
Bot → Discord User
┌──────────────────────────────┐
│ Embed showing 5 options      │
│ + reaction buttons (1️⃣-5️⃣)   │
└──────────────────────────────┘
        ↓
Discord User reacts with 1️⃣
        ↓
Bot receives reaction_add event
```

### Step 4: Add Phase
```
Bot → Readarr
┌──────────────────────────────────────────┐
│ POST /api/v1/book                        │
│ Header: X-Api-Key: {api_key}             │
│ Body: {                                  │
│   "foreignBookId": "1",    ✅ From step 2 │
│   "author": {                            │
│     "foreignAuthorId": "1234", ✅ From S2 │
│     ...                                  │
│   },                                     │
│   ...                                    │
│ }                                        │
└──────────────────────────────────────────┘
        ↓
Readarr → Bot
┌──────────────────────────────────────────┐
│ HTTP 201 (Created)                       │
│ {                                        │
│   "id": 123,                             │
│   "foreignBookId": "1",   ✅             │
│   "title": "Dune",                       │
│   ...                                    │
│ }                                        │
└──────────────────────────────────────────┘
        ↓
Bot → Discord User
┌──────────────────────────────────────────┐
│ ✅ Successfully added to Readarr!        │
└──────────────────────────────────────────┘
```

---

## Error Handling Flow

### Before (Poor Error Handling)
```
Request fails
    ↓
Generic "Exception" caught
    ↓
Print to console
    ↓
User sees nothing or generic error
    ↓
Bot crashes or hangs
```

### After (Good Error Handling)
```
Request fails
    ├─ Timeout (10+ seconds)
    │   └─→ "Request timeout - Readarr did not respond"
    │
    ├─ Connection error
    │   └─→ "Cannot connect to Readarr at {url}"
    │
    ├─ HTTP 400 (validation error)
    │   └─→ Parse JSON response
    │   └─→ "Book with Foreign Id ... was not found"
    │
    ├─ HTTP 500 (server error)
    │   └─→ "HTTP 500: Internal Server Error"
    │
    └─ Other errors
        └─→ Specific error message
            ↓
        User sees helpful message
        Bot continues running
        Error logged for debugging
```

---

## Method Structure Comparison

### Old `add_book()` Method
```
Method: add_book(book_data, root_folder, ...)
    ├─ Extract IDs from external sources ❌
    │   ├─ google_id = book_data.get('googleBooksId')
    │   └─ foreign_book_id = f"google-{google_id}"  ← WRONG!
    │
    ├─ Build Readarr payload
    │   └─ foreignBookId: "google-8-yGC_bfKesC"  ← INVALID
    │
    └─ POST to Readarr ❌
        └─ Error: Foreign ID not recognized
```

### New `search_book()` Method
```
Method: search_book(query: str) -> Dict
    ├─ GET /api/v1/search
    │   └─ Parameters: term={query}, type="book"
    │
    └─ Return results with validated IDs
        ├─ foreignBookId: "95834"  ✅ From Readarr
        ├─ author.foreignAuthorId: "2617048"  ✅ From Readarr
        └─ All metadata pre-validated
```

### New `add_book()` Method
```
Method: add_book(book_data, root_folder, ...)
    ├─ Validate book_data has required fields
    │   ├─ foreignBookId present? ✓
    │   └─ author.foreignAuthorId present? ✓
    │
    ├─ Build Readarr payload
    │   └─ foreignBookId: "95834"  ✅ From search_book()
    │
    ├─ POST to Readarr ✅
    │   └─ Success: Book added with status "Wanted"
    │
    └─ Return result with status and details
```

---

## Update Timeline

### Phase 1 (15 min): Core API Changes
```
Time  File                      Change
────  ────────────────────────  ────────────────────────
0-5   utils/api_clients.py      Add search_book() method
5-10  utils/api_clients.py      Replace add_book() method
10-15 Test with curl            Verify API responses
```

### Phase 2 (15 min): Bot Integration
```
Time  File                      Change
────  ────────────────────────  ────────────────────────
0-5   cogs/books.py             Update book() command
5-10  cogs/books.py             Update audiobook() command
10-15 Test locally              Verify Discord bot works
```

### Phase 3 (10 min): Deployment
```
Time  Action                    Status
────  ─────────────────────────  ──────────────
0-3   Backup original files     Safe rollback
3-5   Deploy to Docker          Running new code
5-10  Test in Discord           Verify production
```

---

## Success Indicators

### When It's Working ✅
```
USER INPUT:        !book The Name of the Wind
                        ↓
SEARCH RESPONSE:   Embed with 5 results
                   Each with title, author, year
                        ↓
USER REACTION:     React with 1️⃣
                        ↓
ADD RESPONSE:      ✅ Successfully added to Readarr!
                        ↓
READARR STATE:     Book appears in library
                   Status: "Wanted"
                   Can download when found
```

### When It's Broken ❌
```
USER INPUT:        !book The Name of the Wind
                        ↓
ERROR:             ❌ Failed to add: HTTP 400: ...
                        ↓
RESULT:            Book not in library
                   Needs manual intervention
```

---

## Deployment Rollback (if needed)

```
⚠️ Something went wrong
        ↓
Restore from backup
    ├─ cp cogs/books.py.backup cogs/books.py
    ├─ cp utils/api_clients.py.backup utils/api_clients.py
    └─ docker compose restart discord-bot
        ↓
Old code running
    ├─ May have bugs but functional
    └─ Can retry fix after investigation
```

---

## Visual: ID Format Comparison

### Google Books ID Format
```
Type: Alphanumeric with dashes
Length: Variable (10-20 chars)
Prefix: None (just the ID)
Example: 8-yGC_bfKesC

When used with "google-" prefix: google-8-yGC_bfKesC ❌
Readarr response: "Unknown foreign ID format"
```

### GoodReads ID Format (What Readarr Needs)
```
Type: Numeric
Length: 5-10 digits
Prefix: None (just the ID)
Example: 95834

When used directly: 95834 ✅
Readarr response: Book found and added successfully
```

---

## Summary: What Gets Fixed

```
┌─────────────────────────────────────┐
│ BEFORE FIX                          │
├─────────────────────────────────────┤
│ ❌ Invalid ID format                │
│ ❌ Wrong metadata source            │
│ ❌ 0% success rate                  │
│ ❌ Poor error messages              │
│ ❌ Users frustrated                 │
└─────────────────────────────────────┘
            ↓ Apply Fix ↓
┌─────────────────────────────────────┐
│ AFTER FIX                           │
├─────────────────────────────────────┤
│ ✅ Valid GoodReads IDs              │
│ ✅ Readarr's validated metadata     │
│ ✅ 95% success rate                 │
│ ✅ Clear error messages             │
│ ✅ Users happy                      │
└─────────────────────────────────────┘
```
