# Project Structure

## Complete Directory Tree

```
yt_auto_story/
├── app/                          # Backend API application
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entrypoint
│   │
│   ├── api/                     # API routes
│   │   ├── __init__.py
│   │   └── routes_story.py      # Story generation endpoints
│   │
│   ├── core/                    # Core configuration
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic-settings configuration
│   │   └── logging_config.py    # Structured logging setup
│   │
│   ├── models/                   # Pydantic models and schemas
│   │   ├── __init__.py
│   │   └── schemas.py            # All data models
│   │
│   ├── services/                # Business logic services
│   │   ├── __init__.py
│   │   ├── story_finder.py      # Find and rank story candidates
│   │   ├── story_rewriter.py    # Convert raw story to script
│   │   ├── character_engine.py # Generate unique characters
│   │   ├── dialogue_engine.py  # Generate emotion-tagged dialogue
│   │   ├── narration_engine.py # Generate voiceover narration
│   │   └── video_plan_engine.py # Create final video plan JSON
│   │
│   └── storage/                  # Storage layer
│       ├── __init__.py
│       └── repository.py        # Episode storage (JSON/SQLite ready)
│
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_story_finder.py
│   ├── test_story_rewriter.py
│   ├── test_character_engine.py
│   ├── test_dialogue_engine.py
│   ├── test_narration_engine.py
│   ├── test_video_plan_engine.py
│   └── test_storage.py
│
├── examples/                     # Example outputs
│   └── example_video_plan.json   # Complete VideoPlan example
│
├── storage/                      # Generated storage (git-ignored)
│   └── episodes/                 # Saved episodes as JSON
│
├── outputs/                      # Legacy CLI outputs (git-ignored)
│
├── config.py                     # Legacy CLI config
├── logging_config.py             # Legacy CLI logging
├── run_story.py                  # Legacy CLI entrypoint
├── story_generator.py            # Legacy CLI story generator
├── voice_generator.py           # Legacy CLI voice generator
├── image_generator.py           # Legacy CLI image generator
├── video_composer.py            # Legacy CLI video composer
│
├── requirements.txt              # Legacy CLI dependencies
├── requirements_backend.txt     # Backend API dependencies
├── pytest.ini                    # Pytest configuration
├── README.md                     # Main project README
├── README_BACKEND.md            # Backend API documentation
└── PROJECT_STRUCTURE.md         # This file
```

## Key Components

### Backend API (`app/`)

- **FastAPI-based REST API** for story generation
- **Modular services** with stub implementations ready for LLM upgrade
- **Type-safe** with Pydantic models throughout
- **Production-ready** with structured logging and error handling

### Services Pipeline

1. **Story Finder** → Finds viral story candidates
2. **Story Rewriter** → Structures story into scenes
3. **Character Engine** → Generates unique characters per episode
4. **Dialogue Engine** → Creates emotion-tagged dialogue
5. **Narration Engine** → Produces voiceover narration
6. **Video Plan Engine** → Creates master JSON for video generators

### Data Models (`app/models/schemas.py`)

- `StoryCandidate` - Raw story from sources
- `StoryScript` - Structured script with scenes
- `Character` / `CharacterSet` - Episode characters
- `DialogueLine` / `DialoguePlan` - Character dialogue
- `NarrationLine` / `NarrationPlan` - Voiceover narration
- `VideoPlan` - Final structure for video generation

### API Endpoints

- `POST /stories/generate` - Generate complete story
- `GET /stories/{episode_id}` - Get video plan
- `GET /stories/{episode_id}/export` - Download JSON

### Testing

Comprehensive pytest suite covering:
- All service modules
- Storage repository
- Data structure validation
- Pipeline integration

## Legacy CLI

The original CLI tool (`run_story.py`) remains functional alongside the new backend API. Both can coexist and share utilities.

