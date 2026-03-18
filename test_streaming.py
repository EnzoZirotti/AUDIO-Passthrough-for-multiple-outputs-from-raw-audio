"""
Tests for SoundCloud streaming service.
Tests search functionality, response quality, and data validation.
"""

import unittest
from streaming_service import SoundCloudService, StreamingManager
import sys


class TestSoundCloudService(unittest.TestCase):
    """Test cases for SoundCloudService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = SoundCloudService()
    
    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        self.assertIsNotNone(self.service)
        # Service should be available if yt-dlp or sclib is installed
        print(f"Service available: {self.service.available}")
        print(f"yt-dlp available: {self.service.ytdlp_available}")
        print(f"sclib available: {self.service.sclib_available}")
    
    def test_similarity_score(self):
        """Test similarity score calculation."""
        # Exact match
        score = self.service._similarity_score("test", "test")
        self.assertEqual(score, 1.0)
        
        # Partial match
        score = self.service._similarity_score("test", "testing")
        self.assertGreater(score, 0.5)
        self.assertLessEqual(score, 1.0)
        
        # No match
        score = self.service._similarity_score("test", "xyz")
        self.assertLess(score, 0.5)
    
    def test_expand_search_queries(self):
        """Test query expansion."""
        query = "the beatles yellow submarine"
        variations = self.service._expand_search_queries(query)
        
        self.assertIn(query, variations)  # Original should be included
        self.assertGreater(len(variations), 1)  # Should have variations
        
        # Check that common words are removed
        has_filtered = any("the" not in v for v in variations)
        self.assertTrue(has_filtered)
    
    def test_search_basic(self):
        """Test basic search functionality."""
        if not self.service.available:
            self.skipTest("SoundCloud service not available")
        
        results = self.service.search("test")
        
        # Should return a list
        self.assertIsInstance(results, list)
        
        # If results found, validate structure
        if results:
            for result in results:
                self._validate_track_result(result)
    
    def test_search_popular_artist(self):
        """Test searching for a popular artist."""
        if not self.service.available:
            self.skipTest("SoundCloud service not available")
        
        results = self.service.search("Griz")
        
        self.assertIsInstance(results, list)
        
        if results:
            print(f"\nFound {len(results)} results for 'Griz':")
            for i, result in enumerate(results[:3], 1):
                print(f"  {i}. {result['artist']} - {result['title']}")
                self._validate_track_result(result)
    
    def test_search_flexible(self):
        """Test flexible search with partial query."""
        if not self.service.available:
            self.skipTest("SoundCloud service not available")
        
        # Try partial search
        results = self.service.search("griz halloween")
        
        self.assertIsInstance(results, list)
        
        if results:
            print(f"\nFound {len(results)} results for 'griz halloween':")
            for i, result in enumerate(results[:3], 1):
                print(f"  {i}. {result['artist']} - {result['title']}")
                self._validate_track_result(result)
    
    def test_search_empty_query(self):
        """Test that empty query returns empty list."""
        results = self.service.search("")
        self.assertEqual(results, [])
        
        results = self.service.search("   ")
        self.assertEqual(results, [])
    
    def test_search_results_sorted(self):
        """Test that search results are sorted by relevance."""
        if not self.service.available:
            self.skipTest("SoundCloud service not available")
        
        results = self.service.search("test")
        
        if len(results) > 1:
            # Check that results are sorted by relevance (descending)
            relevances = [r['relevance'] for r in results]
            self.assertEqual(relevances, sorted(relevances, reverse=True))
    
    def _validate_track_result(self, result):
        """Validate that a track result has the correct structure."""
        # Required fields
        self.assertIn('id', result)
        self.assertIn('title', result)
        self.assertIn('artist', result)
        self.assertIn('url', result)
        self.assertIn('service', result)
        self.assertIn('relevance', result)
        
        # Field types
        self.assertIsInstance(result['id'], str)
        self.assertIsInstance(result['title'], str)
        self.assertIsInstance(result['artist'], str)
        self.assertIsInstance(result['url'], str)
        self.assertIsInstance(result['service'], str)
        self.assertIsInstance(result['relevance'], (int, float))
        
        # Field values
        self.assertGreater(len(result['title']), 0, "Title should not be empty")
        self.assertGreater(len(result['url']), 0, "URL should not be empty")
        self.assertEqual(result['service'], 'soundcloud')
        self.assertGreaterEqual(result['relevance'], 0)
        self.assertLessEqual(result['relevance'], 1)
        
        # URL should be a SoundCloud URL
        self.assertIn('soundcloud.com', result['url'].lower())
        
        # Optional fields
        if 'duration' in result:
            self.assertIsInstance(result['duration'], (int, float))
            self.assertGreaterEqual(result['duration'], 0)


class TestStreamingManager(unittest.TestCase):
    """Test cases for StreamingManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = StreamingManager()
    
    def test_manager_initialization(self):
        """Test that the manager initializes correctly."""
        self.assertIsNotNone(self.manager)
        self.assertIsNotNone(self.manager.soundcloud)
        self.assertIsNotNone(self.manager.temp_dir)
    
    def test_manager_search(self):
        """Test manager search functionality."""
        if not self.manager.soundcloud.available:
            self.skipTest("SoundCloud service not available")
        
        results = self.manager.search("test")
        
        self.assertIsInstance(results, list)
        
        if results:
            for result in results:
                # Validate structure
                self.assertIn('id', result)
                self.assertIn('title', result)
                self.assertIn('artist', result)
                self.assertIn('url', result)
                self.assertIn('service', result)


