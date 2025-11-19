# Quality Improvement Audit & Implementation Plan
## AI Story Shorts Factory - Second Phase Upgrade

---

## Executive Summary

**Current Status**: Pipeline is functional end-to-end but lacks quality polish, advanced features, and production hardening.

**Overall Assessment**: ~40% of requested improvements are implemented. Core functionality works, but quality enhancements, CLI options, and batch processing are missing.

---

## 1. Story Quality Improvements

### Status: `partially implemented`

**Current State**:
- Basic story structure exists in `app/services/story_rewriter.py`
- Simple scene splitting (2-4 scenes based on duration)
- Basic emotion detection (keyword-based)
- Generic logline generation
- No narrative arc structure (HOOK → SETUP → CONFLICT → TWIST → RESOLUTION)
- Scene descriptions are truncated text snippets, not visually descriptive
- No style parameter support

**Gaps**:
- No structured narrative arc
- Scene descriptions lack visual framing (camera, mood, lighting)
- Narration lines are just word-split, not optimized for speech
- No style parameter (`--style courtroom/crime/drama`)
- Hooks are generic, not punchy

**Code Locations for Improvements**:
- `app/services/story_rewriter.py`:
  - `rewrite_story()` - Add narrative arc structure
  - `_create_narrative_arc()` - NEW method
  - `_enhance_scene_description()` - NEW method
  - `_optimize_narration_for_speech()` - NEW method
- `run_full_pipeline.py`:
  - Add `--style` argument (line ~131)
  - Pass style to `story_rewriter.rewrite_story()`

**Function Signatures to Add**:

```python
# In app/services/story_rewriter.py

def rewrite_story(
    self, 
    raw_text: str, 
    title: str, 
    duration_seconds: int = 60,
    style: str = "courtroom_drama"  # NEW parameter
) -> StoryScript:
    """Enhanced with narrative arc and style support."""

def _create_narrative_arc(
    self, 
    raw_text: str, 
    num_scenes: int
) -> dict[str, str]:
    """
    Create structured narrative arc.
    
    Returns:
        {
            "hook": str,
            "setup": str,
            "conflict": str,
            "twist": str,
            "resolution": str
        }
    """

def _enhance_scene_description(
    self,
    scene_text: str,
    scene_role: str,  # "hook", "setup", "conflict", etc.
    style: str
) -> str:
    """
    Create visually descriptive scene with camera framing, mood, lighting.
    
    Returns:
        "Close-up shot of [subject]. Dramatic lighting. Tense atmosphere..."
    """

def _optimize_narration_for_speech(
    self,
    text: str,
    target_words_per_line: int = 12
) -> list[str]:
    """
    Split text into short, punchy, spoken-friendly lines.
    Respects natural pauses and sentence boundaries.
    """
```

**Config Updates**:
- `app/core/config.py`: Add `story_styles: dict[str, dict]` with style templates

---

## 2. Visual Quality Improvements

### Status: `partially implemented`

**Current State**:
- Basic image generation via Hugging Face API
- Placeholder fallback exists
- Fixed 1080x1920 output size
- Simple prompt: `background_prompt + description`
- No seed option
- No panning/zooming
- No high-quality mode

**Gaps**:
- Image prompts don't use emotional tone, camera_style, or vibe
- No deterministic seed for reproducibility
- Static images (no Ken Burns effect)
- No quality tiers (high-quality flag)

**Code Locations for Improvements**:
- `app/services/video_renderer.py`:
  - `_generate_image()` - Enhance prompt building
  - `_build_rich_image_prompt()` - NEW method
  - `_compose_video()` - Add Ken Burns effect (line ~235)
  - `_apply_ken_burns()` - NEW method
- `run_full_pipeline.py`:
  - Add `--high-quality` flag
  - Add `--image-seed` flag

**Function Signatures to Add**:

```python
# In app/services/video_renderer.py

def _build_rich_image_prompt(
    self,
    scene: VideoScene,
    style: str
) -> str:
    """
    Build rich image prompt from scene data.
    
    Uses:
    - scene.description
    - scene.background_prompt
    - scene.camera_style
    - Emotional tone from narration
    - Style-specific vibe
    
    Returns:
        "Cinematic [camera_style] of [subject]. [mood] atmosphere. 
         [lighting]. [vibe]. Professional photography, 4k, detailed."
    """

def _apply_ken_burns(
    self,
    image_clip: ImageClip,
    duration: float,
    effect_type: str = "zoom_in"  # "zoom_in", "zoom_out", "pan_left", "pan_right"
) -> ImageClip:
    """
    Apply Ken Burns effect (pan/zoom) to image clip.
    
    Returns:
        ImageClip with motion effect
    """

def _generate_image(
    self,
    prompt: str,
    output_path: Path,
    seed: Optional[int] = None,  # NEW
    high_quality: bool = False  # NEW
) -> None:
    """Enhanced with seed and quality options."""
```

