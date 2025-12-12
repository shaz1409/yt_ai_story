"""Dialogue Engine - generates emotion-tagged dialogue."""

from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import CharacterSet, DialogueLine, DialoguePlan, Scene, StoryScript
from app.services.llm_client import LLMClient


class DialogueEngine:
    """Generates believable, emotion-tagged dialogue for characters."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the dialogue engine.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.use_llm = getattr(settings, "use_llm_for_dialogue", True)
        self.max_lines_per_scene = getattr(settings, "max_dialogue_lines_per_scene", 2)
        
        if self.use_llm and settings.openai_api_key:
            self.llm_client = LLMClient(settings, logger)
        else:
            self.llm_client = None
            if self.use_llm:
                self.logger.warning("LLM dialogue enabled but OpenAI API key not set, falling back to heuristics")

    def generate_dialogue(
        self,
        story_script: StoryScript,
        character_set: CharacterSet,
    ) -> DialoguePlan:
        """
        Generate dialogue for the story.

        For now, this is a stub that creates basic dialogue.
        In production, this would use LLM to:
        - Create natural, character-appropriate dialogue
        - Match dialogue to scene context
        - Add appropriate emotional tags
        - Time dialogue appropriately

        Args:
            story_script: Story script with scenes
            character_set: Generated characters

        Returns:
            Dialogue plan with all dialogue lines
        """
        self.logger.info("Generating dialogue for story")

        dialogue_lines = []

        # Map characters by role for easy lookup
        character_map = {char.role: char for char in character_set.characters}

        for scene in story_script.scenes:
            scene_dialogue = self._generate_scene_dialogue(scene, character_map)
            dialogue_lines.extend(scene_dialogue)

        dialogue_plan = DialoguePlan(lines=dialogue_lines)

        # Log dialogue distribution by scene role
        scene_role_counts = {}
        for scene in story_script.scenes:
            scene_role = self._detect_scene_role(scene)
            scene_dialogue_count = len([dl for dl in dialogue_lines if dl.scene_id == scene.scene_id])
            if scene_role not in scene_role_counts:
                scene_role_counts[scene_role] = 0
            scene_role_counts[scene_role] += scene_dialogue_count
        
        self.logger.info(f"Generated {len(dialogue_lines)} dialogue lines across {len(story_script.scenes)} scenes")
        if scene_role_counts:
            role_summary = ", ".join([f"{role}: {count}" for role, count in scene_role_counts.items()])
            self.logger.info(f"Dialogue by scene role: {role_summary}")
        
        return dialogue_plan

    def _generate_scene_dialogue(self, scene: Scene, character_map: dict) -> list[DialogueLine]:
        """
        Generate dialogue for a single scene.

        Args:
            scene: Scene to generate dialogue for
            character_map: Map of role -> Character

        Returns:
            List of dialogue lines for this scene
        """
        dialogue_lines = []

        # Determine scene role (hook, setup, conflict, twist, resolution)
        # Extract from scene description or use scene_id as heuristic
        scene_role = self._detect_scene_role(scene)

        # Adjust max_lines based on scene role priority
        # HOOK: 1 strong line, CLASH/TWIST: 2-3 lines, others: default
        if scene_role == "hook":
            max_lines_for_scene = 1  # ONE extremely strong line
        elif scene_role in ["conflict", "twist"]:
            max_lines_for_scene = min(3, self.max_lines_per_scene + 1)  # 2-3 lines of back-and-forth
        else:
            max_lines_for_scene = self.max_lines_per_scene

        # Try LLM generation if enabled
        if self.use_llm and self.llm_client:
            try:
                # Prepare character info for LLM with enhanced depth
                characters = []
                for role, char in character_map.items():
                    if role != "narrator":  # Skip narrator
                        characters.append(
                            {
                                "role": role,
                                "name": char.name,
                                "personality": char.personality,
                                "voice_profile": char.voice_profile,
                                "character_id": char.id,
                                # Enhanced character depth
                                "motivation": getattr(char, "motivation", None),
                                "fear_insecurity": getattr(char, "fear_insecurity", None),
                                "belief_worldview": getattr(char, "belief_worldview", None),
                                "preferred_speech_style": getattr(char, "preferred_speech_style", None),
                                "emotional_trigger": getattr(char, "emotional_trigger", None),
                            }
                        )

                # Get scene emotion marker if available
                scene_emotion = getattr(scene, "emotion", None)

                # Generate dialogue via LLM
                llm_dialogue = self.llm_client.generate_dialogue(
                    scene_description=scene.description,
                    scene_role=scene_role,
                    characters=characters,
                    max_lines=max_lines_for_scene,
                    style=getattr(self.settings, "default_style", "courtroom_drama"),
                    scene_emotion=scene_emotion,  # Pass emotional marker
                )

                # Convert LLM output to DialogueLine objects
                for dialogue_dict in llm_dialogue:
                    character_role = dialogue_dict.get("character_role", "")
                    if character_role in character_map:
                        char = character_map[character_role]
                        dialogue_lines.append(
                            DialogueLine(
                                character_id=char.id,
                                text=dialogue_dict.get("text", ""),
                                emotion=dialogue_dict.get("emotion", "neutral"),
                                scene_id=scene.scene_id,
                                approx_timing_hint=5.0 + (len(dialogue_lines) * 3.0),  # Space out timing
                            )
                        )

                if dialogue_lines:
                    self.logger.debug(f"Generated {len(dialogue_lines)} dialogue lines via LLM for scene {scene.scene_id}")
                    return dialogue_lines

            except Exception as e:
                self.logger.warning(f"LLM dialogue generation failed for scene {scene.scene_id}: {e}, falling back to heuristics")

        # Fallback to heuristic/hardcoded dialogue
        return self._generate_scene_dialogue_heuristic(scene, character_map, scene_role)

    def _detect_scene_role(self, scene: Scene) -> str:
        """
        Detect narrative role of scene (hook, setup, conflict, twist, resolution).

        Args:
            scene: Scene object

        Returns:
            Scene role string
        """
        # Heuristic: use scene_id to determine role
        # This matches the pattern in StoryRewriter
        scene_id = scene.scene_id
        
        # Try to extract from description if it contains role hints
        desc_lower = scene.description.lower()
        if "hook" in desc_lower or scene_id == 1:
            return "hook"
        elif "twist" in desc_lower or "shocking" in desc_lower:
            return "twist"
        elif "conflict" in desc_lower or "tension" in desc_lower:
            return "conflict"
        elif "resolution" in desc_lower or "conclusion" in desc_lower:
            return "resolution"
        elif scene_id == 2:
            return "setup"
        elif scene_id >= 3:
            return "conflict"
        else:
            return "hook"

    def _generate_scene_dialogue_heuristic(
        self, scene: Scene, character_map: dict, scene_role: str
    ) -> list[DialogueLine]:
        """
        Generate dialogue using heuristic/hardcoded approach (fallback).

        Args:
            scene: Scene to generate dialogue for
            character_map: Map of role -> Character
            scene_role: Narrative role of scene

        Returns:
            List of dialogue lines for this scene
        """
        dialogue_lines = []

        # Focus on conflict/twist scenes for maximum impact
        if scene_role in ["conflict", "twist"]:
            # Defendant dialogue in conflict scenes
            if "defendant" in character_map:
                defendant = character_map["defendant"]
                dialogue_lines.append(
                    DialogueLine(
                        character_id=defendant.id,
                        text="This can't be happening!",
                        emotion="shocked",
                        scene_id=scene.scene_id,
                        approx_timing_hint=5.0,
                    )
                )

            # Judge dialogue in conflict/twist
            if "judge" in character_map:
                judge = character_map["judge"]
                dialogue_lines.append(
                    DialogueLine(
                        character_id=judge.id,
                        text="The court has reached a decision.",
                        emotion="stern",
                        scene_id=scene.scene_id,
                        approx_timing_hint=8.0,
                    )
                )

        # Hook scene: opening line
        elif scene_role == "hook" and scene.scene_id == 1:
            if "judge" in character_map:
                judge = character_map["judge"]
                dialogue_lines.append(
                    DialogueLine(
                        character_id=judge.id,
                        text="The court will now proceed.",
                        emotion="neutral",
                        scene_id=scene.scene_id,
                        approx_timing_hint=2.0,
                    )
                )

        # Setup scene: minimal dialogue
        elif scene_role == "setup" and "lawyer" in character_map:
            lawyer = character_map["lawyer"]
            dialogue_lines.append(
                DialogueLine(
                    character_id=lawyer.id,
                    text="Your honor, I must object.",
                    emotion="tense",
                    scene_id=scene.scene_id,
                    approx_timing_hint=5.0,
                )
            )

        return dialogue_lines

