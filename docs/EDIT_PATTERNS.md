# Edit Patterns / Visual Style

**Date:** 2025-11-22  
**Status:** ✅ Complete

---

## Overview

Introduced structural variation through "edit patterns" (visual styles) per episode to prevent videos from feeling copy-paste. Each episode is assigned one of three patterns that determines how clips are selected, durations are allocated, and transitions are applied.

---

## Edit Patterns

### 1. `talking_head_heavy`

**Focus:** More screen time for characters

**Behavior:**
- When dialogue clips exist, favor them heavily
- For each scene with dialogue, ensure at least one talking-head is shown
- Talking-head clips occupy **60-70% of scene duration** (default: 65%)
- B-roll used for intro/outro and brief transitions between TH clips
- Best for: Strong dialogue, character-driven stories

**Example Timeline:**
```
0.0s - 1.5s: B-roll intro
1.5s - 5.0s: Talking-head clip 1
5.0s - 6.0s: B-roll transition
6.0s - 9.5s: Talking-head clip 2
9.5s - 11.0s: B-roll outro
```

---

### 2. `broll_cinematic`

**Focus:** Mostly b-roll + narrator, minimal talking-head

**Behavior:**
- Use b-roll as primary visual
- Only occasionally insert talking-head (max 1 per scene, short: max 3s or 20% of scene)
- Longer, smoother b-roll segments (~4-5s per segment)
- Smooth crossfades between segments (0.4s)
- Best for: Documentary/newsy tone, narration-heavy stories

**Example Timeline:**
```
0.0s - 4.5s: B-roll segment 1 (smooth crossfade)
4.5s - 7.0s: B-roll segment 2 (smooth crossfade)
7.0s - 9.5s: B-roll segment 3 (smooth crossfade)
9.5s - 12.0s: B-roll segment 4 (smooth crossfade)
```

**With one talking-head:**
```
0.0s - 5.0s: B-roll segment 1
5.0s - 7.5s: Talking-head (short, max 3s)
7.5s - 12.0s: B-roll segment 2
```

---

### 3. `mixed_rapid`

**Focus:** Fast alternation between b-roll and talking-head, quicker cuts

**Behavior:**
- Shorter clip durations especially in first 10 seconds
- Hard cap: **1.5-2.0s per clip** at the start, 3.5s later
- Alternate TH / BROLL / TH where dialogue exists
- Quick cuts with fast transitions (0.15-0.2s)
- Best for: High-energy content, ragebait, attention-grabbing

**Example Timeline (first 10 seconds):**
```
0.0s - 1.8s: B-roll (quick cut)
1.8s - 3.5s: Talking-head (quick cut)
3.5s - 5.2s: B-roll (quick cut)
5.2s - 7.0s: Talking-head (quick cut)
7.0s - 8.5s: B-roll (quick cut)
```

---

## Pattern Assignment

**File:** `app/services/video_plan_engine.py`

### Rule-Based Assignment

Pattern is assigned based on:

1. **Dialogue ratio:**
   - **High dialogue (>40%):** → `talking_head_heavy`
   - **Low dialogue (<15%):** → `broll_cinematic`
   - **Medium dialogue (15-40%):** → Weighted random based on niche

2. **Niche/Style weights:**

   **Courtroom:**
   - `talking_head_heavy`: 0.4
   - `broll_cinematic`: 0.2
   - `mixed_rapid`: 0.4

   **Relationship Drama:**
   - `talking_head_heavy`: 0.5
   - `broll_cinematic`: 0.3
   - `mixed_rapid`: 0.2

   **Injustice:**
   - `talking_head_heavy`: 0.3
   - `broll_cinematic`: 0.4
   - `mixed_rapid`: 0.3

   **Ragebait style:**
   - `talking_head_heavy`: 0.3
   - `broll_cinematic`: 0.2
   - `mixed_rapid`: 0.5 (favors rapid cuts)

### Logging

- Logs dialogue ratio and assignment reason
- Logs sampled pattern and weights (for weighted random)

---

## Implementation Details

### Pattern Constants

**File:** `app/services/video_plan_engine.py`

```python
EDIT_PATTERN_TALKING_HEAD_HEAVY = "talking_head_heavy"
EDIT_PATTERN_BROLL_CINEMATIC = "broll_cinematic"
EDIT_PATTERN_MIXED_RAPID = "mixed_rapid"
```

### Metadata Storage

**File:** `app/models/schemas.py`

- Added `edit_pattern: Optional[str]` to `EpisodeMetadata`
- Stored in episode JSON for persistence

### Video Renderer Integration

**File:** `app/services/video_renderer.py`

