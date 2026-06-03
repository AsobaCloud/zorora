"""
Regression tests for Global View data freshness and consistency.

These tests verify that:
1. Facets endpoint returns actual S3 data range (not stale cache)
2. Articles endpoint returns most recent articles by default
3. Filter counts from stats endpoint match articles endpoint
4. UI filter interactions return consistent data
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch


class TestDataFreshness:
    """Ensure Global View shows most recent available data."""
    
    def test_facets_date_range_matches_s3_not_cache(self, app_client):
        """
        Facets endpoint must return date range from S3, not from stale cache.
        
        Regression: Previously returned March 2026 when S3 had June 2026 data.
        """
        # Mock S3 to return current date folders
        today = datetime.utcnow().strftime('%Y-%m-%d')
        a_week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        mock_folders = [
            (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
            for i in range(10)
        ]
        
        mock_articles = [
            {
                "headline": f"Article {i}",
                "date": folder,
                "source": "Test",
                "url": f"https://example.com/{i}",
                "topic_tags": ["test"],
                "country_tags": ["United States"],
            }
            for i, folder in enumerate(mock_folders)
        ]
        
        # Mock S3 functions - these will be imported by cache and newsroom_s3 modules
        with patch('tools.research.newsroom_s3._list_date_folders', return_value=mock_folders):
            with patch('tools.research.newsroom_s3._fetch_articles_from_date', side_effect=lambda s3, folder, max_results: [
                a for a in mock_articles if a['date'] == folder
            ]):
                resp = app_client.get('/api/news-intel/facets')
        
        assert resp.status_code == 200
        data = resp.get_json()
        
        # Date range should match S3 data (recent), not old cache
        assert data['date_range']['max'] == today, \
            f"Expected max date {today}, got {data['date_range']['max']}"
        assert data['date_range']['min'] <= a_week_ago, \
            f"Expected min date around {a_week_ago}, got {data['date_range']['min']}"
    
    def test_articles_default_returns_most_recent_first(self, app_client):
        """
        Articles endpoint must return most recent articles first by default.
        
        Regression: Previously returned articles from March when June data existed.
        """
        today = datetime.utcnow().strftime('%Y-%m-%d')
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
        old_date = "2026-03-01"
        
        mock_articles = [
            {"headline": "Old Article", "date": old_date, "source": "Test", 
             "url": "https://example.com/old", "topic_tags": [], "country_tags": []},
            {"headline": "Yesterday Article", "date": yesterday, "source": "Test",
             "url": "https://example.com/yesterday", "topic_tags": [], "country_tags": []},
            {"headline": "Today Article", "date": today, "source": "Test",
             "url": "https://example.com/today", "topic_tags": [], "country_tags": []},
        ]
        
        with patch('ui.web.app.fetch_newsroom_cached', return_value=(mock_articles, None)):
            resp = app_client.post('/api/news-intel/articles', 
                                   json={"limit": 10},
                                   content_type='application/json')
        
        assert resp.status_code == 200
        data = resp.get_json()
        
        # First article should be most recent
        assert len(data['articles']) > 0
        assert data['articles'][0]['date'] == today, \
            f"Expected most recent article date {today}, got {data['articles'][0]['date']}"


class TestFilterCountConsistency:
    """Ensure filter counts match between stats and articles endpoints."""
    
    def test_stats_count_matches_articles_for_same_filters(self, app_client):
        """
        Stats endpoint country counts must match articles endpoint results.
        
        Regression: Map tooltip showed 50 articles for "Germany", 
        but clicking filter showed different count.
        """
        mock_articles = [
            {"headline": "Germany Energy 1", "date": "2026-06-01", "source": "Test",
             "url": "https://example.com/1", "topic_tags": ["energy"],
             "country_tags": ["Germany"]},
            {"headline": "Germany Energy 2", "date": "2026-06-01", "source": "Test",
             "url": "https://example.com/2", "topic_tags": ["energy"],
             "country_tags": ["Germany"]},
            {"headline": "Germany Politics", "date": "2026-06-01", "source": "Test",
             "url": "https://example.com/3", "topic_tags": ["politics"],
             "country_tags": ["Germany"]},
            {"headline": "France Energy", "date": "2026-06-01", "source": "Test",
             "url": "https://example.com/4", "topic_tags": ["energy"],
             "country_tags": ["France"]},
        ]
        
        with patch('ui.web.app.fetch_newsroom_cached', return_value=(mock_articles, None)):
            # Get stats
            stats_resp = app_client.post('/api/news-intel/stats',
                                        json={},
                                        content_type='application/json')
            stats_data = stats_resp.get_json()
            
            # Get articles
            articles_resp = app_client.post('/api/news-intel/articles',
                                           json={"limit": 100},
                                           content_type='application/json')
            articles_data = articles_resp.get_json()
        
        # Find Germany in stats
        germany_stat = next((s for s in stats_data['stats'] if s['country'] == 'Germany'), None)
        assert germany_stat is not None, "Germany should appear in stats"
        
        # Count Germany articles from articles endpoint
        germany_articles = [a for a in articles_data['articles'] 
                          if 'Germany' in (a.get('country_tags') or [])]
        
        # Stats count must match actual article count
        assert germany_stat['count'] == len(germany_articles), \
            f"Stats shows {germany_stat['count']} Germany articles, " \
            f"but articles endpoint returns {len(germany_articles)}"
    
    def test_topic_filter_count_matches_tooltip_count(self, app_client):
        """
        Topic filter count in tooltip must match filtered article count.
        
        Regression: Map showed "energy: 5" for Germany, 
        but filtering showed different number.
        """
        mock_articles = [
            {"headline": "Germany Energy 1", "date": "2026-06-01", "source": "Test",
             "url": "https://example.com/1", "topic_tags": ["energy"],
             "country_tags": ["Germany"]},
            {"headline": "Germany Energy 2", "date": "2026-06-01", "source": "Test",
             "url": "https://example.com/2", "topic_tags": ["energy"],
             "country_tags": ["Germany"]},
            {"headline": "Germany Politics", "date": "2026-06-01", "source": "Test",
             "url": "https://example.com/3", "topic_tags": ["politics"],
             "country_tags": ["Germany"]},
        ]
        
        with patch('ui.web.app.fetch_newsroom_cached', return_value=(mock_articles, None)):
            # Get stats (used for tooltip counts)
            stats_resp = app_client.post('/api/news-intel/stats',
                                        json={},
                                        content_type='application/json')
            stats_data = stats_resp.get_json()
            
            # Get articles filtered by topic
            articles_resp = app_client.post('/api/news-intel/articles',
                                           json={"topic": "energy", "limit": 100},
                                           content_type='application/json')
            articles_data = articles_resp.get_json()
        
        # Find Germany in stats and check energy topic count
        germany_stat = next((s for s in stats_data['stats'] if s['country'] == 'Germany'), None)
        assert germany_stat is not None
        tooltip_energy_count = germany_stat['topics'].get('energy', 0)
        
        # Count Germany articles with energy topic
        germany_energy_articles = [
            a for a in articles_data['articles']
            if 'Germany' in (a.get('country_tags') or []) and 'energy' in (a.get('topic_tags') or [])
        ]
        
        assert tooltip_energy_count == len(germany_energy_articles), \
            f"Tooltip shows {tooltip_energy_count} energy articles for Germany, " \
            f"but filter returns {len(germany_energy_articles)}"


class TestDateFilterDefaults:
    """Ensure UI defaults to showing most recent articles."""
    
    def test_default_date_range_is_most_recent_week(self, app_client):
        """
        Without date filters, articles should default to most recent week.
        
        Regression: UI showed articles from March 24 instead of most recent.
        """
        today = datetime.utcnow()
        old_date = today - timedelta(days=90)
        
        mock_articles = [
            {"headline": "Old Article", "date": old_date.strftime('%Y-%m-%d'), 
             "source": "Test", "url": "https://example.com/old", 
             "topic_tags": [], "country_tags": []},
            {"headline": "Recent Article", "date": today.strftime('%Y-%m-%d'),
             "source": "Test", "url": "https://example.com/recent",
             "topic_tags": [], "country_tags": []},
        ]
        
        with patch('ui.web.app.fetch_newsroom_cached', return_value=(mock_articles, None)):
            resp = app_client.post('/api/news-intel/articles',
                                   json={"limit": 10},  # No date filters
                                   content_type='application/json')
        
        data = resp.get_json()
        
        # Without date filters, should still get recent articles
        # The default filtering should apply in the UI, but API should support it
        dates = [a['date'] for a in data['articles']]
        
        # Most recent article should be included
        assert today.strftime('%Y-%m-%d') in dates, \
            "Most recent article should be returned without date filters"


@pytest.fixture
def app_client():
    """Create test client for web app."""
    from ui.web.app import app
    from tools.utils.newsroom_cache import get_cache
    
    # Clear cache before each test to ensure fresh state
    cache = get_cache()
    cache.clear()
    
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
