# Repository Audit & Cleanup Plan
**Date:** 2025-11-22  
**Status:** Analysis Complete - Ready for Implementation

---

## Step 1: High-Level Audit

### Current Repository Structure

```
yt_auto_story/
├── app/                          # Main application code
│   ├── api/                      # FastAPI routes (minimal, 1 route)
│   ├── core/                     # Config, logging
│   ├── models/                   # Pydantic schemas
│   ├── pipelines/                # Orchestrators (run_full_pipeline.py)
│   ├── services/                 # Business logic (17 services)
│   ├── storage/                  # Episode repository
│   ├── utils/                    # Utility functions
│   └── main.py                   # FastAPI app entrypoint (unclear if used)
├── docs/                         # Documentation (13 markdown files)
├── scripts/                      # Utility scripts (test_hf_image.py)
├── storage/                      # ⚠️ DUPLICATE: Episode JSON files (root level)
├── tests/                        # Test suite (unit + integration)
├── outputs/                      # Generated videos, images, logs
├── secrets/                      # OAuth credentials (gitignored)
├── venv/                         # Virtual environment (gitignored)
├── run_full_pipeline.py          # ⚠️ WRAPPER: Convenience entrypoint
├── requirements_backend.txt       # Dependencies
├── pyproject.toml                # Project config
├── README.md                     # Main documentation
├── PROJECT_AUDIT.md              # ⚠️ ROOT DOC: Should move to docs/
├── GO_LIVE_UPGRADE_SUMMARY.md    # ⚠️ ROOT DOC: Should move to docs/
└── .gitignore                    # Git ignore rules
```

### Key Entry Points

1. **Primary CLI:** `run_full_pipeline.py` (root) → wraps `app/pipelines/run_full_pipeline.py`
2. **API Server:** `app/main.py` (FastAPI app, unclear if actively used)
3. **Test Scripts:** `scripts/test_hf_image.py`
4. **Test Suite:** `pytest tests/`

### Top-Level Folders & Responsibilities

| Folder | Responsibility | Status |
|--------|---------------|--------|
| `app/` | Core application code | ✅ Well-organized |
| `docs/` | Documentation | ✅ Good, but some root-level docs should move here |
| `scripts/` | Utility scripts | ✅ Minimal, appropriate |
| `tests/` | Test suite | ✅ Well-structured, mirrors `app/` |
| `storage/` | ⚠️ Episode JSON files | ⚠️ **DUPLICATE**: Should use `app/storage/` logic |
| `outputs/` | Generated content | ✅ Appropriate |
| `secrets/` | OAuth credentials | ✅ Gitignored, appropriate |

### Obvious Issues

1. **Duplicate Storage Paths:**
   - `storage/episodes/` at root (contains JSON files)
   - `app/storage/repository.py` uses `settings.storage_path` (likely points to root `storage/`)
   - **Issue:** Confusing to have both. Should consolidate.

2. **Root-Level Documentation:**
   - `PROJECT_AUDIT.md` - Should be in `docs/`
   - `GO_LIVE_UPGRADE_SUMMARY.md` - Should be in `docs/`

3. **Missing `.env.example`:**
   - No template for environment variables
   - Makes onboarding harder

4. **Service Duplication Check Needed:**
   - `character_engine.py` vs `character_video_engine.py` - Both are used, but need to verify they're not redundant
   - `character_engine.py`: Generates character metadata (names, personalities)
   - `character_video_engine.py`: Generates character face images and talking-head clips
   - **Status:** ✅ Not duplicates, different responsibilities

5. **FastAPI App (`app/main.py`):**
   - Exists but unclear if actively used
   - Only 1 route (`/stories/generate`)
   - **Status:** ⚠️ Keep but document if it's for future use or legacy

### Services Inventory

