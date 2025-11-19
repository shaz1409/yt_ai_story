"""Story Rewriter service - converts raw story into structured script."""

import re
from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import CharacterAction, NarrationLine, Scene, StoryScript


# Style presets for emotional/viral content
STYLE_PRESETS = {
    "courtroom_drama": {
        "tone": "formal_dramatic",
        "word_choices": {
            "judge": "judge slams",
            "sentence": "sentence hits",
            "verdict": "verdict shocks",
        },
        "emotional_intensity": "intense",
        "visual_style": "professional_courtroom",
    },
    "ragebait": {
        "tone": "dramatic_gossipy",
        "word_choices": {
            "judge": "judge destroys",
            "sentence": "sentence crushes",
            "verdict": "verdict explodes",
        },
        "emotional_intensity": "extreme",
        "visual_style": "dramatic_closeups",
    },
    "relationship_drama": {
        "tone": "emotional_intimate",
        "word_choices": {
            "judge": "judge confronts",
            "sentence": "sentence devastates",
            "verdict": "verdict reveals",
        },
        "emotional_intensity": "high",
        "visual_style": "emotional_framing",
    },
}


class StoryRewriter:
    """Rewrites raw story text into structured script with scenes."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the story rewriter.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger

    def rewrite_story(
        self, raw_text: str, title: str, duration_seconds: int = 60, style: str = "courtroom_drama"
    ) -> StoryScript:
        """
        Rewrite raw story into structured script with emotional narrative arc.

        Args:
            raw_text: Raw story text
            title: Story title
            duration_seconds: Target duration
            style: Story style (courtroom_drama, ragebait, relationship_drama)

        Returns:
            Structured story script with narrative arc
        """
        self.logger.info(f"Rewriting story: {title} (style: {style})")

        # Get style preset
        style_preset = STYLE_PRESETS.get(style, STYLE_PRESETS["courtroom_drama"])

        # Generate hooky logline based on style
        logline = self._generate_logline(title, style_preset)

        # Determine number of scenes (3-5 for narrative arc)
        num_scenes = max(3, min(5, duration_seconds // 15))
        self.logger.info(f"Creating {num_scenes} scenes for {duration_seconds}s duration with narrative arc")

        # Create narrative arc structure
        arc_structure = self._create_narrative_arc(raw_text, num_scenes, style_preset)

        # Build scenes from arc
        scenes = []
        arc_roles = ["hook", "setup", "conflict", "twist", "resolution"]
        for scene_id in range(1, num_scenes + 1):
            # Map scene to arc role
            if scene_id == 1:
                scene_role = "hook"
            elif scene_id == 2:
                scene_role = "setup"
            elif scene_id == num_scenes:
                scene_role = "resolution"
            elif scene_id == num_scenes - 1:
                scene_role = "twist"
            else:
                scene_role = "conflict"

            # Get arc content for this role
            arc_text = arc_structure.get(scene_role, raw_text)

            # Enhance scene description with visual framing
            scene_description = self._enhance_scene_description(arc_text, scene_role, style)

            # Optimize narration for speech
            narration_texts = self._optimize_narration_for_speech(arc_text, style_preset)
            narration_lines = [
                NarrationLine(
                    text=text,
                    emotion=self._detect_emotion(text, style_preset),
                    scene_id=scene_id,
                )
                for text in narration_texts
            ]

            # Create character actions
            character_actions = [
                CharacterAction(
                    action_description=self._extract_key_action(arc_text, scene_role),
                    emotion=self._detect_emotion(arc_text, style_preset),
                )
            ]

            scene = Scene(
                scene_id=scene_id,
                description=scene_description,
                narration_lines=narration_lines,
                character_actions=character_actions,
            )
            scenes.append(scene)

            # Store arc role in scene metadata (via description prefix for now)
            # In future, could add arc_role field to Scene model

        script = StoryScript(
            title=title,
            logline=logline,
            scenes=scenes,
        )

        self.logger.info(
            f"Created script with {len(scenes)} scenes and {sum(len(s.narration_lines) for s in scenes)} narration lines"
        )
        return script

    def _create_narrative_arc(self, raw_text: str, num_scenes: int, style_preset: dict) -> dict[str, str]:
        """
        Create structured narrative arc from raw text.

        Returns:
            Dict with keys: hook, setup, conflict, twist, resolution
        """
        words = raw_text.split()
        total_words = len(words)

        # Distribute words across arc roles
        if num_scenes == 3:
            # hook, conflict, resolution
            hook_words = words[: total_words // 3]
            conflict_words = words[total_words // 3 : 2 * total_words // 3]
            resolution_words = words[2 * total_words // 3 :]
            return {
                "hook": " ".join(hook_words),
                "setup": " ".join(hook_words[: len(hook_words) // 2]),  # Split hook
                "conflict": " ".join(conflict_words),
                "twist": " ".join(conflict_words[-len(conflict_words) // 3 :]),  # End of conflict
                "resolution": " ".join(resolution_words),
            }
        elif num_scenes == 4:
            # hook, setup, conflict, resolution
            hook_words = words[: total_words // 4]
            setup_words = words[total_words // 4 : total_words // 2]
            conflict_words = words[total_words // 2 : 3 * total_words // 4]
            resolution_words = words[3 * total_words // 4 :]
            return {
                "hook": " ".join(hook_words),
                "setup": " ".join(setup_words),
                "conflict": " ".join(conflict_words),
                "twist": " ".join(conflict_words[-len(conflict_words) // 2 :]),
                "resolution": " ".join(resolution_words),
            }
        else:  # 5 scenes
            # hook, setup, conflict, twist, resolution
            hook_words = words[: total_words // 5]
            setup_words = words[total_words // 5 : 2 * total_words // 5]
            conflict_words = words[2 * total_words // 5 : 3 * total_words // 5]
            twist_words = words[3 * total_words // 5 : 4 * total_words // 5]
            resolution_words = words[4 * total_words // 5 :]
            return {
                "hook": " ".join(hook_words),
                "setup": " ".join(setup_words),
                "conflict": " ".join(conflict_words),
                "twist": " ".join(twist_words),
                "resolution": " ".join(resolution_words),
            }

    def _enhance_scene_description(self, scene_text: str, scene_role: str, style: str) -> str:
        """
        Create visually descriptive scene with camera framing, mood, lighting.

        Args:
            scene_text: Scene text content
            scene_role: Arc role (hook, setup, conflict, twist, resolution)
            style: Story style

        Returns:
            Visually descriptive scene description
        """
        # Camera angles based on role
        camera_map = {
            "hook": "extreme close-up",
            "setup": "medium shot",
            "conflict": "close-up",
            "twist": "dramatic close-up",
            "resolution": "wide shot",
        }

        # Mood based on role
        mood_map = {
            "hook": "shocking, tense",
            "setup": "building tension, ominous",
            "conflict": "explosive, intense",
            "twist": "dramatic, unexpected",
            "resolution": "satisfying, conclusive",
        }

        # Lighting based on style
        lighting_map = {
            "courtroom_drama": "harsh fluorescent courtroom lighting",
            "ragebait": "dramatic shadows, high contrast",
            "relationship_drama": "soft, emotional lighting",
        }

        camera = camera_map.get(scene_role, "medium shot")
        mood = mood_map.get(scene_role, "dramatic")
        lighting = lighting_map.get(style, "dramatic lighting")

        # Extract key subject from scene text (first 30 words)
        key_subject = " ".join(scene_text.split()[:30])

        description = f"{camera.title()} of {key_subject[:80]}. {mood.title()} atmosphere. {lighting}. {style.replace('_', ' ').title()} setting, cinematic framing, ultra-detailed."

        return description

    def _optimize_narration_for_speech(self, text: str, style_preset: dict) -> list[str]:
        """
        Split text into short, spoken-friendly lines (8-14 words each).

        Respects sentence boundaries and natural pauses.
        """
        # Split by sentences first
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        lines = []
        current_line = []

        for sentence in sentences:
            words = sentence.split()
            if not words:
                continue

            # If sentence fits in target range, add as-is
            if 8 <= len(words) <= 14:
                lines.append(sentence)
            elif len(words) < 8:
                # Short sentence - combine with next if possible
                if current_line:
                    combined = " ".join(current_line) + " " + sentence
                    if len(combined.split()) <= 14:
                        current_line = combined.split()
                    else:
                        lines.append(" ".join(current_line))
                        current_line = words
                else:
                    current_line = words
            else:
                # Long sentence - split at natural pauses
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = []

                # Split long sentence at commas or conjunctions
                parts = re.split(r"[,;]\s+", sentence)
                for part in parts:
                    part_words = part.split()
                    if 8 <= len(part_words) <= 14:
                        lines.append(part)
                    elif len(part_words) < 8:
                        if current_line:
                            combined = " ".join(current_line) + ", " + part
                            if len(combined.split()) <= 14:
                                current_line = combined.split()
                            else:
                                lines.append(" ".join(current_line))
                                current_line = part_words
                        else:
                            current_line = part_words
                    else:
                        # Still too long - force split
                        words_list = part_words
                        while len(words_list) > 14:
                            lines.append(" ".join(words_list[:12]))
                            words_list = words_list[12:]
                        if words_list:
                            current_line = words_list

        # Add remaining line
        if current_line:
            lines.append(" ".join(current_line))

        # Ensure we have at least one line
        if not lines:
            # Fallback: simple word-based split
            words = text.split()
            target_words = 12
            for i in range(0, len(words), target_words):
                lines.append(" ".join(words[i : i + target_words]))

        return lines[:10]  # Max 10 lines per scene

    def _detect_emotion(self, text: str, style_preset: dict) -> str:
        """Detect emotion from text with style-aware intensity."""
        text_lower = text.lower()
        intensity = style_preset.get("emotional_intensity", "moderate")

        # Base emotions
        if any(word in text_lower for word in ["shocking", "unexpected", "explodes", "destroys", "slams"]):
            return "dramatic" if intensity == "intense" else "shocked"
        elif any(word in text_lower for word in ["sad", "emotional", "tears", "crying", "devastates"]):
            return "emotional"
        elif any(word in text_lower for word in ["tense", "anxiety", "nervous", "worried", "confronts"]):
            return "tense"
        elif any(word in text_lower for word in ["justice", "satisfaction", "karma", "consequences"]):
            return "satisfying"
        return "dramatic" if intensity in ["intense", "extreme"] else "neutral"

    def _extract_key_action(self, text: str, scene_role: str) -> str:
        """Extract key action from scene text based on role."""
        words = text.split()[:20]  # First 20 words
        key_text = " ".join(words)

        if scene_role == "hook":
            return f"Shocking moment: {key_text[:50]}"
        elif scene_role == "conflict":
            return f"Intense confrontation: {key_text[:50]}"
        elif scene_role == "twist":
            return f"Unexpected reveal: {key_text[:50]}"
        elif scene_role == "resolution":
            return f"Final outcome: {key_text[:50]}"
        else:
            return f"Key moment: {key_text[:50]}"

    def _generate_logline(self, title: str, style_preset: dict) -> str:
        """Generate hooky logline based on style."""
        tone = style_preset.get("tone", "dramatic")

        if tone == "dramatic_gossipy":
            return f"[SHOCKING] {title} - You won't believe what happened next!"
        elif tone == "emotional_intimate":
            return f"An emotional story about {title.lower()} that will leave you speechless."
        else:  # formal_dramatic
            return f"A dramatic courtroom story about {title.lower()} with an unexpected twist."

