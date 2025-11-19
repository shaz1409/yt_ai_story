# Quick Start Guide - Backend API

## Installation

```bash
# Install backend dependencies
pip install -r requirements_backend.txt
```

## Run the API

```bash
# Start the FastAPI server
python -m app.main

# Or with uvicorn directly
uvicorn app.main:app --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Generate Your First Story

### Using curl

```bash
curl -X POST "http://localhost:8000/stories/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "courtroom drama – teen laughs at verdict",
    "duration_target_seconds": 60
  }'
```

### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8000/stories/generate",
    json={
        "topic": "courtroom drama – teen laughs at verdict",
        "duration_target_seconds": 60
    }
)

result = response.json()
print(f"Episode ID: {result['episode_id']}")
print(f"Title: {result['title']}")
```

### Using the Interactive Docs

1. Go to http://localhost:8000/docs
2. Click on `POST /stories/generate`
3. Click "Try it out"
4. Enter your topic and duration
5. Click "Execute"

## Get the Full Video Plan

```bash
# Replace {episode_id} with the ID from generation response
curl http://localhost:8000/stories/{episode_id}
```

## Export as JSON

```bash
# Download the complete video plan as JSON
curl http://localhost:8000/stories/{episode_id}/export -o video_plan.json
```

## Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_story_finder.py
```

## Example Output

See `examples/example_video_plan.json` for a complete example of the generated structure.

## Next Steps

1. **Integrate LLMs**: Update service stubs to use OpenAI/Anthropic APIs
2. **Connect Video APIs**: Send VideoPlan to Pika, Luma, Runway, or Kling
3. **Add TTS**: Connect dialogue/narration to TTS engines
4. **Customize**: Modify service logic for your specific needs

## Architecture Overview

```
Request → Story Finder → Story Rewriter → Character Engine
    ↓
Dialogue Engine → Narration Engine → Video Plan Engine
    ↓
Storage Repository → Response
```

Each service is modular and can be upgraded independently from stubs to LLM-powered implementations.