class TestSearchQuality(unittest.TestCase):
    """Test search quality and relevance."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = SoundCloudService()
        if not self.service.available:
            self.skipTest("SoundCloud service not available")
    
    def test_relevance_scoring(self):
        """Test that relevance scores are meaningful."""
        query = "Griz"
        results = self.service.search(query)
        
        if len(results) < 2:
            self.skipTest("Not enough results to test relevance")
        
        # Top result should have reasonable relevance
        top_result = results[0]
        self.assertGreater(top_result['relevance'], 0.1, 
                          "Top result should have some relevance")
        
        # Check that results with query in title have higher relevance
        title_matches = [r for r in results if query.lower() in r['title'].lower()]
        if title_matches:
            avg_title_relevance = sum(r['relevance'] for r in title_matches) / len(title_matches)
            print(f"\nAverage relevance for title matches: {avg_title_relevance:.2f}")
            self.assertGreater(avg_title_relevance, 0.2)
    
    def test_no_duplicates(self):
        """Test that search results don't contain duplicates."""
        query = "test"
        results = self.service.search(query)
        
        if not results:
            self.skipTest("No results to test")
        
        # Check for duplicate URLs
        urls = [r['url'] for r in results]
        unique_urls = set(urls)
        
        self.assertEqual(len(urls), len(unique_urls), 
                        f"Found {len(urls) - len(unique_urls)} duplicate URLs")
    
    def test_result_diversity(self):
        """Test that results show some diversity."""
        query = "electronic"
        results = self.service.search(query)
        
        if len(results) < 5:
            self.skipTest("Not enough results to test diversity")
        
        # Check that we have different artists
        artists = set(r['artist'] for r in results)
        self.assertGreater(len(artists), 1, 
                          "Results should include multiple artists")
        
        # Check that we have different titles
        titles = set(r['title'] for r in results)
        self.assertGreater(len(titles), 1, 
                          "Results should include multiple titles")


def run_tests():
    """Run all tests and print summary."""
    print("=" * 60)
    print("SoundCloud Streaming Service Tests")
    print("=" * 60)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestSoundCloudService))
    suite.addTests(loader.loadTestsFromTestCase(TestStreamingManager))
    suite.addTests(loader.loadTestsFromTestCase(TestSearchQuality))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n[SUCCESS] All tests passed!")
    else:
        print("\n[FAIL] Some tests failed. See details above.")
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}")
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

