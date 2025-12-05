# YouTube Scheduling Support

**Date:** 2025-11-22  
**Status:** ✅ Fully Implemented

---

## Overview

The AI Story Shorts Factory now supports **scheduled YouTube uploads** with automatic time slot assignment for daily batch generation. Videos can be scheduled to publish at specific times instead of being published immediately.

---

## How Scheduling Works

### 1. Time Slot Assignment

The system uses a **ScheduleManager** service that assigns hardcoded posting time slots:

- **Posting Hours:** `[11, 14, 18, 20, 22]` (local time)
- **Default Timezone:** `Europe/London` (configurable)
- **Business Rules:**
  - If batch count < 5: Uses first N hours
  - If batch count > 5: Repeats the sequence (e.g., 11, 14, 18, 20, 22, 11, 14, ...)

### 2. Metadata Storage

Each episode's `EpisodeMetadata` includes:
- `planned_publish_at: Optional[datetime]` - Scheduled publish time (set before upload)
- `published_at: Optional[datetime]` - Actual publication timestamp (set after upload)
- `youtube_video_id: Optional[str]` - YouTube video ID

### 3. YouTube API Integration

When `scheduled_publish_at` is provided:
- Privacy status is automatically set to `"private"` (required for scheduled uploads)
- `publishAt` field is included in YouTube API request (RFC 3339 format)
- Video remains private until the scheduled time

---

## Daily Mode Usage

### Basic Command

```bash
python run_full_pipeline.py --daily-mode --batch-count 5
```

This will:
1. Force optimisation mode (performance-based video selection)
2. Generate 5 videos
3. Assign time slots: 11:00, 14:00, 18:00, 20:00, 22:00 (local time)
4. Upload all videos as scheduled (private until publish time)

### With Custom Date

```bash
python run_full_pipeline.py --daily-mode --batch-count 5 --date 2025-11-23
```

Schedules videos for November 23, 2025 instead of today.

### With Custom Timezone

The timezone defaults to `Europe/London`. To change it, set in config or modify `ScheduleManager` initialization in `run_full_pipeline.py`.

---

## Example Commands

### Daily Batch (5 videos, today)
```bash
python run_full_pipeline.py --daily-mode --batch-count 5
```

### Daily Batch (3 videos, specific date)
```bash
python run_full_pipeline.py --daily-mode --batch-count 3 --date 2025-11-25
```

### Preview Mode (no upload, but see scheduled times)
```bash
# Note: --daily-mode forces auto-upload, so preview is disabled
# Use regular batch mode for preview:
python run_full_pipeline.py --batch-count 5 --preview
```

### Manual Scheduling (without daily mode)
```bash
# Set planned_publish_at in code/metadata, then:
python run_full_pipeline.py --topic "story topic" --auto-upload
```

---

## Metadata Examples

### Episode JSON with Scheduled Time

```json
{
  "episode_id": "episode_abc123",
  "metadata": {
    "niche": "courtroom",
    "pattern_type": "A",
    "primary_emotion": "anger",
    "planned_publish_at": "2025-11-23T11:00:00+00:00",
    "youtube_video_id": "W4rO0vevQ8M",
    "published_at": "2025-11-22T18:41:20.123456+00:00",
    "published_hour_local": 11
  }
}
```

### Scheduled Time Format

- **ISO 8601 / RFC 3339:** `2025-11-23T11:00:00+00:00`
- **Timezone-aware:** All scheduled times are timezone-aware
- **Storage:** Saved as ISO string in JSON, parsed back to datetime on load

---

## Workflow

### Daily Mode Workflow

1. **User runs:** `python run_full_pipeline.py --daily-mode --batch-count 5`
2. **System:**
   - Forces `USE_OPTIMISATION = True`
   - Forces `--auto-upload = True`
   - Disables `--preview`
   - Initializes `ScheduleManager` with default timezone
   - Gets 5 time slots for today (or `--date` if provided)
3. **For each batch item:**
   - Assigns scheduled time slot
   - Generates story episode
   - Sets `video_plan.metadata.planned_publish_at = scheduled_time`
   - Saves episode with scheduled time
   - Renders video
   - Uploads to YouTube with `scheduled_publish_at` parameter
   - Updates metadata with `youtube_video_id` and `published_at`
   - Re-saves episode with YouTube metadata

