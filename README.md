# YouTube Auto Story Generator

A Python tool to generate AI-powered story content for YouTube Shorts. This tool creates complete story packages including scripts, titles, descriptions, image prompts, and voice narration.

## Features

- **AI Story Generation**: Uses OpenAI to generate engaging, dramatic stories (30-60 seconds)
- **Voice Narration**: Converts story scripts to MP3 audio using ElevenLabs
- **Complete Content Package**: Generates hooks, titles, descriptions, and image prompts
- **Organized Outputs**: Saves everything to timestamped folders for easy management

## Setup

### 1. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```
OPENAI_API_KEY=your_openai_key_here
ELEVENLABS_API_KEY=your_elevenlabs_key_here
ELEVENLABS_VOICE_ID=your_default_voice_id_here
MODEL_NAME=gpt-4o-mini
```

**Getting API Keys:**
- **OpenAI**: Get your API key from [platform.openai.com](https://platform.openai.com/api-keys)
- **ElevenLabs**: Sign up at [elevenlabs.io](https://elevenlabs.io) and get your API key and voice ID from your dashboard

### 4. Run

```bash
python run_story.py --topic "teen laughs in court after verdict" --target-seconds 45 --num-images 6
```

## Usage

### Basic Command

```bash
python run_story.py --topic "your story topic here"
```

### Options

- `--topic` (required): The topic for your story
- `--target-seconds` (default: 45): Target duration in seconds (30-60 recommended)
- `--num-images` (default: 6): Number of image prompts to generate (4-8 recommended)

### Example

```bash
python run_story.py --topic "mysterious package arrives at doorstep" --target-seconds 50 --num-images 8
```

## Output Structure

Each run creates a timestamped folder under `outputs/` with the following files:

```
outputs/
└── 2025-01-13_143022_mysterious-package-arrives/
    ├── hook.txt              # Opening hook line
    ├── story_script.txt      # Full story narration text
    ├── title.txt             # YouTube title
    ├── description.txt       # YouTube description
    ├── image_prompts.txt     # Numbered list of image prompts
    ├── metadata.json         # All data in JSON format
    └── narration.mp3         # Voice narration audio file
```

## Project Structure

```
yt_auto_story/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── config.py                 # Configuration management
├── logging_config.py         # Logging setup
├── run_story.py              # Main entrypoint
├── story_generator.py        # OpenAI story generation
├── voice_generator.py        # ElevenLabs voice generation
├── utils/
│   ├── __init__.py
│   ├── io_utils.py           # File/directory utilities
│   └── text_utils.py         # Text processing utilities
└── outputs/                  # Generated content (git-ignored)
```

## Next Steps

This tool generates the foundation for YouTube Shorts content. Future enhancements could include:

- **Image Generation**: Use `image_prompts.txt` with DALL-E, Midjourney, or Stable Diffusion
- **Video Composition**: Use ffmpeg or MoviePy to combine images, audio, and text overlays
- **Batch Processing**: Generate multiple stories at once
- **Custom Voice Settings**: Fine-tune ElevenLabs voice parameters
- **Story Variations**: Generate multiple versions of the same story

## Logging

Logs are written to:
- **Console**: Real-time colored output
- **File**: `outputs/latest_run.log` (rotates at 10MB, keeps 7 days)

## Requirements

- Python 3.8+
- OpenAI API key
- ElevenLabs API key and voice ID

## License

MIT

