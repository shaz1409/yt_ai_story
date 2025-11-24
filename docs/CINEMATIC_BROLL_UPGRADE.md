# Cinematic B-Roll Generation Upgrade

**Date:** 2025-11-23  
**Status:** ✅ Implemented

---

## Overview

B-roll generation has been upgraded to produce **cinematic, contextual, story-specific real-life camera shots** that look like professional film footage. The system generates 4-6 photorealistic B-roll scenes per video with contextual prompts based on niche, style, and emotion.

---

## Key Features

### 1. B-Roll Categories

**Four Categories:**
- `establishing_scene`: Wide angle establishing shots (courtroom hallway, house driveway, etc.)
- `mid_shot`: Medium shots with natural framing
- `emotional_closeup`: Close-up detail shots with shallow depth of field
- `dramatic_insert`: Dramatic insert shots (hands gripping chair, judge slamming gavel, etc.)

### 2. Contextual Prompts

**Courtroom Drama:**
- Establishing: "wide angle shot of courtroom hallway, warm lighting, empty corridor"
- Mid-shot: "judge's bench close-up, gavel on desk, formal courtroom setting"
- Emotional closeup: "defendant's hands gripping chair, tension visible, shallow focus"
- Dramatic insert: "judge slamming gavel, dramatic motion blur, cinematic lighting"

**Relationship Drama:**
- Establishing: "suburban house driveway, evening lighting, quiet neighborhood"
- Mid-shot: "living room with tension, soft shadows, domestic setting"
- Emotional closeup: "phone screen showing text message, close-up, shallow depth of field"
- Dramatic insert: "door slamming shut, dramatic motion, cinematic framing"

**Crime/Injustice:**
- Establishing: "police station exterior, harsh lighting, urban setting"
- Mid-shot: "police interview room, harsh top lighting, sterile environment"
- Emotional closeup: "handcuffs on table, close-up detail, shallow focus"
- Dramatic insert: "evidence bag being sealed, dramatic motion, cinematic lighting"

### 3. Photorealistic Style

**Prompt Enhancement:**
- "cinematic real photograph, shallow depth of field, 35mm lens, natural lighting, film grain"
- "8k resolution, vertical format 9:16"
- Emotion-aware lighting (harsh for rage, soft for sadness, dramatic for shock)

### 4. Ken Burns Effect

**Subtle Animation:**
- All B-roll images have subtle zoom/pan effect (Ken Burns)
- 10% zoom in over clip duration (100% → 110%)
- Smooth, cinematic movement
- Applied to all B-roll clips in timeline

### 5. Fallback Logic

**Three-Tier Fallback:**
1. **Primary**: HF Endpoint generates photorealistic B-roll
2. **Secondary**: Stock placeholder from `assets/broll_fallbacks/` (if available)
3. **Tertiary**: Generated placeholder with category label

---

## Implementation Details

### Updated Files

1. **`app/models/schemas.py`**:
   - Added `BrollScene` model with `category`, `prompt`, `timing_hint`, `scene_id`
   - Updated `VideoScene` to include `b_roll_scenes: list[BrollScene]`
   - Updated `VideoPlan` to include `b_roll_scenes: list[BrollScene]` (4-6 scenes)

2. **`app/services/video_plan_engine.py`**:
   - Added `_generate_cinematic_broll_scenes()`: Generates 4-6 contextual B-roll scenes
   - Added `_build_contextual_broll_prompts()`: Builds niche/style/emotion-specific prompts
   - Distributes B-roll scenes evenly across video duration
   - Associates B-roll scenes with video scenes

3. **`app/services/hf_endpoint_client.py`**:
   - Added `generate_broll_scene()`: Dedicated method for B-roll generation
   - Enhances prompt with photorealistic style
   - Supports `realism_level` parameter ("high", "ultra", "photoreal")

4. **`app/services/video_renderer.py`**:
   - Added `_generate_cinematic_broll()`: Generates all B-roll scenes with fallback logic
   - Added `_get_broll_fallback()`: Retrieves stock placeholders from `assets/broll_fallbacks/`
   - Added `_create_placeholder_broll()`: Creates placeholder with category label
   - Added `_apply_ken_burns_effect()`: Applies subtle zoom/pan to static images
   - Updated all B-roll clip creation to use Ken Burns effect
   - Integrated B-roll into video timeline with crossfade transitions

