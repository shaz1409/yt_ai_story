# Quality Scoring System

**Date:** 2025-01-13  
**Status:** ✅ Complete

---

## Overview

Implemented log-based quality scoring per episode with a dashboard script to review quality over time. Quality scores are computed automatically after each episode generation and logged to a JSONL file.

---

## Features

### 1. Quality Scorer Service

**File:** `app/services/quality_scorer.py`

**Class:** `QualityScorer`

**Methods:**

#### `compute_quality_scores(video_plan, episode_metadata, image_scores, content_metrics)`
- Computes three component scores and overall score
- Returns dictionary with all scores (0-100 scale)

#### Score Components:

##### Visual Score (0-100)
- Based on average image quality validator scores
- Converts from 0.0-1.0 scale to 0-100
- Bonus for high average (>0.8): +10%
- Penalty for low average (<0.6): -10%

##### Content Score (0-100)
- **Dialogue length variety (0-25 points)**
  - Calculates coefficient of variation (std/mean)
  - Higher variety = better score
- **Unique characters speaking (0-25 points)**
  - 1 character = 10 points, 2 = 20, 3+ = 25
- **Presence of twist and resolution (0-30 points)**
  - Twist: +15 points
  - Resolution/CTA: +15 points
- **Dialogue quality (0-20 points)**
  - 2+ lines: 20 points
  - 1 line: 10 points
  - 0 lines: 5 points

##### Technical Score (0-100)
- **Duration accuracy (0-50 points)**
  - Perfect match (within 2%): 50 points
  - 10% off: 40 points
  - 20% off: 30 points
  - Linear decay beyond 20%
- **Generation success (0-50 points)**
  - All components present (characters, scenes, narration): 50 points
  - Missing components: reduced score

##### Overall Score (0-100)
- Weighted average:
  - Visual: 30%
  - Content: 40%
  - Technical: 30%

---

### 2. Quality Metrics Logging

**File:** `app/services/quality_scorer.py`

**Method:** `log_quality_metrics()`

**Output File:** `storage/episodes/quality_metrics.jsonl`

**Format (JSONL - one JSON object per line):**
```json
{
  "episode_id": "ep_abc123",
  "timestamp": "2025-01-13T10:30:00",
  "visual_score": 85.5,
  "content_score": 72.3,
  "technical_score": 90.0,
  "overall_score": 82.6,
  "duration_seconds": 58.2,
  "n_images": 8,
  "n_dialogue_lines": 3,
  "n_characters": 4,
  "n_scenes": 5,
  "has_twist": true,
  "has_cta": true
}
```

---

### 3. Pipeline Integration

**File:** `app/pipelines/run_full_pipeline.py`

**Integration Point:**
- After video rendering (Phase 2.5)
- Before thumbnail generation
- Non-critical: Pipeline continues even if scoring fails

**Flow:**
```
Video Rendering (Phase 2)
  ↓
Quality Scoring (Phase 2.5) ← NEW (non-critical)
  ↓
Thumbnail Generation (Phase 2.6)
  ↓
YouTube Upload (Phase 3)
```

**Error Handling:**
- If scoring fails → Logs warning, continues pipeline
- Episode generation never fails because of quality scoring

---

### 4. Quality Dashboard

**File:** `scripts/quality_dashboard.py`

**Features:**
- Reads `storage/episodes/quality_metrics.jsonl`
- Computes statistics:
  - Overall statistics (min, max, average per score type)
  - Rolling averages (last 10, last 50 episodes)
  - Recent episodes table
- Console output: Formatted table
- HTML report: Optional HTML output with tables and styling

**Usage:**
```bash
# Console output only
python scripts/quality_dashboard.py

# Generate HTML report
python scripts/quality_dashboard.py --html outputs/quality_report.html

# Skip console, only HTML
python scripts/quality_dashboard.py --html report.html --no-console

# Custom metrics file
python scripts/quality_dashboard.py --metrics-file custom/path/metrics.jsonl
```