### Regular Mode Workflow

1. **User runs:** `python run_full_pipeline.py --topic "story" --auto-upload`
2. **System:**
   - Generates story episode
   - Renders video
   - Uploads immediately (public)
   - Updates metadata with `youtube_video_id` and `published_at`

---

## Configuration

### Timezone

Default timezone is `Europe/London`. To change:

**Via environment variable (recommended):**
```bash
# In .env file
TIMEZONE=America/New_York
```

**Supported timezones:**
- `Europe/London` (default)
- `America/New_York`
- `America/Los_Angeles`
- `America/Chicago`
- Any valid IANA timezone string

### Posting Hours

Default posting hours are `[11, 14, 18, 20, 22]` (11 AM, 2 PM, 6 PM, 8 PM, 10 PM).

**Via environment variable:**
```bash
# In .env file (comma-separated, 24-hour format)
DAILY_POSTING_HOURS=9,12,15,18,21
```

**Note:** The system will cycle through these hours if you generate more videos than available slots. For example, with 5 hours and 7 videos, it will use: 9, 12, 15, 18, 21, 9, 12.

---

## Logging

### Scheduled Upload Logs

```
============================================================
SCHEDULING: Assigned time slots
============================================================
  Slot 1: 2025-11-23T11:00:00+00:00
  Slot 2: 2025-11-23T14:00:00+00:00
  Slot 3: 2025-11-23T18:00:00+00:00
  Slot 4: 2025-11-23T20:00:00+00:00
  Slot 5: 2025-11-23T22:00:00+00:00
============================================================
...
Assigned scheduled publish time: 2025-11-23T11:00:00+00:00
Set planned_publish_at in metadata: 2025-11-23T11:00:00+00:00
...
============================================================
Starting YouTube upload
Scheduling video for 2025-11-23T11:00:00+00:00
Setting publishAt to: 2025-11-23T11:00:00+00:00
...
✅ Scheduled publish confirmed: 2025-11-23T11:00:00Z
   Video will be published at: 2025-11-23 11:00:00+00:00
============================================================
```

---

## Technical Details

### ScheduleManager

**File:** `app/services/schedule_manager.py`

- Uses Python 3.9+ `zoneinfo` (or falls back to `pytz` for older Python)
- Returns timezone-aware `datetime` objects
- Handles timezone localization correctly

### YouTube Uploader

**File:** `app/services/youtube_uploader.py`

- Accepts `scheduled_publish_at: Optional[datetime]` parameter
- Converts to RFC 3339 format for YouTube API
- Handles timezone-aware and naive datetimes
- Automatically sets `privacy_status = "private"` when scheduling

### Metadata Model

**File:** `app/models/schemas.py`

- `planned_publish_at: Optional[datetime]` field in `EpisodeMetadata`
- Serializes to ISO string in JSON
- Parses back to datetime on load

---

## Troubleshooting

### Timezone Issues

**Problem:** Scheduled times are in wrong timezone

**Solution:** 
- Check `ScheduleManager` timezone initialization
- Verify timezone string is valid (e.g., "Europe/London", "America/New_York")
- Use `pytz.all_timezones` to list valid timezones

### Scheduling Not Working

**Problem:** Videos publish immediately instead of scheduled time

**Solution:**
- Check logs for "Scheduling video for..." message
- Verify `publishAt` is in API request (check YouTube API response)
- Ensure `privacy_status` is set to "private" (required for scheduling)

### Metadata Not Saved

**Problem:** `planned_publish_at` not in episode JSON

**Solution:**
- Check logs for "Set planned_publish_at in metadata" message
- Verify `repository.save_episode()` is called after setting scheduled time
- Check JSON serialization (should use `model_dump(mode='json')`)

---

## Future Enhancements

Potential improvements:
- Configurable posting hours via settings
- Day-of-week specific schedules
- Timezone per video (for multi-region channels)
- Schedule conflict detection
- Reschedule failed uploads

---

## Summary

✅ **Scheduling is fully implemented:**
- Daily mode with automatic time slot assignment
- Metadata persistence for scheduled times
- YouTube API integration for scheduled uploads
- Comprehensive logging and error handling
- Backward compatible (existing workflows unchanged)

**Ready for production use!**