---

## B-Roll Generation Flow

```
VideoPlan Creation
  ↓
Generate 4-6 BrollScene objects
  ├─ Category: establishing_scene, mid_shot, emotional_closeup, dramatic_insert
  ├─ Contextual prompt based on niche/style/emotion
  ├─ Timing hint (distributed across video duration)
  └─ Associated scene_id
  ↓
Video Rendering
  ↓
For each BrollScene:
  ├─ Try HF Endpoint (generate_broll_scene)
  ├─ If fails → Try fallback from assets/broll_fallbacks/
  └─ If fails → Create placeholder
  ↓
Apply Ken Burns effect (subtle zoom/pan)
  ↓
Insert into timeline with crossfade transitions
```

---

## Ken Burns Effect

**Implementation:**
- Subtle zoom: 100% → 110% over clip duration
- Linear interpolation for smooth movement
- Applied to all B-roll image clips
- Maintains 1080x1920 aspect ratio
- Falls back gracefully if effect fails

**Usage:**
```python
img_clip = ImageClip(str(image_path)).set_duration(duration)
img_clip = img_clip.resize((1080, 1920))
img_clip = self._apply_ken_burns_effect(img_clip, duration)  # Apply zoom/pan
```

---

## Fallback System

**Tier 1: HF Endpoint (Primary)**
- Uses `HFEndpointClient.generate_broll_scene()`
- Photorealistic quality
- Contextual to story

**Tier 2: Stock Placeholders (Secondary)**
- Location: `assets/broll_fallbacks/`
- Files: `{category}.png` or `{category}.jpg`
- Generic fallback: `generic.png` or `generic.jpg`
- Copied to output directory if found

**Tier 3: Generated Placeholder (Tertiary)**
- Created on-the-fly with category label
- Professional gradient background
- Category name and prompt preview
- Ensures video always has visuals

---

## File Structure

```
outputs/
  └── {episode_id}/
      ├── images/              # Scene visuals
      ├── broll/               # Cinematic B-roll scenes
      │   ├── broll_establishing_scene_00.png
      │   ├── broll_mid_shot_01.png
      │   ├── broll_emotional_closeup_02.png
      │   └── broll_dramatic_insert_03.png
      └── ...

assets/
  └── broll_fallbacks/         # Stock placeholder images (optional)
      ├── establishing_scene.png
      ├── mid_shot.png
      ├── emotional_closeup.png
      ├── dramatic_insert.png
      └── generic.png
```

---

## Configuration

**No new configuration required:**
- Uses existing `HF_ENDPOINT_URL` and `HF_ENDPOINT_TOKEN`
- B-roll generation is automatic
- Fallback system works without additional setup

**Optional:**
- Add stock placeholders to `assets/broll_fallbacks/` for better fallbacks
- Customize prompts in `_build_contextual_broll_prompts()` for specific niches

---

## Backward Compatibility

✅ **Fully backward compatible:**
- Legacy `b_roll_prompts` field still works
- Old scene visuals continue to function
- B-roll scenes are optional (empty list if not generated)
- Existing videos continue to work unchanged

---

## Testing

**To test:**
```bash
python run_full_pipeline.py --topic "test story" --style courtroom_drama --preview
```

**Expected behavior:**
- `VideoPlan.b_roll_scenes` contains 4-6 `BrollScene` objects
- B-roll images generated in `outputs/.../broll/`
- Images are photorealistic with contextual prompts
- Ken Burns effect applied to all B-roll clips
- Smooth crossfade transitions between clips
- Fallback placeholders used if HF fails

---

## Future Enhancements

1. **LLM-Generated Prompts**: Use LLM to generate more creative B-roll prompts
2. **Motion Blur**: Add motion blur to dramatic_insert shots
3. **Color Grading**: Apply niche-specific color grading (warm for courtroom, cool for crime)
4. **Multiple Variants**: Generate multiple variants per category and select best
5. **Stock Library**: Build a library of high-quality stock B-roll images

---

## Notes

- B-roll scenes are distributed evenly across video duration
- Categories rotate to ensure variety (establishing → mid → closeup → insert → repeat)
- Emotion-aware prompts enhance visual tone (harsh lighting for rage, soft for sadness)
- Ken Burns effect is subtle (10% zoom) to avoid distraction
- All B-roll images are 1080x1920 (vertical format) for YouTube Shorts

