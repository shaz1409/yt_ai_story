"""Image Post-Processor - enhances images after validation."""

import cv2
import numpy as np
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageEnhance, ImageFilter
from app.core.config import Settings
from app.core.logging_config import get_logger


class ImagePostProcessor:
    """Post-processes images to enhance visual quality."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize image post-processor.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.enabled = getattr(settings, "image_post_processing_enabled", True)
        self.image_look = getattr(settings, "image_look", "cinematic")
        self.sharpness_strength = getattr(settings, "image_sharpness_strength", "medium")

    def enhance_image(
        self, input_path: Path, output_path: Path, image_type: str = "scene_broll"
    ) -> Path:
        """
        Enhance image with adaptive contrast, sharpening, color depth, and optional grading.

        Args:
            input_path: Path to input image (original, validated image)
            output_path: Path to save enhanced image
            image_type: Type of image ("character_portrait" or "scene_broll")

        Returns:
            Path to enhanced image

        Raises:
            Exception: If enhancement fails
        """
        if not self.enabled:
            self.logger.debug("Image post-processing disabled, skipping enhancement")
            return input_path

        if not input_path.exists():
            self.logger.warning(f"Input image not found: {input_path}, skipping enhancement")
            return input_path

        try:
            # Check if processed image already exists (caching)
            if output_path.exists():
                self.logger.debug(f"Processed image already exists, reusing: {output_path}")
                return output_path

            self.logger.info(f"Enhancing {image_type} image: {input_path.name}")

            # Load image
            img = cv2.imread(str(input_path))
            if img is None:
                self.logger.warning(f"Could not load image for enhancement: {input_path}")
                return input_path

            # Convert BGR to RGB for PIL processing
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(img_rgb)

            # 1. Adaptive contrast boost
            pil_image = self._apply_adaptive_contrast(pil_image)

            # 2. Sharpening mask
            pil_image = self._apply_sharpening(pil_image)

            # 3. Improve color depth
            pil_image = self._improve_color_depth(pil_image)

            # 4. Optional light cinematic grading
            if self.image_look == "cinematic":
                pil_image = self._apply_cinematic_grading(pil_image)
            elif self.image_look == "warm":
                pil_image = self._apply_warm_grading(pil_image)
            # "neutral" - no grading applied

            # Convert back to numpy array and BGR for saving
            img_enhanced = np.array(pil_image)
            img_enhanced_bgr = cv2.cvtColor(img_enhanced, cv2.COLOR_RGB2BGR)

            # Save enhanced image
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), img_enhanced_bgr, [cv2.IMWRITE_PNG_COMPRESSION, 3])

            self.logger.info(f"✅ Enhanced image saved: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Error enhancing image {input_path}: {e}")
            # Return original if enhancement fails
            return input_path

    def _apply_adaptive_contrast(self, image: Image.Image) -> Image.Image:
        """
        Apply adaptive contrast boost.

        Uses CLAHE (Contrast Limited Adaptive Histogram Equalization) for better contrast
        without over-enhancing.

        Args:
            image: PIL Image

        Returns:
            Enhanced PIL Image
        """
        try:
            # Convert to numpy array
            img_array = np.array(image)

            # Convert RGB to LAB color space for better contrast adjustment
            lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)

            # Apply CLAHE to L channel (lightness)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_channel_enhanced = clahe.apply(l_channel)

            # Merge channels back
            lab_enhanced = cv2.merge([l_channel_enhanced, a_channel, b_channel])
            img_enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)

            return Image.fromarray(img_enhanced)

        except Exception as e:
            self.logger.warning(f"Error applying adaptive contrast: {e}, using original")
            return image

    def _apply_sharpening(self, image: Image.Image) -> Image.Image:
        """
        Apply sharpening mask based on configured strength.

        Args:
            image: PIL Image

        Returns:
            Sharpened PIL Image
        """
        try:
            # Map strength to enhancement factor
            strength_map = {
                "low": 1.2,
                "medium": 1.5,
                "high": 2.0,
            }
            factor = strength_map.get(self.sharpness_strength, 1.5)

            # Apply unsharp mask filter
            # Convert to numpy for better control
            img_array = np.array(image)

            # Create unsharp mask
            blurred = cv2.GaussianBlur(img_array, (0, 0), 2.0)
            sharpened = cv2.addWeighted(img_array, 1.0 + factor, blurred, -factor, 0)

            # Clip values to valid range
            sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)

            return Image.fromarray(sharpened)

        except Exception as e:
            self.logger.warning(f"Error applying sharpening: {e}, using original")
            return image

    def _improve_color_depth(self, image: Image.Image) -> Image.Image:
        """
        Improve color depth and saturation.

        Args:
            image: PIL Image

        Returns:
            Enhanced PIL Image
        """
        try:
            # Enhance saturation slightly
            enhancer = ImageEnhance.Color(image)
            image = enhancer.enhance(1.1)  # 10% saturation boost

            # Enhance vibrance (selective saturation boost)
            # Convert to numpy for HSV manipulation
            img_array = np.array(image)
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)

            # Boost saturation in HSV space (more control)
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.15, 0, 255).astype(np.uint8)

            # Convert back to RGB
            img_enhanced = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

            return Image.fromarray(img_enhanced)

        except Exception as e:
            self.logger.warning(f"Error improving color depth: {e}, using original")
            return image

    def _apply_cinematic_grading(self, image: Image.Image) -> Image.Image:
        """
        Apply light cinematic color grading.

        Creates a subtle cinematic look with:
        - Slight desaturation
        - Cool shadows, warm highlights
        - Slight contrast boost

        Args:
            image: PIL Image

        Returns:
            Graded PIL Image
        """
        try:
            # Convert to numpy array
            img_array = np.array(image).astype(np.float32)

            # Split into RGB channels
            r, g, b = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]

            # Apply cinematic curve (subtle S-curve)
            # Boost shadows slightly, compress highlights
            img_array = np.power(img_array / 255.0, 0.95) * 255.0

            # Add slight color shift (cool shadows, warm highlights)
            # Create a mask for shadows and highlights
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            shadow_mask = (luminance < 85).astype(np.float32)
            highlight_mask = (luminance > 170).astype(np.float32)

            # Cool shadows (slight blue tint)
            img_array[:, :, 2] = img_array[:, :, 2] + shadow_mask * 5  # Boost blue in shadows

            # Warm highlights (slight orange tint)
            img_array[:, :, 0] = img_array[:, :, 0] + highlight_mask * 3  # Boost red in highlights
            img_array[:, :, 1] = img_array[:, :, 1] + highlight_mask * 2  # Boost green in highlights

            # Clip and convert back
            img_array = np.clip(img_array, 0, 255).astype(np.uint8)

            return Image.fromarray(img_array)

        except Exception as e:
            self.logger.warning(f"Error applying cinematic grading: {e}, using original")
            return image

    def _apply_warm_grading(self, image: Image.Image) -> Image.Image:
        """
        Apply warm color grading.

        Creates a warm, inviting look with:
        - Slight orange/yellow tint
        - Boosted warm tones

        Args:
            image: PIL Image

        Returns:
            Graded PIL Image
        """
        try:
            # Convert to numpy array
            img_array = np.array(image).astype(np.float32)

            # Add warm tint (boost red and yellow, reduce blue)
            img_array[:, :, 0] = np.clip(img_array[:, :, 0] * 1.05, 0, 255)  # Boost red
            img_array[:, :, 1] = np.clip(img_array[:, :, 1] * 1.03, 0, 255)  # Boost green (yellow component)
            img_array[:, :, 2] = np.clip(img_array[:, :, 2] * 0.97, 0, 255)  # Reduce blue

            # Convert back
            img_array = img_array.astype(np.uint8)

            return Image.fromarray(img_array)

        except Exception as e:
            self.logger.warning(f"Error applying warm grading: {e}, using original")
            return image

    def get_processed_path(self, original_path: Path) -> Path:
        """
        Get the path for a processed image based on the original path.

        Args:
            original_path: Path to original image

        Returns:
            Path to processed image in outputs/processed/
        """
        # Create processed path: outputs/processed/{relative_path_from_outputs}
        project_root = Path(__file__).parent.parent.parent
        processed_dir = project_root / "outputs" / "processed"

        # Get relative path from outputs/ (or project root if not in outputs/)
        if "outputs" in str(original_path):
            # Extract path after outputs/
            parts = original_path.parts
            outputs_idx = None
            for i, part in enumerate(parts):
                if part == "outputs":
                    outputs_idx = i
                    break
            if outputs_idx is not None:
                relative_parts = parts[outputs_idx + 1:]
                processed_path = processed_dir / Path(*relative_parts)
            else:
                # Fallback: use filename in processed directory
                processed_path = processed_dir / original_path.name
        else:
            # Not in outputs/, use filename
            processed_path = processed_dir / original_path.name

        return processed_path

