# AI Story Shorts Factory

An automated pipeline for generating viral YouTube Shorts from story topics. The system generates structured emotional stories, creates photoreal character animations, renders vertical videos, and optionally uploads to YouTube.

## 🎯 Features

- **Auto Story Selection**: Automatically finds and scores high-virality stories from niches (courtroom, relationship_drama, injustice, etc.)
- **Emotional Narrative Arcs**: Generates stories with HOOK → SETUP → CONFLICT → TWIST → RESOLUTION structure
- **Photoreal Character Animations**: Talking-head clips for key dialogue lines with optional lip-sync (D-ID/HeyGen)
- **Character Consistency**: Same character faces reused across episodes via intelligent caching
- **Cinematic B-Roll**: Contextual, emotion-aware scene visuals with Ken Burns effects
- **Multi-Style Support**: Courtroom drama, ragebait, relationship drama
- **Full Pipeline**: Topic → Story → VideoPlan → Rendered Video → YouTube Upload
- **Daily Batch Scheduling**: Automated daily batches with configurable time slots
- **Resume on Failure**: Checkpoint system to resume from last successful step
- **Rate Limiting**: Automatic throttling to prevent API rate limit errors
- **Analytics Tracking**: Performance metrics for video optimization
- **Modular Architecture**: Clean, extensible services ready for production

## 🚀 Quick Start

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Create virtual environment:**
   ```bash
   make venv
   ```

3. **Install dependencies:**
   ```bash
   make install
   ```

4. **Run preview (single video, no upload):**
   ```bash
   make run-preview
   ```

5. **Run daily batch (with scheduling):**
   ```bash
   make run-daily
   ```

