# Story Quality Improvements Summary

**Date:** 2025-01-27  
**Goal:** Improve story quality for maximum watch-through without changing interfaces

---

## PART A — StoryRewriter Improvements

### Changes Made:

1. **Viral-Strength HOOK Templates**
   - Added 4 proven template structures:
     * "I wasn't supposed to see this, but..."
     * "This started normally—then everything changed."
     * "He thought no one would ever find out."
     * "Everyone warned her, and she ignored them."
   - HOOK must use one of these templates OR shocking dialogue OR visceral image

2. **New Beat Structure**
   - Updated beat types to include:
     * HOOK
     * SETUP
     * CONFRONTATION
     * ESCALATION
     * TURNING_POINT
     * CONSEQUENCE
     * OUTCOME
     * FINAL_STING (replaces CTA)
   
3. **FINAL_STING Beat**
   - Must be exactly ONE powerful sentence
   - Examples:
     * "And that's how everything changed."
     * "She still won't admit it was her fault."
     * "He regrets every second of it."
   - Replaces old CTA (backward compatible)

4. **Length Constraints**
   - MAX 2-3 sentences per beat section
   - Narrative propulsion > descriptive filler
   - Minimal backstory

### Files Modified:
- `app/services/story_rewriter.py` - Updated prompt and beat processing

---

## PART B — DialogueEngine Improvements

### Changes Made:

1. **Natural Emotional Speech**
   - Added sentence starters:
     * "Wait—what?"
     * "You can't be serious."
     * "That's not what happened."
     * "Are you lying to me right now?"

2. **Interruptions and Cut-Offs**
   - Use ellipsis (...) for trailing thoughts
   - Use double dashes (--) for cut-offs
   - Examples:
     * "Wait—what did you just say?"
     * "I can't believe you—"
     * "That's not... that's not possible."

3. **No Passive Narration**
   - NEVER: "He explained that she was not being honest."
   - INSTEAD: "Are you lying to me right now?"
   - Characters speak directly, not through narration

4. **Emotion-Based Speech Patterns**
   - **anger** → clipped speech, direct confrontation
   - **shock** → one-word reactions, disbelief
   - **sad** → pauses, softer language, trailing off
   - **tense** → rapid questions, contradictions, defensive

5. **Variety Requirements** (at least 1 per scene):
   - Rhetorical question
   - Small talk denial
   - Contradiction line
   - Escalating statement

### Files Modified:
- `app/services/llm_client.py` - Updated dialogue generation prompt

---

## PART C — VideoPlanEngine Improvements

### Changes Made:

1. **HOOK Linkage**
   - First visual scene explicitly linked to HOOK text
   - Logs confirmation when HOOK is found in first scene

2. **Character Spoken Lines Timing**
   - Ensures lines occur every 8-12 seconds
   - New method: `_sample_character_spoken_lines_with_timing()`
   - Replaces old method (kept for backward compatibility)

3. **Reveal/Contradiction Detection**
   - Lines are scored and prioritized for:
     * Reveal keywords: "not", "never", "didn't", "actually", "truth", "real", "secret", "hidden"
     * Contradiction keywords: "but", "however", "except", "though"
     * Rhetorical questions (boosted score)
   - High-scoring lines (reveals/contradictions) are prioritized

4. **Reveal Points Field**
   - Added optional `reveal_points: Optional[list[int]]` to `VideoPlan` schema
   - Contains timestamps (in seconds) when revelations occur
   - Calculated from:
     * Character spoken lines with reveal/contradiction keywords
     * Scene descriptions with "TURNING_POINT" or "TWIST"
   - Backward compatible (optional field)

### Files Modified:
- `app/services/video_plan_engine.py` - Added timing logic and reveal point calculation
- `app/models/schemas.py` - Added `reveal_points` field to `VideoPlan`

---

## Backward Compatibility

✅ **All changes are backward compatible:**
- No interface changes
- No breaking JSON changes
- Optional fields only
- Legacy methods kept for compatibility
- Old beat types (CTA) still supported

---

## Sample Generated JSON

```json
{
  "episode_id": "ep_20250127_001",
  "topic": "Courtroom drama - teen laughs at verdict",
  "duration_target_seconds": 60,
  "style": "courtroom_drama",
  "title": "Judge's Verdict Shocks Everyone",
  "logline": "A teenager's reaction to a life-changing verdict reveals the truth.",
  "characters": [...],
  "scenes": [
    {
      "scene_id": 1,
      "description": "HOOK: I wasn't supposed to see this, but the judge laughed as he read the sentence.",
      "narration": [
        {
          "text": "I wasn't supposed to see this, but the judge laughed as he read the sentence.",
          "emotion": "shock"
        }
      ],
      "emotion": "shocked"
    },
    ...
  ],
  "character_spoken_lines": [
    {
      "character_id": "char_judge_001",
      "line_text": "Wait—what did you just say?",
      "emotion": "shocked",
      "scene_id": 2,
      "approx_timing_seconds": 10.5
    },
    {
      "character_id": "char_defendant_001",
      "line_text": "That's not what happened. That's not—",
      "emotion": "defensive",
      "scene_id": 3,
      "approx_timing_seconds": 22.3
    },
    ...
  ],
  "reveal_points": [10, 22, 35, 48],
  "metadata": {...}
}
```

---

## Verification Checklist

✅ JSON still validates  
✅ Schemas still load  
✅ VideoRenderer still correctly maps lines  
✅ No default behaviour changes when no dialogue exists  
✅ All interfaces unchanged  
✅ Backward compatible with existing code  

---

**Improvements Complete** ✅
