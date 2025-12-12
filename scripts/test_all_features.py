#!/usr/bin/env python3
"""Test script to verify all new features work correctly."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all new modules can be imported."""
    print("Testing imports...")
    
    try:
        from app.utils.rate_limiter import RateLimiter, get_openai_limiter, get_hf_limiter, get_elevenlabs_limiter
        print("  ✅ rate_limiter imported")
    except Exception as e:
        print(f"  ❌ rate_limiter import failed: {e}")
        return False
    
    try:
        from app.utils.error_handler import format_error_message, get_fallback_suggestion
        print("  ✅ error_handler imported")
    except Exception as e:
        print(f"  ❌ error_handler import failed: {e}")
        return False
    
    try:
        from app.services.checkpoint_manager import CheckpointManager
        print("  ✅ checkpoint_manager imported")
    except Exception as e:
        print(f"  ❌ checkpoint_manager import failed: {e}")
        return False
    
    try:
        from app.services.analytics_service import AnalyticsService
        print("  ✅ analytics_service imported")
    except Exception as e:
        print(f"  ❌ analytics_service import failed: {e}")
        return False
    
    try:
        from app.services.lipsync_provider import LipSyncProvider, DIDLipSyncProvider, get_lipsync_provider
        print("  ✅ lipsync_provider imported")
    except Exception as e:
        print(f"  ❌ lipsync_provider import failed: {e}")
        return False
    
    return True


def test_rate_limiter():
    """Test rate limiter functionality."""
    print("\nTesting rate limiter...")
    
    try:
        from app.utils.rate_limiter import RateLimiter
        
        limiter = RateLimiter(max_calls=2, time_window=1.0)
        
        # Test can_proceed
        assert limiter.can_proceed() == True, "Should allow first call"
        limiter.wait_if_needed()
        assert limiter.can_proceed() == True, "Should allow second call"
        limiter.wait_if_needed()
        assert limiter.can_proceed() == False, "Should block third call (limit is 2)"
        
        print("  ✅ Rate limiter works correctly")
        return True
    except Exception as e:
        print(f"  ❌ Rate limiter test failed: {e}")
        return False


def test_error_handler():
    """Test error handler functionality."""
    print("\nTesting error handler...")
    
    try:
        from app.utils.error_handler import format_error_message, get_fallback_suggestion
        
        # Test formatting
        error = ValueError("API key not configured")
        msg = format_error_message("TTS generation", error, {"episode_id": "test123"})
        assert "TTS generation" in msg, "Should include operation name"
        assert "episode_id=test123" in msg, "Should include context"
        
        # Test suggestions
        suggestion = get_fallback_suggestion("TTS", error)
        assert suggestion is not None, "Should provide suggestion"
        
        print("  ✅ Error handler works correctly")
        return True
    except Exception as e:
        print(f"  ❌ Error handler test failed: {e}")
        return False


def test_checkpoint_manager():
    """Test checkpoint manager functionality."""
    print("\nTesting checkpoint manager...")
    
    try:
        from app.core.config import Settings
        from app.core.logging_config import get_logger
        from app.services.checkpoint_manager import CheckpointManager
        
        settings = Settings()
        logger = get_logger(__name__)
        manager = CheckpointManager(settings, logger)
        
        # Test save/load
        test_data = {"test": "data", "number": 42}
        manager.save_checkpoint("test_episode", CheckpointManager.STAGE_STORY_GENERATED, test_data)
        
        loaded = manager.load_checkpoint("test_episode", CheckpointManager.STAGE_STORY_GENERATED)
        assert loaded == test_data, "Loaded data should match saved data"
        
        # Test has_checkpoint
        assert manager.has_checkpoint("test_episode", CheckpointManager.STAGE_STORY_GENERATED) == True
        
        # Cleanup
        manager.clear_checkpoint("test_episode", CheckpointManager.STAGE_STORY_GENERATED)
        
        print("  ✅ Checkpoint manager works correctly")
        return True
    except Exception as e:
        print(f"  ❌ Checkpoint manager test failed: {e}")
        return False


def test_analytics_service():
    """Test analytics service functionality."""
    print("\nTesting analytics service...")
    
    try:
        from app.core.config import Settings
        from app.core.logging_config import get_logger
        from app.services.analytics_service import AnalyticsService
        from datetime import datetime
        
        settings = Settings()
        logger = get_logger(__name__)
        analytics = AnalyticsService(settings, logger)
        
        # Test record_video_upload
        analytics.record_video_upload(
            episode_id="test_episode",
            youtube_video_id="test_video_id",
            title="Test Video",
            niche="courtroom",
            style="courtroom_drama",
            published_at=datetime.now(),
        )
        
        # Test get_video_metrics
        metrics = analytics.get_video_metrics("test_episode")
        assert metrics is not None, "Should return metrics"
        
        # Test update_video_metrics
        analytics.update_video_metrics("test_episode", views=100, likes=10)
        metrics = analytics.get_video_metrics("test_episode")
        assert metrics["views"] == 100, "Views should be updated"
        
        # Test get_top_performers
        top = analytics.get_top_performers(metric="views", limit=5)
        assert isinstance(top, list), "Should return list"
        
        print("  ✅ Analytics service works correctly")
        return True
    except Exception as e:
        print(f"  ❌ Analytics service test failed: {e}")
        return False


def test_stable_character_id():
    """Test stable character ID generation."""
    print("\nTesting stable character ID...")
    
    try:
        from app.core.config import Settings
        from app.core.logging_config import get_logger
        from app.models.schemas import Character
        from app.services.character_video_engine import CharacterVideoEngine
        
        settings = Settings()
        logger = get_logger(__name__)
        engine = CharacterVideoEngine(settings, logger)
        
        # Create two characters with same role/appearance
        char1 = Character(
            id="judge_abc123",  # Different episode ID
            role="judge",
            name="Judge Williams",
            appearance={"age_range": "50-70", "gender": "male"},
            personality="authoritative, stern",
            voice_profile="deep authoritative",
        )
        
        char2 = Character(
            id="judge_xyz789",  # Different episode ID
            role="judge",
            name="Judge Williams",
            appearance={"age_range": "50-70", "gender": "male"},
            personality="authoritative, stern",
            voice_profile="deep authoritative",
        )
        
        # Should generate same stable ID
        stable_id1 = engine._generate_stable_character_id(char1)
        stable_id2 = engine._generate_stable_character_id(char2)
        
        assert stable_id1 == stable_id2, f"Same character should have same stable ID: {stable_id1} != {stable_id2}"
        
        print(f"  ✅ Stable character ID works: {stable_id1}")
        return True
    except Exception as e:
        print(f"  ❌ Stable character ID test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing All New Features")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Rate Limiter", test_rate_limiter),
        ("Error Handler", test_error_handler),
        ("Checkpoint Manager", test_checkpoint_manager),
        ("Analytics Service", test_analytics_service),
        ("Stable Character ID", test_stable_character_id),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ {name} test crashed: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print("=" * 60)
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())

