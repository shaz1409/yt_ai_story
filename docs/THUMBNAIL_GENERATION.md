# Automatic Thumbnail Generation

**Date:** 2025-01-13  
**Status:** ✅ Complete

---

## Overview

Implemented automatic YouTube thumbnail generation with three modes: frame extraction, HF generation, and hybrid (generated with frame fallback).

---

## Features

### 1. Config Settings

**File:** `app/core/config.py`

**New Settings:**
- `thumbnail_enabled: bool = True` - Enable/disable thumbnail generation
- `thumbnail_mode: str = "hybrid"` - Generation mode: "frame", "generated", or "hybrid"
- `thumbnail_add_text: bool = True` - Add title text overlay to generated thumbnails

**Environment Variables:**
```bash
THUMBNAIL_ENABLED=true
THUMBNAIL_MODE=hybrid          # or "frame" or "generated"
THUMBNAIL_ADD_TEXT=true        # Add title overlay (default: true)
```

---

### 2. Thumbnail Generation Modes

#### Frame Mode (`THUMBNAIL_MODE=frame`)

**Strategy:**
- Extracts best frame from rendered video
- Prioritizes frames with character talking-heads (if available)
- Falls back to middle of video (usually most interesting)
- Resizes/crops to 1280x720 (YouTube standard)

**Advantages:**
- Fast (no API calls)
- Guaranteed to match video content
- No additional costs

**Disadvantages:**
- May not be the most engaging frame
- Limited to what's in the video

#### Generated Mode (`THUMBNAIL_MODE=generated`)

**Strategy:**
- Uses HF endpoint to generate custom thumbnail
- Prompt includes: title, logline, niche, emotion, style
- Optional text overlay with title
- Resizes/crops to 1280x720

**Advantages:**
- Highly customizable and engaging
- Can emphasize key conflict/emotion
- Professional appearance

**Disadvantages:**
- Requires HF endpoint
- Additional API call (cost/time)
- May not match video exactly

#### Hybrid Mode (`THUMBNAIL_MODE=hybrid`) - **Default**

**Strategy:**
1. Try HF generation first
2. If HF fails → fallback to frame extraction
3. Logs which method was used

**Advantages:**
- Best of both worlds
- Graceful degradation
- Always produces a thumbnail

**Disadvantages:**
- Slightly more complex logic

---

### 3. Thumbnail Generator Service

**File:** `app/services/thumbnail_generator.py`

**Class:** `ThumbnailGenerator`

**Methods:**

#### `generate_thumbnail(video_plan, video_path, episode_id)`
- Main entry point for thumbnail generation
- Selects mode based on config
- Returns `Path` to thumbnail or `None` if disabled/failed

#### `_generate_frame_thumbnail(video_path, thumbnail_path, video_plan)`
- Extracts best frame from video
- Uses MoviePy to get frame at optimal time
- Resizes/crops to 1280x720

#### `_generate_hf_thumbnail(video_path, thumbnail_path, video_plan)`
- Generates thumbnail via HF endpoint
- Builds dramatic prompt from metadata
- Optionally adds text overlay
- Resizes/crops to 1280x720

#### `_build_thumbnail_prompt(title, logline, niche, primary_emotion, style)`
- Builds engaging thumbnail prompt
- Maps emotions to visual descriptors
- Includes cinematic keywords

#### `_resize_to_thumbnail(img, target_size)`
- Resizes and crops image to exact dimensions
- Maintains aspect ratio
- Uses high-quality LANCZOS resampling

#### `_add_text_overlay(img, title, logline)`
- Adds title text overlay (optional)
- White text with black shadow for readability
- Tries to use system bold fonts
- Falls back gracefully if fonts unavailable

---

### 4. YouTube Uploader Integration

**File:** `app/services/youtube_uploader.py`

**Changes:**
- Added `thumbnail_path` parameter to `upload()` method
- Added `_upload_thumbnail()` method
- Uploads thumbnail after video upload completes
- Validates thumbnail dimensions (1280x720)
- Non-critical: Upload continues even if thumbnail fails

**YouTube API:**
- Uses `thumbnails().set()` endpoint
- Requires video ID (from upload response)
- Accepts JPG/PNG (JPG recommended)

---

### 5. Pipeline Integration

**File:** `app/pipelines/run_full_pipeline.py`

**Changes:**
- Generates thumbnail after video rendering (Phase 2.5)
- Passes thumbnail path to YouTube uploader
- Logs thumbnail generation status
- Handles failures gracefully (non-critical)

**Flow:**
```
Video Rendering (Phase 2)
  ↓
Thumbnail Generation (Phase 2.5) ← NEW
  ↓
YouTube Upload (Phase 3) - includes thumbnail
```

