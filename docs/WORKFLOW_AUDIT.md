# Workflow Audit: Current State vs Desired Daily Batch Workflow

**Date:** 2025-11-22  
**Auditor:** Staff-level Engineering Review

---

## 1. Current Behavior Summary

### 1.1 `run_full_pipeline.py` Current Capabilities

**Single Video Mode:**
- ✅ Generates one video from a topic or auto-selected story
- ✅ Supports `--topic` (manual) or `--auto-topic` (LLM-generated candidates)
- ✅ Full pipeline: story sourcing → generation → rendering → optional upload
- ✅ Preview mode (`--preview`) or upload mode (`--auto-upload`)

**Batch Mode:**
- ✅ Supports `--batch-count N` for sequential generation
- ✅ Each batch item gets a new `episode_id`
- ✅ Continues on individual failures (logs error, continues to next)
- ✅ Final summary: success/failed counts

**Optimisation Mode:**
- ✅ Enabled via `USE_OPTIMISATION=true` env var
- ✅ When enabled AND no `--topic` provided:
  - Calls `OptimisationEngine.select_batch_plan(batch_count)`
  - Gets list of `PlannedVideo` objects
  - Uses planned video attributes (niche, style, pattern_type, emotions) for each batch item
- ✅ Falls back to simple mix if no performance data exists

**Upload Behavior:**
- ✅ `--auto-upload`: Uploads immediately to YouTube (public)
- ✅ `--preview`: Skips upload entirely
- ❌ **No scheduling support** - all uploads are immediate

### 1.2 EpisodeMetadata Population

**During Story Generation:**
- ✅ `niche`, `pattern_type`, `primary_emotion`, `secondary_emotion`
- ✅ `num_beats`, `num_scenes`, `num_dialogue_lines`, `num_narration_lines`
- ✅ `has_twist`, `has_cta`
- ✅ `style`, `llm_model_story`, `llm_model_dialogue`
- ✅ Saved to `storage/episodes/{episode_id}.json` after story generation

**During Video Rendering:**
- ✅ `video_duration_sec`, `audio_duration_sec`
- ✅ `num_broll_clips`, `num_talking_head_clips`
- ✅ `hf_model`, `tts_provider`, `talking_heads_enabled`
- ✅ Re-saved to storage after rendering

**After YouTube Upload:**
- ✅ `youtube_video_id` (stored in metadata)
- ✅ `published_at` (timestamp when uploaded)
- ✅ `published_hour_local` (hour 0-23)
- ❌ **No `planned_publish_at` field** - scheduling not supported

### 1.3 Beat-Based Story Generation

**Current Implementation:**
- ✅ `StoryRewriter._generate_story_from_beats()` uses LLM to generate beats
- ✅ Patterns A/B/C supported (HOOK → TRIGGER → CONTEXT → CLASH → TWIST → CTA)
- ✅ Always includes CTA beat
- ✅ Emotion-driven (rage/injustice/shock/disgust)
- ✅ Returns `pattern_type` for metadata

**Flow:**
1. If `niche`, `primary_emotion`, `secondary_emotion`, `topic_hint` provided → uses beat-based generation
2. Falls back to legacy story rewriting if beat generation fails
3. Builds `StoryScript` from beats with proper scene structure

### 1.4 Optimisation Engine

**Current Implementation:**
- ✅ `OptimisationEngine.select_batch_plan(batch_count, fallback_niche)`
- ✅ Loads recent episodes (up to 100) from repository
- ✅ Groups by `(niche, pattern_type, primary_emotion)`
- ✅ Scores groups by `views_24h` + engagement bonus (likes/comments)
- ✅ Samples `PlannedVideo` objects proportionally to scores
- ✅ Falls back to `_generate_simple_mix()` if no performance data