**17 services in `app/services/`:**
1. `character_engine.py` - Character metadata generation
2. `character_video_engine.py` - Character face images & talking-head clips
3. `dialogue_engine.py` - Dialogue generation (LLM-powered)
4. `hf_endpoint_client.py` - Hugging Face Inference Endpoint client
5. `llm_client.py` - Centralized OpenAI client
6. `metadata_generator.py` - Title, description, tags generation
7. `narration_engine.py` - Narration text generation
8. `optimisation_engine.py` - Batch optimization based on performance
9. `schedule_manager.py` - Daily posting schedule management
10. `story_finder.py` - Story candidate selection
11. `story_rewriter.py` - Story → script conversion (beat-based)
12. `story_source.py` - Story candidate generation
13. `tts_client.py` - Text-to-speech (ElevenLabs/OpenAI)
14. `video_plan_engine.py` - VideoPlan JSON creation
15. `video_renderer.py` - Final video composition
16. `virality_scorer.py` - Story virality scoring
17. `youtube_uploader.py` - YouTube upload & scheduling

**All services are actively used** ✅

---

## Repo Overview (for README)

### What This Project Does End-to-End

The **AI Story Shorts Factory** is an automated pipeline that generates viral YouTube Shorts from story topics:

1. **Story Sourcing** (optional): Finds or generates story candidates from niches (courtroom, relationship_drama, injustice) and scores them for virality
2. **Story Processing**: Converts raw story text into structured script with HOOK → TRIGGER → CONTEXT → CLASH → TWIST → CTA narrative beats
3. **Character Generation**: Creates unique characters (judge, defendant, lawyer) with appearance, personality, and voice profiles
4. **Content Generation**: Produces dialogue lines (LLM-powered), narration, and complete `VideoPlan` JSON
5. **Video Rendering**: 
   - Generates photoreal character face images (HF FLUX endpoint)
   - Creates talking-head clips for key dialogue lines
   - Generates emotion-aware scene b-roll images
   - Composes final vertical 1080x1920 .mp4 video with narration audio
6. **YouTube Upload** (optional): Uploads/schedules videos with metadata (title, description, tags)

**End-to-end flow:**
```
Topic/Niche → Story Candidates → Virality Scoring → Top Story → 
Script (Beats) → Characters → Dialogue → Narration → VideoPlan → 
Character Faces → Talking-Heads → Scene B-Roll → Final Video → 
YouTube Upload/Schedule
```

### Main Modules & How They Connect

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Entry Points                         │
│  run_full_pipeline.py → app/pipelines/run_full_pipeline.py │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
┌───────▼────────┐            ┌─────────▼──────────┐
│   Pipelines    │            │   API (FastAPI)    │
│  Orchestrators │            │   (Optional)       │
└───────┬────────┘            └───────────────────┘
        │
        │ Uses
        │
┌───────▼────────────────────────────────────────────────────┐
│                    Services Layer                           │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Story: story_source, virality_scorer, story_finder,  │ │
│  │        story_rewriter                                 │ │
│  │ Content: character_engine, dialogue_engine,           │ │
│  │          narration_engine, metadata_generator         │ │
│  │ Video: video_plan_engine, character_video_engine,     │ │
│  │        video_renderer, hf_endpoint_client             │ │
│  │ Platform: youtube_uploader, schedule_manager,         │ │
│  │           optimisation_engine                        │ │
│  │ Core: llm_client, tts_client                         │ │
│  └──────────────────────────────────────────────────────┘ │
└───────┬────────────────────────────────────────────────────┘
        │
        │ Uses
        │
┌───────▼────────────────────────────────────────────────────┐
│                    Core Layer                               │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ config.py (Settings from .env)                        │ │
│  │ logging_config.py (Loguru setup)                      │ │
│  └──────────────────────────────────────────────────────┘ │
└───────┬────────────────────────────────────────────────────┘
        │
        │ Uses
        │
┌───────▼────────────────────────────────────────────────────┐
│                    Models Layer                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ schemas.py (Pydantic models: VideoPlan, Episode,     │ │
│  │             Character, Scene, etc.)                   │ │
│  └──────────────────────────────────────────────────────┘ │
└───────┬────────────────────────────────────────────────────┘
        │
        │ Uses
        │
