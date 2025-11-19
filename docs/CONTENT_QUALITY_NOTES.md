# Content Quality Notes

## Overview

This document summarizes the content quality improvements made to ensure videos are 50-65 seconds long with emotional, ragebait-style content suitable for viral YouTube Shorts.

## Timing & Duration

### Target Word Counts
- **For 60s videos**: Target 120-150 words of narration total
- **Per scene (4 scenes)**: ~30-40 words per scene
- **Speech rate**: ~2.2 words/second
- **Dialogue**: Additional 8-12 dialogue lines (1-2 sentences each) contribute ~15-25 seconds

### Implementation
- `story_rewriter.py`: Uses LLM to expand narration from short raw text to target word count
- `_expand_narration_with_llm()`: Generates emotional, dramatic narration for each scene role
- Falls back to heuristic expansion if LLM unavailable
- Audio is looped/extended if narration is still too short (in `video_renderer.py`)

### Duration Logic
- If audio < 90% of target: Loop audio to fill target duration
- If audio > 110% of target: Trim to target duration
- Otherwise: Use audio as-is (±10% tolerance)

## Story Arc & Emotional Content

### Narrative Arc Structure
1. **Hook**: Shocking opening that grabs attention (first 3-5 seconds)
2. **Setup**: Building tension, setting up conflict
3. **Conflict**: Explosive confrontation with high emotional stakes
4. **Twist**: Dramatic unexpected reveal
5. **Resolution**: Satisfying conclusion with clear consequences

### Emotional Intensity
- **Courtroom Drama**: Focus on injustice, power dynamics, emotional consequences
- **Ragebait**: Maximize emotional polarity (shock, anger, injustice, humiliation)
- **Relationship Drama**: Emotional depth and personal stakes

### LLM Prompts
- `story_rewriter.py`: Generates expanded narration with emotional, dramatic language
- `llm_client.py`: Dialogue and metadata prompts emphasize:
  - Clear villains (cold judge, arrogant teen) and victims
  - High emotional stakes
  - Dramatic confrontation
  - YouTube-safe but emotionally sharp content

## Dialogue

### Requirements
- **Length**: 1-2 sentences max, speakable in 3-5 seconds
- **Character voices**:
  - Judge: Firm, authoritative, slightly cold
  - Defendant: Defensive, sarcastic, arrogant, or desperate
  - Lawyer: Urgent, trying to control chaos
- **Emotional focus**: Conflict, shock, injustice
- **Style**: Believable but heightened for drama

### Implementation
- `dialogue_engine.py`: Uses LLM via `llm_client.generate_dialogue()`
- Prompts emphasize scene role (hook/conflict/twist) and character personalities
- Falls back to heuristic dialogue if LLM fails

## Metadata (Titles, Descriptions, Hooks)

### Title Patterns (Courtroom Drama)
- "Judge's {action} Leaves {subject} {reaction}... Until This Happens"
- "{subject} {action} At Judge's Verdict, But The Room Goes Silent"
- "[SHOCKING] {subject} {action} In Court - What The Judge Did Next"

### Hook Lines
- First 3-5 seconds, maximum emotional impact
- Examples:
  - "Nobody expected what the judge did next..."
  - "The courtroom went silent when he laughed."
  - "This teen thought he could get away with anything."

### Tags
- **Niche**: courtroom, justice, trial, legal, court
- **Entities**: judge, teen, defendant, lawyer, verdict
- **Emotions**: karma, justice, unfair, shocking, consequences
- **Viral**: true story, viral, shorts, storytime

### Implementation
- `metadata_generator.py`: Uses LLM via `llm_client.generate_metadata()`
- Prompts include title patterns and emotional framing
- Falls back to heuristic generation if LLM fails

## Placeholder Images

### When Used
- When Hugging Face API returns 410 (model gone) or other errors
- When no Hugging Face token is provided

### Design
- **Background**: Dark blue-gray gradient with blur effect
- **Text**: White, bold, centered, with shadow for readability
- **Content**: Cleaned scene description (removes camera/lighting metadata)
- **Layout**: Max 3 lines, 8 words per line, centered vertically

### Implementation
- `video_renderer.py`: `_create_placeholder_image()` creates professional placeholders
- `character_video_engine.py`: `_create_placeholder_character_image()` for character faces

## Configuration

### Environment Variables
- `OPENAI_API_KEY`: Required for LLM-based narration, dialogue, and metadata generation
- `HUGGINGFACE_TOKEN`: Optional, improves image generation rate limits

### Settings
- `use_llm_for_dialogue`: Default `True` (in `config.py`)
- `dialogue_model`: Default `"gpt-4o-mini"` (in `config.py`)
- `max_dialogue_lines_per_scene`: Default `2` (in `config.py`)
- `use_llm_for_metadata`: Default `True` (in `config.py`)

## Backward Compatibility

All changes are **additive and non-breaking**:
- Existing CLI flags unchanged
- Episode JSON schema unchanged
- Fallback to heuristics if LLM unavailable
- Existing video rendering pipeline unchanged

## Future Improvements

1. **Better image generation**: Consider alternative APIs (OpenAI DALL-E, Stability AI) if Hugging Face continues to fail
2. **Narration pacing**: Add pauses between scenes for better pacing
3. **Dialogue timing**: Better synchronization of dialogue with scene visuals
4. **A/B testing**: Test different title patterns and hook lines for engagement