**Config Updates**:
- `app/core/config.py`: Add `image_quality_presets: dict[str, dict]` (standard/high)

---

## 3. Timing & Pacing

### Status: `partially implemented`

**Current State**:
- Basic duration calculation based on narration lines (line ~262-275 in `video_renderer.py`)
- Equal fallback if no narration
- No transitions
- No strict timing enforcement
- No playback rate adjustment

**Gaps**:
- Doesn't account for dialogue lines in duration
- No fade transitions between scenes
- No strict timing mode (±3 seconds enforcement)
- No playback rate adjustment

**Code Locations for Improvements**:
- `app/services/video_renderer.py`:
  - `_compose_video()` - Enhance duration calculation (line ~262)
  - `_calculate_scene_durations()` - NEW method
  - `_add_transitions()` - NEW method
  - `_enforce_strict_timing()` - NEW method
- `run_full_pipeline.py`:
  - Add `--strict-timing` flag

**Function Signatures to Add**:

```python
# In app/services/video_renderer.py

def _calculate_scene_durations(
    self,
    video_plan: VideoPlan,
    audio_duration: float,
    target_duration: float
) -> list[float]:
    """
    Calculate scene durations considering:
    - Narration line count
    - Dialogue line count
    - Target total duration
    
    Returns:
        List of durations per scene
    """

def _add_transitions(
    self,
    video_clips: list[ImageClip],
    transition_duration: float = 0.5
) -> list[ImageClip]:
    """
    Add fade transitions between scene clips.
    
    Returns:
        List of clips with transitions
    """

def _enforce_strict_timing(
    self,
    final_video: VideoClip,
    target_duration: float,
    tolerance: float = 3.0
) -> VideoClip:
    """
    Adjust video to match target duration within tolerance.
    Uses playback rate adjustment if needed.
    
    Returns:
        Adjusted VideoClip
    """
```

---

## 4. Audio Quality

### Status: `missing`

**Current State**:
- Basic TTS generation exists
- No loudness normalization
- No background ambience
- No voice style parameter

**Gaps**:
- No LUFS normalization (-14 to -16 LUFS)
- No background audio tracks
- No voice style selection

**Code Locations for Improvements**:
- `app/services/video_renderer.py`:
  - `_generate_narration_audio()` - Add post-processing (line ~83)
  - `_normalize_audio_loudness()` - NEW method
  - `_add_background_ambience()` - NEW method
- `app/services/tts_client.py`:
  - `generate_speech()` - Add voice_style parameter
- `run_full_pipeline.py`:
  - Add `--voice-style` flag

**Function Signatures to Add**:

```python
# In app/services/video_renderer.py

def _normalize_audio_loudness(
    self,
    audio_path: Path,
    target_lufs: float = -14.0
) -> Path:
    """
    Normalize audio to target LUFS using ffmpeg or pydub.
    
    Returns:
        Path to normalized audio file
    """

def _add_background_ambience(
    self,
    audio_path: Path,
    ambience_type: str,  # "courtroom", "tension", "dramatic"
    volume_db: float = -25.0
) -> Path:
    """
    Mix background ambience at specified volume.
    
    Returns:
        Path to mixed audio file
    """

# In app/services/tts_client.py

def generate_speech(
    self,
    text: str,
    output_path: Path,
    voice_id: Optional[str] = None,
    voice_style: str = "neutral"  # NEW: "calm", "dramatic", "news", "documentary"
) -> None:
    """Enhanced with voice style support."""
```

**Config Updates**:
- `app/core/config.py`: Add `audio_loudness_target: float = -14.0`
- `app/core/config.py`: Add `ambience_library_path: Optional[str]` for ambience files

---

## 5. Error Hardening & Logging

### Status: `partially implemented`

**Current State**:
- Basic logging exists throughout
- Some error handling
- No timing metrics
- No provider tracking
- No debug/trace modes

**Gaps**:
- No scene-by-scene render times
- No TTS provider logging
- No image generator tracking
- No stage timing
- No debug/trace flags
- Generic exception messages

**Code Locations for Improvements**:
- `app/services/video_renderer.py`:
  - `render()` - Add timing decorators (line ~32)
  - Add provider logging throughout
- `app/core/logging_config.py`:
  - Add `debug_mode` and `trace_mode` support
- `run_full_pipeline.py`:
  - Add `--debug` and `--trace` flags
