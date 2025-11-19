"""Story generation using OpenAI."""

import json
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from config import Settings


class StoryRequest(BaseModel):
    """Request model for story generation."""

    topic: str = Field(..., description="The topic for the story")
    target_duration_seconds: int = Field(default=45, description="Target duration in seconds")
    num_images: int = Field(default=6, description="Number of image prompts to generate")


class StoryResult(BaseModel):
    """Result model containing generated story content."""

    hook: str = Field(..., description="Opening hook line (1-2 sentences)")
    story_script: str = Field(..., description="Full story script to be narrated")
    title: str = Field(..., description="YouTube title (max ~70 chars)")
    description: str = Field(..., description="YouTube description (2-4 sentences)")
    image_prompts: list[str] = Field(..., description="List of image prompts for scenes")


class StoryGenerator:
    """Generates story content using OpenAI."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize the story generator.

        Args:
            settings: Application settings.
            logger: Logger instance.
        """
        self.settings = settings
        self.logger = logger
        self.client = OpenAI(api_key=settings.openai_api_key)

    def generate_story(self, request: StoryRequest) -> StoryResult:
        """
        Generate a complete story from a topic.

        Args:
            request: Story generation request.

        Returns:
            Generated story result.

        Raises:
            Exception: If generation or parsing fails.
        """
        self.logger.info(f"Generating story for topic: {request.topic}")

        system_prompt = """You are a professional YouTube Shorts content creator. 
You create engaging, dramatic stories that hook viewers immediately. 
Your stories are:
- 30-60 seconds when spoken (approximately 75-150 words)
- Written in present tense
- High-emotion and dramatic
- Safe for YouTube (no explicit violence, gore, or policy violations)
- Compelling and shareable

Always return your response as valid JSON with these exact keys:
- "hook": A 1-2 sentence opening hook that grabs attention
- "story_script": The full story text to be narrated (present tense, dramatic)
- "title": A clicky YouTube title (max 70 characters)
- "description": A YouTube description (2-4 sentences)
- "image_prompts": An array of strings, each describing a realistic scene that matches moments in the story
"""

        user_prompt = f"""Create a YouTube Shorts story about: {request.topic}

Requirements:
- Story script should be approximately {request.target_duration_seconds} seconds when spoken (roughly {int(request.target_duration_seconds * 2.5)} words)
- Generate exactly {request.num_images} image prompts
- Make it dramatic, emotional, and engaging
- Ensure it's safe for YouTube content policies

Return ONLY valid JSON with the structure specified above. Do not include any markdown formatting or code blocks."""

        try:
            self.logger.info("Sending request to OpenAI...")
            response = self.client.chat.completions.create(
                model=self.settings.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.8,
            )

            self.logger.info("Received response from OpenAI")
            content = response.choices[0].message.content

            if not content:
                raise ValueError("Empty response from OpenAI")

            # Parse JSON response
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON response: {e}")
                self.logger.error(f"Response content: {content[:500]}")
                raise ValueError(f"Invalid JSON response from OpenAI: {e}")

            # Validate and create result
            result = StoryResult(
                hook=data.get("hook", ""),
                story_script=data.get("story_script", ""),
                title=data.get("title", ""),
                description=data.get("description", ""),
                image_prompts=data.get("image_prompts", []),
            )

            self.logger.info(f"Successfully generated story: {result.title}")
            self.logger.info(f"Story script length: {len(result.story_script)} characters")
            self.logger.info(f"Number of image prompts: {len(result.image_prompts)}")

            return result

        except Exception as e:
            self.logger.error(f"Error generating story: {e}")
            raise

