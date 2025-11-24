# Photorealistic Character Image Generation

**Date:** 2025-11-23  
**Status:** ✅ Implemented

---

## Overview

Character image generation has been upgraded to produce **highly realistic, human-like images** using Hugging Face FLUX.1-dev / Juggernaut XL / RealVis XL / Hyper-SDXL models. The system maintains consistent appearance for the same character across different shots using seed locking and character_id determinism.

---

## Key Features

### 1. Ultra-Realistic Prompts

**Photorealistic Style (default):**
- "ultra-realistic portrait of a human"
- "cinematic lighting, shallow depth of field, 50mm lens"
- "natural skin texture, detailed facial features"
- "Kodak Portra 400 film grain, Sony FX3 color grading"
- "8k resolution, sharp focus on eyes, soft bokeh background"

**Artistic Style (backward compatible):**
- Legacy prompts available when `image_style="artistic"`
- Maintains backward compatibility with existing videos

### 2. Personality → Appearance Mapping

**Age Mapping:**
- Experienced/authoritative → 50-70 years old
- Young/teen → 18-25 years old
- Professional/confident → 35-50 years old
- Default → 30-45 years old

**Gender Mapping:**
- Extracted from appearance or role-based defaults
- Supports diverse representation

**Expression Mapping:**
- Stern/authoritative → "serious, determined"
- Nervous/anxious → "worried, tense"
- Confident → "confident, composed"
- Defensive → "defensive, guarded"
- Default → "neutral, professional"

**Clothing Mapping:**
- Judge → "black judicial robes"
- Lawyer/Prosecutor → "professional business suit, formal attire"
- Defendant → "formal courtroom attire"
- Default → "professional attire"

### 3. Identity Persistence

**Seed Locking:**
- Character ID is hashed to generate a deterministic seed (0-4294967295)
- Same character_id → same seed → consistent appearance
- Uses MD5 hash of character_id for reproducibility

**Character Identity Embedding:**
- Seed is stored implicitly via character_id
- Multiple images of the same character maintain consistency
- No need for separate identity storage

### 4. Parameter Controls

**Available Parameters:**
- `seed`: Random seed for consistency (0-4294967295, auto-generated from character_id)
- `sharpness`: Sharpness level (1-10, default 8)
- `realism_level`: "high", "ultra", "photoreal" (default "ultra")
- `film_style`: "kodak_portra", "canon", "sony_fx3", "fuji" (default "kodak_portra")

**Configuration:**
- Set via `CHARACTER_IMAGE_STYLE` env var: "photorealistic" or "artistic"
- Default: "photorealistic"

### 5. File Organization

**New Location:**
- Character images saved to `outputs/characters/` for better organization
- Filename: `character_{character_id}_face.png`

**Backward Compatibility:**
- Also copied to `outputs/.../character_faces/` for legacy support
- Existing code continues to work

---

## Implementation Details

### Updated Files

1. **`app/services/character_video_engine.py`**:
   - `_build_character_face_prompt()`: Enhanced with photorealistic prompts and personality mapping
   - `generate_character_face_image()`: Added seed locking and parameter controls
   - `_generate_character_seed()`: Generates deterministic seed from character_id
   - `_generate_character_image()`: Accepts seed, sharpness, realism_level, film_style parameters
   - `ensure_character_assets()`: Saves to `outputs/characters/` directory
   - Added personality mapping methods:
     - `_map_personality_to_age()`
     - `_map_personality_to_gender()`
     - `_map_personality_to_ethnicity()`
     - `_map_personality_to_hair()`
     - `_map_personality_to_expression()`
     - `_map_personality_to_clothing()`

2. **`app/services/hf_endpoint_client.py`**:
   - `generate_image()`: Added seed, sharpness, realism_level, film_style parameters
   - Parameters are added to prompt for models that support them
   - Supports FLUX.1-dev, Juggernaut XL, RealVis XL, Hyper-SDXL

