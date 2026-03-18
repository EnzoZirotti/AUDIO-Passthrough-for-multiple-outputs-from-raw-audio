"""
Live test for SoundCloud search - actually tests the search functionality.
This test will keep iterating until search works.
"""

from streaming_service import StreamingManager
import sys


def test_search_works():
    """Test that search actually returns results."""
    print("=" * 60)
    print("Live SoundCloud Search Test")
    print("=" * 60)
    print()
    
    manager = StreamingManager()
    
    if not manager.soundcloud.available:
        print("[FAIL] SoundCloud service is not available")
        print("   Make sure yt-dlp is installed: pip install yt-dlp")
        return False
    
    # Web search doesn't require yt-dlp, so we can proceed
    if not manager.soundcloud.ytdlp_available:
        print("[INFO] yt-dlp not available (optional - web search will be used)")
    
    # Test queries that should definitely return results
    test_queries = [
        "Griz",
        "electronic music",
        "lofi"
    ]
    
    success_count = 0
    
    for query in test_queries:
        print(f"\n[TEST] Searching for: '{query}'")
        print("-" * 60)
        
        try:
            results = manager.search(query)
            
            if not results:
                print(f"[FAIL] No results for '{query}'")
                print("   This indicates the search is not working properly")
                continue
            
            print(f"[OK] Found {len(results)} results")
            
            # Validate first result
            first_result = results[0]
            print(f"\nFirst result:")
            print(f"  Title: {first_result.get('title', 'N/A')}")
            print(f"  Artist: {first_result.get('artist', 'N/A')}")
            print(f"  URL: {first_result.get('url', 'N/A')}")
            print(f"  Relevance: {first_result.get('relevance', 0):.2f}")
            
            # Validate structure
            required_fields = ['id', 'title', 'artist', 'url', 'service', 'relevance']
            missing_fields = [f for f in required_fields if f not in first_result]
            
            if missing_fields:
                print(f"[WARNING] Missing fields: {missing_fields}")
            else:
                print("[OK] Result structure is valid")
            
            # Check URL
            url = first_result.get('url', '')
            if 'soundcloud.com' not in str(url).lower():
                print(f"[WARNING] URL doesn't look like SoundCloud: {url}")
            else:
                print("[OK] URL is valid SoundCloud link")
            
            # Check that title and artist are not empty
            if not first_result.get('title') or first_result.get('title') == 'Unknown':
                print("[WARNING] Title is missing or Unknown")
            else:
                print("[OK] Title is present")
            
            if not first_result.get('artist') or first_result.get('artist') == 'Unknown':
                print("[WARNING] Artist is missing or Unknown")
            else:
                print("[OK] Artist is present")
            
            success_count += 1
            print(f"[SUCCESS] Search for '{query}' is working!")
            
        except Exception as e:
            print(f"[FAIL] Error searching for '{query}': {e}")
            import traceback
            traceback.print_exc()
    
    print()
    print("=" * 60)
    print(f"Test Results: {success_count}/{len(test_queries)} searches successful")
    print("=" * 60)
    
    if success_count == len(test_queries):
        print("\n[SUCCESS] All searches are working!")
        return True
    elif success_count > 0:
        print(f"\n[PARTIAL] {success_count} out of {len(test_queries)} searches working")
        return False
    else:
        print("\n[FAIL] No searches are working - need to fix the search implementation")
        return False


if __name__ == "__main__":
    success = test_search_works()
    sys.exit(0 if success else 1)