┌───────▼────────────────────────────────────────────────────┐
│                    Storage Layer                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ repository.py (EpisodeRepository - JSON file storage) │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘

External APIs:
- OpenAI (LLM, TTS)
- Hugging Face Inference Endpoint (FLUX - images)
- ElevenLabs (TTS - optional)
- YouTube Data API v3 (upload/schedule)
```

---

## Step 2: Proposed Structure & Plan

### Target Structure

```
yt_auto_story/
├── app/
│   ├── __init__.py
│   ├── api/                      # FastAPI routes (keep, document usage)
│   │   ├── __init__.py
│   │   └── routes_story.py
│   ├── core/                     # Config, logging (keep as-is)
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── logging_config.py
│   ├── models/                   # Pydantic schemas (keep as-is)
│   │   ├── __init__.py
│   │   └── schemas.py
│   ├── pipelines/                # Orchestrators (keep as-is)
│   │   ├── __init__.py
│   │   └── run_full_pipeline.py
│   ├── services/                 # Business logic (keep as-is, all 17 services)
│   │   ├── __init__.py
│   │   └── [17 service files]
│   ├── storage/                  # Episode repository (keep as-is)
│   │   ├── __init__.py
│   │   └── repository.py
│   ├── utils/                    # Utilities (keep as-is)
│   │   ├── __init__.py
│   │   ├── io_utils.py
│   │   └── text_utils.py
│   └── main.py                   # FastAPI app (keep, add comment about usage)
│
├── docs/                         # All documentation
│   ├── backend.md
│   ├── CONTENT_QUALITY_NOTES.md
│   ├── EDIT_PATTERNS.md
│   ├── PRIORITY1_IMPLEMENTATION.md
│   ├── scheduling_support.md
│   ├── STORY_QUALITY_IMPROVEMENTS.md
│   ├── VISUAL_QUALITY_IMPROVEMENTS.md
│   ├── WORKFLOW_AUDIT.md
│   ├── pipeline.md
│   ├── quality_audit.md
│   ├── quickstart.md
│   ├── story_sourcing.md
│   ├── structure.md
│   ├── examples/
│   │   └── example_video_plan.json
│   ├── PROJECT_AUDIT.md          # ⬅️ MOVE from root
│   └── GO_LIVE_UPGRADE_SUMMARY.md # ⬅️ MOVE from root
│
├── scripts/                      # Utility scripts (keep as-is)
│   ├── README.md
│   └── test_hf_image.py
│
├── tests/                        # Test suite (keep as-is)
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   └── [unit test files]
│   └── integration/
│       └── [integration test files]
│
├── storage/                      # ⚠️ KEEP: Episode JSON files (used by repository)
│   └── episodes/
│       └── [episode JSON files]
│
├── outputs/                      # Generated content (keep)
├── secrets/                      # OAuth credentials (gitignored, keep)
├── venv/                         # Virtual environment (gitignored, keep)
│
├── run_full_pipeline.py          # ✅ KEEP: Convenience entrypoint
├── requirements_backend.txt      # ✅ KEEP: Dependencies
├── pyproject.toml                # ✅ KEEP: Project config
├── README.md                     # ✅ KEEP: Main documentation
├── .gitignore                    # ✅ KEEP: Update if needed
├── .env.example                  # ⬅️ CREATE: Environment variable template
└── Makefile                      # ⬅️ CREATE: Common commands
```

### Proposed Changes

#### 1. Move Root-Level Documentation
- **Move:** `PROJECT_AUDIT.md` → `docs/PROJECT_AUDIT.md`
- **Move:** `GO_LIVE_UPGRADE_SUMMARY.md` → `docs/GO_LIVE_UPGRADE_SUMMARY.md`
- **Reason:** Consolidate all docs in `docs/` folder

#### 2. Create `.env.example`
- **Create:** `.env.example` with all required/optional environment variables
- **Include:**
  - OpenAI API key
  - Hugging Face endpoint URL & token
  - ElevenLabs API key (optional)
  - YouTube OAuth credentials
  - Optimisation flags
  - Scheduling flags
  - LLM model settings

#### 3. Create `Makefile`
- **Create:** `Makefile` with common commands:
  - `make lint` - Run linter
  - `make test` - Run tests
  - `make run-preview` - Run single preview
  - `make run-daily` - Run daily batch
  - `make test-hf` - Test HF image generation

#### 4. Update `.gitignore`
- **Review:** Ensure `storage/` is NOT ignored (episode JSON files should be tracked)
- **Ensure:** `outputs/`, `secrets/`, `venv/` are ignored
- **Add:** `.env` (if not already present)

#### 5. Document FastAPI Usage
- **Add:** Comment in `app/main.py` explaining if it's for future use or legacy
- **Option:** Add note in README about API vs CLI usage

#### 6. Update README
- **Refresh:** Environment variables section (reference `.env.example`)
- **Add:** Makefile commands section
- **Add:** Clear entry points section
- **Update:** Project structure to reflect current state

### Files to Keep (No Changes)

- ✅ All `app/` structure (well-organized)
- ✅ All `tests/` structure (well-organized)
- ✅ `scripts/` (minimal, appropriate)
- ✅ `run_full_pipeline.py` (convenience wrapper, keep)
- ✅ `storage/` at root (used by repository, keep)

### Files to Delete

- ❌ None (all files appear to be in use)

### Files to Create

- ✅ `.env.example` (environment variable template)
- ✅ `Makefile` (common commands)

---

## Step 3: Implementation Plan

### Phase 1: Safe Documentation Moves
1. Move `PROJECT_AUDIT.md` → `docs/PROJECT_AUDIT.md`
2. Move `GO_LIVE_UPGRADE_SUMMARY.md` → `docs/GO_LIVE_UPGRADE_SUMMARY.md`
3. Update any references in README/docs if they exist

### Phase 2: Create Missing Files
1. Create `.env.example` with all environment variables
2. Create `Makefile` with common commands

### Phase 3: Update Existing Files
1. Update `.gitignore` (ensure correct patterns)
2. Update `README.md` (refresh sections, add Makefile commands)
3. Add comment to `app/main.py` about usage

### Phase 4: Verification
1. Test that `run_full_pipeline.py` still works
2. Test that `scripts/test_hf_image.py` still works
3. Verify imports still work after moves

---

## Step 4: Repo Hygiene Checklist

- [ ] `.gitignore` - Review and update
- [ ] `.env.example` - Create with all env vars
- [ ] `README.md` - Refresh sections
- [ ] `Makefile` - Create with common commands
- [ ] `app/main.py` - Add usage comment

---

## Step 5: Remaining Tech Debt (Intentionally Not Touched)

1. **FastAPI API Layer:**
   - `app/main.py` and `app/api/` exist but unclear if actively used
   - **Decision:** Keep but document. Likely for future web UI or API access.

2. **Storage Path Confusion:**
   - `storage/` at root vs `app/storage/` (repository code)
   - **Decision:** Keep as-is. `app/storage/repository.py` uses `settings.storage_path` which points to root `storage/`. This is fine, just document it.

3. **Service Count:**
   - 17 services is a lot, but all are actively used
   - **Decision:** Keep as-is. Modularity is good for maintainability.

4. **Test Coverage:**
   - Not all services have tests
   - **Decision:** Out of scope for this cleanup. Document in tech debt.

---

## Summary

**Current State:** ✅ Well-organized, minimal issues

**Proposed Changes:**
1. Move 2 root-level docs to `docs/`
2. Create `.env.example`
3. Create `Makefile`
4. Update README and `.gitignore`
5. Add documentation comments

**Risk Level:** 🟢 Low - All changes are safe, no code modifications

**Estimated Time:** ~30 minutes

**Breaking Changes:** None

