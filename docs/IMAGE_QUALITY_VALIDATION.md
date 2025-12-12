# Image Quality Validation Implementation

**Date:** 2025-01-13  
**Status:** ✅ Complete

---

## Overview

Implemented comprehensive image quality validation before images are accepted into the video pipeline. Images are scored on multiple metrics, and low-quality images are automatically regenerated or replaced with fallbacks.

---

## Features

### 1. Quality Scoring System

**File:** `app/services/image_quality_validator.py`

**Scoring Metrics (0.0 to 1.0 scale):**

1. **Sharpness (0.0-0.4)** - Variance of Laplacian
   - Very sharp: > 300 variance → 1.0
   - Good: 100-300 variance → 0.5-1.0
   - Blurry: < 100 variance → 0.0-0.5

2. **Resolution (0.0-0.2)** - Shortest edge check
   - Ideal: >= 1920px → 1.0
   - Acceptable: >= 1024px → 0.5-1.0
   - Below minimum: < 1024px → 0.0-0.5

3. **Facial Structure (0.0-0.2)** - For character images only
   - Uses OpenCV face detection
   - Checks face size and positioning
   - Non-character images get full points

4. **Lighting (0.0-0.2)** - Balanced exposure
   - Penalizes overexposed areas (> 10% of image)
   - Penalizes underexposed areas (> 20% of image)
   - Checks HSV value channel

**Minimum Threshold:** `MIN_ACCEPTABLE_SCORE = 0.65` (configurable via `MIN_IMAGE_QUALITY_SCORE` in `.env`)

---

## Integration Points

### 1. CharacterVideoEngine

**File:** `app/services/character_video_engine.py`

**Changes:**
- Added `ImageQualityValidator` initialization
- Updated `generate_character_face_image()` with retry logic:
  - Up to 3 attempts per character image
  - Validates quality after each generation
  - Varies seed slightly on retry
  - Falls back to `assets/characters_fallbacks/` on failure

**Log Messages:**
- `✅ Accepted character image with quality score X.XXX`
- `Regenerating character image (attempt N/3)`
- `Using fallback character image`

### 2. HFEndpointClient

**File:** `app/services/hf_endpoint_client.py`

**Changes:**
- Added `ImageQualityValidator` initialization
- Updated `generate_image()` to validate quality after generation
- Updated `generate_broll_scene()` with retry logic:
  - Up to 3 attempts per B-roll image
  - Validates quality after each generation
  - Varies prompt slightly on retry
  - Falls back to `assets/broll_fallbacks/` on failure

**Log Messages:**
- `✅ Accepted {image_type} image with quality score X.XXX`
- `Regenerating B-roll image (attempt N/3)`
- `Using fallback B-roll image`

---

## Fallback System

### Fallback Directories

1. **Character Fallbacks:** `assets/characters_fallbacks/`
   - Priority order:
     1. `{role}_fallback.png` (e.g., `judge_fallback.png`)
     2. `character_fallback.png`
     3. Any `.png` file in directory

2. **B-Roll Fallbacks:** `assets/broll_fallbacks/`
   - Priority order:
     1. `broll_fallback.png`
     2. Any `.png` file in directory

**Note:** Directories are created automatically if they don't exist.

---

## Configuration

### Environment Variables

```bash
# Minimum acceptable image quality score (0.0 to 1.0)
MIN_IMAGE_QUALITY_SCORE=0.65
```

### Default Values

- `min_image_quality_score`: 0.65 (65% quality threshold)

---

## Dependencies

**New Dependency:**
- `opencv-python>=4.8.0` - For image quality validation (sharpness, face detection, lighting)
- `numpy>=1.24.0` - Required by opencv-python

**Added to:** `requirements_backend.txt`

---

## Usage

### Automatic

Quality validation runs automatically for all image generation:
- Character face images
- B-roll scene images

### Manual Testing

```python
from app.services.image_quality_validator import ImageQualityValidator
from app.core.config import Settings
from app.core.logging_config import get_logger
from pathlib import Path

settings = Settings()
logger = get_logger(__name__)
validator = ImageQualityValidator(settings, logger)

# Score an image
score = validator.score_image(Path("path/to/image.png"), "character_portrait")
print(f"Quality score: {score:.3f}")

# Check if acceptable
is_acceptable = validator.is_acceptable(Path("path/to/image.png"), "character_portrait")
print(f"Acceptable: {is_acceptable}")
```

---

## Retry Logic

### Character Images

1. Generate image with seed
2. Validate quality
3. If score < 0.65:
   - Retry with varied seed (seed + attempt * 1000)
   - Up to 3 attempts total
4. If all attempts fail:
   - Try fallback from `assets/characters_fallbacks/`
   - If no fallback, create placeholder

### B-Roll Images

1. Generate image with prompt
2. Validate quality
3. If score < 0.65:
   - Retry with varied prompt (adds "attempt N" suffix)
   - Up to 3 attempts total
4. If all attempts fail:
   - Try fallback from `assets/broll_fallbacks/`
   - If no fallback, create placeholder

---

## Logging

### Quality Acceptance

```
✅ Accepted character image with quality score 0.782: character_judge_123_face.png
✅ Accepted scene_broll image with quality score 0.856: broll_scene_1.png
```

### Quality Rejection & Retry

```
Image quality score 0.542 below threshold (0.650)
Regenerating character image (attempt 2/3)
Regenerating B-roll image (attempt 2/3)
```

### Fallback Usage

```
Using fallback character image: assets/characters_fallbacks/judge_fallback.png
Using fallback B-roll image: assets/broll_fallbacks/broll_fallback.png
```

---

## Backward Compatibility

✅ **Fully backward compatible:**
- Narrator-only pipeline still works
- Existing placeholder logic preserved
- No breaking changes to APIs
- Quality validation is opt-in (runs automatically but doesn't break existing flow)

---

## Testing

### Test Image Quality

1. Generate a test image
2. Run validator on it
3. Check score and acceptance

### Test Retry Logic

1. Set `MIN_IMAGE_QUALITY_SCORE=0.95` (very high threshold)
2. Generate character/B-roll image
3. Verify retry attempts are logged
4. Verify fallback is used after max attempts

### Test Fallbacks

1. Create fallback images in `assets/characters_fallbacks/` and `assets/broll_fallbacks/`
2. Force quality failure (high threshold)
3. Verify fallback images are used

---

## Future Enhancements

1. **Quality Metrics Dashboard** - Track quality scores over time
2. **Adaptive Thresholds** - Adjust thresholds based on image type
3. **Quality-Based Prompting** - Use quality feedback to improve prompts
4. **Batch Quality Analysis** - Analyze quality trends across batches

---

## Files Modified

1. `app/services/image_quality_validator.py` - **NEW** - Quality validation service
2. `app/services/character_video_engine.py` - Added quality validation and retry logic
3. `app/services/hf_endpoint_client.py` - Added quality validation and retry logic
4. `app/services/video_renderer.py` - Updated to handle new return type from `generate_broll_scene()`
5. `app/core/config.py` - Added `min_image_quality_score` setting
6. `requirements_backend.txt` - Added `opencv-python` and `numpy` dependencies

---

## Summary

✅ Image quality validation is now fully integrated into the pipeline. All images are automatically validated before acceptance, with automatic retry logic and fallback support. The system is backward compatible and doesn't break existing workflows.

