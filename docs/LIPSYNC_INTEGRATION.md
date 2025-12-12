# Lip-Sync Integration Guide

**Date:** 2025-11-23  
**Status:** ✅ Foundation Complete (Ready for API Integration)

---

## Overview

The system now has a foundation for real lip-sync talking-head generation. The architecture is ready to integrate D-ID or HeyGen APIs for realistic mouth movement.

---

## Current Implementation

### Architecture

The system uses a **pluggable provider pattern**:

1. **`LipSyncProvider`** (abstract base class)
   - Defines interface for lip-sync generation
   - Can be swapped with different providers

2. **`DIDLipSyncProvider`** (D-ID implementation)
   - Structure ready for D-ID API integration
   - Requires `DID_API_KEY` environment variable

3. **`HeyGenLipSyncProvider`** (HeyGen implementation)
   - Structure ready for HeyGen API integration
   - Requires `HEYGEN_API_KEY` environment variable

4. **Fallback Chain:**
   - Try lip-sync provider (if configured)
   - Fallback to basic talking-head (Ken Burns + zoom)
   - Fallback to scene visual (if all fail)

### Configuration

**Environment Variables:**
```bash
# Enable lip-sync
USE_LIPSYNC=true

# D-ID (option 1)
DID_API_KEY=your_did_api_key
DID_API_URL=https://api.d-id.com  # optional, defaults to this

# HeyGen (option 2)
HEYGEN_API_KEY=your_heygen_api_key
HEYGEN_API_URL=https://api.heygen.com  # optional, defaults to this
```

**Priority:**
- If both D-ID and HeyGen are configured, D-ID takes priority
- If neither is configured, falls back to basic talking-head

---

## How to Complete D-ID Integration

### Step 1: Get D-ID API Key

1. Sign up at https://www.d-id.com/
2. Get API key from dashboard
3. Add to `.env`: `DID_API_KEY=your_key`

### Step 2: Implement API Calls

Update `app/services/lipsync_provider.py` → `DIDLipSyncProvider.generate_talking_head()`:

```python
def generate_talking_head(self, base_image_path: Path, audio_path: Path, output_path: Path) -> Path:
    import requests
    
    # 1. Upload image
    with open(base_image_path, 'rb') as f:
        image_response = requests.post(
            f"{self.api_url}/images",
            headers={"Authorization": f"Basic {self.api_key}"},
            files={"image": f}
        )
    image_id = image_response.json()["id"]
    
    # 2. Upload audio
    with open(audio_path, 'rb') as f:
        audio_response = requests.post(
            f"{self.api_url}/audios",
            headers={"Authorization": f"Basic {self.api_key}"},
            files={"audio": f}
        )
    audio_id = audio_response.json()["id"]
    
    # 3. Create talk
    talk_response = requests.post(
        f"{self.api_url}/talks",
        headers={"Authorization": f"Basic {self.api_key}"},
        json={
            "source_url": image_id,
            "script": {
                "type": "audio",
                "audio_url": audio_id
            }
        }
    )
    talk_id = talk_response.json()["id"]
    
    # 4. Poll for completion
    import time
    while True:
        status_response = requests.get(
            f"{self.api_url}/talks/{talk_id}",
            headers={"Authorization": f"Basic {self.api_key}"}
        )
        status = status_response.json()["status"]
        if status == "done":
            result_url = status_response.json()["result_url"]
            break
        elif status == "error":
            raise Exception(f"D-ID generation failed: {status_response.json()}")
        time.sleep(2)
    
    # 5. Download result
    video_response = requests.get(result_url)
    with open(output_path, 'wb') as f:
        f.write(video_response.content)
    
    return output_path
```

### Step 3: Test

```bash
# Set API key
export DID_API_KEY=your_key
export USE_LIPSYNC=true

# Run pipeline
python run_full_pipeline.py --topic "test" --preview
```

---

## How to Complete HeyGen Integration

Similar process - see HeyGen API docs: https://docs.heygen.com/

---

## Cost Estimates

**D-ID:**
- ~$0.10-0.50 per talking-head clip
- Pay-per-use pricing

**HeyGen:**
- ~$0.10-0.50 per talking-head clip
- Subscription or pay-per-use

**For 5 videos/day with 3 talking-heads each:**
- ~$1.50-7.50/day in lip-sync costs

---

## Current Status

✅ **Foundation Complete:**
- Provider architecture in place
- Configuration system ready
- Fallback chain working
- Easy to swap providers

⏳ **Needs Implementation:**
- D-ID API calls (see Step 2 above)
- HeyGen API calls
- Error handling and retries
- Rate limiting

---

## Testing Without API

The system works without lip-sync APIs - it falls back to basic talking-head (static image + zoom + audio). This is sufficient for testing and development.

---

## Next Steps

1. **Choose Provider:** D-ID or HeyGen (or both)
2. **Get API Key:** Sign up and get credentials
3. **Implement API Calls:** Follow Step 2 above
4. **Test:** Run pipeline with `USE_LIPSYNC=true`
5. **Monitor Costs:** Track API usage

---

## Notes

- Lip-sync is **optional** - system works without it
- Falls back gracefully if API fails
- Can be enabled/disabled per video via config
- Multiple providers can coexist (priority-based selection)

