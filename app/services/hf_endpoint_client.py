"""Hugging Face Inference Endpoint Client for image generation."""

import io
import time
from pathlib import Path
from typing import Any, Optional

import requests
from PIL import Image

from app.core.config import Settings
from app.core.logging_config import get_logger


class HFEndpointClient:
    """Client for generating images via Hugging Face Inference Endpoint."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the HF Endpoint client.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.endpoint_url = getattr(settings, "hf_endpoint_url", None)
        self.endpoint_token = getattr(settings, "hf_endpoint_token", None)

        if not self.endpoint_url:
            raise ValueError(
                "HF_ENDPOINT_URL not configured. Set HF_ENDPOINT_URL in .env file."
            )
        if not self.endpoint_token:
            raise ValueError(
                "HF_ENDPOINT_TOKEN not configured. Set HF_ENDPOINT_TOKEN in .env file."
            )

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        image_type: str = "scene_broll",
        seed: Optional[int] = None,
        sharpness: int = 8,
        realism_level: str = "ultra",
        film_style: str = "kodak_portra",
    ) -> None:
        """
        Generate image from prompt using HF Inference Endpoint with photorealistic parameters.

        Args:
            prompt: Image generation prompt
            output_path: Path to save the generated image
            image_type: Type of image ("character_portrait" or "scene_broll")
            seed: Random seed for consistency (0-4294967295, optional)
            sharpness: Sharpness level (1-10, default 8)
            realism_level: Realism level ("high", "ultra", "photoreal")
            film_style: Film style ("kodak_portra", "canon", "sony_fx3", "fuji")

        Raises:
            Exception: If image generation fails
        """
        import time
        start_time = time.time()
        
        prompt_preview = prompt[:120] + "..." if len(prompt) > 120 else prompt
        self.logger.info(f"Using HF endpoint (FLUX) for image generation: {self.endpoint_url}")
        self.logger.info(f"Image type: {image_type}")
        self.logger.info(f"Prompt: {prompt_preview}")
        
        if seed is not None:
            self.logger.info(f"Seed: {seed} (for consistency)")
        if image_type == "character_portrait":
            self.logger.info(f"Photorealistic parameters: sharpness={sharpness}, realism={realism_level}, film={film_style}")

        headers = {
            "Authorization": f"Bearer {self.endpoint_token}",
            "Content-Type": "application/json",
        }

        # Build payload with optional parameters
        payload = {"inputs": prompt}
        
        # Add photorealistic parameters if provided (FLUX.1-dev / Juggernaut XL support these)
        if image_type == "character_portrait":
            # Add parameters to prompt for models that support them
            # Some models accept parameters in the payload, others need them in the prompt
            # For now, we'll add them to the prompt as text instructions
            param_prompt_suffix = f", sharpness {sharpness}/10, {realism_level} realism, {film_style} film style"
            if seed is not None:
                param_prompt_suffix += f", seed {seed}"
            
            # Some HF endpoints accept parameters in payload, try that first
            # If the endpoint supports it, we can add parameters directly
            # For FLUX.1-dev, parameters might be in a separate "parameters" field
            enhanced_prompt = prompt + param_prompt_suffix
            
            # Try to add parameters to payload if endpoint supports it
            # This depends on the specific endpoint implementation
            # For now, we'll enhance the prompt and let the endpoint handle it
            payload = {"inputs": enhanced_prompt}
            
            # If endpoint supports direct parameters (check endpoint docs), uncomment:
            # payload = {
            #     "inputs": prompt,
            #     "parameters": {
            #         "seed": seed,
            #         "guidance_scale": 7.5,
            #         "num_inference_steps": 50,
            #     }
            # }

        try:
            response = requests.post(
                self.endpoint_url,
                json=payload,
                headers=headers,
                timeout=120,  # Longer timeout for image generation
            )

            if response.status_code == 503:
                self.logger.warning("Endpoint loading, waiting 15 seconds...")
                time.sleep(15)
                response = requests.post(
                    self.endpoint_url,
                    json=payload,
                    headers=headers,
                    timeout=120,
                )

            if response.status_code != 200:
                error_body = ""
                try:
                    error_body = response.text[:500] if hasattr(response, "text") else ""
                except:
                    pass

                error_msg = f"HF Endpoint error: status {response.status_code}"
                if error_body:
                    error_msg += f" - {error_body}"

                self.logger.error(error_msg)
                raise Exception(error_msg)

            # Check response content type and format
            content_type = response.headers.get("Content-Type", "").lower()
            self.logger.debug(f"Response Content-Type: {content_type}")
            self.logger.debug(f"Response length: {len(response.content)} bytes")

            image = None

            # Check if response is JSON (may contain base64-encoded image or error)
            if "application/json" in content_type or (response.content and response.content.startswith(b"{")):
                try:
                    import json
                    import base64
                    response_data = json.loads(response.text)
                    
                    # Check if image is base64 encoded in JSON response
                    if isinstance(response_data, dict):
                        # Some endpoints return {"image": "base64_string"} or {"output": "base64_string"} or just the base64 string
                        image_b64 = response_data.get("image") or response_data.get("output") or response_data.get("data")
                        
                        # If no image key, check if the entire response is a base64 string
                        if not image_b64 and isinstance(response_data, str):
                            image_b64 = response_data
                        
                        if image_b64:
                            # Decode base64 image
                            if isinstance(image_b64, str):
                                # Remove data URL prefix if present
                                if "," in image_b64:
                                    image_b64 = image_b64.split(",")[1]
                                image_bytes = base64.b64decode(image_b64)
                                image = Image.open(io.BytesIO(image_bytes))
                                self.logger.debug("Successfully decoded base64 image from JSON response")
                            else:
                                error_msg = f"HF Endpoint returned unexpected image format in JSON: {type(image_b64)}"
                                self.logger.error(error_msg)
                                raise Exception(error_msg)
                        else:
                            # JSON error response
                            error_msg = f"HF Endpoint returned JSON error: {response_data}"
                            self.logger.error(error_msg)
                            raise Exception(error_msg)
                    elif isinstance(response_data, str):
                        # Response might be a base64 string directly
                        try:
                            image_bytes = base64.b64decode(response_data)
                            image = Image.open(io.BytesIO(image_bytes))
                            self.logger.debug("Successfully decoded base64 image from string response")
                        except:
                            error_msg = f"HF Endpoint returned unexpected JSON format: {response_data}"
                            self.logger.error(error_msg)
                            raise Exception(error_msg)
                    else:
                        error_msg = f"HF Endpoint returned unexpected JSON format: {type(response_data)}"
                        self.logger.error(error_msg)
                        raise Exception(error_msg)
                except json.JSONDecodeError:
                    # Not JSON, will try to parse as binary image below
                    pass
                except Exception as e:
                    if "image" not in str(e).lower() and "base64" not in str(e).lower():
                        error_msg = f"Failed to decode base64 image from JSON: {e}"
                        self.logger.error(error_msg)
                        raise Exception(error_msg) from e
                    # If it's an image-related error, continue to try binary parsing

            # If not JSON or JSON didn't contain image, try to open as direct binary image
            if image is None:
                try:
                    image = Image.open(io.BytesIO(response.content))
                    self.logger.debug("Successfully parsed binary image response")
                except Exception as e:
                    # Log response preview for debugging
                    preview = response.content[:200] if len(response.content) > 200 else response.content
                    self.logger.error(f"Failed to parse image. Response preview: {preview}")
                    self.logger.error(f"Content-Type: {content_type}")
                    self.logger.error(f"Response length: {len(response.content)} bytes")
                    raise Exception(f"Cannot parse response as image: {e}. Response may be JSON or invalid image format.")

            # Success - save image
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            target_size = (1080, 1920)  # 9:16 vertical
            image = image.resize(target_size, Image.Resampling.LANCZOS)
            image.save(output_path, "PNG", quality=95)
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"✅ Successfully generated {image_type} image: {output_path}")
            self.logger.info(f"   Round-trip latency: {elapsed_time:.2f}s")

        except requests.exceptions.RequestException as e:
            elapsed_time = time.time() - start_time
            error_msg = f"Network error calling HF Endpoint: {e}"
            self.logger.error(f"❌ Failed to generate {image_type} image: {error_msg} (latency: {elapsed_time:.2f}s)")
            raise Exception(error_msg) from e
        except Exception as e:
            elapsed_time = time.time() - start_time
            self.logger.error(f"❌ Failed to generate {image_type} image via HF Endpoint: {e} (latency: {elapsed_time:.2f}s)")
            raise

    def generate_broll_scene(
        self,
        prompt: str,
        output_path: Path,
        realism_level: str = "high",
    ) -> None:
        """
        Generate a cinematic B-roll scene with photorealistic quality.

        Args:
            prompt: B-roll scene prompt
            output_path: Path to save the generated image
            realism_level: Realism level ("high", "ultra", "photoreal")

        Raises:
            Exception: If image generation fails
        """
        # Enhance prompt with photorealistic style
        enhanced_prompt = f"{prompt}, cinematic real photograph, shallow depth of field, 35mm lens, natural lighting, film grain, {realism_level} realism, 8k resolution, vertical format 9:16"

        # Use existing generate_image method with scene_broll type
        self.generate_image(
            prompt=enhanced_prompt,
            output_path=output_path,
            image_type="scene_broll",
            realism_level=realism_level,
        )