- All services:
  - Improve exception messages with user-friendly context

**Function Signatures to Add**:

```python
# In app/core/logging_config.py

def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
    debug_mode: bool = False,  # NEW
    trace_mode: bool = False  # NEW
) -> None:
    """Enhanced with debug/trace modes."""

# In app/services/video_renderer.py

def render(
    self,
    video_plan: VideoPlan,
    output_dir: Path
) -> Path:
    """
    Enhanced with:
    - Scene-by-scene timing
    - Provider tracking
    - Stage timing
    - Better error messages
    """
```

**New Utility Module**:
- `app/utils/timing.py` - Timing decorators and context managers

---

## 6. CLI Experience

### Status: `partially implemented`

**Current State**:
- Basic CLI exists with `--topic`, `--duration-target-seconds`, `--auto-upload`, `--output-dir`
- No episode ID lookup
- No dry-run mode
- No render-only mode
- No upload-only mode

**Gaps**:
- Missing `--episode-id` for re-rendering
- Missing `--dry-run` flag
- Missing `--render-only` flag
- Missing `--upload-only` flag
- CLI help could be cleaner

**Code Locations for Improvements**:
- `run_full_pipeline.py`:
  - Add all missing flags (line ~125-153)
  - Refactor `main()` to handle different modes
  - Improve help text formatting

**Function Signatures to Add**:

```python
# In run_full_pipeline.py

def load_existing_episode(
    episode_id: str,
    repository: EpisodeRepository
) -> VideoPlan:
    """Load existing episode by ID."""

def main():
    """
    Enhanced with:
    - --episode-id: Load existing episode
    - --dry-run: Generate story only, skip render/upload
    - --render-only: Skip story generation, render existing episode
    - --upload-only: Skip story/render, upload existing video
    """
```

---

## 7. Smart Title & Description Templates

### Status: `partially implemented`

**Current State**:
- Basic metadata generation in `generate_video_metadata()` (line ~93)
- Simple title truncation
- Basic description from logline
- Simple tag generation

**Gaps**:
- No clickable title templates (e.g., `[SHOCKING] ...`)
- No hashtag generation
- No YouTube-safe formatting
- No template customization

**Code Locations for Improvements**:
- `run_full_pipeline.py`:
  - `generate_video_metadata()` - Enhance with templates (line ~93)
  - `_generate_clickable_title()` - NEW method
  - `_generate_hashtags()` - NEW method
  - `_format_for_youtube()` - NEW method
- Add `--title-template` and `--description-template` flags

**Function Signatures to Add**:

```python
# In run_full_pipeline.py

def _generate_clickable_title(
    video_plan: VideoPlan,
    template: Optional[str] = None
) -> str:
    """
    Generate clickable YouTube title.
    
    Templates:
    - "[SHOCKING] {title}"
    - "{title} - You Won't Believe What Happened"
    - "{title} | {emotion} Moment"
    
    Returns:
        Clickable title (max 100 chars)
    """

def _generate_hashtags(
    video_plan: VideoPlan,
    max_tags: int = 10
) -> list[str]:
    """
    Generate relevant hashtags from:
    - Topic keywords
    - Style
    - Emotions detected
    - Story elements
    """

def generate_video_metadata(
    video_plan: VideoPlan,
    title_template: Optional[str] = None,  # NEW
    description_template: Optional[str] = None  # NEW
) -> tuple[str, str, list[str]]:
    """Enhanced with template support."""
```

---

## 8. Stability for Batch Generation

### Status: `missing`

**Current State**:
- No batch processing script
- No rate limiting
- No sleep between runs
- No success/failure tracking

**Gaps**:
- Entire feature missing

**Code Locations for New Implementation**:
- Create `run_batch.py` at repo root
- Create `app/utils/rate_limiter.py` for rate limiting
- Create `app/utils/batch_tracker.py` for success/failure tracking

**Function Signatures to Add**:

```python
# New file: run_batch.py

def process_batch(
    topics_file: Path,
    output_dir: Path,
    delay_between_runs: float = 30.0,
    max_retries: int = 3
) -> dict[str, Any]:
    """
    Process batch of topics from file.
    
    Returns:
        {
            "total": int,
            "success": int,
            "failed": int,
            "results": list[dict]
        }
    """

def main():
    """
    CLI for batch processing:
    --topics-file topics.txt
    --delay-seconds 30
    --max-retries 3
    --continue-on-error
    """

# New file: app/utils/rate_limiter.py

class RateLimiter:
    """Rate limiting for API calls."""
    
    def __init__(
        self,
        max_calls_per_minute: int,
        max_calls_per_hour: int
    ):
        """Initialize rate limiter."""
    
    def wait_if_needed(self, api_type: str) -> None:
        """Wait if rate limit would be exceeded."""
    
    def record_call(self, api_type: str) -> None:
        """Record API call for rate tracking."""

# New file: app/utils/batch_tracker.py

class BatchTracker:
    """Track batch processing results."""
    
    def log_success(self, topic: str, episode_id: str, video_path: Path) -> None:
        """Log successful processing."""
    
    def log_failure(self, topic: str, error: Exception) -> None:
        """Log failed processing."""
    
    def get_summary(self) -> dict[str, Any]:
        """Get batch processing summary."""
```

