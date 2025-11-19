# Story Sourcing & Virality Scoring Implementation

## Overview

This document describes the implementation of the **Story Sourcing & Virality Scoring Engine** that was added to the AI Story Shorts Factory pipeline. This new layer sits **before** the story rewriting step and enables automatic selection of high-virality stories from specific niches.

## New Files

### 1. `app/services/story_source.py`
**StorySourceService** - Generates multiple story candidates for given niches or topics.

**Key Methods:**
- `generate_candidates_from_topic(topic, niche, num_candidates)` - Generate candidates based on a specific topic
- `generate_candidates_for_niche(niche, num_candidates)` - Generate candidates for a niche without a specific topic

**Features:**
- Stub-based generation using niche-specific templates (courtroom, relationship_drama, injustice, workplace_drama)
- Optional LLM-based generation (when `use_llm_for_story_finder` config is enabled)
- Clean interface for swapping stubs with real data sources later

### 2. `app/services/virality_scorer.py`
**ViralityScorer** - Scores story candidates on multiple emotional and virality dimensions.

**Key Methods:**
- `score_candidate(candidate)` - Compute detailed virality score for a single candidate
- `rank_candidates(candidates)` - Score and rank all candidates by overall_score (descending)

**Scoring Dimensions:**
- `shock` (30% weight) - Surprising, unexpected events
- `rage` (25% weight) - Triggers anger/indignation
- `injustice` (20% weight) - Unfair treatment, bad outcomes
- `relatability` (10% weight) - Common situations people recognize
- `twist_strength` (10% weight) - How strong the twist/reversal is
- `clarity` (5% weight) - How easy the story is to follow

**Features:**
- Heuristic-based scoring using keyword analysis
- Optional LLM-based scoring (when `use_llm_for_story_finder` config is enabled)
- Weighted overall score calculation

### 3. Updated `app/models/schemas.py`
**New Models:**
- `StoryCandidate` - Enhanced with `id`, `source`, and `niche` fields
- `ViralityScore` - Detailed scoring model with all virality dimensions

### 4. Updated `run_full_pipeline.py`
**New CLI Flags:**
- `--auto-topic` - Automatically select a high-virality story from the specified niche
- `--niche` - Story niche for auto-topic selection (default: "courtroom")
- `--num-candidates` - Number of candidates to generate (default: 5)

**Integration:**
- When `--auto-topic` is used, the pipeline:
  1. Generates N candidates for the specified niche
  2. Scores and ranks them by virality
  3. Selects the top candidate
  4. Passes its `raw_text` to the existing story rewriting pipeline
- Backward compatible: `--topic` still works as before

### 5. Tests
- `tests/test_story_source.py` - Unit tests for StorySourceService
- `tests/test_virality_scorer.py` - Unit tests for ViralityScorer

## Usage Examples

### Auto-select a high-virality courtroom story:
```bash
python run_full_pipeline.py --auto-topic --niche "courtroom" --auto-upload
```

### Auto-select from relationship_drama niche with 10 candidates:
```bash
python run_full_pipeline.py --auto-topic --niche "relationship_drama" --num-candidates 10 --duration-target-seconds 60
```

### Traditional mode (still works):
```bash
python run_full_pipeline.py --topic "teen laughs in court" --style "courtroom_drama"
```

## Example Log Output

When using `--auto-topic`, you'll see logs like:

```
============================================================
PHASE 0: Story Sourcing & Virality Scoring
============================================================
Generating 5 candidates for niche: courtroom
Scoring candidates for virality...
Top 3 candidates by virality:
  1. Judge's Verdict Shocks Everyone in Courtroom... (score: 0.823, shock=0.85, rage=0.60)
  2. Teen's Reaction to Sentence Goes Viral... (score: 0.791, shock=0.80, rage=0.55)
  3. Courtroom Erupts After Unexpected Verdict... (score: 0.765, shock=0.75, rage=0.70)
============================================================
SELECTED CANDIDATE:
  ID: candidate_abc123def456
  Title: Judge's Verdict Shocks Everyone in Courtroom
  Overall Score: 0.823
  Breakdown: shock=0.85, rage=0.60, injustice=0.70, relatability=0.65, twist=0.80, clarity=0.90
============================================================
Top 3 candidates:
  1. Judge's Verdict Shocks Everyone in Courtroom... (score: 0.823)
  2. Teen's Reaction to Sentence Goes Viral... (score: 0.791)
  3. Courtroom Erupts After Unexpected Verdict... (score: 0.765)
```

## Architecture Notes

### Modularity
- All services use clean interfaces that can be swapped with real implementations
- Stub logic is clearly separated from LLM logic
- Configuration-driven (use `use_llm_for_story_finder` setting to enable LLM)

### Backward Compatibility
- Existing `--topic` mode still works
- `StoryCandidate` model maintains backward compatibility with `source_id` field
- `StoryFinder` service still works independently

### Extensibility
- Easy to add new niches by adding templates to `NICHE_TEMPLATES`
- Easy to add new scoring dimensions by updating `ViralityScore` model
- Easy to swap stub generation with real scraping/API calls

## Configuration

To enable LLM-based story generation and scoring, add to your `.env`:

```bash
USE_LLM_FOR_STORY_FINDER=true
OPENAI_API_KEY=your_key_here
```

## Next Steps

1. **Real Data Sources**: Replace stub generation with actual scraping/API calls
2. **Advanced Scoring**: Fine-tune scoring weights based on performance data
3. **Niche Expansion**: Add more niche templates (e.g., "karma", "revenge", "redemption")
4. **A/B Testing**: Track which virality scores correlate with actual video performance
5. **Caching**: Cache generated candidates to avoid regenerating for same niche

