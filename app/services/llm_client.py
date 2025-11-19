"""LLM Client - centralized OpenAI client for LLM operations."""

from typing import Any, Optional

from app.core.config import Settings
from app.core.logging_config import get_logger


class LLMClient:
    """Centralized LLM client for OpenAI operations."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize LLM client.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self._client = None

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI

                if not self.settings.openai_api_key:
                    raise ValueError("OpenAI API key not configured")

                self._client = OpenAI(api_key=self.settings.openai_api_key)
            except ImportError:
                raise ImportError("OpenAI package not installed. Install with: pip install openai")

        return self._client

    def generate_dialogue(
        self,
        scene_description: str,
        scene_role: str,
        characters: list[dict],
        max_lines: int = 2,
        style: str = "courtroom_drama",
    ) -> list[dict]:
        """
        Generate dialogue lines for a scene using LLM.

        Args:
            scene_description: Scene description
            scene_role: Narrative role (hook, setup, conflict, twist, resolution)
            characters: List of character dicts with {role, name, personality, voice_profile}
            max_lines: Maximum number of dialogue lines to generate
            style: Story style (courtroom_drama, ragebait, relationship_drama)

        Returns:
            List of dialogue dicts with {character_id, text, emotion, approx_timing_hint}

        Raises:
            Exception: If LLM generation fails
        """
        self.logger.debug(f"Generating dialogue for scene role: {scene_role}, style: {style}")

        # Build character context
        character_context = []
        for char in characters:
            char_desc = f"{char['role']} ({char.get('name', 'unnamed')}): {char.get('personality', 'neutral')}"
            character_context.append(char_desc)

        # Build emotional, ragebait-focused prompt
        if style == "courtroom_drama":
            style_instructions = """
- Judge: Firm, authoritative, slightly cold. Uses formal language but with emotional weight.
- Defendant: Defensive, sarcastic, arrogant, or desperate (depending on scene). Shows lack of respect or fear.
- Lawyer: Urgent, trying to control chaos. Professional but emotional.
- Focus on power dynamics, injustice, and emotional consequences.
- Create clear villains (cold judge, arrogant teen) and victims.
"""
        elif style == "ragebait":
            style_instructions = """
- Maximize emotional polarity: shock, anger, injustice, humiliation.
- Judge: Cold, dismissive, or unexpectedly harsh.
- Defendant: Arrogant, defiant, or shockingly disrespectful.
- Lawyer: Desperate, trying to save the situation.
- Emphasize the most outrageous, rage-inducing moments.
"""
        else:
            style_instructions = """
- Focus on emotional depth and personal stakes.
- Characters show vulnerability, regret, or determination.
- Dialogue reveals relationships and consequences.
"""

        emotion_map = {
            "hook": "SHOCKING opening - something unexpected happens immediately",
            "setup": "building tension - setting up the conflict and stakes",
            "conflict": "explosive confrontation - high emotional stakes, clear conflict",
            "twist": "dramatic reveal - something that changes everything",
            "resolution": "emotional payoff - consequences and final outcome",
        }

        emotion_goal = emotion_map.get(scene_role, "dramatic")

        # Build prompt
        prompt = f"""Generate {max_lines} short, punchy dialogue lines for a viral {style} YouTube Short.

Scene context:
{scene_description}

Narrative role: {scene_role} ({emotion_goal})

Characters present:
{chr(10).join(character_context)}

Style instructions:
{style_instructions}

Requirements:
- Each line should be 1-2 sentences max, speech-friendly (speakable in 3-5 seconds)
- Match character personality and role EXACTLY
- Focus on EMOTION and CONFLICT - make it feel real and dramatic
- Lines should be believable but heightened for drama
- For hook scenes: start with something shocking or unexpected
- For conflict scenes: emphasize confrontation and high stakes
- For twist scenes: reveal something that changes everything
- Avoid cheesy Reddit-style over-explaining
- Keep it YouTube-safe but emotionally sharp

