# AI Story Shorts Factory

An automated pipeline for generating viral YouTube Shorts from story topics. The system generates structured emotional stories, creates photoreal character animations, renders vertical videos, and optionally uploads to YouTube.

## 🎯 Features

- **Auto Story Selection**: Automatically finds and scores high-virality stories from niches (courtroom, relationship_drama, injustice, etc.)
- **Emotional Narrative Arcs**: Generates stories with HOOK → SETUP → CONFLICT → TWIST → RESOLUTION structure
- **Photoreal Character Animations**: Talking-head clips for key dialogue lines (Option B architecture)
- **Multi-Style Support**: Courtroom drama, ragebait, relationship drama
- **Full Pipeline**: Topic → Story → VideoPlan → Rendered Video → YouTube Upload
- **Modular Architecture**: Clean, extensible services ready for production

## 🚀 Quick Start

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements_backend.txt
```

### 2. Configure API Keys

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required:
- `OPENAI_API_KEY` - For story generation
- `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` - For narration (or use OpenAI TTS)

Optional:
- `HUGGINGFACE_TOKEN` - Improves image generation rate limits
- `YOUTUBE_CLIENT_SECRETS_FILE` - For automatic YouTube uploads

### 3. Run the Pipeline

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
  --auto-upload
```

## 📖 Documentation

- **[Backend Documentation](docs/backend.md)** - Complete backend architecture
- **[Quick Start Guide](docs/quickstart.md)** - Detailed setup instructions
- **[Pipeline Documentation](docs/pipeline.md)** - Full pipeline implementation details
- **[Story Sourcing](docs/story_sourcing.md)** - Auto story selection and virality scoring
- **[Quality Audit](docs/quality_audit.md)** - Quality improvements and roadmap

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

## ⚙️ Configuration

All configuration is done via environment variables (see `.env.example`):

- **LLM Settings**: `OPENAI_API_KEY`, `OPENAI_MODEL`
- **TTS Settings**: `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`
- **Image Generation**: `HUGGINGFACE_TOKEN`
- **Talking Heads**: `USE_TALKING_HEADS`, `MAX_TALKING_HEAD_LINES_PER_VIDEO`
- **Story Sourcing**: `USE_LLM_FOR_STORY_FINDER`
- **YouTube**: `YOUTUBE_CLIENT_SECRETS_FILE`

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

## 📝 CLI Options

```bash
python run_full_pipeline.py --help
```

**Key Flags:**
- `--topic` - Specific story topic (or use `--auto-topic`)
- `--auto-topic` - Auto-select high-virality story
- `--niche` - Story niche (courtroom, relationship_drama, injustice, workplace_drama)
- `--style` - Story style (courtroom_drama, ragebait, relationship_drama)
- `--duration-target-seconds` - Target video length
- `--auto-upload` - Automatically upload to YouTube
- `--no-talking-heads` - Disable character animations
- `--max-talking-head-lines` - Max animated dialogue lines

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
