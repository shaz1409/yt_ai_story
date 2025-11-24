# Character Talking Clips Feature

**Date:** 2025-11-23  
**Status:** ✅ Implemented

---

## Overview

Characters now speak selected dialogue lines using their own generated AI voices. The narrator continues doing 70-80% of the storytelling, with character clips inserted between narration segments.

---

## Implementation Summary

### 1. Schema Updates (`app/models/schemas.py`)

**New Models:**
- `CharacterVoiceProfile`: Detailed voice profile with gender, age_range, tone_adjectives, example_text
- `CharacterSpokenLine`: Represents a line that should be spoken by a character (not narrator)

**Updated Models:**
- `Character`: Added `detailed_voice_profile: Optional[CharacterVoiceProfile]` field
- `VideoScene`: Added `character_spoken_lines: list[CharacterSpokenLine]` field
- `VideoPlan`: Added `character_spoken_lines: list[CharacterSpokenLine]` field

### 2. Character Engine Updates (`app/services/character_engine.py`)

**New Method:**
- `_generate_detailed_voice_profile()`: Generates a `CharacterVoiceProfile` for each character with:
  - Gender (extracted from appearance or role-based default)
  - Age range (from appearance or template)
  - Tone adjectives (from personality traits)
  - Example text (role-specific reference text)

**Updated Method:**
- `_generate_character()`: Now calls `_generate_detailed_voice_profile()` and sets `character.detailed_voice_profile`

### 3. TTS Client Updates (`app/services/tts_client.py`)

**New Method:**
- `generate_character_voice()`: Generates character voice audio using detailed voice profile
  - Maps voice profile to ElevenLabs or OpenAI TTS voice ID
  - Uses gender, age, and tone adjectives to select appropriate voice
  - Falls back to default voice if mapping fails

**New Helper:**
- `_map_detailed_voice_profile_to_id()`: Maps `CharacterVoiceProfile` to provider-specific voice ID
  - OpenAI: Uses voices like "onyx" (deep male), "nova" (young female), "shimmer" (mature female)
  - ElevenLabs: Uses default voice_id from settings (can be enhanced with voice cloning)

### 4. Video Plan Engine Updates (`app/services/video_plan_engine.py`)

**New Method:**
- `_sample_character_spoken_lines()`: Samples 2-4 dialogue lines for character speech
  - Filters out narrator dialogue
  - Scores lines by emotion (prioritizes high-emotion lines: angry, rage, shocked, tense)
  - Selects top N lines (2-4) based on emotion scores
  - Converts to `CharacterSpokenLine` objects with timing hints

**Updated Method:**
- `create_video_plan()`: Now calls `_sample_character_spoken_lines()` and sets `video_plan.character_spoken_lines`

### 5. Character Video Engine Updates (`app/services/character_video_engine.py`)

**Updated Method:**
- `generate_talking_head_clip()`: Now accepts `emotion` parameter
  - Uses HF FLUX character image as base
  - Falls back to Ken Burns + subtle mouth-movement effect if direct talking-head fails
  - Logs emotion for better visual treatment

### 6. Video Renderer Updates (`app/services/video_renderer.py`)

**New Methods:**
- `_generate_character_voice_clips()`: Generates character voice audio for all `character_spoken_lines`
  - Uses `TTSClient.generate_character_voice()` with detailed voice profile
  - Falls back to simple `voice_profile` if `detailed_voice_profile` not available
  - Returns mapping: `line_index -> audio_path`

- `_generate_character_talking_head_clips()`: Generates talking-head video clips for character spoken lines
  - Uses character voice audio clips
  - Calls `CharacterVideoEngine.generate_talking_head_clip()` for each line
  - Returns mapping: `(scene_id, character_id) -> clip_path`

- `_build_timeline_with_character_clips()`: Builds video timeline with character clips inserted
  - Timeline: Narration → Character Clip → Narration → Character Clip → ...
  - Splits narration audio into segments
  - Inserts character talking-head clips at appropriate timestamps
  - Uses scene visuals for narration segments
  - Adds crossfade transitions between segments

