#!/usr/bin/env python3
"""
TMDb Trailer Client - Fetch YouTube trailer URLs from TMDb API
(Trailarr doesn't expose a query API - it uses TMDb internally to fetch trailers)
"""
import requests
from typing import Optional, Dict


class TrailarrClient:
    """Client for fetching YouTube trailer URLs from TMDb API (same source as Trailarr)"""

    def __init__(self, base_url: str = "http://trailarr:7889", tmdb_api_key: str = ""):
        """
        Initialize client

        Args:
            base_url: Trailarr URL (for health checks only)
            tmdb_api_key: TMDb API key (from docker-compose.yml TMDB_API_KEY)
        """
        self.base_url = base_url.rstrip('/')
        self.tmdb_api_key = tmdb_api_key
        self.tmdb_base_url = "https://api.themoviedb.org/3"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Boo-Bot/1.0'})

    def get_trailer_url(self, title: str, year: Optional[int] = None) -> Optional[str]:
        """
        Get YouTube trailer URL for a movie by querying TMDb API

        Args:
            title: Movie title
            year: Release year (optional but recommended for accuracy)

        Returns:
            YouTube URL string (e.g., https://www.youtube.com/watch?v=XXXXX) or None if not found

        Note:
            Uses TMDb API (same source Trailarr uses) since Trailarr doesn't expose a query API.
        """
        try:
            # Step 1: Search for the movie on TMDb
            search_params = {
                'api_key': self.tmdb_api_key,
                'query': title,
                'language': 'en-US'
            }
            if year:
                search_params['year'] = year

            search_response = self.session.get(
                f"{self.tmdb_base_url}/search/movie",
                params=search_params,
                timeout=5
            )

            if search_response.status_code != 200:
                print(f"⚠️ TMDb search failed with status {search_response.status_code}")
                return None

            search_data = search_response.json()
            results = search_data.get('results', [])

            if not results:
                print(f"ℹ️ No TMDb results found for '{title}' ({year})")
                return None

            # Get the first (most relevant) match
            movie = results[0]
            movie_id = movie.get('id')
            movie_title = movie.get('title', title)

            print(f"✓ Found TMDb movie: {movie_title} (ID: {movie_id})")

            # Step 2: Get videos (trailers) for this movie
            videos_params = {
                'api_key': self.tmdb_api_key,
                'language': 'en-US'
            }

            videos_response = self.session.get(
                f"{self.tmdb_base_url}/movie/{movie_id}/videos",
                params=videos_params,
                timeout=5
            )

            if videos_response.status_code != 200:
                print(f"⚠️ TMDb videos request failed with status {videos_response.status_code}")
                return None

            videos_data = videos_response.json()
            videos = videos_data.get('results', [])

            # Step 3: Find YouTube trailers
            # Filter for YouTube trailers (site=YouTube, type=Trailer)
            youtube_trailers = [
                v for v in videos
                if v.get('site', '').lower() == 'youtube' and v.get('type', '').lower() == 'trailer'
            ]

            if not youtube_trailers:
                print(f"ℹ️ No YouTube trailers found for '{movie_title}'")
                return None

            # Get the first trailer's YouTube ID
            video_key = youtube_trailers[0].get('key')
            if not video_key:
                print(f"⚠️ Trailer found but missing YouTube key")
                return None

            # Construct YouTube URL
            youtube_url = f"https://www.youtube.com/watch?v={video_key}"
            print(f"✓ Found trailer URL for '{movie_title}': {youtube_url}")
            return youtube_url

        except requests.exceptions.Timeout:
            print(f"⚠️ TMDb API timeout for '{title}'")
            return None
        except requests.exceptions.ConnectionError:
            print(f"⚠️ Cannot connect to TMDb API")
            return None
        except Exception as e:
            print(f"⚠️ Error querying TMDb for '{title}': {e}")
            return None

    def get_tv_trailer_url(self, title: str, year: Optional[int] = None, season_number: Optional[int] = None) -> Optional[str]:
        """
        Get YouTube trailer URL for a TV series by querying TMDb API

        Args:
            title: TV series title
            year: First air year (optional but recommended for accuracy)
            season_number: Season number (optional - for season-specific trailers)

        Returns:
            YouTube URL string (e.g., https://www.youtube.com/watch?v=XXXXX) or None if not found

        Logic:
            - If season_number provided: Try season-specific trailer first, then series trailer as fallback
            - If no season_number: Get series-level trailer only
        """
        try:
            # Step 1: Search for the TV series on TMDb
            search_params = {
                'api_key': self.tmdb_api_key,
                'query': title,
                'language': 'en-US'
            }
            if year:
                search_params['first_air_date_year'] = year

            search_response = self.session.get(
                f"{self.tmdb_base_url}/search/tv",
                params=search_params,
                timeout=5
            )

            if search_response.status_code != 200:
                print(f"⚠️ TMDb TV search failed with status {search_response.status_code}")
                return None

            search_data = search_response.json()
            results = search_data.get('results', [])

            if not results:
                print(f"ℹ️ No TMDb results found for TV series '{title}' ({year})")
                return None

            # Get the first (most relevant) match
            series = results[0]
            series_id = series.get('id')
            series_title = series.get('name', title)

            print(f"✓ Found TMDb TV series: {series_title} (ID: {series_id})")

            # Step 2: Try season-specific trailer if season_number provided
            if season_number is not None:
                season_trailer = self._get_season_trailer(series_id, season_number, series_title)
                if season_trailer:
                    return season_trailer
                print(f"ℹ️ No season {season_number} trailer found for '{series_title}'")

            # Step 3: Get series-level trailer (fallback or primary if no season specified)
            videos_params = {
                'api_key': self.tmdb_api_key,
                'language': 'en-US'
            }

            videos_response = self.session.get(
                f"{self.tmdb_base_url}/tv/{series_id}/videos",
                params=videos_params,
                timeout=5
            )

            if videos_response.status_code != 200:
                print(f"⚠️ TMDb TV videos request failed with status {videos_response.status_code}")
                return None

            videos_data = videos_response.json()
            videos = videos_data.get('results', [])

            # Filter for YouTube trailers
            youtube_trailers = [
                v for v in videos
                if v.get('site', '').lower() == 'youtube' and v.get('type', '').lower() == 'trailer'
            ]

            if not youtube_trailers:
                print(f"ℹ️ No YouTube series trailers found for '{series_title}'")
                return None

            # Get the first trailer's YouTube ID
            video_key = youtube_trailers[0].get('key')
            if not video_key:
                print(f"⚠️ Series trailer found but missing YouTube key")
                return None

            # Construct YouTube URL
            youtube_url = f"https://www.youtube.com/watch?v={video_key}"
            print(f"✓ Found series trailer URL for '{series_title}': {youtube_url}")
            return youtube_url

        except requests.exceptions.Timeout:
            print(f"⚠️ TMDb API timeout for TV series '{title}'")
            return None
        except requests.exceptions.ConnectionError:
            print(f"⚠️ Cannot connect to TMDb API")
            return None
        except Exception as e:
            print(f"⚠️ Error querying TMDb for TV series '{title}': {e}")
            return None

    def _get_season_trailer(self, series_id: int, season_number: int, series_title: str) -> Optional[str]:
        """
        Get YouTube trailer URL for a specific TV season

        Args:
            series_id: TMDb TV series ID
            season_number: Season number
            series_title: Series title (for logging)

        Returns:
            YouTube URL string or None if not found
        """
        try:
            videos_params = {
                'api_key': self.tmdb_api_key,
                'language': 'en-US'
            }

            videos_response = self.session.get(
                f"{self.tmdb_base_url}/tv/{series_id}/season/{season_number}/videos",
                params=videos_params,
                timeout=5
            )

            if videos_response.status_code != 200:
                return None

            videos_data = videos_response.json()
            videos = videos_data.get('results', [])

            # Filter for YouTube trailers
            youtube_trailers = [
                v for v in videos
                if v.get('site', '').lower() == 'youtube' and v.get('type', '').lower() == 'trailer'
            ]

            if not youtube_trailers:
                return None

            video_key = youtube_trailers[0].get('key')
            if not video_key:
                return None

            youtube_url = f"https://www.youtube.com/watch?v={video_key}"
            print(f"✓ Found season {season_number} trailer URL for '{series_title}': {youtube_url}")
            return youtube_url

        except Exception as e:
            print(f"⚠️ Error fetching season {season_number} trailer: {e}")
            return None

    def health_check(self) -> bool:
        """
        Check if Trailarr service is accessible (optional - just for status display)

        Returns:
            True if Trailarr is reachable, False otherwise
        """
        try:
            # Trailarr web UI should respond on root path
            response = self.session.get(
                f"{self.base_url}/",
                timeout=2
            )
            if response.status_code in [200, 301, 302]:
                return True
            return False
        except:
            return False
