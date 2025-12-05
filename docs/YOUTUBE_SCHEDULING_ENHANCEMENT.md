# YouTube Scheduling Enhancement

**Date:** 2025-11-23  
**Status:** ✅ Complete

---

## Summary

Enhanced YouTube scheduling support with **configurable timezone and posting hours** via environment variables. The system now fully supports automated daily batch generation with scheduled uploads.

---

## What Was Enhanced

### 1. Configurable Timezone ✅

**Before:** Hardcoded `Europe/London` timezone  
**After:** Configurable via `TIMEZONE` environment variable

**Configuration:**
```bash
# In .env file
TIMEZONE=America/New_York
```

**Supported:** Any valid IANA timezone string (e.g., `Europe/London`, `America/New_York`, `America/Los_Angeles`, `America/Chicago`)

### 2. Configurable Posting Hours ✅

**Before:** Hardcoded `[11, 14, 18, 20, 22]` hours  
**After:** Configurable via `DAILY_POSTING_HOURS` environment variable

**Configuration:**
```bash
# In .env file (comma-separated, 24-hour format)
DAILY_POSTING_HOURS=9,12,15,18,21
```

**Default:** `[11, 14, 18, 20, 22]` (11 AM, 2 PM, 6 PM, 8 PM, 10 PM)

### 3. Settings Integration ✅

Added new settings to `app/core/config.py`:
- `timezone: str = Field(default="Europe/London", ...)`
- `daily_posting_hours: list[int] = Field(default=[11, 14, 18, 20, 22], ...)`

### 4. ScheduleManager Updates ✅

- Made `posting_hours` a constructor parameter (no longer hardcoded class variable)
- Added validation for posting hours (must be integers 0-23)
- Updated to use configurable values from Settings

### 5. Pipeline Integration ✅

Updated `run_full_pipeline.py` to:
- Use `settings.timezone` instead of hardcoded value
- Use `settings.daily_posting_hours` instead of hardcoded list
- Log timezone and posting hours when daily mode is enabled

---

## Files Modified

1. **`app/core/config.py`**
   - Added `timezone` field (default: `"Europe/London"`)
   - Added `daily_posting_hours` field (default: `[11, 14, 18, 20, 22]`)

2. **`app/services/schedule_manager.py`**
   - Updated `__init__()` to accept `posting_hours` parameter
   - Added validation for posting hours
   - Removed hardcoded `POSTING_HOURS` class variable
   - Updated `get_daily_slots()` to use `self.posting_hours`

3. **`app/pipelines/run_full_pipeline.py`**
   - Updated to use `settings.timezone` and `settings.daily_posting_hours`
   - Added logging for timezone and posting hours

4. **`docs/scheduling_support.md`**
   - Updated configuration section with environment variable examples
   - Added supported timezone examples

5. **`README.md`**
   - Added configuration examples for timezone and posting hours

---

## Usage Examples

### Basic Daily Batch (Default Settings)

```bash
python run_full_pipeline.py --daily-mode --batch-count 5
```

**Result:**
- Uses `Europe/London` timezone
- Uses `[11, 14, 18, 20, 22]` posting hours
- Generates 5 videos scheduled at: 11:00, 14:00, 18:00, 20:00, 22:00

### Custom Timezone and Hours

**In `.env` file:**
```bash
TIMEZONE=America/New_York
DAILY_POSTING_HOURS=9,12,15,18,21
```

**Command:**
```bash
python run_full_pipeline.py --daily-mode --batch-count 5
```

**Result:**
- Uses `America/New_York` timezone
- Uses `[9, 12, 15, 18, 21]` posting hours
- Generates 5 videos scheduled at: 9:00, 12:00, 15:00, 18:00, 21:00 (Eastern Time)

### Custom Date

```bash
python run_full_pipeline.py --daily-mode --batch-count 5 --date 2025-11-25
```

Schedules videos for November 25, 2025 instead of today.

---

## How It Works

1. **Daily Mode Activation:**
   - User runs: `--daily-mode --batch-count 5`
   - System initializes `ScheduleManager` with:
     - Timezone from `settings.timezone` (or `TIMEZONE` env var)
     - Posting hours from `settings.daily_posting_hours` (or `DAILY_POSTING_HOURS` env var)

2. **Time Slot Assignment:**
   - `ScheduleManager.get_daily_slots(target_date, count)` generates timezone-aware datetime objects
   - If `count > len(posting_hours)`, hours cycle (e.g., with 5 hours and 7 videos: 9, 12, 15, 18, 21, 9, 12)

3. **Video Generation & Upload:**
   - Each batch item gets assigned a scheduled time slot
   - `planned_publish_at` is set in episode metadata
   - Video is uploaded to YouTube with `scheduled_publish_at` parameter
   - Video remains private until scheduled publish time

---

## Backward Compatibility

✅ **Fully backward compatible:**
- Default timezone (`Europe/London`) and posting hours (`[11, 14, 18, 20, 22]`) match previous hardcoded values
- Existing workflows continue to work unchanged
- No breaking changes to API or CLI

---

## Testing

**Syntax Check:**
```bash
python3 -m py_compile app/services/schedule_manager.py app/core/config.py app/pipelines/run_full_pipeline.py
```

**Expected:** ✅ All files compile without errors

**Manual Test:**
```bash
# Test with default settings
python run_full_pipeline.py --daily-mode --batch-count 3 --preview

# Test with custom timezone (set TIMEZONE in .env first)
python run_full_pipeline.py --daily-mode --batch-count 3 --preview
```

---

## Future Enhancements

1. **Time Window Configuration:** Support for posting windows (e.g., "10:00-20:00") instead of fixed hours
2. **Day-of-Week Patterns:** Different posting schedules for weekdays vs weekends
3. **Performance-Based Scheduling:** Optimize posting times based on historical performance data
4. **Multiple Timezones:** Support for scheduling across multiple timezones in a single batch

---

## Notes

- Timezone support requires Python 3.9+ (uses `zoneinfo`) or `pytz` package for older Python versions
- Posting hours must be integers between 0-23 (24-hour format)
- All scheduled times are timezone-aware and stored in ISO 8601 format
- YouTube requires videos to be `private` when scheduling (automatically handled)