- `_build_composite_audio()`: Builds composite audio timeline
  - Combines narration audio segments with character voice audio clips
  - Ensures smooth transitions
  - Matches total duration

**Updated Methods:**
- `render()`: Now generates character voice clips and talking-head clips if `character_spoken_lines` exist
- `_extract_narration_text()`: Excludes character spoken lines from narration text
- `_compose_video()`: Now accepts `character_voice_clips` parameter and uses timeline builder when character clips exist

---

## Pipeline Flow

### Before (Narrator-Only):
```
Story → VideoPlan → Narration Audio → Scene Visuals → Final Video
```

### After (With Character Clips):
```
Story → VideoPlan
  ├─ Narration Lines → Narration Audio
  └─ Character Spoken Lines (2-4 sampled)
      ├─ Character Voice Audio (via TTSClient.generate_character_voice)
      └─ Talking-Head Video Clips (via CharacterVideoEngine)
      
Timeline Builder:
  Narration Segment → Character Clip → Narration Segment → Character Clip → ...
  
Final Video: Composite Audio + Video Timeline
```

---

## Configuration

**Character Voice Selection:**
- Uses `CharacterVoiceProfile` (gender, age_range, tone_adjectives)
- Maps to ElevenLabs or OpenAI TTS voices
- Falls back to default voice if mapping fails

**Sampling Logic:**
- Samples 2-4 dialogue lines per video
- Prioritizes high-emotion lines (angry, rage, shocked, tense)
- Filters out narrator dialogue

**Timeline Distribution:**
- Narrator: 70-80% of total duration
- Characters: 20-30% of total duration
- Smooth crossfade transitions (0.5s) between segments

---

## Backward Compatibility

✅ **Fully backward compatible:**
- All new fields are optional (`Optional[...]` or `default_factory=list`)
- If `character_spoken_lines` is empty or missing, pipeline falls back to narrator-only mode
- Existing narrator-only videos continue to work unchanged
- Old dialogue-based talking heads still work as fallback

---

## Files Modified

1. ✅ `app/models/schemas.py` - Added `CharacterVoiceProfile`, `CharacterSpokenLine`, updated `Character`, `VideoScene`, `VideoPlan`
2. ✅ `app/services/character_engine.py` - Added `_generate_detailed_voice_profile()`
3. ✅ `app/services/tts_client.py` - Added `generate_character_voice()`, `_map_detailed_voice_profile_to_id()`
4. ✅ `app/services/video_plan_engine.py` - Added `_sample_character_spoken_lines()`
5. ✅ `app/services/character_video_engine.py` - Updated `generate_talking_head_clip()` to accept `emotion`
6. ✅ `app/services/video_renderer.py` - Added timeline building and composite audio methods

---

## Testing

**To test:**
```bash
python run_full_pipeline.py --topic "test story" --style courtroom_drama --preview
```

**Expected behavior:**
- VideoPlan should have `character_spoken_lines` (2-4 lines)
- Character voice audio files generated in `outputs/.../character_audio/`
- Talking-head clips generated in `outputs/.../talking_heads/`
- Final video alternates between narration segments and character clips
- Composite audio includes both narration and character voices

---

## Future Enhancements

1. **Voice Cloning**: Use ElevenLabs voice cloning API to create unique voices per character
2. **Lip Sync**: Add lip-sync to talking-head clips for more realistic character speech
3. **Emotion-Aware Visuals**: Adjust character facial expressions based on emotion
4. **Dynamic Sampling**: Adjust number of character lines based on video duration or story type

---

## Notes

- Character clips use existing HF FLUX character images as base
- Falls back to scene visuals if talking-head generation fails
- All character voice generation uses the same TTS provider as narration (ElevenLabs or OpenAI)
- Timeline builder ensures smooth transitions with crossfades
- Composite audio matches total video duration

