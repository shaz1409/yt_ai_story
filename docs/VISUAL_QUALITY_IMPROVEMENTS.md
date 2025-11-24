# Visual Quality Improvements

**Date:** 2025-11-22  
**Status:** ✅ Complete

---

## Overview

Upgraded visual quality using the Hugging Face FLUX endpoint with emotion-aware prompts, clear separation of image types, HOOK-first visual bias, and improved b-roll distribution.

---

## Changes Implemented

### 1. Clear Separation of Image Types

**Files:**
- `app/services/hf_endpoint_client.py`
- `app/services/character_video_engine.py`
- `app/services/video_renderer.py`

#### Image Type Enumeration
- Introduced `image_type` parameter: `"character_portrait"` | `"scene_broll"`

#### Character Portrait Prompts
- **Focus:** Close-up portrait, facial expression, clothing, age, gender
- **Lighting:** Neutral or slightly dramatic
- **Composition:** Single subject
- **Example:** "Close-up portrait, middle-aged judge, authoritative expression, neutral lighting, single subject, photorealistic, 4k quality"

#### Scene B-roll Prompts
- **Focus:** Wide or medium shots of environment (courtroom, hallway, etc.)
- **Composition:** Cinematic, shallow depth of field, over-the-shoulder shots
- **Example:** "Angry courtroom, teenage defendant smirking, judge stunned, cinematic, 4k, realistic, dramatic lighting"

#### Logging
- Logs `image_type` for each generation
- Logs truncated prompt (first 120 chars)
- Logs success/failure and round-trip latency

---

### 2. Emotion-Aware Prompts

**File:** `app/services/video_renderer.py` (`_build_emotion_aware_broll_prompt`)

#### Metadata Integration
Uses metadata fields:
- `niche` (courtroom, relationship_drama, etc.)
- `primary_emotion` (rage, shock, injustice, disgust)
- `secondary_emotion` (optional)
- `beat_type` (HOOK, TRIGGER, CONTEXT, CLASH, TWIST, CTA)

#### Emotion-to-Visual Mapping

| Emotion | Visual Tone |
|---------|-------------|
| `rage` / `anger` | Harsh lighting, tense atmosphere, visible anger, clenched jaws, raised voices |
| `injustice` | Uneasy atmosphere, people avoiding eye contact, uncomfortable expressions, moral conflict |
| `shock` | Wide eyes, gasps, hands over mouth, frozen courtroom, stunned expressions |
| `disgust` | Uneasy body language, people avoiding eye contact, uncomfortable expressions, distaste |
| `sadness` | Somber lighting, emotional expressions, tears, downcast faces |
| `fear` | Tense atmosphere, worried expressions, defensive body language |
| `satisfaction` | Triumphant atmosphere, just resolution, relieved expressions |

#### Prompt Structure
```
[emotion adjective] [niche description], [beat-specific moment], [visual tone], [composition], quality tags
```

**Example for courtroom HOOK:**
```
Angry courtroom with wooden benches, opening moment attention-grabbing scene, harsh lighting tense atmosphere visible anger, cinematic over-the-shoulder shot, 4k realistic dramatic lighting, vertical format 9:16
```

#### Beat-Specific Composition
- **HOOK/CLASH:** Cinematic, over-the-shoulder shot, dramatic framing
- **TWIST:** Cinematic, wide shot revealing the twist
- **Others:** Cinematic, shallow depth of field

---

### 3. HOOK-First Visual Bias

**File:** `app/services/video_renderer.py` (`_generate_scene_visuals`)

#### Extra B-roll Generation
- For first scene (HOOK): Generates **extra b-roll variant**
- Uses `_build_hook_variant_prompt` for more extreme/triggering prompt
- Variant saved as `scene_01_variant.png`
- Logs: `"HOOK visual prompt: ..."`

#### Hook Variant Prompt
- Focuses on "most triggering visual"
- Emphasizes "extreme facial expressions"
- Uses "harsh dramatic lighting"
- Example: `"Extreme shock moment, shocking opening scene, most triggering visual, extreme facial expressions, harsh dramatic lighting, cinematic close-up on emotion"`

#### Usage
- Primary HOOK image used in timeline
- Variant available for future use or quick cuts
- Can be used in first 3-5 seconds for visual variety

---

### 4. FLUX Endpoint Usage + Fallbacks

**File:** `app/services/hf_endpoint_client.py`

#### Endpoint Priority
- **Primary:** HF Inference Endpoint (FLUX) when `HF_ENDPOINT_URL` + `HF_ENDPOINT_TOKEN` are set
- **Fallback:** Old Inference API / placeholders if endpoint fails

#### Enhanced Logging
For each generation:
- ✅ Logs `image_type` (character_portrait or scene_broll)
- ✅ Logs truncated prompt (first 120 chars)
- ✅ Logs success vs failure
- ✅ Logs round-trip latency

**Example log output:**
```
Using HF endpoint (FLUX) for image generation: https://...
Image type: scene_broll
Prompt: Angry courtroom, teenage defendant smirking as the verdict is read, judge stunned, family in tears, cinematic, 4k, realistic, dramatic lighting...
✅ Successfully generated scene_broll image: outputs/.../scene_01.png
   Round-trip latency: 3.45s
```