---

## 9. Graceful Fallbacks

### Status: `partially implemented`

**Current State**:
- Image generation has placeholder fallback
- TTS has stub mode
- Some error handling exists

**Gaps**:
- No explicit fallback chain documentation
- No fallback for TTS failures (should use stub)
- No warnings for missing API keys upfront
- No fallback quality degradation path

**Code Locations for Improvements**:
- `app/services/video_renderer.py`:
  - Add fallback chain in `_generate_image()` (line ~137)
  - Add fallback in `_generate_narration_audio()` (line ~83)
- `run_full_pipeline.py`:
  - Add upfront API key validation
  - Add warnings for missing keys

**Function Signatures to Add**:

```python
# In app/services/video_renderer.py

def _generate_image_with_fallback(
    self,
    prompt: str,
    output_path: Path,
    scene: VideoScene
) -> None:
    """
    Try image generation with fallback chain:
    1. Hugging Face API (high quality)
    2. Placeholder with rich text (medium)
    3. Simple placeholder (low)
    """

def _generate_narration_with_fallback(
    self,
    text: str,
    output_path: Path,
    video_plan: VideoPlan
) -> None:
    """
    Try TTS with fallback chain:
    1. ElevenLabs
    2. OpenAI TTS
    3. Stub TTS
    """
```

---

## Staged Implementation Plan

### Stage 1: Low Effort → High Impact (Week 1)

**Priority**: Get immediate quality improvements with minimal code changes.

1. **CLI Enhancements** (4 hours)
   - Add `--episode-id`, `--dry-run`, `--render-only`, `--upload-only`
   - Improve help text
   - **Files**: `run_full_pipeline.py`

2. **Smart Title/Description** (3 hours)
   - Implement clickable title templates
   - Add hashtag generation
   - **Files**: `run_full_pipeline.py` (`generate_video_metadata()`)

3. **Better Logging** (2 hours)
   - Add scene-by-scene timing
   - Log TTS/image provider used
   - Add `--debug` flag
   - **Files**: `app/services/video_renderer.py`, `app/core/logging_config.py`, `run_full_pipeline.py`

4. **Graceful Fallbacks** (3 hours)
   - Explicit fallback chains
   - Upfront API key validation
   - Better error messages
   - **Files**: `app/services/video_renderer.py`, `run_full_pipeline.py`

**Total**: ~12 hours, immediate quality boost

---

### Stage 2: Quality Upgrades (Week 2-3)

**Priority**: Significant quality improvements requiring more implementation.

1. **Story Quality** (8 hours)
   - Implement narrative arc structure
   - Enhanced scene descriptions with visual framing
   - Style parameter support
   - Speech-optimized narration
   - **Files**: `app/services/story_rewriter.py`, `app/services/video_plan_engine.py`, `run_full_pipeline.py`

2. **Visual Quality** (6 hours)
   - Rich image prompts (emotion, camera, vibe)
   - Ken Burns effect (pan/zoom)
   - Seed option for reproducibility
   - **Files**: `app/services/video_renderer.py`, `run_full_pipeline.py`

3. **Timing & Pacing** (5 hours)
   - Enhanced duration calculation (narration + dialogue)
   - Fade transitions between scenes
   - Strict timing mode
   - **Files**: `app/services/video_renderer.py`, `run_full_pipeline.py`

4. **Audio Quality** (6 hours)
   - LUFS normalization
   - Background ambience mixing
   - Voice style parameter
   - **Files**: `app/services/video_renderer.py`, `app/services/tts_client.py`, `run_full_pipeline.py`

**Total**: ~25 hours, major quality improvements

---

### Stage 3: Advanced Polish (Week 4)

**Priority**: Nice-to-have features for production readiness.

1. **Batch Processing** (8 hours)
   - Create `run_batch.py`
   - Rate limiting utilities
   - Success/failure tracking
   - **Files**: `run_batch.py` (new), `app/utils/rate_limiter.py` (new), `app/utils/batch_tracker.py` (new)

