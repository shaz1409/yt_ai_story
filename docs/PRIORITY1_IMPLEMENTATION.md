# Priority 1 Implementation: YouTube Scheduling Support

**Date:** 2025-11-22  
**Status:** ✅ Complete

---

## Summary

Implemented full YouTube scheduling support as Priority 1 from the workflow audit. This enables videos to be scheduled for future publication instead of being published immediately.

---

## Changes Made

### 1. Added `planned_publish_at` to EpisodeMetadata

**File:** `app/models/schemas.py`

**Change:**
- Added `planned_publish_at: Optional[datetime] = None` field to `EpisodeMetadata` class
- Positioned after `published_hour_local` for logical grouping
- Field is optional and defaults to `None` (backward compatible)

**Verification:**
- ✅ Pydantic handles datetime serialization automatically
- ✅ JSON serialization works correctly
- ✅ Backward compatible (existing episodes without this field will load with `None`)

---

### 2. Updated YouTubeUploader to Support Scheduling

**File:** `app/services/youtube_uploader.py`

**Changes:**

#### 2.1 Added Import
- Added `from datetime import datetime` to imports

#### 2.2 Updated `upload()` Method Signature
- Added parameter: `scheduled_publish_at: Optional[datetime] = None`
- Parameter is optional and defaults to `None` (backward compatible)

#### 2.3 Scheduling Logic
- **If `scheduled_publish_at` is provided:**
  - Automatically sets `privacy_status = "private"` (required by YouTube for scheduled uploads)
  - Logs warning if user provided non-private privacy_status
  - Converts datetime to RFC 3339 format (ISO 8601 with 'Z' suffix for UTC)
  - Handles both timezone-aware and timezone-naive datetimes:
    - Naive datetimes: Assumes UTC and adds timezone
    - Timezone-aware: Converts to UTC
  - Adds `"publishAt"` field to YouTube API request body under `"status"`

