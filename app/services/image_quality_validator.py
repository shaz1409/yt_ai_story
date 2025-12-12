"""Image Quality Validator - validates image quality before acceptance into pipeline."""

import cv2
import numpy as np
from pathlib import Path
from typing import Any, Optional

from PIL import Image
from app.core.config import Settings
from app.core.logging_config import get_logger


class ImageQualityValidator:
    """Validates image quality using multiple metrics."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize image quality validator.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.min_acceptable_score = getattr(
            settings, "min_image_quality_score", 0.65
        )

    def score_image(
        self, image_path: Path, image_type: str = "scene_broll"
    ) -> float:
        """
        Score image quality on a 0.0 to 1.0 scale.

        Scoring factors:
        - Variance of Laplacian (sharpness detection): 0.0-0.4
        - Resolution check (>1024px shortest edge): 0.0-0.2
        - Facial structure detection (for character images): 0.0-0.2
        - Balanced lighting (avoid blown out whites): 0.0-0.2

        Args:
            image_path: Path to image file
            image_type: Type of image ("character_portrait" or "scene_broll")

        Returns:
            Quality score (0.0 to 1.0)
        """
        try:
            # Load image
            img = cv2.imread(str(image_path))
            if img is None:
                self.logger.warning(f"Could not load image for validation: {image_path}")
                return 0.0

            # Convert to RGB if needed
            if len(img.shape) == 3 and img.shape[2] == 3:
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            else:
                img_rgb = img

            # Convert to grayscale for some metrics
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

            scores = []

            # 1. Variance of Laplacian (sharpness detection) - 0.0 to 0.4
            sharpness_score = self._score_sharpness(gray)
            scores.append(("sharpness", sharpness_score * 0.4))

            # 2. Resolution check - 0.0 to 0.2
            resolution_score = self._score_resolution(img)
            scores.append(("resolution", resolution_score * 0.2))

            # 3. Facial structure detection (for character images) - 0.0 to 0.2
            if image_type == "character_portrait":
                face_score = self._score_facial_structure(img)
                scores.append(("facial_structure", face_score * 0.2))
            else:
                # For B-roll, skip facial structure check
                scores.append(("facial_structure", 0.2))  # Full points for non-character images

            # 4. Balanced lighting - 0.0 to 0.2
            lighting_score = self._score_lighting(img_rgb)
            scores.append(("lighting", lighting_score * 0.2))

            # Calculate total score
            total_score = sum(score for _, score in scores)

            # Log breakdown for debugging
            self.logger.debug(
                f"Image quality scores for {image_path.name}: "
                f"sharpness={scores[0][1]:.3f}, resolution={scores[1][1]:.3f}, "
                f"facial_structure={scores[2][1]:.3f}, lighting={scores[3][1]:.3f}, "
                f"total={total_score:.3f}"
            )

            return min(1.0, max(0.0, total_score))

        except Exception as e:
            self.logger.error(f"Error validating image {image_path}: {e}")
            return 0.0

    def _score_sharpness(self, gray_image: np.ndarray) -> float:
        """
        Score image sharpness using Variance of Laplacian.

        Args:
            gray_image: Grayscale image array

        Returns:
            Sharpness score (0.0 to 1.0)
        """
        try:
            # Calculate Laplacian variance
            laplacian = cv2.Laplacian(gray_image, cv2.CV_64F)
            variance = laplacian.var()

            # Normalize: typical good images have variance > 100
            # Very sharp: > 300, Good: 100-300, Blurry: < 100
            if variance > 300:
                return 1.0
            elif variance > 100:
                # Linear interpolation between 100 and 300
                return 0.5 + (variance - 100) / 400  # 0.5 to 1.0
            elif variance > 50:
                # Linear interpolation between 50 and 100
                return variance / 200  # 0.25 to 0.5
            else:
                return variance / 200  # 0.0 to 0.25

        except Exception as e:
            self.logger.warning(f"Error calculating sharpness: {e}")
            return 0.0

    def _score_resolution(self, image: np.ndarray) -> float:
        """
        Score image resolution (check shortest edge > 1024px).

        Args:
            image: Image array

        Returns:
            Resolution score (0.0 to 1.0)
        """
        try:
            height, width = image.shape[:2]
            shortest_edge = min(height, width)

            # Minimum acceptable: 1024px
            # Ideal: >= 1920px (full vertical resolution)
            if shortest_edge >= 1920:
                return 1.0
            elif shortest_edge >= 1024:
                # Linear interpolation between 1024 and 1920
                return 0.5 + (shortest_edge - 1024) / 1792  # 0.5 to 1.0
            else:
                # Below minimum
                return shortest_edge / 2048  # 0.0 to 0.5

        except Exception as e:
            self.logger.warning(f"Error calculating resolution: {e}")
            return 0.0

    def _score_facial_structure(self, image: np.ndarray) -> float:
        """
        Detect distorted/warped facial structure for character images.

        Uses OpenCV face detection to check if face is present and well-formed.

        Args:
            image: Image array

        Returns:
            Facial structure score (0.0 to 1.0)
        """
        try:
            # Load face cascade classifier
            face_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_cascade = cv2.CascadeClassifier(face_cascade_path)

            if face_cascade.empty():
                self.logger.warning("Face cascade classifier not available, skipping facial structure check")
                return 0.5  # Neutral score if we can't check

            # Convert to grayscale for face detection
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

            # Detect faces
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(50, 50),
            )

            if len(faces) == 0:
                # No face detected - might be a character image without clear face
                # This could be acceptable for some character types
                self.logger.debug("No face detected in character image - may be acceptable")
                return 0.5  # Neutral score

            # Check if face is reasonably sized and centered
            # For character portraits, we expect a clear, well-framed face
            total_area = image.shape[0] * image.shape[1]
            face_scores = []

            for (x, y, w, h) in faces:
                face_area = w * h
                face_ratio = face_area / total_area

                # Good face should be reasonably large (10-40% of image)
                if 0.1 <= face_ratio <= 0.4:
                    face_scores.append(1.0)
                elif 0.05 <= face_ratio < 0.1 or 0.4 < face_ratio <= 0.6:
                    # Acceptable but not ideal
                    face_scores.append(0.7)
                else:
                    # Too small or too large
                    face_scores.append(0.3)

            # Return average score if multiple faces, or single face score
            if face_scores:
                return sum(face_scores) / len(face_scores)
            else:
                return 0.5

        except Exception as e:
            self.logger.warning(f"Error detecting facial structure: {e}")
            return 0.5  # Neutral score on error

    def _score_lighting(self, image_rgb: np.ndarray) -> float:
        """
        Score balanced lighting (avoid blown out whites).

        Checks for overexposed areas (blown out whites) and underexposed areas.

        Args:
            image_rgb: RGB image array

        Returns:
            Lighting score (0.0 to 1.0)
        """
        try:
            # Convert to HSV for better lighting analysis
            hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
            v_channel = hsv[:, :, 2]  # Value (brightness) channel

            # Check for overexposed areas (blown out whites)
            # Very bright pixels (> 240 out of 255) indicate overexposure
            overexposed_pixels = np.sum(v_channel > 240)
            total_pixels = v_channel.size
            overexposed_ratio = overexposed_pixels / total_pixels

            # Check for underexposed areas (very dark)
            # Very dark pixels (< 15 out of 255) indicate underexposure
            underexposed_pixels = np.sum(v_channel < 15)
            underexposed_ratio = underexposed_pixels / total_pixels

            # Calculate score
            # Penalize excessive overexposure (> 10% of image)
            if overexposed_ratio > 0.1:
                overexposure_penalty = min(1.0, overexposed_ratio * 5)  # 0.0 to 1.0 penalty
                overexposure_score = 1.0 - overexposure_penalty
            else:
                overexposure_score = 1.0

            # Penalize excessive underexposure (> 20% of image)
            if underexposed_ratio > 0.2:
                underexposure_penalty = min(1.0, (underexposed_ratio - 0.2) * 2)  # 0.0 to 1.0 penalty
                underexposure_score = 1.0 - underexposure_penalty
            else:
                underexposure_score = 1.0

            # Combined score (average of both)
            lighting_score = (overexposure_score + underexposure_score) / 2.0

            return lighting_score

        except Exception as e:
            self.logger.warning(f"Error calculating lighting: {e}")
            return 0.5  # Neutral score on error

    def is_acceptable(self, image_path: Path, image_type: str = "scene_broll") -> bool:
        """
        Check if image meets minimum quality threshold.

        Args:
            image_path: Path to image file
            image_type: Type of image ("character_portrait" or "scene_broll")

        Returns:
            True if image is acceptable, False otherwise
        """
        score = self.score_image(image_path, image_type)
        return score >= self.min_acceptable_score