2. **High-Quality Mode** (3 hours)
   - Larger images / better model settings
   - Quality presets in config
   - **Files**: `app/services/video_renderer.py`, `app/core/config.py`, `run_full_pipeline.py`

3. **Advanced Logging** (2 hours)
   - Trace mode
   - Performance metrics export
   - **Files**: `app/core/logging_config.py`, all services

**Total**: ~13 hours, production polish

---

## Implementation Checklist

### Stage 1 (Immediate)
- [ ] Add `--episode-id` flag to `run_full_pipeline.py`
- [ ] Add `--dry-run` flag
- [ ] Add `--render-only` flag
- [ ] Add `--upload-only` flag
- [ ] Implement `_generate_clickable_title()`
- [ ] Implement `_generate_hashtags()`
- [ ] Add scene timing logs
- [ ] Add provider tracking logs
- [ ] Add `--debug` flag
- [ ] Add upfront API key validation
- [ ] Improve error messages

### Stage 2 (Quality)
- [ ] Implement `_create_narrative_arc()`
- [ ] Implement `_enhance_scene_description()`
- [ ] Implement `_optimize_narration_for_speech()`
- [ ] Add `--style` parameter
- [ ] Implement `_build_rich_image_prompt()`
- [ ] Implement `_apply_ken_burns()`
- [ ] Add `--image-seed` flag
- [ ] Implement `_calculate_scene_durations()` (enhanced)
- [ ] Implement `_add_transitions()`
- [ ] Implement `_enforce_strict_timing()`
- [ ] Add `--strict-timing` flag
- [ ] Implement `_normalize_audio_loudness()`
- [ ] Implement `_add_background_ambience()`
- [ ] Add `--voice-style` parameter

### Stage 3 (Polish)
- [ ] Create `run_batch.py`
- [ ] Create `RateLimiter` utility
- [ ] Create `BatchTracker` utility
- [ ] Add `--high-quality` flag
- [ ] Add quality presets to config
- [ ] Add `--trace` flag
- [ ] Add performance metrics export

---

## Config Updates Required

### `app/core/config.py` additions:

```python
# Story Quality
story_styles: dict[str, dict] = Field(
    default={
        "courtroom_drama": {
            "tone": "formal",
            "visual_style": "professional",
            "lighting": "dramatic"
        },
        "crime_drama": {
            "tone": "tense",
            "visual_style": "cinematic",
            "lighting": "moody"
        },
        "drama": {
            "tone": "emotional",
            "visual_style": "artistic",
            "lighting": "soft"
        }
    }
)

# Visual Quality
image_quality_presets: dict[str, dict] = Field(
    default={
        "standard": {
            "num_inference_steps": 20,
            "guidance_scale": 7.5
        },
        "high": {
            "num_inference_steps": 50,
            "guidance_scale": 9.0
        }
    }
)

# Audio Quality
audio_loudness_target: float = Field(default=-14.0)
ambience_library_path: Optional[str] = Field(default=None)

# Batch Processing
batch_delay_seconds: float = Field(default=30.0)
batch_max_retries: int = Field(default=3)
```

---

## Notes on Additive Changes

All proposed changes are **additive** and **backward compatible**:

1. **New parameters are optional** with sensible defaults
2. **Existing functionality unchanged** - old code paths still work
3. **New flags are opt-in** - default behavior preserved
4. **Fallbacks ensure** system works even if new features fail
5. **No breaking changes** to existing APIs or data structures

---

## Risk Assessment

**Low Risk** (Stage 1):
- CLI additions are isolated
- Logging improvements are safe
- Title/description changes are cosmetic

**Medium Risk** (Stage 2):
- Story structure changes need testing
- Audio processing requires ffmpeg/pydub
- Timing changes could affect video length

**Low Risk** (Stage 3):
- Batch processing is new feature
- Quality modes are opt-in
- Advanced logging is additive

---

## Testing Strategy

1. **Unit Tests**: Each new function gets tests
2. **Integration Tests**: Full pipeline with new features
3. **Regression Tests**: Ensure old functionality still works
4. **Quality Tests**: Verify output quality improvements

---

## Estimated Timeline

- **Stage 1**: 1 week (12 hours)
- **Stage 2**: 2-3 weeks (25 hours)
- **Stage 3**: 1 week (13 hours)
- **Total**: 4-5 weeks for complete implementation

---

## Conclusion

The codebase is **~40% complete** for the requested quality improvements. Stage 1 improvements can be implemented quickly for immediate impact, while Stages 2-3 provide comprehensive quality upgrades. All changes are additive and maintain backward compatibility.