3. **`app/services/video_renderer.py`**:
   - Updated to use `character_image_style` from settings
   - Passes image_style to `ensure_character_assets()`

4. **`app/core/config.py`**:
   - Added `character_image_style: str = Field(default="photorealistic", ...)`
   - Configurable via `CHARACTER_IMAGE_STYLE` env var

---

## Usage

### Default (Photorealistic):
```python
# Character images are automatically generated with photorealistic style
# Uses seed locking for consistency
character_assets = character_video_engine.ensure_character_assets(
    video_plan, output_dir, style="courtroom_drama"
)
```

### Artistic Style (Legacy):
```python
# Set in .env:
# CHARACTER_IMAGE_STYLE=artistic

# Or in code:
character_assets = character_video_engine.ensure_character_assets(
    video_plan, output_dir, style="courtroom_drama", image_style="artistic"
)
```

### Custom Parameters:
```python
# Generate with custom parameters
character_video_engine._generate_character_image(
    prompt="...",
    output_path=Path("..."),
    seed=12345,  # Custom seed
    sharpness=9,  # Higher sharpness
    realism_level="photoreal",  # Maximum realism
    film_style="sony_fx3",  # Different film style
)
```

---

## Character Consistency

**How It Works:**
1. Character ID is hashed using MD5
2. Hash is converted to 32-bit integer seed (0-4294967295)
3. Same character_id → same seed → consistent appearance
4. Multiple images of the same character maintain visual consistency

**Example:**
```python
character_id = "judge_abc123"
seed = _generate_character_seed(character_id)  # Always same seed for same ID
# Result: Same character appearance across all shots
```

---

## Model Support

**Supported Models:**
- FLUX.1-dev (recommended)
- Juggernaut XL
- RealVis XL
- Hyper-SDXL

**Parameter Handling:**
- Parameters are added to prompt text for maximum compatibility
- Some endpoints may support direct parameter fields (can be configured)
- Falls back gracefully if parameters are not supported

---

## Backward Compatibility

✅ **Fully backward compatible:**
- Legacy prompts available via `image_style="artistic"`
- Old character images in `character_faces/` still work
- New images are also copied to legacy location
- Existing videos continue to work unchanged

---

## Configuration

**Environment Variables:**
```bash
# Character image style
CHARACTER_IMAGE_STYLE=photorealistic  # or "artistic"
```

**Default Settings:**
- Style: "photorealistic"
- Sharpness: 8/10
- Realism: "ultra"
- Film: "kodak_portra"
- Seed: Auto-generated from character_id

---

## File Structure

```
outputs/
  ├── characters/              # New: Photorealistic character images
  │   ├── character_judge_abc123_face.png
  │   └── character_defendant_xyz789_face.png
  └── {episode_id}/
      └── character_faces/     # Legacy: Also copied here for compatibility
          ├── character_judge_abc123_face.png
          └── character_defendant_xyz789_face.png
```

---

## Testing

**To test:**
```bash
python run_full_pipeline.py --topic "test story" --style courtroom_drama --preview
```

**Expected behavior:**
- Character images generated in `outputs/characters/`
- Images are photorealistic with natural skin texture
- Same character_id produces consistent appearance
- Images also copied to legacy `character_faces/` location

---

## Future Enhancements

1. **Voice Cloning Integration**: Link character images with voice profiles
2. **Emotion-Aware Expressions**: Adjust facial expressions based on scene emotion
3. **Action Shots**: Support "character_action_shot" type for dynamic scenes
4. **Style Presets**: Pre-defined style presets (cinematic, documentary, news, etc.)
5. **Multi-Angle Views**: Generate multiple angles of the same character

---

## Notes

- Seed locking ensures consistency but doesn't guarantee identical images (model variance)
- Photorealistic prompts work best with FLUX.1-dev and similar models
- Parameters are added to prompt text for maximum endpoint compatibility
- Character images are 1080x1920 (vertical format) for YouTube Shorts

