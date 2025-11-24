"""Story Rewriter service - converts raw story into structured script."""

import json
import re
from typing import Any, Optional

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import Beat, CharacterAction, NarrationLine, Scene, StoryScript


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
        self,
        raw_text: str,
        title: str,
        duration_seconds: int = 60,
        style: str = "courtroom_drama",
        niche: Optional[str] = None,
        primary_emotion: Optional[str] = None,
        secondary_emotion: Optional[str] = None,
        topic_hint: Optional[str] = None,
    ) -> tuple[StoryScript, Optional[str]]:
        """
        Rewrite raw story into structured script with emotional narrative arc.

        Args:
            raw_text: Raw story text
            title: Story title
            duration_seconds: Target duration
            style: Story style (courtroom_drama, ragebait, relationship_drama)
            niche: Story niche (optional, for beat-based generation)
            primary_emotion: Primary emotion (optional, for beat-based generation)
            secondary_emotion: Secondary emotion (optional, for beat-based generation)
            topic_hint: Topic hint (optional, for beat-based generation)

        Returns:
            Structured story script with narrative arc
        """
        self.logger.info(f"Rewriting story: {title} (style: {style})")

        # Try beat-based generation if we have the required inputs
        pattern_type = None
        if niche and primary_emotion:
            try:
                beats_result, pattern_type = self._generate_story_from_beats(
                    niche=niche,
                    primary_emotion=primary_emotion,
                    secondary_emotion=secondary_emotion,
                    topic_hint=topic_hint or title,
                    style=style,
                    duration_seconds=duration_seconds,
                )
                if beats_result:
                    self.logger.info("Successfully generated story from beats")
                    return beats_result, pattern_type
            except Exception as e:
                self.logger.warning(f"Beat-based generation failed: {e}, falling back to legacy logic")
                # Fall through to legacy logic

        # Legacy logic (fallback or when beat inputs not available)
        self.logger.info("Using legacy story generation logic")

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

            # Expand narration using LLM to reach target word count (120-150 words for 60s)
            # Target: ~30-40 words per scene for 4 scenes = 120-160 words total
            target_words_per_scene = max(25, (duration_seconds * 2.2) // num_scenes)  # ~2.2 words/sec
            expanded_narration = self._expand_narration_with_llm(
                arc_text, scene_role, title, style, target_words_per_scene, style_preset
            )

            # Optimize narration for speech
            narration_texts = self._optimize_narration_for_speech(expanded_narration, style_preset)
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
        return script, pattern_type

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

    def _expand_narration_with_llm(
        self, arc_text: str, scene_role: str, title: str, style: str, target_words: int, style_preset: dict
    ) -> str:
        """
        Expand narration text using LLM to reach target word count with emotional, ragebait content.

        Args:
            arc_text: Original arc text (may be short)
            scene_role: Narrative role (hook, setup, conflict, twist, resolution)
            title: Story title
            style: Story style
            target_words: Target word count for this scene
            style_preset: Style preset dict

        Returns:
            Expanded narration text (target_words length, emotional and dramatic)
        """
        # Check if LLM is available
        if not hasattr(self.settings, "openai_api_key") or not self.settings.openai_api_key:
            self.logger.debug("No OpenAI API key, using original text with basic expansion")
            return self._expand_narration_heuristic(arc_text, target_words)

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.settings.openai_api_key)
            model = getattr(self.settings, "dialogue_model", "gpt-4o-mini")

            # Build emotional prompt based on style and scene role
            emotion_map = {
                "hook": "SHOCKING opening that grabs attention immediately",
                "setup": "building tension and setting up the conflict",
                "conflict": "explosive confrontation with high emotional stakes",
                "twist": "dramatic unexpected reveal that changes everything",
                "resolution": "satisfying conclusion with clear consequences",
            }

            emotion_goal = emotion_map.get(scene_role, "dramatic")

            # Style-specific instructions
            if style == "courtroom_drama":
                style_instructions = """
- Focus on injustice, power dynamics, and emotional consequences
- Use formal but dramatic language
- Emphasize the judge's authority and the defendant's vulnerability or arrogance
- Create clear villains (cold judge, arrogant teen) and victims
"""
            elif style == "ragebait":
                style_instructions = """
- Maximize emotional polarity: shock, anger, injustice, humiliation
- Use dramatic, gossipy language
- Create clear "good vs evil" dynamics
- Emphasize the most outrageous moments
"""
            else:
                style_instructions = """
- Focus on emotional depth and personal stakes
- Use intimate, emotional language
- Emphasize relationships and consequences
"""

            prompt = f"""Write {target_words} words of dramatic narration for a {style} YouTube Short.

Story: {title}
Scene role: {scene_role} ({emotion_goal})
Original context: {arc_text[:200]}

Requirements:
{style_instructions}
- Write exactly {target_words} words (no more, no less)
- Make it tight, high-stakes, and emotionally charged
- Use short, punchy sentences (8-14 words each)
- Focus on what's happening NOW, not backstory
- Create vivid imagery and emotional impact
- For hook: start with something shocking or unexpected
- For conflict: emphasize the confrontation and stakes
- For twist: reveal something that changes everything
- For resolution: show clear consequences and emotional payoff

Write ONLY the narration text, no labels or explanations:"""

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at writing viral, emotional narration for YouTube Shorts. Write tight, dramatic content that maximizes engagement and emotional impact.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=300,  # Enough for ~150 words
            )

            expanded = response.choices[0].message.content.strip()
            word_count = len(expanded.split())
            self.logger.debug(f"Expanded narration for {scene_role}: {word_count} words (target: {target_words})")

            # If still too short, pad with heuristic expansion
            if word_count < target_words * 0.7:
                self.logger.warning(f"LLM expansion too short ({word_count} < {target_words}), padding with heuristic")
                expanded = self._expand_narration_heuristic(expanded, target_words)

            return expanded

        except Exception as e:
            self.logger.warning(f"LLM narration expansion failed: {e}, using heuristic expansion")
            return self._expand_narration_heuristic(arc_text, target_words)

    def _expand_narration_heuristic(self, text: str, target_words: int) -> str:
        """
        Heuristic expansion when LLM is unavailable.

        Expands text by adding emotional descriptors and dramatic language.
        """
        words = text.split()
        current_words = len(words)

        if current_words >= target_words:
            return text

        # Add emotional descriptors and dramatic language
        emotional_additions = [
            "in a shocking turn of events",
            "the tension in the room was palpable",
            "nobody saw this coming",
            "the courtroom fell silent",
            "what happened next would change everything",
            "the judge's words hit like a hammer",
            "the defendant's reaction stunned everyone",
            "this was the moment everything changed",
        ]

        needed_words = target_words - current_words
        additions_to_use = needed_words // 5  # ~5 words per addition

        expanded = text
        for i, addition in enumerate(emotional_additions[:additions_to_use]):
            if i % 2 == 0:
                expanded = f"{expanded}. {addition.capitalize()}"
            else:
                expanded = f"{expanded}, {addition}"

        # Trim to target if over
        expanded_words = expanded.split()
        if len(expanded_words) > target_words:
            expanded = " ".join(expanded_words[:target_words])

        return expanded

    def _generate_story_from_beats(
        self,
        niche: str,
        primary_emotion: str,
        secondary_emotion: Optional[str],
        topic_hint: str,
        style: str,
        duration_seconds: int,
    ) -> tuple[Optional[StoryScript], Optional[str]]:
        """
        Generate story from beats using LLM with beat-based prompt.

        Args:
            niche: Story niche
            primary_emotion: Primary emotion
            secondary_emotion: Secondary emotion (optional)
            topic_hint: Topic hint
            style: Story style
            duration_seconds: Target duration

        Returns:
            StoryScript if successful, None if LLM fails
        """
        # Check if LLM is available
        if not hasattr(self.settings, "openai_api_key") or not self.settings.openai_api_key:
            self.logger.debug("No OpenAI API key, cannot use beat-based generation")
            return None

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.settings.openai_api_key)
            model = getattr(self.settings, "dialogue_model", "gpt-4o-mini")

            # Calculate word budget (2.3 words per second for narration)
            target_word_count = int(duration_seconds * 2.3)
            # Aim for 130-150 words for 60s, adjust proportionally
            if duration_seconds == 60:
                target_word_count = 140  # Sweet spot for 60s
            else:
                target_word_count = max(100, int(duration_seconds * 2.3))
            
            self.logger.info(f"Target narration word count: {target_word_count} words (for {duration_seconds}s video)")

            # Build beat-based prompt
            emotion_context = f"Primary emotion: {primary_emotion}"
            if secondary_emotion:
                emotion_context += f", Secondary emotion: {secondary_emotion}"

            prompt = f"""You generate a short-form, highly engaging, emotionally provoking story for vertical video.

Input variables:
- niche: {niche}
- primary_emotion: {primary_emotion}
- secondary_emotion: {secondary_emotion or "none"}
- topic_hint: {topic_hint}

Beat types:
- HOOK: Opening that grabs attention immediately (MUST grab attention within 1-2 seconds)
- TRIGGER: Event that sets the story in motion
- CONTEXT: Background information and setup
- CLASH: Main conflict or confrontation
- TWIST: Unexpected reveal or reversal
- CTA: Call-to-action or conclusion (MUST end with a direct question to viewers)

Patterns:
- Pattern A: HOOK → TRIGGER → CONTEXT → CLASH → TWIST → CTA
- Pattern B: HOOK → CONTEXT → CLASH → TRIGGER → CTA
- Pattern C: HOOK → CONTEXT → TWIST → CLASH → CTA

CRITICAL REQUIREMENTS:

1. HOOK (10-15% of word budget):
   - MUST start with either:
     (a) A shocking line of dialogue (e.g., "The judge laughed as he read the sentence.")
     OR
     (b) A visceral image (e.g., "A teenager smirks as the victim's family sobs in court.")
   - Must grab attention within 1-2 seconds
   - Must be emotionally triggering (shock, outrage, injustice)
   - Keep it concise but powerful

2. TRIGGER/CONTEXT (25-35% of word budget):
   - Set up the story efficiently
   - Avoid long backstory dumps
   - Keep beats concise
   - Focus on what matters for emotional impact

3. CLASH/TWIST (30-40% of word budget):
   - This is where the emotional peak happens
   - Make it intense, dramatic, rage-inducing
   - Focus on injustice, shock, or moral conflict
   - This is NOT neutral news - make viewers feel something

4. CTA (10-15% of word budget):
   - MUST end with a single, direct question aimed at the viewer
   - Explicitly ask for their opinion in the comments
   - Examples:
     * "Should the judge have gone easier on them?"
     * "Was this justice, or did the system fail?"
     * "If this happened in your city, what would YOU want the sentence to be?"
   - Make it personal and engaging

WORD BUDGET:
- Total narration text across all beats should be around {target_word_count} words
- Keep beats concise; avoid long backstory dumps
- Distribute words roughly: HOOK (10-15%), TRIGGER/CONTEXT (25-35%), CLASH/TWIST (30-40%), CTA (10-15%)

EMOTIONAL FRAMING:
- Lean into outrage, injustice, and shock. This is not neutral news – make viewers feel something immediately.
- Focus less on legal realism and more on emotional impact and moral conflict.
- Target emotion: {emotion_context}
- Make it viral, emotional, and engaging
- Focus on {niche} niche with {style} style

TECHNICAL:
- Choose ONE pattern (A, B, or C) that best fits the story
- Generate beats in the chosen pattern order
- Each beat must have: type, speaker ("narrator" or a character_id), target_emotion (rage/injustice/shock/disgust), and text
- Text should be 1-3 sentences, speech-friendly (8-14 words per sentence)
- Always end with a CTA beat

Output JSON ONLY (no markdown, no code blocks):
{{
  "pattern_type": "A" | "B" | "C",
  "beats": [
    {{
      "type": "HOOK",
      "speaker": "narrator",
      "target_emotion": "shock",
      "text": "..."
    }},
    ...
  ]
}}"""

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at creating viral, emotional stories for YouTube Shorts. Generate beat-based narratives that maximize engagement and emotional impact. Always output valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.85,
                max_tokens=2000,
            )

            # Parse JSON response
            response_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            beats_data = json.loads(response_text)
            
            pattern_type = beats_data.get("pattern_type", "A")
            beats_list = beats_data.get("beats", [])
            
            if not beats_list:
                self.logger.warning("No beats returned from LLM")
                return None, None, None

            # Validate word count
            total_words = sum(len(beat.get("text", "").split()) for beat in beats_list)
            min_words = int(target_word_count * 0.7)  # Allow 30% tolerance
            
            self.logger.info(f"Generated {len(beats_list)} beats using pattern {pattern_type}")
            self.logger.info(f"Total narration words: {total_words} (target: {target_word_count}, min: {min_words})")
            
            # Log HOOK and CTA lines for inspection
            hook_beat = next((b for b in beats_list if b.get("type") == "HOOK"), None)
            cta_beat = next((b for b in beats_list if b.get("type") == "CTA"), None)
            if hook_beat:
                hook_text = hook_beat.get("text", "")[:100]  # First 100 chars
                self.logger.info(f"HOOK line: {hook_text}...")
            if cta_beat:
                cta_text = cta_beat.get("text", "")
                self.logger.info(f"CTA line: {cta_text}")
            
            # If text is too short, try regenerating once
            if total_words < min_words:
                self.logger.warning(
                    f"Story text too short ({total_words} words < {min_words} min). "
                    f"Regenerating once with emphasis on word count..."
                )
                
                # Regenerate with stronger word count emphasis
                retry_prompt = prompt + f"\n\nIMPORTANT: Previous attempt was too short ({total_words} words). You MUST generate at least {target_word_count} words total across all beats. Expand descriptions, add more detail to CLASH/TWIST beats, and ensure CTA is substantial."
                
                try:
                    retry_response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert at creating viral, emotional stories for YouTube Shorts. Generate beat-based narratives that maximize engagement and emotional impact. Always output valid JSON only.",
                            },
                            {"role": "user", "content": retry_prompt},
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.85,
                        max_tokens=2000,
                    )
                    
                    retry_text = retry_response.choices[0].message.content.strip()
                    if retry_text.startswith("```"):
                        retry_text = retry_text.split("```")[1]
                        if retry_text.startswith("json"):
                            retry_text = retry_text[4:]
                        retry_text = retry_text.strip()
                    
                    retry_beats_data = json.loads(retry_text)
                    retry_beats_list = retry_beats_data.get("beats", [])
                    retry_total_words = sum(len(beat.get("text", "").split()) for beat in retry_beats_list)
                    
                    if retry_total_words >= min_words:
                        self.logger.info(f"Regeneration successful: {retry_total_words} words (target: {target_word_count})")
                        beats_list = retry_beats_list
                        pattern_type = retry_beats_data.get("pattern_type", pattern_type)
                    else:
                        self.logger.warning(f"Regeneration still too short ({retry_total_words} words). Using original beats.")
                except Exception as e:
                    self.logger.warning(f"Regeneration failed: {e}. Using original beats.")

            # Convert beats to StoryScript
            script = self._build_script_from_beats(beats_list, topic_hint, style, pattern_type, target_word_count)
            return script, pattern_type

        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse JSON from LLM: {e}")
            return None, None
        except Exception as e:
            self.logger.warning(f"Beat-based generation failed: {e}")
            return None, None

    def _build_script_from_beats(
        self, beats_list: list[dict], title: str, style: str, pattern_type: str, target_word_count: Optional[int] = None
    ) -> StoryScript:
        """
        Build StoryScript from beats.

        Args:
            beats_list: List of beat dictionaries
            title: Story title
            style: Story style
            pattern_type: Pattern type (A, B, or C)

        Returns:
            StoryScript object
        """
        # Parse beats into Beat objects
        beats = []
        for beat_dict in beats_list:
            try:
                beat = Beat(
                    type=beat_dict.get("type", "CONTEXT"),
                    speaker=beat_dict.get("speaker", "narrator"),
                    target_emotion=beat_dict.get("target_emotion", "shock"),
                    text=beat_dict.get("text", ""),
                )
                beats.append(beat)
            except Exception as e:
                self.logger.warning(f"Failed to parse beat: {e}, skipping")
                continue

        if not beats:
            raise ValueError("No valid beats to build script from")

        # Ensure CTA is at the end
        cta_beats = [b for b in beats if b.type == "CTA"]
        non_cta_beats = [b for b in beats if b.type != "CTA"]
        beats = non_cta_beats + cta_beats

        # Group beats into scenes
        # Strategy: Group consecutive beats by type or create new scene for major transitions
        scenes = []
        current_scene_beats = []
        scene_id = 1

        for i, beat in enumerate(beats):
            # Start new scene for major beat types or when we have enough beats
            should_start_new_scene = (
                beat.type in ["HOOK", "CLASH", "TWIST", "CTA"]
                or len(current_scene_beats) >= 2
            )

            if should_start_new_scene and current_scene_beats:
                # Create scene from current beats
                scene = self._create_scene_from_beats(current_scene_beats, scene_id, style)
                scenes.append(scene)
                scene_id += 1
                current_scene_beats = [beat]
            else:
                current_scene_beats.append(beat)

        # Add final scene
        if current_scene_beats:
            scene = self._create_scene_from_beats(current_scene_beats, scene_id, style)
            scenes.append(scene)

        # Generate logline from first beat
        logline = self._generate_logline_from_beats(beats, style)

        # Calculate and log word distribution by beat type
        word_counts_by_type = {}
        for beat in beats:
            beat_type = beat.type
            word_count = len(beat.text.split())
            if beat_type not in word_counts_by_type:
                word_counts_by_type[beat_type] = 0
            word_counts_by_type[beat_type] += word_count
        
        total_narration_words = sum(word_counts_by_type.values())
        
        # Log word distribution
        self.logger.info(f"Word distribution by beat type:")
        for beat_type, count in word_counts_by_type.items():
            percentage = (count / total_narration_words * 100) if total_narration_words > 0 else 0
            self.logger.info(f"  {beat_type}: {count} words ({percentage:.1f}%)")
        
        if target_word_count:
            self.logger.info(f"Total narration words: {total_narration_words} (target: {target_word_count})")
            if total_narration_words < target_word_count * 0.7:
                self.logger.warning(f"⚠️  Story is significantly shorter than target ({total_narration_words} < {int(target_word_count * 0.7)})")

        script = StoryScript(
            title=title,
            logline=logline,
            scenes=scenes,
        )

        # Count narration lines across all scenes
        total_narration_lines = sum(len(scene.narration) for scene in scenes)
        
        self.logger.info(
            f"Built script with {len(scenes)} scenes, {len(beats)} beats, {total_narration_lines} narration lines (pattern: {pattern_type})"
        )
        return script

    def _create_scene_from_beats(self, beats: list[Beat], scene_id: int, style: str) -> Scene:
        """
        Create a Scene from a list of beats.

        Args:
            beats: List of Beat objects
            scene_id: Scene identifier
            style: Story style

        Returns:
            Scene object
        """
        # Determine scene description from beat types
        beat_types = [b.type for b in beats]
        primary_type = beat_types[0] if beat_types else "CONTEXT"

        # Build scene description
        camera_map = {
            "HOOK": "extreme close-up",
            "TRIGGER": "medium shot",
            "CONTEXT": "wide shot",
            "CLASH": "close-up",
            "TWIST": "dramatic close-up",
            "CTA": "medium shot",
        }

        camera = camera_map.get(primary_type, "medium shot")
        scene_description = f"{camera.title()} framing. {primary_type.lower().replace('_', ' ')} scene. {style.replace('_', ' ').title()} setting, cinematic, ultra-detailed."

        # Convert beats to narration lines
        narration_lines = []
        character_actions = []

        for beat in beats:
            if beat.speaker == "narrator":
                # Split text into sentences for narration lines
                sentences = re.split(r"[.!?]+", beat.text)
                sentences = [s.strip() for s in sentences if s.strip()]

                for sentence in sentences:
                    if sentence:
                        narration_lines.append(
                            NarrationLine(
                                text=sentence,
                                emotion=self._map_emotion_from_target(beat.target_emotion),
                                scene_id=scene_id,
                            )
                        )
            else:
                # Character action (dialogue will be handled separately)
                character_actions.append(
                    CharacterAction(
                        character_id=beat.speaker,
                        action_description=beat.text,
                        emotion=self._map_emotion_from_target(beat.target_emotion),
                    )
                )

        # Ensure at least one narration line
        if not narration_lines:
            # Use first beat text as narration
            narration_lines.append(
                NarrationLine(
                    text=beats[0].text if beats else "Scene continues...",
                    emotion="dramatic",
                    scene_id=scene_id,
                )
            )

        return Scene(
            scene_id=scene_id,
            description=scene_description,
            narration_lines=narration_lines,
            character_actions=character_actions,
        )

    def _map_emotion_from_target(self, target_emotion: str) -> str:
        """Map target emotion to narration emotion."""
        emotion_map = {
            "rage": "dramatic",
            "injustice": "emotional",
            "shock": "dramatic",
            "disgust": "dramatic",
        }
        return emotion_map.get(target_emotion.lower(), "dramatic")

    def _generate_logline_from_beats(self, beats: list[Beat], style: str) -> str:
        """Generate logline from beats."""
        if not beats:
            return "A dramatic story with an unexpected twist."

        # Use HOOK beat text as logline base
        hook_beats = [b for b in beats if b.type == "HOOK"]
        if hook_beats:
            hook_text = hook_beats[0].text
            # Truncate to ~60 chars
            if len(hook_text) > 60:
                hook_text = hook_text[:57] + "..."
            return hook_text

        # Fallback to first beat
        first_text = beats[0].text
        if len(first_text) > 60:
            first_text = first_text[:57] + "..."
        return first_text