See [Environment Variables](#-environment-variables) section for required API keys.

## 🎯 Entry Points

- **CLI (recommended):** `run_full_pipeline.py` - Main orchestration script
- **API (optional):** `app/main.py` - FastAPI server with `/stories/generate` endpoint (for future UI or remote triggering)

## ⚙️ Environment Variables

All configuration is done via environment variables. See `.env.example` for a complete template with all available options.

**Required:**
- `OPENAI_API_KEY` - For story generation, dialogue, and metadata
- `HF_ENDPOINT_URL` + `HF_ENDPOINT_TOKEN` - For image generation (Hugging Face Inference Endpoint)

**Optional but recommended:**
- `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` - For better TTS quality (falls back to OpenAI TTS)
- `YOUTUBE_CLIENT_SECRETS_FILE` - For automatic YouTube uploads/scheduling

**Feature toggles:**
- `USE_OPTIMISATION` - Enable performance-based batch optimization
- `USE_TALKING_HEADS` - Enable character animations
- `USE_LLM_FOR_DIALOGUE` - Use LLM for dialogue generation (default: true)
- `USE_LLM_FOR_METADATA` - Use LLM for titles/descriptions (default: true)
- `USE_LIPSYNC` - Enable real lip-sync for talking-heads (requires D-ID or HeyGen API key)
- `ENABLE_RATE_LIMITING` - Enable rate limiting for API calls (default: true)

**Rate limiting (optional):**
- `OPENAI_RATE_LIMIT` - OpenAI calls per minute (default: 60)
- `HF_RATE_LIMIT` - Hugging Face calls per minute (default: 30)
- `ELEVENLABS_RATE_LIMIT` - ElevenLabs calls per minute (default: 100)

**Scheduling (optional):**
- `TIMEZONE` - Timezone for scheduling (default: Europe/London)
- `DAILY_POSTING_HOURS` - Posting hours in 24-hour format, comma-separated (default: 11,14,18,20,22)

**Lip-sync (optional):**
- `DID_API_KEY` - D-ID API key for real lip-sync
- `HEYGEN_API_KEY` - HeyGen API key for real lip-sync

See `.env.example` for the complete list of all environment variables.

## 🛠️ Makefile Commands

```bash
make venv        # Create virtual environment
make install     # Install dependencies
make test        # Run tests
make lint        # Basic lint check
make run-preview # Run single pipeline (preview mode)
make run-daily   # Run full daily batch
make test-hf     # Test Hugging Face image generation
```

## 📝 CLI Usage

**Auto-select a high-virality story:**
```bash
python run_full_pipeline.py \
  --auto-topic \
  --niche "courtroom" \
  --style "courtroom_drama" \
  --auto-upload
```

**Use a specific topic:**
```bash
python run_full_pipeline.py \
  --topic "teen laughs in court after verdict" \
  --style "courtroom_drama" \
  --duration-target-seconds 60 \
  --preview
```

**Daily batch with scheduling:**
```bash
python run_full_pipeline.py \
  --daily-mode \
  --batch-count 5 \
  --date 2025-11-23
```

This will:
- Generate 5 videos using optimisation engine
- Assign time slots (default: 11:00, 14:00, 18:00, 20:00, 22:00 local time)
- Upload all videos as scheduled (private until publish time)

**Configure timezone and posting hours:**
```bash
# In .env file
TIMEZONE=America/New_York
DAILY_POSTING_HOURS=9,12,15,18,21
```

**Dry-run mode (test without rendering):**
```bash
python run_full_pipeline.py --topic "test story" --dry-run
```

**Resume from checkpoint (if pipeline failed):**
```bash
python run_full_pipeline.py --topic "story" --resume
```

See `python run_full_pipeline.py --help` for all available options.

## 📖 Documentation

- **[Backend Documentation](docs/backend.md)** - Complete backend architecture
- **[Quick Start Guide](docs/quickstart.md)** - Detailed setup instructions
- **[Pipeline Documentation](docs/pipeline.md)** - Full pipeline implementation details
- **[Story Sourcing](docs/story_sourcing.md)** - Auto story selection and virality scoring
- **[Quality Audit](docs/quality_audit.md)** - Quality improvements and roadmap
- **[Today's Features](docs/TODAY_FEATURES_SUMMARY.md)** - Summary of latest features (character caching, dry-run, lip-sync, analytics, etc.)
- **[Lip-Sync Integration](docs/LIPSYNC_INTEGRATION.md)** - Guide for integrating D-ID/HeyGen
- **[Scheduling Guide](docs/YOUTUBE_SCHEDULING_ENHANCEMENT.md)** - YouTube scheduling configuration

## 🏗️ Architecture

```
Topic / Niche
  ↓
Story Sourcing & Virality Scoring
  ↓
Story Rewriting → VideoPlan
  ↓
Character Generation + Dialogue + Narration
  ↓
Video Rendering
  ├─ Character Face Images
  ├─ Talking-Head Clips (key dialogue)
  ├─ Scene Visuals
  └─ Final Composition
  ↓
YouTube Upload (optional)
```

## 🎬 Talking-Head Character Animations

The system uses **Option B** architecture:
- Generates photoreal character face images
- Creates talking-head clips for top N emotional dialogue lines
- Inserts clips into video timeline at appropriate scenes
- Narrator handles most storytelling, characters speak key lines

**Configuration:**
```bash
# Disable talking-heads
--no-talking-heads

# Set max animated lines
--max-talking-head-lines 5
```

## 📁 Project Structure

```
app/
  api/          # FastAPI routes
  core/         # Config, logging
  models/       # Pydantic schemas
  services/     # Business logic services
  utils/        # Utility functions
  storage/      # Episode storage
  pipelines/    # Orchestrator scripts

docs/           # Documentation
tests/
  unit/         # Unit tests
  integration/  # Integration tests

run_full_pipeline.py  # Main CLI entrypoint
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run integration tests
pytest tests/integration/
```


## 🛠️ Development

### Code Quality

The project uses:
- **ruff** for linting
- **black** for formatting
- **pytest** for testing

### Adding New Services

1. Create service in `app/services/`
2. Add tests in `tests/unit/`
3. Update `app/core/config.py` if new settings needed
4. Document in `docs/`


## 🎯 Use Cases

1. **Batch Content Creation**: Generate multiple videos from a niche
2. **Viral Story Discovery**: Auto-find high-virality stories
3. **Consistent Branding**: Same character faces across episodes
4. **Rapid Prototyping**: Test different story styles quickly

## 📄 License

See LICENSE file (if applicable)

## 🤝 Contributing

1. Follow the existing code structure
2. Add tests for new features
3. Update documentation
4. Ensure all tests pass

---

**Built with**: Python 3.11+, FastAPI, Pydantic, MoviePy, OpenAI, ElevenLabs