**Limitations:**
- ❌ No date-based planning (doesn't consider "today's batch")
- ❌ No time slot assignment
- ❌ Returns generic mix if no historical data

---

## 2. Gap Analysis vs Desired Workflow

### 2.1 Daily Job / Entrypoint

**Status:** ❌ **Missing**

**Desired:**
- Single command: `python run_daily_batch.py --date YYYY-MM-DD --count 5`
- Or: `python run_full_pipeline.py --batch-count 5 --daily-mode`

**Current:**
- `run_full_pipeline.py` exists but:
  - No `--date` parameter
  - No `--daily-mode` flag
  - No hardcoded posting time slots
  - Batch mode exists but doesn't assign times

**Files Involved:**
- `app/pipelines/run_full_pipeline.py` (main entrypoint)
- Could create `app/pipelines/run_daily_batch.py` (new wrapper)

**Blockers:**
- No time slot assignment logic
- No date-based workflow
- No integration between batch generation and scheduling

---

### 2.2 Optimisation-Driven Topic Selection

**Status:** ✅ **Fully Implemented** (with minor gaps)

**Desired:**
- When `USE_OPTIMISATION=true`: choose 5 `PlannedVideo` specs based on performance
- When `USE_OPTIMISATION=false`: fallback to simple mix

**Current:**
- ✅ `OptimisationEngine.select_batch_plan()` exists
- ✅ Returns `PlannedVideo` objects with niche, style, pattern_type, emotions
- ✅ Uses historical performance data (views_24h, engagement)
- ✅ Falls back to simple mix if no data
- ✅ Integrated into `run_full_pipeline.py` when `USE_OPTIMISATION=true` and no `--topic`

**Gaps:**
- ⚠️ No explicit "exploration" vs "exploitation" balance (currently pure proportional sampling)
- ⚠️ No date-specific planning (could optimize for "what works on this day of week")

**Files:**
- `app/services/optimisation_engine.py` ✅
- `app/pipelines/run_full_pipeline.py` (lines 292-346) ✅

---

### 2.3 Beat-Based Story + Emotional Flow

**Status:** ✅ **Fully Implemented**

**Desired:**
- Beat-based LLM prompt (HOOK, TRIGGER, CONTEXT, CLASH, TWIST, CTA)
- Strong hook, emotional triggers, clear context, moral dilemma, explicit CTA

**Current:**
- ✅ `StoryRewriter._generate_story_from_beats()` implements all beat types
- ✅ Patterns A/B/C supported
- ✅ Always includes CTA beat
- ✅ Emotion-driven (target_emotion per beat)
- ✅ LLM prompt emphasizes viral, emotional, engaging content
- ✅ CTA explicitly required in prompt

**Files:**
- `app/services/story_rewriter.py` (lines 600-692) ✅

**No gaps identified** - implementation matches desired workflow.

---

### 2.4 Visuals & B-roll

**Status:** ✅ **Partially Implemented** (for later enhancement)

**Desired:**
- B-roll images/clips matching niche, scene/beat, target emotion
- Good prompts into HF endpoint

**Current:**
- ✅ Scene visuals generated via HF endpoint (or placeholders)
- ✅ Prompts include scene description, style, emotion
- ⚠️ B-roll prompts could be more emotion/beat-specific
- ✅ Talking heads optional (not blocker)

**Files:**
- `app/services/video_renderer.py` (scene visual generation)
- `app/services/hf_endpoint_client.py` (image generation)

**Note:** User said "for later, but please include in audit" - this is acceptable for now.

---

### 2.5 Metadata + Scheduling

**Status:** ❌ **Partially Implemented** (scheduling missing)

**Desired:**
- Rich `EpisodeMetadata` with all fields
- `planned_publish_at` (scheduled time)
- YouTube uploader sets scheduled publish time (not immediate)

**Current:**
- ✅ `EpisodeMetadata` has most fields populated:
  - ✅ niche, pattern_type, emotions, topics
  - ✅ video_duration_sec, num_broll_clips, num_talking_head_clips
  - ✅ youtube_video_id, published_at, published_hour_local
- ❌ **Missing `planned_publish_at` field** in `EpisodeMetadata`
- ❌ **YouTube uploader does NOT support scheduling**
  - `YouTubeUploader.upload()` only accepts `privacy_status`
  - No `publishAt` parameter in YouTube API call
  - All uploads are immediate (`privacy_status="public"`)

**Files:**
- `app/models/schemas.py` (EpisodeMetadata model) - needs `planned_publish_at` field
- `app/services/youtube_uploader.py` - needs scheduling support
- `app/pipelines/run_full_pipeline.py` - needs to pass scheduled time to uploader

**Blockers:**
- YouTube Data API v3 requires `publishAt` in `status` object for scheduled uploads
- Must be RFC 3339 format (ISO 8601)
- Need to store `planned_publish_at` in metadata before upload

---

### 2.6 Fixed Posting Times

**Status:** ❌ **Missing**

**Desired:**
- Hardcoded daily posting slots: 11:00, 14:00, 18:00, 20:00, 22:00 (local time)
- Map each of 5 videos to one time slot
- Ensure YouTube upload is scheduled (not published immediately)

**Current:**
- ❌ No time slot assignment logic
- ❌ No hardcoded posting times
- ❌ No timezone handling
- ❌ No mapping of batch items to time slots

**Files Needed:**
- New: `app/services/schedule_manager.py` (or similar)
- Update: `app/pipelines/run_full_pipeline.py` (assign times to batch items)
- Update: `app/services/youtube_uploader.py` (accept and use scheduled time)

**Blockers:**
- No time slot manager
- No date + time slot → `datetime` conversion
- No integration with batch loop

---

## 3. Prioritized Next-Step Plan

### Priority 1: YouTube Scheduling Support

**Goal:** Enable scheduled uploads (not immediate)

**Files to Modify:**
1. **`app/models/schemas.py`**
   - Add `planned_publish_at: Optional[datetime]` to `EpisodeMetadata`

2. **`app/services/youtube_uploader.py`**
   - Add `scheduled_publish_at: Optional[datetime] = None` parameter to `upload()` method
   - If `scheduled_publish_at` is provided:
     - Set `privacy_status="private"` (required for scheduled uploads)
     - Add `"publishAt": scheduled_publish_at.isoformat() + "Z"` to `status` object
   - Update method signature and docstring

3. **`app/pipelines/run_full_pipeline.py`**
   - Pass `scheduled_publish_at` to `uploader.upload()` when available
   - Store `planned_publish_at` in `video_plan.metadata` before upload

**Estimated Effort:** 2-3 hours

---

### Priority 2: Time Slot Assignment

**Goal:** Assign each batch item to a hardcoded posting time

**Files to Create/Modify:**
1. **New: `app/services/schedule_manager.py`**
   - Class: `ScheduleManager`
   - Method: `get_posting_slots(date: date, count: int) -> list[datetime]`
   - Hardcoded slots: `[11, 14, 18, 20, 22]` (hours in local time)
   - Convert to `datetime` objects for the given date
   - Handle timezone (use `settings.timezone` or default to local)

2. **`app/core/config.py`**
   - Add `timezone: str = Field(default="UTC", description="Timezone for scheduling")`

3. **`app/pipelines/run_full_pipeline.py`**
   - Import `ScheduleManager`
   - In batch loop, get posting slots for today (or `--date` if provided)
   - Assign `scheduled_publish_at` to each batch item
   - Pass to `uploader.upload()` when uploading

**Estimated Effort:** 3-4 hours

---

### Priority 3: Daily Batch Entrypoint

**Goal:** Single command for daily batch generation

**Files to Create/Modify:**
1. **Option A: New `app/pipelines/run_daily_batch.py`**
   - Wrapper around `run_full_pipeline.py` logic
   - CLI: `--date YYYY-MM-DD --count 5`
   - Defaults: today's date, count=5
   - Calls `run_full_pipeline.py` internals or refactors shared logic

2. **Option B: Extend `run_full_pipeline.py`**
   - Add `--daily-mode` flag
   - Add `--date YYYY-MM-DD` parameter (defaults to today)
   - When `--daily-mode`:
     - Force `USE_OPTIMISATION=true` (or require it)
     - Force `--batch-count 5` (or use `--count` if provided)
     - Force `--auto-upload` (no preview in daily mode)
     - Assign time slots automatically

**Recommendation:** Option B (extend existing) - simpler, less duplication

**Estimated Effort:** 2-3 hours

---

### Priority 4: Integration & Testing

**Goal:** Wire everything together and test end-to-end

**Files to Modify:**
1. **`app/pipelines/run_full_pipeline.py`**
   - Integrate `ScheduleManager` into batch loop
   - Ensure `planned_publish_at` is set before upload
   - Log scheduled times clearly

2. **Update metadata population:**
   - Ensure `planned_publish_at` is saved to episode JSON
   - Update `video_plan.metadata` after scheduling assignment

3. **Testing:**
   - Test with `--daily-mode --date 2025-11-23 --count 5`
   - Verify 5 videos generated
   - Verify each has unique `planned_publish_at`
   - Verify YouTube uploads are scheduled (check API response)
   - Verify metadata saved correctly

**Estimated Effort:** 2-3 hours

---

### Priority 5: Enhancements (Optional)

**Goal:** Improve optimisation and UX

**Files to Modify:**
1. **`app/services/optimisation_engine.py`**
   - Add exploration/exploitation balance (e.g., 80% top performers, 20% random)
   - Consider day-of-week patterns if data available

2. **`app/pipelines/run_full_pipeline.py`**
   - Better logging for daily mode (show assigned times clearly)
   - Validation: ensure date is today or future (not past)

3. **`app/core/config.py`**
   - Add `daily_batch_count: int = 5` (configurable default)
   - Add `daily_posting_slots: list[int] = [11, 14, 18, 20, 22]` (configurable slots)

**Estimated Effort:** 2-3 hours

---

## 4. Summary

### What Works Now ✅
- Batch generation (`--batch-count`)
- Optimisation engine (performance-based selection)
- Beat-based story generation (patterns A/B/C, CTA included)
- Rich metadata population (most fields)
- YouTube upload (immediate only)

### What's Missing ❌
- Daily batch entrypoint (`--daily-mode` or new script)
- Time slot assignment (hardcoded 5 slots per day)
- YouTube scheduling (`publishAt` support)
- `planned_publish_at` metadata field

### Critical Path
1. **YouTube scheduling** (Priority 1) - blocks everything else
2. **Time slot assignment** (Priority 2) - needed for daily workflow
3. **Daily entrypoint** (Priority 3) - user-facing command
4. **Integration** (Priority 4) - wire it all together

### Estimated Total Effort
- **Core implementation (Priorities 1-4):** 9-13 hours
- **Enhancements (Priority 5):** 2-3 hours (optional)

### Risk Assessment
- **Low Risk:** YouTube scheduling API is well-documented
- **Medium Risk:** Timezone handling (ensure consistent behavior)
- **Low Risk:** Integration (mostly wiring existing components)

---

**Next Steps:** Implement in priority order, test after each priority, then proceed to next.