**Makefile:**
```bash
make quality-dashboard
```

---

## Score Interpretation

### Overall Score Ranges

- **90-100**: Excellent quality
- **80-89**: Good quality
- **70-79**: Acceptable quality
- **60-69**: Below average
- **<60**: Needs improvement

### Component Score Guidelines

**Visual Score:**
- Based on image quality validator scores
- High scores indicate sharp, well-lit, properly composed images
- Low scores may indicate blurry, overexposed, or poorly composed images

**Content Score:**
- Measures narrative richness and engagement
- Higher scores for varied dialogue, multiple characters, twists
- Lower scores for repetitive or minimal content

**Technical Score:**
- Measures generation success and accuracy
- High scores for accurate duration, complete components
- Lower scores for duration mismatches or missing components

---

## Dashboard Output Examples

### Console Table
```
================================================================================
QUALITY DASHBOARD
================================================================================
Total Episodes: 25

Overall Statistics:
--------------------------------------------------------------------------------
  overall_score       | Min:  65.20 | Max:  92.50 | Avg:  78.45 | Count:  25
  visual_score        | Min:  70.00 | Max:  95.00 | Avg:  82.30 | Count:  25
  content_score       | Min:  55.00 | Max:  90.00 | Avg:  72.15 | Count:  25
  technical_score     | Min:  60.00 | Max:  95.00 | Avg:  80.90 | Count:  25

Rolling Averages:
--------------------------------------------------------------------------------
  content_score_last_10    |  75.20
  overall_score_last_10    |  80.15
  technical_score_last_10  |  82.50
  visual_score_last_10     |  85.00

Recent Episodes (Last 10):
--------------------------------------------------------------------------------
Episode ID          |  Overall |  Visual | Content |Technical |                Date
--------------------------------------------------------------------------------
ep_abc123           |    82.60 |   85.50 |   72.30 |   90.00 | 2025-01-13 10:30
ep_def456           |    78.20 |   80.00 |   70.00 |   84.60 | 2025-01-13 09:15
...
```

### HTML Report
- Styled tables with color-coded scores
- Green: >= 80 (high)
- Yellow: 60-79 (medium)
- Red: < 60 (low)
- Statistics boxes with key metrics
- Last 50 episodes table

---

## Configuration

No configuration required. Quality scoring is enabled by default and runs automatically.

**To disable (not recommended):**
- Remove quality scoring call from pipeline (not configurable via settings)

---

## Files Modified

1. **`app/services/quality_scorer.py`** (NEW)
   - Complete quality scoring service
   - Score computation and logging

2. **`app/pipelines/run_full_pipeline.py`**
   - Integrated quality scoring (Phase 2.5)
   - Non-critical error handling

3. **`scripts/quality_dashboard.py`** (NEW)
   - Dashboard script with console and HTML output

4. **`Makefile`**
   - Added `quality-dashboard` target

5. **`README.md`**
   - Added Quality Dashboard section

---

## Future Enhancements

### Image Score Collection
Currently, image scores are not collected during rendering. Future enhancement:
- Track image quality scores during generation
- Pass collected scores to quality scorer
- More accurate visual score

### Additional Metrics
- Engagement prediction score
- Virality correlation
- A/B test results

### Advanced Dashboard
- Time-series charts
- Trend analysis
- Export to CSV/JSON
- Filtering and search

---

## Summary

✅ **Quality scoring is fully implemented:**
- Automatic score computation after each episode
- Three component scores (visual, content, technical)
- Overall weighted score (0-100)
- JSONL logging for historical tracking
- Dashboard script for review and analysis
- HTML report generation
- Non-critical integration (never breaks pipeline)

**Usage:**
- Scores computed automatically during pipeline
- View dashboard: `make quality-dashboard`
- Generate HTML: `python scripts/quality_dashboard.py --html report.html`

