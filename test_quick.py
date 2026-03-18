"""
Quick test script to verify SoundCloud search is working.
Run this to quickly check if search returns good results.
"""

from streaming_service import StreamingManager


def quick_test():
    """Run a quick test of the search functionality."""
    print("=" * 60)
    print("Quick SoundCloud Search Test")
    print("=" * 60)
    print()
    
    manager = StreamingManager()
    
    if not manager.soundcloud.available:
        print("[FAIL] SoundCloud service is not available")
        print("   Make sure yt-dlp is installed: pip install yt-dlp")
        return False
    
    # Test queries
    test_queries = [
        "Griz",
        "electronic music",
        "lofi hip hop"
    ]
    
    all_passed = True
    
    for query in test_queries:
        print(f"\n[TEST] Testing search: '{query}'")
        print("-" * 60)
        
        try:
            results = manager.search(query)
            
            if not results:
                print(f"[FAIL] No results for '{query}'")
                all_passed = False
                continue
            
            print(f"[OK] Found {len(results)} results")
            
            # Validate first few results
            print("\nTop results:")
            for i, result in enumerate(results[:3], 1):
                print(f"  {i}. {result['artist']} - {result['title']}")
                print(f"     URL: {result['url']}")
                print(f"     Relevance: {result['relevance']:.2f}")
                
                # Quick validation
                if not result['title'] or not result['url']:
                    print(f"     [WARNING] Missing data")
                    all_passed = False
                if 'soundcloud.com' not in result['url'].lower():
                    print(f"     [WARNING] URL doesn't look like SoundCloud")
                    all_passed = False
            
        except Exception as e:
            print(f"[FAIL] Error searching for '{query}': {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    print()
    print("=" * 60)
    if all_passed:
        print("[SUCCESS] All quick tests passed!")
    else:
        print("[FAIL] Some tests failed")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    import sys
    success = quick_test()
    sys.exit(0 if success else 1)