---

### 5. B-roll Distribution in Timeline

**File:** `app/services/video_renderer.py` (`_compose_video`)

#### Narration-Only Stretches
- **Rule:** Avoid holding same still image for > 3-4 seconds
- **Implementation:** 
  - If scene duration > 3.5s, split into multiple cuts
  - Each cut max 3.5s duration
  - Quick fade transitions between cuts (0.2s)
- **HOOK scenes:** Use variant image for first cut if available

#### Dialogue-Heavy Moments
- **Rule:** Alternate TH → BROLL → TH (not just TH for whole duration)
- **Implementation:**
  - Pattern: BROLL → TH → BROLL → TH → ...
  - B-roll segments max 3.5s each
  - Quick fade transitions (0.3s)
  - HOOK scenes: Use variant for first b-roll segment

#### Quick Cuts for HOOK
- First 3-5 seconds of video prioritize visual variety
- If HOOK variant exists, use it in first cut/segment
- Multiple quick cuts in first 3-5 seconds if scene is long

#### Example Timeline

**Scene with talking heads:**
```
0.0s - 2.0s: B-roll (HOOK variant if available)
2.0s - 4.5s: Talking-head clip
4.5s - 6.5s: B-roll
6.5s - 9.0s: Talking-head clip
9.0s - 11.0s: B-roll
```

**Narration-only scene (long):**
```
0.0s - 3.5s: B-roll cut 1 (HOOK variant if available)
3.5s - 7.0s: B-roll cut 2
7.0s - 10.5s: B-roll cut 3
```

---

## Files Modified

1. ✅ `app/services/hf_endpoint_client.py`
   - Added `image_type` parameter to `generate_image()`
   - Enhanced logging (image_type, prompt preview, latency)
   - Added `time` import for latency tracking

2. ✅ `app/services/character_video_engine.py`
   - Updated `_build_character_face_prompt()` for character portrait focus
   - Updated `_generate_character_image()` to pass `image_type="character_portrait"`

3. ✅ `app/services/video_renderer.py`
   - Updated `_generate_scene_visuals()` to use emotion-aware prompts
   - Added `_build_emotion_aware_broll_prompt()` with emotion mapping
   - Added `_build_hook_variant_prompt()` for HOOK scenes
   - Added `_detect_beat_type_from_scene()` heuristic
   - Updated `_generate_image()` to pass `image_type="scene_broll"`
   - Updated `_compose_video()` for improved b-roll distribution:
     - Split long narration-only scenes into multiple cuts (max 3.5s each)
     - Alternate TH → BROLL → TH for dialogue-heavy scenes
     - Use HOOK variant in first cut/segment if available

---

## Expected Improvements

### Before
- Generic prompts not tied to emotions or beats
- Single image type for all generation
- Long static images (10+ seconds)
- Talking-head clips dominate entire scene duration
- No visual variety in HOOK scenes

### After
- **Emotion-aware prompts** that match story tone (rage, shock, injustice)
- **Clear separation** between character portraits and scene b-roll
- **Quick cuts** for narration-only scenes (max 3.5s per cut)
- **Alternating TH/BROLL** for dialogue-heavy scenes
- **HOOK-first bias** with extra variant generation
- **Comprehensive logging** for debugging and quality inspection

---

## Testing

### Manual Testing Checklist

- [ ] Generate video with HOOK scene
- [ ] Verify HOOK variant image is generated (`scene_01_variant.png`)
- [ ] Check logs show "HOOK visual prompt: ..."
- [ ] Verify emotion-aware prompts match metadata (rage, shock, etc.)
- [ ] Check narration-only scenes are split into multiple cuts (if > 3.5s)
- [ ] Verify dialogue-heavy scenes alternate TH → BROLL → TH
- [ ] Check logs show image_type, prompt preview, latency
- [ ] Verify character portraits use "character_portrait" type
- [ ] Verify scene b-roll uses "scene_broll" type

### Example Test Command

```bash
python run_full_pipeline.py --topic "teen laughs in court" --style courtroom_drama --duration-target-seconds 60 --preview
```

Check logs for:
- "Image type: scene_broll"
- "HOOK visual prompt: ..."
- "Splitting into X cuts (max 3.5s per cut)"
- "Alternating TH/BROLL..."
- "Round-trip latency: X.XXs"

---

## Configuration

### Required Environment Variables

```bash
HF_ENDPOINT_URL=https://your-endpoint-url
HF_ENDPOINT_TOKEN=your-token
```

### Optional Settings

- `use_talking_heads`: Enable/disable talking-head generation (default: True)
- `max_talking_head_lines_per_video`: Max talking-head clips per video (default: 3)

---

## Summary

✅ **All requirements implemented:**
- Clear separation of image types (character_portrait vs scene_broll)
- Emotion-aware prompts using metadata (niche, emotions, beat types)
- HOOK-first visual bias (extra b-roll variant)
- FLUX endpoint usage with enhanced logging
- Improved b-roll distribution (quick cuts, TH/BROLL alternation)

**Ready for testing and refinement!**

