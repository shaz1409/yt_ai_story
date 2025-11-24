# Story & Pacing Quality Improvements

**Date:** 2025-11-22  
**Status:** ✅ Complete

---

## Overview

Implemented comprehensive improvements to story structure, pacing, and emotional impact. Focus is on **TEXT/STRUCTURE only** (no video rendering changes).

---

## Changes Implemented

### 1. Controlled Story Length & Pace

**File:** `app/services/story_rewriter.py`

#### Word Budget System
- **Calculation:** ~2.3 spoken words per second for narration
- **For 60s video:** Target 130-150 words (sweet spot: 140 words)
- **For other durations:** Proportional calculation (min 100 words)

#### LLM Prompt Updates
- Explicitly mentions target word count in prompt
- Instructions to keep beats concise, avoid long backstory dumps
- Word budget distribution guidance:
  - HOOK: 10-15% of words
  - TRIGGER/CONTEXT: 25-35%
  - CLASH/TWIST: 30-40%
  - CTA: 10-15%

#### Validation & Regeneration
- Validates total word count after LLM generation
- If text is < 70% of target, logs warning and regenerates once
- Falls back to original if regeneration still too short
- Logs word distribution by beat type

#### Logging
- Total narration words vs target
- Word distribution by beat type (with percentages)
- Warning if story significantly shorter than target

---

### 2. Stronger, Darker Hooks

**File:** `app/services/story_rewriter.py` (`_generate_story_from_beats`)

#### HOOK Requirements
- **Must start with either:**
  - (a) Shocking line of dialogue (e.g., "The judge laughed as he read the sentence.")
  - (b) Visceral image (e.g., "A teenager smirks as the victim's family sobs in court.")
- **Must grab attention within 1-2 seconds**
- **Must be emotionally triggering** (shock, outrage, injustice)

#### Emotional Framing
- "Lean into outrage, injustice, and shock. This is not neutral news – make viewers feel something immediately."
- "Focus less on legal realism and more on emotional impact and moral conflict."
- Emphasizes emotional impact over factual accuracy

#### Logging
- Logs first HOOK line (first 100 characters) for quick inspection

---

### 3. Viewer-Involving CTA

**File:** `app/services/story_rewriter.py` (`_generate_story_from_beats`)

#### CTA Requirements
- **MUST end with a single, direct question** aimed at the viewer
- **Explicitly asks for opinion in comments**
- Examples provided:
  - "Should the judge have gone easier on them?"
  - "Was this justice, or did the system fail?"
  - "If this happened in your city, what would YOU want the sentence to be?"

#### Implementation
- CTA is separate beat and becomes final narration line
- `has_cta = True` flag remains correct in metadata
- CTA gets 10-15% of word budget

#### Logging
- Logs final CTA line for inspection

---

### 4. Dialogue-Narration Balance

**Files:** 
- `app/services/dialogue_engine.py`
- `app/services/llm_client.py`

#### Dialogue Prioritization
- **HOOK scenes:** ONE extremely strong line (e.g., from judge/defendant/victim)
- **CLASH/TWIST scenes:** 2-3 lines of back-and-forth dialogue
- **Other scenes:** 1-2 lines as needed

#### LLM Prompt Updates
- **Critical constraint:** "Do NOT restate the narrator's sentences. Instead, write what the characters would actually say or shout in that moment."
- Characters should react emotionally to described events, not repeat them
- Avoid dialogue that simply repeats narration text

#### Implementation
- `_generate_scene_dialogue` adjusts `max_lines` based on scene role:
  - `hook`: 1 line
  - `conflict`/`twist`: 2-3 lines
  - Others: default (2 lines)

#### Logging
- Logs dialogue distribution by scene role
- Shows count of dialogue lines per role type

---

### 5. Comprehensive Logging

#### Story Rewriter Logging
- Target narration word count
- Total narration words vs target
- Word distribution by beat type (with percentages)
- Number of beats, scenes, narration lines
- First HOOK line (first 100 chars)
- Final CTA line
- Warning if story significantly shorter than target

#### Dialogue Engine Logging
- Total dialogue lines across scenes
- Dialogue distribution by scene role (hook, conflict, twist, etc.)