---

## Configuration Examples

### Use Frame Extraction (Fast, Free)
```bash
THUMBNAIL_ENABLED=true
THUMBNAIL_MODE=frame
```

### Use HF Generation (Custom, Engaging)
```bash
THUMBNAIL_ENABLED=true
THUMBNAIL_MODE=generated
THUMBNAIL_ADD_TEXT=true
# Requires HF_ENDPOINT_URL and HF_ENDPOINT_TOKEN
```

### Use Hybrid (Recommended)
```bash
THUMBNAIL_ENABLED=true
THUMBNAIL_MODE=hybrid
THUMBNAIL_ADD_TEXT=true
# Tries HF first, falls back to frame if HF unavailable
```

### Disable Thumbnails
```bash
THUMBNAIL_ENABLED=false
# YouTube will auto-select a frame
```

---

## Thumbnail Prompt Examples

### Courtroom Drama, Shocked Emotion
```
cinematic, highly detailed, dramatic YouTube thumbnail, 
courtroom scene, shocked expressions, wide eyes, dramatic moment, 
professional composition, high contrast, vibrant colors, 
1280x720 aspect ratio, vertical framing, 
engaging visual that captures: [logline], 
photorealistic, film quality, shallow depth of field, 
cinematic lighting, dramatic shadows
```

### Relationship Drama, Angered Emotion
```
cinematic, highly detailed, dramatic YouTube thumbnail, 
relationship_drama scene, tense confrontation, angry faces, high stakes, 
professional composition, high contrast, vibrant colors, 
1280x720 aspect ratio, vertical framing, 
engaging visual that captures: [logline], 
photorealistic, film quality, shallow depth of field, 
cinematic lighting, dramatic shadows
```

---

## Error Handling

### Thumbnail Generation Fails
- **Behavior:** Logs warning, continues pipeline
- **Impact:** YouTube auto-selects a frame
- **Pipeline:** Continues normally

### Thumbnail Upload Fails
- **Behavior:** Logs warning, video upload still succeeds
- **Impact:** Video uploaded without custom thumbnail
- **Pipeline:** Continues normally

### HF Endpoint Unavailable (Hybrid Mode)
- **Behavior:** Falls back to frame extraction
- **Log:** "HF thumbnail generation failed, falling back to frame"
- **Impact:** None (thumbnail still generated)

---

## File Structure

```
outputs/
  thumbnails/
    {episode_id}.jpg    # Generated thumbnails
```

---

## Performance

### Frame Mode
- **Time:** ~1-2 seconds
- **Cost:** Free
- **API Calls:** 0

### Generated Mode
- **Time:** ~15-40 seconds (HF generation)
- **Cost:** HF API usage
- **API Calls:** 1 (HF endpoint)

### Hybrid Mode
- **Time:** ~15-40 seconds (if HF succeeds) or ~1-2 seconds (if fallback)
- **Cost:** HF API usage (if HF succeeds)
- **API Calls:** 1 (HF endpoint) or 0 (if fallback)

---

## Files Modified

1. **`app/core/config.py`**
   - Added `thumbnail_enabled`, `thumbnail_mode`, `thumbnail_add_text`

2. **`app/services/thumbnail_generator.py`** (NEW)
   - Complete thumbnail generation service
   - Frame extraction and HF generation
   - Text overlay support

3. **`app/services/youtube_uploader.py`**
   - Added `thumbnail_path` parameter
   - Added `_upload_thumbnail()` method

4. **`app/pipelines/run_full_pipeline.py`**
   - Integrated thumbnail generation (Phase 2.5)
   - Passes thumbnail to YouTube uploader

---

## Testing

### Test Frame Mode
```bash
THUMBNAIL_MODE=frame python run_full_pipeline.py --topic "test" --preview
# Check outputs/thumbnails/ for generated thumbnail
```

### Test Generated Mode
```bash
THUMBNAIL_MODE=generated python run_full_pipeline.py --topic "test" --preview
# Requires HF endpoint configured
```

### Test Hybrid Mode
```bash
THUMBNAIL_MODE=hybrid python run_full_pipeline.py --topic "test" --preview
# Tries HF, falls back to frame if HF unavailable
```

---

## Summary

✅ **Automatic thumbnail generation is fully implemented:**
- Three modes: frame, generated, hybrid
- Frame extraction from video
- HF-generated custom thumbnails
- Text overlay support
- YouTube upload integration
- Graceful error handling
- Comprehensive logging

**Usage:**
- Set `THUMBNAIL_ENABLED=true` and `THUMBNAIL_MODE=hybrid` (recommended)
- Thumbnails automatically generated after video rendering
- Automatically uploaded to YouTube with video
- Falls back gracefully if generation fails