Return as JSON array:
[
  {{
    "character_role": "judge",
    "text": "Short, punchy dialogue line here",
    "emotion": "stern"
  }},
  ...
]
"""

        try:
            client = self._get_client()
            model = getattr(self.settings, "dialogue_model", "gpt-4o-mini")

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at writing viral, emotional, ragebait dialogue for YouTube Shorts. Generate short, punchy lines that maximize emotional impact, create clear villains/victims, and drive engagement. Focus on shock, injustice, and dramatic confrontation.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.85,  # Higher temp for more creative, emotional dialogue
            )

            import json

            content = response.choices[0].message.content
            data = json.loads(content)

            # Extract dialogue lines (handle both array and object with "dialogue" key)
            if isinstance(data, list):
                dialogue_list = data
            elif isinstance(data, dict):
                dialogue_list = data.get("dialogue", [])
            else:
                dialogue_list = []

            # Limit to max_lines
            dialogue_list = dialogue_list[:max_lines]

            self.logger.debug(f"Generated {len(dialogue_list)} dialogue lines via LLM")
            return dialogue_list

        except Exception as e:
            self.logger.error(f"LLM dialogue generation failed: {e}")
            raise

    def generate_metadata(
        self,
        video_plan: Any,
        style: str = "courtroom_drama",
    ) -> dict[str, Any]:
        """
        Generate clickbait metadata (title, description, tags, hook) using LLM.

        Args:
            video_plan: VideoPlan object
            style: Story style

        Returns:
            Dict with keys: title, description, tags (list), hook_line (optional)

        Raises:
            Exception: If LLM generation fails
        """
        self.logger.debug("Generating metadata via LLM")

        # Extract key info from video plan
        topic = video_plan.topic
        logline = video_plan.logline or ""
        title = video_plan.title or ""
        scenes = video_plan.scenes

        # Extract key events from scenes
        key_events = []
        for scene in scenes[:3]:  # First 3 scenes
            if scene.description:
                key_events.append(scene.description[:100])

        # Style-specific title patterns
        if style == "courtroom_drama":
            title_patterns = [
                "Judge's {action} Leaves {subject} {reaction}... Until This Happens",
                "{subject} {action} At Judge's Verdict, But The Room Goes Silent",
                "[SHOCKING] {subject} {action} In Court - What The Judge Did Next",
                "Judge {action} {subject} - You Won't Believe What Happened",
            ]
        elif style == "ragebait":
            title_patterns = [
                "[SHOCKING] {subject} {action} - This Will Make You Angry",
                "{subject} {action} And Everyone Lost Their Mind",
                "Nobody Expected {subject} To {action} - The Aftermath Is Insane",
            ]
        else:
            title_patterns = [
                "{subject} {action} - This Story Will Break Your Heart",
                "The Truth About {subject} {action} Will Shock You",
            ]

        prompt = f"""Generate viral, clickbait YouTube Short metadata for a {style} story.

Story topic: {topic}
Logline: {logline}
Title: {title}

Key events:
{chr(10).join(f"- {event}" for event in key_events[:3])}

Title patterns to consider:
{chr(10).join(f"- {pattern}" for pattern in title_patterns[:3])}

Generate:
1. A HOOK LINE (1 sentence, maximum emotional impact, first 3-5 seconds)
   - Should be shocking, unexpected, or emotionally charged
   - Examples: "Nobody expected what the judge did next...", "The courtroom went silent when he laughed.", "This teen thought he could get away with anything."
   
2. A CLICKABLE TITLE (max 90 chars, use emotional framing)
   - For courtroom_drama: Use patterns like "Judge's Sentence Leaves Teen Laughing... Until This Happens"
   - Include emotional words: SHOCKING, INSANE, UNBELIEVABLE, etc.
   - Create curiosity gap: "...Until This Happens", "What Happened Next", etc.
   
3. A SHORT DESCRIPTION (2-3 lines summarizing the story, then 5-8 relevant hashtags)
   - First 2 lines: emotional summary of the story
   - Then hashtags: #courtroom #justice #karma #true story #teen #judge etc.
   
4. RELEVANT TAGS (10-15 tags, mix of niche, entities, emotions)
   - Niche: courtroom, justice, trial, legal, court
   - Entities: judge, teen, defendant, lawyer, verdict
   - Emotions: karma, justice, unfair, shocking, karma, consequences
   - Viral: true story, viral, shorts, storytime

Return as JSON:
{{
  "hook_line": "Opening hook sentence (shocking, emotional, first 3-5 seconds)",
  "title": "Clickable YouTube title (max 90 chars, emotional, curiosity gap)",
  "description": "Full description with hashtags",
  "tags": ["tag1", "tag2", ...]
}}
"""

        try:
            client = self._get_client()
            model = getattr(self.settings, "dialogue_model", "gpt-4o-mini")

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at creating viral, clickbait YouTube Shorts metadata for ragebait and courtroom drama content. Generate titles, hooks, and descriptions that maximize clicks, emotional engagement, and shares. Focus on shock, injustice, and curiosity gaps.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.8,  # Higher temp for more creative, clickable titles
            )

            import json

            content = response.choices[0].message.content
            data = json.loads(content)

            # Ensure all required fields
            result = {
                "title": data.get("title", title)[:100],  # Enforce 100 char limit
                "description": data.get("description", logline),
                "tags": data.get("tags", [])[:15],  # Limit to 15 tags
                "hook_line": data.get("hook_line", ""),
            }

            self.logger.debug("Generated metadata via LLM")
            return result

        except Exception as e:
            self.logger.error(f"LLM metadata generation failed: {e}")
            raise

