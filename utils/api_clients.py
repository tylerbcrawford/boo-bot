"""
API clients for external services (Readarr, Sonarr, Radarr, etc.)
"""
import requests
from typing import Optional, Dict, List


class ReadarrClient:
    """Client for Readarr API"""

    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.headers = {'X-Api-Key': api_key}

    def test_connection(self) -> Dict:
        """Test connection to Readarr"""
        try:
            response = requests.get(
                f"{self.url}/api/v1/system/status",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def search_books(self, query: str) -> List[Dict]:
        """Search for books using Readarr's lookup endpoint (uses GoodReads)"""
        try:
            response = requests.get(
                f"{self.url}/api/v1/book/lookup",
                params={'term': query},
                headers=self.headers,
                timeout=15
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error searching Readarr: {e}")
            return []

    def search_author(self, name: str) -> Optional[Dict]:
        """Search for an author using Readarr's lookup endpoint"""
        try:
            response = requests.get(
                f"{self.url}/api/v1/author/lookup",
                params={'term': name},
                headers=self.headers,
                timeout=15
            )
            if response.status_code == 200:
                authors = response.json()
                return authors[0] if authors else None
            return None
        except Exception as e:
            print(f"Error searching author in Readarr: {e}")
            return None
    
    def add_book_from_lookup(self, book_data: Dict, root_folder: str, quality_profile_id: int,
                              metadata_profile_id: int, monitored: bool = True, debug: bool = False) -> Dict:
        """
        Add book to Readarr using data from Readarr's own lookup endpoint.
        book_data should be a result from search_books() which uses /api/v1/book/lookup.
        """
        # Extract author name from authorTitle (format: "lastname, firstname Title")
        author_title = book_data.get('authorTitle', '')
        # Try to extract just the author name (before the book title)
        author_name = author_title.split(book_data.get('title', ''))[0].strip()
        if not author_name:
            # Fallback: use the whole authorTitle
            author_name = author_title

        # Search for the author to get their foreignAuthorId
        author_data = self.search_author(author_name)
        if not author_data:
            # Try searching with just the first part of authorTitle
            parts = author_title.split()
            if len(parts) >= 2:
                author_data = self.search_author(' '.join(parts[:2]))

        if not author_data:
            return {'success': False, 'error': f'Could not find author for: {author_name}'}

        # Construct the payload using Readarr's expected format
        readarr_book = {
            'title': book_data.get('title'),
            'foreignBookId': book_data.get('foreignBookId'),
            'titleSlug': book_data.get('titleSlug', book_data.get('foreignBookId')),
            'monitored': monitored,
            'anyEditionOk': book_data.get('anyEditionOk', True),
            'editions': [{
                'title': book_data.get('title'),
                'foreignEditionId': book_data.get('foreignEditionId'),
                'monitored': monitored
            }],
            'author': {
                'authorName': author_data.get('authorName'),
                'authorNameLastFirst': author_data.get('authorNameLastFirst'),
                'foreignAuthorId': author_data.get('foreignAuthorId'),
                'titleSlug': author_data.get('titleSlug'),
                'monitored': True,
                'qualityProfileId': quality_profile_id,
                'metadataProfileId': metadata_profile_id,
                'rootFolderPath': root_folder
            },
            'addOptions': {
                'monitor': 'all' if monitored else 'none',
                'searchForNewBook': True
            }
        }

        # Add images if available
        if book_data.get('images'):
            readarr_book['images'] = book_data.get('images')

        try:
            if debug:
                import json
                print(f"DEBUG: Sending to Readarr: {self.url}/api/v1/book")
                print(f"DEBUG: Payload: {json.dumps(readarr_book, indent=2)}")

            response = requests.post(
                f"{self.url}/api/v1/book",
                json=readarr_book,
                headers=self.headers,
                timeout=30
            )

            if debug:
                print(f"DEBUG: Response status: {response.status_code}")
                print(f"DEBUG: Response body: {response.text}")

            if response.status_code in [200, 201]:
                return {'success': True, 'data': response.json()}
            elif response.status_code == 400:
                # Parse actual error message from Readarr
                try:
                    error_data = response.json()
                    if isinstance(error_data, list) and len(error_data) > 0:
                        error_msg = error_data[0].get('errorMessage', str(error_data))
                    elif isinstance(error_data, dict):
                        error_msg = error_data.get('message', error_data.get('errorMessage', str(error_data)))
                    else:
                        error_msg = str(error_data)
                except:
                    error_msg = response.text
                return {'success': False, 'error': f'Readarr error: {error_msg}'}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_books_by_author(self, author_id: int) -> List[Dict]:
        """Get all books by a specific author"""
        try:
            response = requests.get(
                f"{self.url}/api/v1/book",
                headers=self.headers,
                timeout=15
            )
            if response.status_code == 200:
                all_books = response.json()
                # Filter to only books by this author
                # Note: Use 'authorId' field directly, not nested 'author.id'
                return [b for b in all_books if b.get('authorId') == author_id]
            return []
        except Exception as e:
            print(f"Error getting books by author: {e}")
            return []

    def get_author_by_id(self, author_id: int) -> Optional[Dict]:
        """Get author details by ID"""
        try:
            response = requests.get(
                f"{self.url}/api/v1/author/{author_id}",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting author: {e}")
            return None

    def unmonitor_author(self, author_id: int) -> bool:
        """Unmonitor an author by ID"""
        try:
            # Get current author data
            author_data = self.get_author_by_id(author_id)
            if not author_data:
                return False

            # Set monitored to False
            author_data['monitored'] = False

            response = requests.put(
                f"{self.url}/api/v1/author/{author_id}",
                json=author_data,
                headers=self.headers,
                timeout=15
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error unmonitoring author: {e}")
            return False

    def unmonitor_book(self, book_id: int) -> bool:
        """Unmonitor a book by ID using bulk editor endpoint"""
        try:
            response = requests.put(
                f"{self.url}/api/v1/book/editor",
                json={'bookIds': [book_id], 'monitored': False},
                headers=self.headers,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error unmonitoring book: {e}")
            return False

    def delete_book(self, book_id: int) -> bool:
        """Delete a book by ID"""
        try:
            response = requests.delete(
                f"{self.url}/api/v1/book/{book_id}",
                params={'deleteFiles': 'false', 'addImportListExclusion': 'false'},
                headers=self.headers,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error deleting book: {e}")
            return False

    def search_book(self, book_id: int) -> bool:
        """Trigger a search for a specific book"""
        try:
            response = requests.post(
                f"{self.url}/api/v1/command",
                json={
                    'name': 'BookSearch',
                    'bookIds': [book_id]
                },
                headers=self.headers,
                timeout=15
            )
            return response.status_code in [200, 201]
        except Exception as e:
            print(f"Error triggering book search: {e}")
            return False

    def add_book_with_cleanup(self, book_data: Dict, root_folder: str, quality_profile_id: int,
                               metadata_profile_id: int, debug: bool = False) -> Dict:
        """
        Add a book to Readarr and immediately:
        1. Unmonitor the author
        2. Delete all other books by that author
        3. Trigger search for ONLY the requested book

        Returns dict with success, data, and cleanup_stats
        """
        # First, add the book (with searchForNewBook=False to prevent auto-search of all books)
        # We'll trigger a targeted search after cleanup

        # Extract author info for lookup
        author_title = book_data.get('authorTitle', '')
        author_name = author_title.split(book_data.get('title', ''))[0].strip()
        if not author_name:
            author_name = author_title

        # Search for the author
        author_data = self.search_author(author_name)
        if not author_data:
            parts = author_title.split()
            if len(parts) >= 2:
                author_data = self.search_author(' '.join(parts[:2]))

        if not author_data:
            return {'success': False, 'error': f'Could not find author for: {author_name}'}

        # Construct payload - note: searchForNewBook=False to prevent mass search
        readarr_book = {
            'title': book_data.get('title'),
            'foreignBookId': book_data.get('foreignBookId'),
            'titleSlug': book_data.get('titleSlug', book_data.get('foreignBookId')),
            'monitored': True,
            'anyEditionOk': book_data.get('anyEditionOk', True),
            'editions': [{
                'title': book_data.get('title'),
                'foreignEditionId': book_data.get('foreignEditionId'),
                'monitored': True
            }],
            'author': {
                'authorName': author_data.get('authorName'),
                'authorNameLastFirst': author_data.get('authorNameLastFirst'),
                'foreignAuthorId': author_data.get('foreignAuthorId'),
                'titleSlug': author_data.get('titleSlug'),
                'monitored': False,  # Author should NOT be monitored
                'qualityProfileId': quality_profile_id,
                'metadataProfileId': metadata_profile_id,
                'rootFolderPath': root_folder
            },
            'addOptions': {
                'monitor': 'none',  # Don't auto-monitor other books
                'searchForNewBook': False  # We'll search manually after cleanup
            }
        }

        if book_data.get('images'):
            readarr_book['images'] = book_data.get('images')

        try:
            if debug:
                import json
                print(f"DEBUG: Adding book with cleanup: {book_data.get('title')}")

            response = requests.post(
                f"{self.url}/api/v1/book",
                json=readarr_book,
                headers=self.headers,
                timeout=30
            )

            if response.status_code not in [200, 201]:
                if response.status_code == 400:
                    try:
                        error_data = response.json()
                        if isinstance(error_data, list) and len(error_data) > 0:
                            error_msg = error_data[0].get('errorMessage', str(error_data))
                        elif isinstance(error_data, dict):
                            error_msg = error_data.get('message', error_data.get('errorMessage', str(error_data)))
                        else:
                            error_msg = str(error_data)
                    except:
                        error_msg = response.text
                    return {'success': False, 'error': f'Readarr error: {error_msg}'}
                return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}

            added_book = response.json()
            added_book_id = added_book.get('id')
            # Author ID can be in 'authorId' field or nested in 'author.id'
            author_id = added_book.get('authorId') or added_book.get('author', {}).get('id')

            cleanup_stats = {
                'author_unmonitored': False,
                'books_unmonitored': 0,
                'search_triggered': False
            }

            # Step 1: Unmonitor the author
            if author_id:
                if self.unmonitor_author(author_id):
                    cleanup_stats['author_unmonitored'] = True
                    if debug:
                        print(f"DEBUG: Unmonitored author ID {author_id}")

            # Step 2: Wait for Readarr to finish adding all author books, then unmonitor them
            # Readarr adds other books async - we need to keep checking until stable
            import time

            if author_id:
                max_retries = 5
                last_count = 0

                for attempt in range(max_retries):
                    time.sleep(2)  # Wait 2 seconds between checks

                    author_books = self.get_books_by_author(author_id)
                    current_count = len(author_books)

                    if debug:
                        print(f"DEBUG: Attempt {attempt+1}: Found {current_count} books by author ID {author_id}")

                    # Unmonitor all books except the one we added
                    for book in author_books:
                        if book.get('id') != added_book_id and book.get('monitored', False):
                            if self.unmonitor_book(book.get('id')):
                                cleanup_stats['books_unmonitored'] += 1
                                if debug:
                                    print(f"DEBUG: Unmonitored: {book.get('title')}")

                    # If count is stable (same as last check), we're done
                    if current_count == last_count and current_count > 0:
                        break
                    last_count = current_count

            # Step 4: Make sure our book is monitored and trigger search
            try:
                requests.put(
                    f"{self.url}/api/v1/book/editor",
                    json={'bookIds': [added_book_id], 'monitored': True},
                    headers=self.headers,
                    timeout=10
                )
            except Exception:
                pass

            # Step 5: Trigger search for ONLY this book
            if self.search_book(added_book_id):
                cleanup_stats['search_triggered'] = True
                if debug:
                    print(f"DEBUG: Triggered search for book ID {added_book_id}")

            return {
                'success': True,
                'data': added_book,
                'cleanup_stats': cleanup_stats
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def add_book(self, book_data: Dict, root_folder: str, quality_profile_id: int,
                 metadata_profile_id: int, monitored: bool = True, debug: bool = False) -> Dict:
        """
        Legacy method for backward compatibility.
        Prefers add_book_from_lookup format, falls back to Google Books format.
        """
        # Check if this is data from Readarr lookup (has foreignBookId with numeric GoodReads ID)
        if book_data.get('foreignBookId') and book_data.get('foreignBookId', '').isdigit():
            return self.add_book_from_lookup(book_data, root_folder, quality_profile_id,
                                             metadata_profile_id, monitored, debug)

        # Legacy Google Books format - convert and try Readarr lookup
        query = book_data.get('title', '')
        if book_data.get('authors'):
            query += f" {book_data['authors'][0]}"

        # Search using Readarr's lookup to get proper GoodReads IDs
        lookup_results = self.search_books(query)
        if lookup_results:
            # Use the first match
            return self.add_book_from_lookup(lookup_results[0], root_folder, quality_profile_id,
                                             metadata_profile_id, monitored, debug)
        else:
            return {'success': False, 'error': f'Book not found in Readarr/GoodReads: {query}'}


class SonarrClient:
    """Client for Sonarr API (TV Shows)"""

    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.headers = {'X-Api-Key': api_key}

    def test_connection(self) -> Dict:
        """Test connection to Sonarr"""
        try:
            response = requests.get(
                f"{self.url}/api/v3/system/status",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def search_series(self, query: str) -> List[Dict]:
        """Search for TV series using Sonarr's lookup endpoint"""
        try:
            response = requests.get(
                f"{self.url}/api/v3/series/lookup",
                params={'term': query},
                headers=self.headers,
                timeout=15
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error searching Sonarr: {e}")
            return []

    def add_series(self, series_data: Dict, root_folder: str, quality_profile_id: int) -> Dict:
        """Add a TV series to Sonarr from lookup data"""
        payload = {
            'tvdbId': series_data.get('tvdbId'),
            'title': series_data.get('title'),
            'titleSlug': series_data.get('titleSlug'),
            'images': series_data.get('images', []),
            'seasons': series_data.get('seasons', []),
            'rootFolderPath': root_folder,
            'qualityProfileId': quality_profile_id,
            'monitored': True,
            'addOptions': {
                'monitor': 'all',
                'searchForMissingEpisodes': True,
            },
        }

        try:
            response = requests.post(
                f"{self.url}/api/v3/series",
                json=payload,
                headers=self.headers,
                timeout=30
            )

            if response.status_code in [200, 201]:
                return {'success': True, 'data': response.json()}
            elif response.status_code == 400:
                try:
                    error_data = response.json()
                    if isinstance(error_data, list) and len(error_data) > 0:
                        error_msg = error_data[0].get('errorMessage', str(error_data))
                    elif isinstance(error_data, dict):
                        error_msg = error_data.get('message', error_data.get('errorMessage', str(error_data)))
                    else:
                        error_msg = str(error_data)
                except Exception:
                    error_msg = response.text
                # Detect "already exists" as a soft success
                if 'already' in error_msg.lower() or 'exist' in error_msg.lower():
                    return {'success': False, 'error': error_msg, 'already_exists': True}
                return {'success': False, 'error': f'Sonarr error: {error_msg}'}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class RadarrClient:
    """Client for Radarr API (Movies)"""

    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.headers = {'X-Api-Key': api_key}

    def test_connection(self) -> Dict:
        """Test connection to Radarr"""
        try:
            response = requests.get(
                f"{self.url}/api/v3/system/status",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def search_movies(self, query: str) -> List[Dict]:
        """Search for movies using Radarr's lookup endpoint"""
        try:
            response = requests.get(
                f"{self.url}/api/v3/movie/lookup",
                params={'term': query},
                headers=self.headers,
                timeout=15
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error searching Radarr: {e}")
            return []

    def add_movie(self, movie_data: Dict, root_folder: str, quality_profile_id: int) -> Dict:
        """Add a movie to Radarr from lookup data"""
        payload = {
            'tmdbId': movie_data.get('tmdbId'),
            'title': movie_data.get('title'),
            'titleSlug': movie_data.get('titleSlug'),
            'images': movie_data.get('images', []),
            'rootFolderPath': root_folder,
            'qualityProfileId': quality_profile_id,
            'monitored': True,
            'minimumAvailability': 'released',
            'addOptions': {
                'searchForMovie': True,
            },
        }

        try:
            response = requests.post(
                f"{self.url}/api/v3/movie",
                json=payload,
                headers=self.headers,
                timeout=30
            )

            if response.status_code in [200, 201]:
                return {'success': True, 'data': response.json()}
            elif response.status_code == 400:
                try:
                    error_data = response.json()
                    if isinstance(error_data, list) and len(error_data) > 0:
                        error_msg = error_data[0].get('errorMessage', str(error_data))
                    elif isinstance(error_data, dict):
                        error_msg = error_data.get('message', error_data.get('errorMessage', str(error_data)))
                    else:
                        error_msg = str(error_data)
                except Exception:
                    error_msg = response.text
                # Detect "already exists" as a soft success
                if 'already' in error_msg.lower() or 'exist' in error_msg.lower():
                    return {'success': False, 'error': error_msg, 'already_exists': True}
                return {'success': False, 'error': f'Radarr error: {error_msg}'}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
