#!/usr/bin/env python3
"""Test script to verify character consistency across episodes."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import Settings
from app.core.logging_config import get_logger, setup_logging
from app.models.schemas import Character
from app.services.character_video_engine import CharacterVideoEngine


def test_character_consistency():
    """Test that same character generates same face image."""
    settings = Settings()
    setup_logging()
    logger = get_logger(__name__)
    
    engine = CharacterVideoEngine(settings, logger)
    
    # Create test character
    from app.models.schemas import CharacterVoiceProfile
    
    character1 = Character(
        id="judge_test123",
        role="judge",
        name="Judge Williams",
        appearance={"age_range": "50-70", "gender": "male", "formality": "high"},
        personality="authoritative, stern, fair, experienced",
        voice_profile="deep authoritative",
        detailed_voice_profile=CharacterVoiceProfile(
            gender="male",
            age_range="50-70",
            tone_adjectives=["authoritative", "stern"],
            example_text="The court will now proceed.",
        ),
    )
    
    # Generate stable ID
    stable_id1 = engine._generate_stable_character_id(character1)
    logger.info(f"Character 1 stable ID: {stable_id1}")
    
    # Create same character again (different episode ID)
    character2 = Character(
        id="judge_xyz789",  # Different episode ID
        role="judge",
        name="Judge Williams",
        appearance={"age_range": "50-70", "gender": "male", "formality": "high"},
        personality="authoritative, stern, fair, experienced",
        voice_profile="deep authoritative",
        detailed_voice_profile=CharacterVoiceProfile(
            gender="male",
            age_range="50-70",
            tone_adjectives=["authoritative", "stern"],
            example_text="The court will now proceed.",
        ),
    )
    
    stable_id2 = engine._generate_stable_character_id(character2)
    logger.info(f"Character 2 stable ID: {stable_id2}")
    
    # Verify they have same stable ID
    if stable_id1 == stable_id2:
        logger.info("✅ PASS: Same character generates same stable ID")
        return True
    else:
        logger.error(f"❌ FAIL: Different stable IDs: {stable_id1} != {stable_id2}")
        return False


def test_seed_consistency():
    """Test that same character_id generates same seed."""
    settings = Settings()
    setup_logging()
    logger = get_logger(__name__)
    
    engine = CharacterVideoEngine(settings, logger)
    
    # Test seed generation
    character_id1 = "judge_abc123"
    seed1 = engine._generate_character_seed(character_id1)
    
    character_id2 = "judge_abc123"  # Same ID
    seed2 = engine._generate_character_seed(character_id2)
    
    if seed1 == seed2:
        logger.info(f"✅ PASS: Same character_id generates same seed: {seed1}")
        return True
    else:
        logger.error(f"❌ FAIL: Different seeds: {seed1} != {seed2}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Character Consistency Tests")
    print("=" * 60)
    
    test1 = test_character_consistency()
    test2 = test_seed_consistency()
    
    print("=" * 60)
    if test1 and test2:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)