---

## Technical Details

### Word Budget Calculation

```python
# For 60s video
target_word_count = 140  # Sweet spot

# For other durations
target_word_count = max(100, int(duration_seconds * 2.3))
```

### Word Distribution Targets

| Beat Type | Target % | Example (140 words) |
|-----------|----------|---------------------|
| HOOK | 10-15% | 14-21 words |
| TRIGGER/CONTEXT | 25-35% | 35-49 words |
| CLASH/TWIST | 30-40% | 42-56 words |
| CTA | 10-15% | 14-21 words |

### Validation Threshold

- **Minimum:** 70% of target word count
- **Example:** For 140 words target, minimum is 98 words
- **If below minimum:** Regenerates once with stronger word count emphasis

---

## Example Log Output

```
Target narration word count: 140 words (for 60s video)
Generated 6 beats using pattern A
Total narration words: 145 (target: 140, min: 98)
HOOK line: The judge laughed as he read the sentence. The courtroom fell silent...
CTA line: Should the judge have gone easier on them? What do YOU think?
Word distribution by beat type:
  HOOK: 18 words (12.4%)
  TRIGGER: 12 words (8.3%)
  CONTEXT: 35 words (24.1%)
  CLASH: 52 words (35.9%)
  TWIST: 18 words (12.4%)
  CTA: 10 words (6.9%)
Built script with 5 scenes, 6 beats, 7 narration lines (pattern: A)
Generated 10 dialogue lines across 5 scenes
Dialogue by scene role: hook: 1, conflict: 3, twist: 2, setup: 1, resolution: 0
```

---

## Files Modified

1. ✅ `app/services/story_rewriter.py`
   - Updated `_generate_story_from_beats` prompt with word budget, stronger hooks, CTA requirements
   - Added word count validation and regeneration logic
   - Updated `_build_script_from_beats` to log word distribution
   - Added comprehensive logging (HOOK, CTA, word counts)

2. ✅ `app/services/dialogue_engine.py`
   - Updated `_generate_scene_dialogue` to prioritize HOOK (1 line) and CLASH/TWIST (2-3 lines)
   - Added dialogue distribution logging by scene role

3. ✅ `app/services/llm_client.py`
   - Updated `generate_dialogue` prompt to avoid repeating narration
   - Added constraint: "Do NOT restate the narrator's sentences"
   - Updated dialogue prioritization instructions

---

## Expected Improvements

### Before
- Stories often too short (10-15 seconds of narration)
- Weak hooks that don't grab attention
- Generic CTAs that don't invite engagement
- Dialogue that repeats narration
- Unbalanced word distribution

### After
- Stories reliably fill 55-60 seconds of narration
- Strong hooks with shocking dialogue or visceral images
- Direct, engaging CTAs that ask for viewer opinion
- Dialogue that reacts emotionally, doesn't repeat narration
- Balanced word distribution across beats
- Comprehensive logging for quality inspection

---

## Testing

### Manual Testing Checklist

- [ ] Generate story with 60s target duration
- [ ] Verify total narration words is 130-150
- [ ] Check HOOK line is shocking/visceral
- [ ] Verify CTA ends with direct question
- [ ] Check word distribution is balanced
- [ ] Verify HOOK scene has 1 dialogue line
- [ ] Verify CLASH/TWIST scenes have 2-3 dialogue lines
- [ ] Check dialogue doesn't repeat narration
- [ ] Review logs for word counts and distribution

### Example Test Command

```bash
python run_full_pipeline.py --topic "teen laughs in court" --style courtroom_drama --duration-target-seconds 60 --preview
```

Check logs for:
- "Target narration word count: 140 words"
- "Total narration words: XXX (target: 140)"
- "HOOK line: ..."
- "CTA line: ..."
- "Word distribution by beat type:"

---

## Summary

✅ **All requirements implemented:**
- Word budget system with validation
- Stronger, darker hooks (shocking dialogue or visceral images)
- Viewer-involving CTAs (direct questions)
- Dialogue-narration balance (prioritize HOOK/CLASH/TWIST, avoid repetition)
- Comprehensive logging (word counts, HOOK, CTA, dialogue distribution)

**Ready for testing and refinement!**

