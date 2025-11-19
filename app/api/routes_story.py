"""FastAPI routes for story generation."""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.schemas import GenerateStoryRequest, GenerateStoryResponse, VideoPlan
from app.services.character_engine import CharacterEngine
from app.services.dialogue_engine import DialogueEngine
from app.services.narration_engine import NarrationEngine
from app.services.story_finder import StoryFinder
from app.services.story_rewriter import StoryRewriter
from app.services.video_plan_engine import VideoPlanEngine
from app.storage.repository import EpisodeRepository

router = APIRouter(prefix="/stories", tags=["stories"])


def get_services(settings: Settings, logger: Any) -> dict:
    """Get all service instances."""
    return {
        "story_finder": StoryFinder(settings, logger),
        "story_rewriter": StoryRewriter(settings, logger),
        "character_engine": CharacterEngine(settings, logger),
        "dialogue_engine": DialogueEngine(settings, logger),
        "narration_engine": NarrationEngine(settings, logger),
        "video_plan_engine": VideoPlanEngine(settings, logger),
        "repository": EpisodeRepository(settings, logger),
    }


@router.post("/generate", response_model=GenerateStoryResponse)
async def generate_story(request: GenerateStoryRequest) -> GenerateStoryResponse:
    """
    Generate a complete story video plan.

    Pipeline:
    StoryFinder → StoryRewriter → CharacterEngine → DialogueEngine → NarrationEngine → VideoPlanEngine
    """
    from app.core.config import settings
    from app.core.logging_config import get_logger

    logger = get_logger(__name__, topic=request.topic)
    logger.info("=" * 60)
    logger.info("Starting story generation pipeline")
    logger.info(f"Topic: {request.topic}")
    logger.info(f"Duration: {request.duration_target_seconds}s")
    logger.info("=" * 60)

    try:
        # Get services
        services = get_services(settings, logger)

        # Generate episode ID
        episode_id = f"episode_{uuid.uuid4().hex[:12]}"
        logger.info(f"Episode ID: {episode_id}")

        # Step 1: Find best story candidate
        logger.info("Step 1: Finding story candidate...")
        story_finder = services["story_finder"]
        candidate = story_finder.get_best_story(request.topic)
        logger.info(f"Selected candidate: {candidate.title}")

        # Step 2: Rewrite story into script
        logger.info("Step 2: Rewriting story into script...")
        story_rewriter = services["story_rewriter"]
        story_script = story_rewriter.rewrite_story(
            candidate.raw_text,
            candidate.title,
            request.duration_target_seconds,
        )
        logger.info(f"Created script with {len(story_script.scenes)} scenes")

        # Step 3: Generate characters
        logger.info("Step 3: Generating characters...")
        character_engine = services["character_engine"]
        character_set = character_engine.generate_characters(story_script, settings.default_style)
        logger.info(f"Generated {len(character_set.characters)} characters")

        # Step 4: Generate dialogue
        logger.info("Step 4: Generating dialogue...")
        dialogue_engine = services["dialogue_engine"]
        dialogue_plan = dialogue_engine.generate_dialogue(story_script, character_set)
        logger.info(f"Generated {len(dialogue_plan.lines)} dialogue lines")

        # Step 5: Generate narration
        logger.info("Step 5: Generating narration...")
        narration_engine = services["narration_engine"]
        narration_plan = narration_engine.generate_narration(story_script)
        logger.info(f"Generated {len(narration_plan.lines)} narration lines")

        # Step 6: Create video plan
        logger.info("Step 6: Creating video plan...")
        video_plan_engine = services["video_plan_engine"]
        video_plan = video_plan_engine.create_video_plan(
            episode_id=episode_id,
            topic=request.topic,
            story_script=story_script,
            character_set=character_set,
            dialogue_plan=dialogue_plan,
            narration_plan=narration_plan,
            duration_seconds=request.duration_target_seconds,
            style=settings.default_style,
        )

        # Step 7: Save episode
        logger.info("Step 7: Saving episode...")
        repository = services["repository"]
        repository.save_episode(video_plan)

        logger.info("=" * 60)
        logger.info("Story generation complete!")
        logger.info("=" * 60)

        return GenerateStoryResponse(
            episode_id=episode_id,
            title=video_plan.title,
            logline=video_plan.logline,
            scene_count=len(video_plan.scenes),
            character_count=len(video_plan.characters),
            status="completed",
        )

    except Exception as e:
        logger.error(f"Error generating story: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Story generation failed: {str(e)}")


@router.get("/{episode_id}", response_model=VideoPlan)
async def get_story(episode_id: str) -> VideoPlan:
    """Get full video plan for an episode."""
    from app.core.config import settings
    from app.core.logging_config import get_logger

    logger = get_logger(__name__, episode_id=episode_id)
    logger.info(f"Fetching episode: {episode_id}")

    repository = EpisodeRepository(settings, logger)
    video_plan = repository.load_episode(episode_id)

    if not video_plan:
        raise HTTPException(status_code=404, detail=f"Episode {episode_id} not found")

    return video_plan


@router.get("/{episode_id}/export")
async def export_story(episode_id: str) -> Response:
    """Export episode as downloadable JSON file."""
    from app.core.config import settings
    from app.core.logging_config import get_logger

    logger = get_logger(__name__, episode_id=episode_id)
    logger.info(f"Exporting episode: {episode_id}")

    repository = EpisodeRepository(settings, logger)
    video_plan = repository.load_episode(episode_id)

    if not video_plan:
        raise HTTPException(status_code=404, detail=f"Episode {episode_id} not found")

    # Convert to JSON
    json_content = video_plan.model_dump_json(indent=2)

    return Response(
        content=json_content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{episode_id}.json"'},
    )

