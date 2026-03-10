#!/usr/bin/env python3
"""
Check Readarr configuration settings (root folders, profiles, etc.)
"""
import requests
import sys
import os
from dotenv import load_dotenv

load_dotenv()

def check_readarr(name, url, api_key):
    """Check a Readarr instance configuration"""
    print(f"\n{'='*60}")
    print(f"Checking: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    headers = {'X-Api-Key': api_key}

    try:
        # Check root folders
        print("\n📁 Root Folders:")
        response = requests.get(f"{url}/api/v1/rootfolder", headers=headers, timeout=10)
        if response.status_code == 200:
            folders = response.json()
            for folder in folders:
                print(f"  ID: {folder['id']} | Path: {folder['path']}")
        else:
            print(f"  ❌ Failed to get root folders: HTTP {response.status_code}")

        # Check quality profiles
        print("\n⚙️  Quality Profiles:")
        response = requests.get(f"{url}/api/v1/qualityprofile", headers=headers, timeout=10)
        if response.status_code == 200:
            profiles = response.json()
            for profile in profiles:
                print(f"  ID: {profile['id']} | Name: {profile['name']}")
        else:
            print(f"  ❌ Failed to get quality profiles: HTTP {response.status_code}")

        # Check metadata profiles
        print("\n📋 Metadata Profiles:")
        response = requests.get(f"{url}/api/v1/metadataprofile", headers=headers, timeout=10)
        if response.status_code == 200:
            profiles = response.json()
            for profile in profiles:
                print(f"  ID: {profile['id']} | Name: {profile['name']}")
        else:
            print(f"  ❌ Failed to get metadata profiles: HTTP {response.status_code}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Check all Readarr instances"""
    print("\n" + "="*60)
    print("READARR CONFIGURATION CHECKER")
    print("="*60)

    instances = [
        ("Readarr (eBooks 1)",
         os.getenv('READARR_URL', 'http://localhost:8787'),
         os.getenv('READARR_API_KEY')),

        ("Readarr-Audio (Audiobooks 1)",
         os.getenv('READARR_AUDIOBOOK_URL', 'http://localhost:8788'),
         os.getenv('READARR_AUDIOBOOK_API_KEY')),

        ("Readarr2 (eBooks 2)",
         os.getenv('READARR2_URL', 'http://localhost:8789'),
         os.getenv('READARR2_API_KEY')),

        ("Readarr-Audio2 (Audiobooks 2)",
         os.getenv('READARR_AUDIO2_URL', 'http://localhost:8790'),
         os.getenv('READARR_AUDIO2_API_KEY')),
    ]

    for name, url, api_key in instances:
        check_readarr(name, url, api_key)

    print("\n" + "="*60)
    print("Configuration from .env:")
    print("="*60)
    print(f"READARR2_ROOT_FOLDER: {os.getenv('READARR2_ROOT_FOLDER')}")
    print(f"READARR2_QUALITY_PROFILE_ID: {os.getenv('READARR2_QUALITY_PROFILE_ID')}")
    print(f"READARR2_METADATA_PROFILE_ID: {os.getenv('READARR2_METADATA_PROFILE_ID')}")
    print()
    print(f"READARR_AUDIO2_ROOT_FOLDER: {os.getenv('READARR_AUDIO2_ROOT_FOLDER')}")
    print(f"READARR_AUDIO2_QUALITY_PROFILE_ID: {os.getenv('READARR_AUDIO2_QUALITY_PROFILE_ID')}")
    print(f"READARR_AUDIO2_METADATA_PROFILE_ID: {os.getenv('READARR_AUDIO2_METADATA_PROFILE_ID')}")
    print("="*60)


if __name__ == '__main__':
    main()