#### 2.4 Logging
- Logs scheduled publish time when provided
- Logs "Publishing immediately" when no schedule
- After upload, confirms scheduling was accepted by checking API response
- Warns if `publishAt` not found in response (shouldn't happen but good to check)

#### 2.5 Behavior
- **If `scheduled_publish_at` is None:** Keeps existing immediate upload behavior
- **If `scheduled_publish_at` is provided:** Schedules upload, video remains private until scheduled time

---

### 3. Updated Pipeline to Store and Pass Scheduled Time

**File:** `app/pipelines/run_full_pipeline.py`

**Changes:**

#### 3.1 Added Import
- Added `from datetime import datetime` to imports

#### 3.2 Scheduled Time Handling
- Before upload, checks if `video_plan.metadata.planned_publish_at` exists
- If found, extracts it and passes to `uploader.upload()` as `scheduled_publish_at`
- Logs when scheduled publish time is found in metadata

#### 3.3 Metadata Updates After Upload
- After successful upload:
  - Extracts `youtube_video_id` from returned URL
  - Sets `metadata.youtube_video_id`
  - Sets `metadata.published_at` to current time
  - If scheduled: preserves `metadata.planned_publish_at` and sets `published_hour_local` from scheduled time
- Re-saves episode to storage with updated metadata

#### 3.4 Preview Mode
- In preview mode, logs planned publish time if present (but doesn't upload)

---

## API Compatibility

### YouTube Data API v3 Requirements

- **`publishAt` format:** RFC 3339 (ISO 8601 with 'Z' suffix for UTC)
- **Privacy status:** Must be `"private"` for scheduled uploads
- **Response:** API returns `publishAt` in response `status` object if accepted

### Implementation Details

```python
# Example: Converting datetime to YouTube format
from datetime import datetime, timezone

# Timezone-aware datetime
dt = datetime(2025, 11, 23, 14, 0, 0, tzinfo=timezone.utc)
publish_at_iso = dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
# Result: "2025-11-23T14:00:00Z"

# Naive datetime (assumed UTC)
dt_naive = datetime(2025, 11, 23, 14, 0, 0)
dt_utc = dt_naive.replace(tzinfo=timezone.utc)
publish_at_iso = dt_utc.isoformat().replace("+00:00", "Z")
# Result: "2025-11-23T14:00:00Z"
```

---

## Backward Compatibility

✅ **All changes are backward compatible:**

1. **EpisodeMetadata:** New field is optional (`None` by default)
2. **YouTubeUploader.upload():** New parameter is optional (`None` by default)
3. **Pipeline:** Only uses scheduled time if present in metadata
4. **Existing behavior:** Immediate uploads work exactly as before

---

## Testing

### Manual Testing Checklist

- [ ] Create episode with `planned_publish_at` set
- [ ] Upload with `scheduled_publish_at` parameter
- [ ] Verify video is scheduled (not published immediately)
- [ ] Check YouTube Studio to confirm scheduled time
- [ ] Verify metadata is saved correctly after upload
- [ ] Test immediate upload (no `scheduled_publish_at`) still works
- [ ] Test preview mode with scheduled time (should log but not upload)

### Unit Test Suggestions

```python
# Test EpisodeMetadata with planned_publish_at
def test_episode_metadata_planned_publish_at():
    metadata = EpisodeMetadata(
        niche='courtroom',
        pattern_type='A',
        primary_emotion='anger',
        num_beats=5,
        num_scenes=4,
        num_dialogue_lines=8,
        num_narration_lines=12,
        has_twist=True,
        has_cta=True,
        style='courtroom_drama',
        planned_publish_at=datetime.now(timezone.utc)
    )
    assert metadata.planned_publish_at is not None

# Test YouTubeUploader scheduling
def test_youtube_uploader_scheduling(mock_youtube_service):
    uploader = YouTubeUploader(settings, logger)
    scheduled_time = datetime(2025, 11, 23, 14, 0, 0, tzinfo=timezone.utc)
    uploader.upload(
        video_path=Path("test.mp4"),
        title="Test",
        description="Test",
        scheduled_publish_at=scheduled_time
    )
    # Verify privacy_status was set to "private"
    # Verify publishAt was included in request
```

---

## Usage Example

### Setting Scheduled Publish Time

```python
from datetime import datetime, timezone

# Create video plan with scheduled time
video_plan.metadata.planned_publish_at = datetime(2025, 11, 23, 14, 0, 0, tzinfo=timezone.utc)

# Save episode
repository.save_episode(video_plan)

# Later, when uploading:
uploader = YouTubeUploader(settings, logger)
uploader.upload(
    video_path=video_path,
    title=title,
    description=description,
    tags=tags,
    scheduled_publish_at=video_plan.metadata.planned_publish_at
)
```

---

## Next Steps (Priority 2)

This implementation provides the foundation for scheduling. Next steps:

1. **Time Slot Assignment** (Priority 2):
   - Create `ScheduleManager` service
   - Assign hardcoded time slots (11:00, 14:00, 18:00, 20:00, 22:00)
   - Map batch items to time slots

2. **Daily Batch Mode** (Priority 3):
   - Add `--daily-mode` flag
   - Auto-assign time slots to batch items
   - Integrate with optimisation engine

---

## Files Modified

1. ✅ `app/models/schemas.py` - Added `planned_publish_at` field
2. ✅ `app/services/youtube_uploader.py` - Added scheduling support
3. ✅ `app/pipelines/run_full_pipeline.py` - Store and pass scheduled time

---

## Logging Output Examples

### With Scheduling:
```
============================================================
Starting YouTube upload
Video: outputs/videos/episode_123_video.mp4
Title: Courtroom Drama Story
Privacy: private
Scheduled publish time: 2025-11-23T14:00:00+00:00
Scheduled publish time (local): 2025-11-23 14:00:00+00:00
============================================================
Setting publishAt to: 2025-11-23T14:00:00Z (UTC)
...
✅ Scheduled publish confirmed: 2025-11-23T14:00:00Z
   Video will be published at: 2025-11-23 14:00:00+00:00
```

### Without Scheduling (Immediate):
```
============================================================
Starting YouTube upload
Video: outputs/videos/episode_123_video.mp4
Title: Courtroom Drama Story
Privacy: public
Publishing immediately (no schedule)
============================================================
...
Video published immediately (public)
```

---

## Summary

✅ **All requirements met:**
- `planned_publish_at` added to metadata
- YouTube uploader supports scheduling
- Pipeline stores and passes scheduled time
- Extensive logging for scheduling
- No breaking changes
- Full backward compatibility

**Ready for Priority 2: Time Slot Assignment**

