"""Character Engine - generates unique characters for each story."""

import uuid
from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import Character, CharacterSet


class CharacterEngine:
    """Generates unique characters for each story episode."""

    # Character templates for different roles
    ROLE_TEMPLATES = {
        "judge": {
            "name_prefixes": ["Judge", "Honorable"],
            "appearance": {"age_range": "50-70", "gender": "any", "formality": "high"},
            "personality_traits": ["authoritative", "stern", "fair", "experienced"],
            "voice_profiles": ["deep authoritative", "calm authoritative", "stern male"],
        },
        "defendant": {
            "name_prefixes": [],
            "appearance": {"age_range": "18-40", "gender": "any", "formality": "low"},
            "personality_traits": ["nervous", "defensive", "emotional", "anxious"],
            "voice_profiles": ["young anxious", "nervous", "emotional"],
        },
        "lawyer": {
            "name_prefixes": ["Attorney", "Counselor"],
            "appearance": {"age_range": "30-60", "gender": "any", "formality": "high"},
            "personality_traits": ["confident", "articulate", "strategic", "persuasive"],
            "voice_profiles": ["confident professional", "articulate", "persuasive"],
        },
        "narrator": {
            "name_prefixes": [],
            "appearance": {},
            "personality_traits": ["neutral", "clear", "engaging"],
            "voice_profiles": ["clear neutral", "engaging", "professional"],
        },
        "witness": {
            "name_prefixes": [],
            "appearance": {"age_range": "25-65", "gender": "any", "formality": "medium"},
            "personality_traits": ["nervous", "truthful", "detailed"],
            "voice_profiles": ["nervous", "detailed", "hesitant"],
        },
        "prosecutor": {
            "name_prefixes": ["Prosecutor", "DA"],
            "appearance": {"age_range": "35-60", "gender": "any", "formality": "high"},
            "personality_traits": ["aggressive", "confident", "methodical"],
            "voice_profiles": ["aggressive", "confident", "methodical"],
        },
    }

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the character engine.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger

    def generate_characters(self, story_script: Any, style: str = "courtroom_drama") -> CharacterSet:
        """
        Generate unique characters for the story.

        Characters are generated fresh for each episode - no reuse.

        Args:
            story_script: Story script to analyze
            style: Story style (affects character types)

        Returns:
            CharacterSet with all characters
        """
        self.logger.info(f"Generating characters for style: {style}")

        # Determine required roles based on style
        if style == "courtroom_drama":
            roles = ["judge", "defendant", "lawyer", "narrator"]
        elif style == "crime_drama":
            roles = ["judge", "defendant", "prosecutor", "lawyer", "narrator"]
        else:
            # Default: courtroom drama
            roles = ["judge", "defendant", "lawyer", "narrator"]

        characters = []
        narrator_id = None

        for role in roles:
            character = self._generate_character(role, len(characters))
            characters.append(character)

            if role == "narrator":
                narrator_id = character.id

        character_set = CharacterSet(
            characters=characters,
            narrator_id=narrator_id,
        )

        self.logger.info(f"Generated {len(characters)} characters: {[c.role for c in characters]}")
        return character_set

    def _generate_character(self, role: str, index: int) -> Character:
        """
        Generate a single character for a role.

        Args:
            role: Character role
            index: Character index (for uniqueness)

        Returns:
            Generated character
        """
        template = self.ROLE_TEMPLATES.get(role, self.ROLE_TEMPLATES["narrator"])

        # Generate unique name
        name = self._generate_name(role, template, index)

        # Build appearance
        appearance = template.get("appearance", {}).copy()
        appearance["unique_id"] = uuid.uuid4().hex[:8]

        # Build personality
        personality = ", ".join(template.get("personality_traits", ["neutral"]))

        # Select voice profile
        voice_profiles = template.get("voice_profiles", ["neutral"])
        voice_profile = voice_profiles[index % len(voice_profiles)]

        # Generate detailed voice profile for character speech
        detailed_voice_profile = self._generate_detailed_voice_profile(role, template, appearance)

        character = Character(
            id=f"{role}_{uuid.uuid4().hex[:8]}",
            role=role,
            name=name,
            appearance=appearance,
            personality=personality,
            voice_profile=voice_profile,
            detailed_voice_profile=detailed_voice_profile,
        )

        return character

    def _generate_detailed_voice_profile(self, role: str, template: dict, appearance: dict) -> Any:
        """
        Generate detailed voice profile for character TTS.

        Args:
            role: Character role
            template: Character template
            appearance: Appearance dict

        Returns:
            CharacterVoiceProfile object
        """
        from app.models.schemas import CharacterVoiceProfile

        # Extract gender from appearance or template
        gender = appearance.get("gender", "any")
        if gender == "any":
            # Default based on role
            if role in ["judge", "prosecutor", "lawyer"]:
                gender = "male"  # Default to male for authoritative roles
            else:
                gender = "any"

        # Extract age range
        age_range = appearance.get("age_range", template.get("appearance", {}).get("age_range", "30-50"))

        # Extract tone adjectives from personality traits
        personality_traits = template.get("personality_traits", ["neutral"])
        tone_adjectives = [trait for trait in personality_traits if trait in [
            "stern", "authoritative", "nervous", "defensive", "emotional", "anxious",
            "confident", "articulate", "aggressive", "methodical", "hesitant"
        ]]
        if not tone_adjectives:
            tone_adjectives = ["neutral"]

        # Generate example text based on role and personality
        example_texts = {
            "judge": "The court will now proceed with the verdict.",
            "defendant": "I can't believe this is happening to me.",
            "lawyer": "Your honor, I must object to this line of questioning.",
            "prosecutor": "The evidence clearly shows the defendant's guilt.",
            "witness": "I saw what happened that night, I'm sure of it.",
        }
        example_text = example_texts.get(role, "This is a statement from the character.")

        return CharacterVoiceProfile(
            gender=gender,
            age_range=age_range,
            tone_adjectives=tone_adjectives,
            example_text=example_text,
        )

    def _generate_name(self, role: str, template: dict, index: int) -> str:
        """Generate a unique name for the character."""
        prefixes = template.get("name_prefixes", [])
        first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Davis", "Miller", "Wilson", "Moore"]

        if prefixes:
            prefix = prefixes[index % len(prefixes)]
            last_name = last_names[index % len(last_names)]
            return f"{prefix} {last_name}"
        else:
            first_name = first_names[index % len(first_names)]
            last_name = last_names[index % len(last_names)]
            return f"{first_name} {last_name}"

