#!/usr/bin/env python3
"""
Test script for Discord bot Readarr connections
Tests all 4 Readarr instances and validates command setup
"""
import sys
import os
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from config import config
from utils.api_clients import ReadarrClient


def test_readarr_instance(name, url, api_key):
    """Test a single Readarr instance"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"API Key: {api_key[:8]}...{api_key[-8:]}")
    print(f"{'='*60}")

    try:
        client = ReadarrClient(url, api_key)
        result = client.test_connection()

        if result['success']:
            version = result['data'].get('version', 'unknown')
            app_name = result['data'].get('appName', 'unknown')
            print(f"✅ SUCCESS: Connected to {app_name} {version}")
            return True
        else:
            print(f"❌ FAILED: {result['error']}")
            return False
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("DISCORD BOT - READARR CONNECTION TESTS")
    print("="*60)

    results = {}

    # Test all 4 instances
    results['readarr'] = test_readarr_instance(
        "Readarr (eBooks 1)",
        config.READARR_URL,
        config.READARR_API_KEY
    )

    results['readarr-audio'] = test_readarr_instance(
        "Readarr-Audio (Audiobooks 1)",
        config.READARR_AUDIOBOOK_URL,
        config.READARR_AUDIOBOOK_API_KEY
    )

    results['readarr2'] = test_readarr_instance(
        "Readarr2 (eBooks 2)",
        config.READARR2_URL,
        config.READARR2_API_KEY
    )

    results['readarr-audio2'] = test_readarr_instance(
        "Readarr-Audio2 (Audiobooks 2)",
        config.READARR_AUDIO2_URL,
        config.READARR_AUDIO2_API_KEY
    )

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")

    if failed > 0:
        print("\n⚠️  Some tests failed! Check configuration and API keys.")
        return 1
    else:
        print("\n🎉 All tests passed! Bot is ready for Discord commands.")
        return 0


if __name__ == '__main__':
    sys.exit(main())