- Reads `edit_pattern` from `video_plan.metadata`
- Logs pattern at start of render: `"Edit pattern for this episode: {edit_pattern}"`
- Adjusts clip selection and durations based on pattern
- Falls back to default behavior if pattern is None or unknown

---

## Pattern-Specific Behaviors

### Talking-Head Heavy

**Dialogue scenes:**
- 65% of scene duration allocated to talking-heads
- 35% allocated to b-roll (intro, transitions, outro)
- Ensures at least one talking-head per scene with dialogue

**Narration-only scenes:**
- Uses default b-roll cuts (max 3.5s per cut)

---

### B-Roll Cinematic

**Dialogue scenes:**
- Max 1 talking-head per scene
- Talking-head duration: max 3s or 20% of scene
- Inserted in middle of scene
- Rest is smooth b-roll segments with crossfades

**Narration-only scenes:**
- Longer segments (~4-5s per segment)
- Smooth crossfades (0.4s)
- No quick cuts

---

### Mixed Rapid

**Dialogue scenes:**
- Fast alternation: BROLL → TH → BROLL → TH
- Clip durations: 1.5-2.0s in first 10 seconds, 3.5s later
- Quick transitions (0.15-0.2s)

**Narration-only scenes:**
- Shorter cuts: 1.5-2.0s in first 10 seconds, 3.5s later
- Quick transitions (0.15-0.2s)

---

## Fallback Behavior

If `edit_pattern` is None or unknown:
- Uses default rendering behavior (existing logic)
- Logs: `"No edit pattern set, using default rendering behaviour."`
- Maintains backward compatibility with older episodes

---

## Files Modified

1. ✅ `app/models/schemas.py`
   - Added `edit_pattern: Optional[str]` to `EpisodeMetadata`

2. ✅ `app/services/video_plan_engine.py`
   - Added pattern constants
   - Added `_assign_edit_pattern()` method
   - Added `_get_pattern_weights_for_niche()` method
   - Integrated pattern assignment into `create_video_plan()`

3. ✅ `app/services/video_renderer.py`
   - Updated `render()` to log edit pattern
   - Updated `_compose_video()` to use pattern-specific logic:
     - `talking_head_heavy`: 65% TH, 35% b-roll
     - `broll_cinematic`: Max 1 short TH, smooth b-roll segments
     - `mixed_rapid`: Fast alternation, short clips (1.5-2.0s early, 3.5s later)
   - Pattern-specific transitions and cut durations

---

## Expected Improvements

### Before
- All videos used same clip selection and duration logic
- No structural variation between episodes
- Videos felt copy-paste

### After
- **Structural variation** through 3 distinct patterns
- **Pattern-specific behaviors:**
  - Talking-head heavy: More character screen time
  - B-roll cinematic: Documentary/newsy feel
  - Mixed rapid: High-energy, attention-grabbing
- **Automatic assignment** based on dialogue ratio and niche
- **Backward compatible** with fallback to default behavior

---

## Testing

### Manual Testing Checklist

- [ ] Generate video with high dialogue ratio (>40%)
- [ ] Verify pattern is `talking_head_heavy`
- [ ] Check logs show "Edit pattern for this episode: talking_head_heavy"
- [ ] Verify talking-head clips occupy ~65% of scene duration
- [ ] Generate video with low dialogue ratio (<15%)
- [ ] Verify pattern is `broll_cinematic`
- [ ] Check b-roll segments are longer (~4-5s) with smooth crossfades
- [ ] Generate video with medium dialogue ratio
- [ ] Verify pattern is sampled based on niche weights
- [ ] Generate video with ragebait style
- [ ] Verify pattern favors `mixed_rapid`
- [ ] Check first 10 seconds have short clips (1.5-2.0s)
- [ ] Verify fallback behavior when pattern is None

### Example Test Commands

```bash
# High dialogue (should get talking_head_heavy)
python run_full_pipeline.py --topic "judge confronts defendant" --style courtroom_drama --preview

# Low dialogue (should get broll_cinematic)
python run_full_pipeline.py --topic "courtroom overview" --style courtroom_drama --preview

# Ragebait style (should favor mixed_rapid)
python run_full_pipeline.py --topic "shocking verdict" --style ragebait --preview
```

Check logs for:
- "Edit pattern for this episode: ..."
- Pattern-specific behavior logs (e.g., "allocating 65% to TH, 35% to b-roll")
- Clip durations and transitions

---

## Summary

✅ **All requirements implemented:**
- Defined 3 edit patterns (talking_head_heavy, broll_cinematic, mixed_rapid)
- Pattern assignment based on dialogue ratio and niche weights
- Pattern-specific clip selection and durations in video renderer
- Comprehensive logging
- Fallback behavior for None/unknown patterns

**Ready for testing and refinement!**

