# AI Story Shorts Factory - Backend API

A modular, production-ready backend system for generating structured video content for AI video generation tools.

## Architecture

```
app/
  api/              # FastAPI routes
  core/             # Configuration and logging
  models/           # Pydantic schemas
  services/         # Business logic (stub implementations with LLM upgrade paths)
  storage/          # Repository layer
  main.py           # FastAPI application entrypoint
```

## Features

- **Modular Services**: Each step in the pipeline is a separate, testable service
- **Stub Implementations**: All services work out-of-the-box with stubs, ready for LLM integration
- **Clean Architecture**: Strong separation of concerns, type hints everywhere
- **Production Ready**: Structured logging, error handling, comprehensive tests
- **Extensible**: Easy to upgrade from stubs to LLM-powered implementations

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements_backend.txt
```

### 2. Configure Environment

Create `.env` file (or use existing):

```bash
# API Keys (optional for stub mode)
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
TTS_API_KEY=your_key_here

# Application Settings
DEBUG=false
LOG_LEVEL=INFO
STORAGE_PATH=storage/episodes
DEFAULT_STYLE=courtroom_drama
```

### 3. Run the API

```bash
# Development mode
python -m app.main

# Or with uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Access API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### POST /stories/generate

Generate a complete story video plan.

**Request:**
```json
{
  "topic": "courtroom drama – teen laughs at verdict",
  "duration_target_seconds": 60
}
```

**Response:**
```json
{
  "episode_id": "episode_abc123",
  "title": "Teen Laughs in Court - Breaking News",
  "logline": "A dramatic story...",
  "scene_count": 3,
  "character_count": 4,
  "status": "completed"
}
```

### GET /stories/{episode_id}

Get full video plan for an episode.

### GET /stories/{episode_id}/export

Download episode as JSON file.

## Pipeline

The generation pipeline follows this flow:

1. **Story Finder** → Finds and ranks story candidates
2. **Story Rewriter** → Converts raw text into structured script with scenes
3. **Character Engine** → Generates unique characters for the episode
4. **Dialogue Engine** → Creates emotion-tagged dialogue
5. **Narration Engine** → Produces voiceover narration
6. **Video Plan Engine** → Creates master JSON structure for video generators

## Services

### Story Finder (`app/services/story_finder.py`)

- `find_candidates(topic)` → Returns list of story candidates
- `score_candidate(candidate)` → Scores viral potential
- `get_best_story(topic)` → Returns highest-scored candidate

**Upgrade Path**: Replace stub with web scraping or LLM-powered candidate generation.

### Story Rewriter (`app/services/story_rewriter.py`)

- `rewrite_story(raw_text, title, duration)` → Creates structured script with scenes

**Upgrade Path**: Use LLM to analyze narrative structure and create compelling scenes.

### Character Engine (`app/services/character_engine.py`)

- `generate_characters(story_script, style)` → Creates unique characters per episode

**Upgrade Path**: Use LLM to generate more detailed, context-aware characters.

### Dialogue Engine (`app/services/dialogue_engine.py`)

- `generate_dialogue(story_script, character_set)` → Creates emotion-tagged dialogue

**Upgrade Path**: Use LLM to generate natural, character-appropriate dialogue.

### Narration Engine (`app/services/narration_engine.py`)

- `generate_narration(story_script)` → Produces voiceover narration

**Upgrade Path**: Use LLM to refine and enhance narration for TTS.

### Video Plan Engine (`app/services/video_plan_engine.py`)

- `create_video_plan(...)` → Creates final JSON structure for video generators

**Upgrade Path**: Enhance background prompts and B-roll generation with LLM.

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=app --cov-report=html
```

## Example Output

See `examples/example_video_plan.json` for a complete example of the generated VideoPlan structure for the topic "teen laughs in court after verdict".

## Storage

Episodes are stored as JSON files in `storage/episodes/` by default. The repository layer provides a clean interface for future migration to SQLite or PostgreSQL.

## Logging

Structured logging with context fields:
- `episode_id`: Current episode being processed
- `topic`: Story topic
- `service_stage`: Current pipeline stage

Logs are written to console (colored) and optionally to files with rotation.

## Full Pipeline (CLI)

The complete pipeline from topic to YouTube upload is available via the CLI script:

```bash
python run_full_pipeline.py --topic "courtroom drama – teen laughs at verdict" --auto-upload
```

### Pipeline Steps

1. **Story Generation**: Creates VideoPlan from topic
2. **Video Rendering**: Generates narration audio, scene visuals, composes final .mp4
3. **YouTube Upload**: Uploads video to YouTube (if `--auto-upload` is used)

### Configuration for Full Pipeline

#### TTS (Text-to-Speech)

Set one of these in `.env`:

```bash
# Option 1: ElevenLabs (recommended)
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here

# Option 2: OpenAI TTS
OPENAI_API_KEY=your_key_here
```

If neither is set, a stub TTS will be used (requires `pydub` for silent audio generation).

#### Image Generation

Optional - for better visuals:

```bash
HUGGINGFACE_TOKEN=your_token_here
```

If not set, placeholder images will be generated.

#### YouTube Upload

1. **Get OAuth Credentials**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a project
   - Enable YouTube Data API v3
   - Create OAuth 2.0 credentials (Desktop app)
   - Download `client_secrets.json`

2. **Configure**:
   ```bash
   YOUTUBE_CLIENT_SECRETS_FILE=path/to/client_secrets.json
   YOUTUBE_TOKEN_FILE=youtube_token.json  # Optional, default location
   ```

3. **First Run**: OAuth flow will open in browser for authorization

### CLI Options

```bash
python run_full_pipeline.py \
  --topic "your story topic" \
  --duration-target-seconds 60 \
  --auto-upload \
  --output-dir outputs/videos
```

- `--topic` (required): Story topic
- `--duration-target-seconds` (optional): Target duration, default 60
- `--auto-upload` (flag): Automatically upload to YouTube
- `--output-dir` (optional): Output directory, default `outputs/videos`

### Services

#### Video Renderer (`app/services/video_renderer.py`)

- Generates narration audio via TTS
- Generates scene visuals (Hugging Face or placeholders)
- Composes vertical 1080x1920 .mp4 video
- Uses MoviePy for video composition

#### YouTube Uploader (`app/services/youtube_uploader.py`)

- Handles OAuth 2.0 flow
- Uploads videos via YouTube Data API v3
- Sets title, description, tags, privacy
- Returns YouTube video URL

#### TTS Client (`app/services/tts_client.py`)

- Supports multiple providers (ElevenLabs, OpenAI, stub)
- Auto-detects available provider
- Clean interface for easy provider swapping

## Next Steps

1. **LLM Integration**: Replace stub implementations with LLM calls (OpenAI, Anthropic)
2. **Video API Integration**: Connect to Pika, Luma, Runway, or Kling APIs
3. **Database Migration**: Move from JSON storage to SQLite/PostgreSQL
4. **Batch Processing**: Add endpoints for generating multiple stories
5. **Enhanced Visuals**: Improve image generation with better prompts/models

## License

MIT

