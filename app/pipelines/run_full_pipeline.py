"""Full pipeline orchestrator - topic → story → video → YouTube upload."""

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

from app.core.config import Settings, settings
from app.core.logging_config import get_logger, setup_logging
from app.services.character_engine import CharacterEngine
from app.services.dialogue_engine import DialogueEngine
from app.services.metadata_generator import MetadataGenerator
from app.services.narration_engine import NarrationEngine
from app.services.story_finder import StoryFinder
from app.services.story_rewriter import StoryRewriter
from app.services.story_source import StorySourceService
from app.services.video_plan_engine import VideoPlanEngine
from app.services.video_renderer import VideoRenderer
from app.services.virality_scorer import ViralityScorer
from app.services.youtube_uploader import YouTubeUploader
from app.storage.repository import EpisodeRepository


def generate_story_episode(
    topic: str,
    duration_seconds: int,
    settings: Settings,
    logger: Any,
    repository: EpisodeRepository,
    style: str = "courtroom_drama",
    raw_story_text: Optional[str] = None,
    raw_story_title: Optional[str] = None,
) -> tuple[str, Any]:
    """
    Generate a story episode and VideoPlan.

    Args:
        topic: Story topic (for metadata)
        duration_seconds: Target duration
        settings: App settings
        logger: Logger instance
        repository: Episode repository
        style: Story style
        raw_story_text: Optional pre-selected raw story text (if provided, skips story finding)
        raw_story_title: Optional title for the raw story

    Returns:
        Tuple of (episode_id, video_plan)
    """
    import uuid

    # Get services
    story_rewriter = StoryRewriter(settings, logger)
    character_engine = CharacterEngine(settings, logger)
    dialogue_engine = DialogueEngine(settings, logger)
    narration_engine = NarrationEngine(settings, logger)
    video_plan_engine = VideoPlanEngine(settings, logger)

    # Generate episode ID
    episode_id = f"episode_{uuid.uuid4().hex[:12]}"
    logger.info(f"Episode ID: {episode_id}")

    # Step 1: Get story text (either provided or find it)
    if raw_story_text:
        logger.info("Step 1: Using provided story text...")
        story_text = raw_story_text
        story_title = raw_story_title or topic
    else:
        logger.info("Step 1: Finding story candidate...")
        story_finder = StoryFinder(settings, logger)
        candidate = story_finder.get_best_story(topic)
        logger.info(f"Selected candidate: {candidate.title}")
        story_text = candidate.raw_text
        story_title = candidate.title

    # Step 2: Rewrite story into script
    logger.info("Step 2: Rewriting story into script...")
    story_script = story_rewriter.rewrite_story(story_text, story_title, duration_seconds, style)
    logger.info(f"Created script with {len(story_script.scenes)} scenes")

    # Step 3: Generate characters
    logger.info("Step 3: Generating characters...")
    character_set = character_engine.generate_characters(story_script, style)
    logger.info(f"Generated {len(character_set.characters)} characters")

    # Step 4: Generate dialogue
    logger.info("Step 4: Generating dialogue...")
    dialogue_plan = dialogue_engine.generate_dialogue(story_script, character_set)
    logger.info(f"Generated {len(dialogue_plan.lines)} dialogue lines")

    # Step 5: Generate narration
    logger.info("Step 5: Generating narration...")
    narration_plan = narration_engine.generate_narration(story_script)
    logger.info(f"Generated {len(narration_plan.lines)} narration lines")

    # Step 6: Create video plan
    logger.info("Step 6: Creating video plan...")
    video_plan = video_plan_engine.create_video_plan(
        episode_id=episode_id,
        topic=topic,
        story_script=story_script,
        character_set=character_set,
        dialogue_plan=dialogue_plan,
        narration_plan=narration_plan,
        duration_seconds=duration_seconds,
        style=style,
    )

    # Step 7: Save episode
    logger.info("Step 7: Saving episode...")
    repository.save_episode(video_plan)

    return episode_id, video_plan


# Legacy helper functions removed - now using MetadataGenerator service


def generate_video_metadata(
    video_plan: Any,
    settings: Settings,
    logger: Any,
    title_template: Optional[str] = None,
    description_template: Optional[str] = None,
) -> tuple[str, str, list[str], str]:
    """
    Generate YouTube metadata from VideoPlan using MetadataGenerator.

    Args:
        video_plan: VideoPlan object
        settings: Application settings
        logger: Logger instance
        title_template: Optional custom title template (overrides LLM)
        description_template: Optional custom description template (overrides LLM)

    Returns:
        Tuple of (title, description, tags, hook_line)
    """
    metadata_gen = MetadataGenerator(settings, logger)
    metadata = metadata_gen.generate_metadata(video_plan)

    # Apply custom templates if provided (override LLM output)
    if title_template:
        try:
            metadata.title = title_template.format(
                title=metadata.title, topic=video_plan.topic, logline=video_plan.logline
            )
        except KeyError:
            pass  # Use LLM title if template fails

    if description_template:
        try:
            metadata.description = description_template.format(
                logline=video_plan.logline or "",
                title=metadata.title,
                topic=video_plan.topic,
                hashtags=" ".join([f"#{tag}" for tag in metadata.tags]),
            )
        except KeyError:
            pass  # Use LLM description if template fails

    return metadata.title, metadata.description, metadata.tags, metadata.hook_line


def main():
    """Main entrypoint for full pipeline."""
    parser = argparse.ArgumentParser(
        description="AI Story Shorts Factory - Full Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Story topic (e.g., 'courtroom drama – teen laughs at verdict'). Required unless --auto-topic is used.",
    )
    parser.add_argument(
        "--auto-topic",
        action="store_true",
        help="Automatically select a high-virality story from the specified niche (requires --niche)",
    )
    parser.add_argument(
        "--niche",
        type=str,
        default="courtroom",
        choices=["courtroom", "relationship_drama", "injustice", "workplace_drama"],
        help="Story niche for auto-topic selection (default: courtroom)",
    )
    parser.add_argument(
        "--num-candidates",
        type=int,
        default=5,
        help="Number of story candidates to generate when using --auto-topic (default: 5)",
    )
    parser.add_argument(
        "--duration-target-seconds",
        type=int,
        default=60,
        help="Target video duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview mode: generate and render video but do not upload to YouTube",
    )
    parser.add_argument(
        "--auto-upload",
        action="store_true",
        help="Automatically upload video to YouTube after rendering (requires explicit flag)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/videos",
        help="Output directory for videos (default: outputs/videos)",
    )
    parser.add_argument(
        "--style",
        type=str,
        default="courtroom_drama",
        choices=["courtroom_drama", "ragebait", "relationship_drama"],
        help="Story style: courtroom_drama (formal), ragebait (viral), relationship_drama (emotional) (default: courtroom_drama)",
    )
    parser.add_argument(
        "--title-template",
        type=str,
        default=None,
        help="Custom title template (e.g., '[SHOCKING] {title} - You Won't Believe This!')",
    )
    parser.add_argument(
        "--description-template",
        type=str,
        default=None,
        help="Custom description template (use {logline}, {title}, {topic}, {hashtags})",
    )
    parser.add_argument(
        "--no-talking-heads",
        action="store_true",
        help="Disable talking-head character animations (use static images only)",
    )
    parser.add_argument(
        "--max-talking-head-lines",
        type=int,
        default=None,
        help="Maximum number of dialogue lines to animate (default: 3)",
    )
    parser.add_argument(
        "--batch-count",
        type=int,
        default=1,
        help="Number of videos to generate in batch (default: 1, sequential)",
    )

    args = parser.parse_args()

    # Validate mutually exclusive flags
    if args.preview and args.auto_upload:
        parser.error("--preview and --auto-upload are mutually exclusive. Use --preview to generate without upload.")

    # Validate arguments
    if not args.auto_topic and not args.topic:
        parser.error("Either --topic or --auto-topic must be provided")

    # Setup logging
    topic_for_logging = args.topic or f"auto-{args.niche}"
    setup_logging(log_level=settings.log_level)
    logger = get_logger(__name__, topic=topic_for_logging)

    logger.info("=" * 60)
    logger.info("AI Story Shorts Factory - Full Pipeline")
    if args.auto_topic:
        logger.info(f"Mode: AUTO-TOPIC (niche: {args.niche}, candidates: {args.num_candidates})")
    else:
        logger.info(f"Topic: {args.topic}")
    logger.info(f"Style: {args.style}")
    logger.info(f"Duration: {args.duration_target_seconds}s")
    logger.info(f"Batch count: {args.batch_count}")
    if args.preview:
        logger.info("Mode: PREVIEW (no upload)")
    elif args.auto_upload:
        logger.info("Mode: AUTO-UPLOAD (will upload to YouTube)")
    else:
        logger.info("Mode: GENERATE ONLY (no upload)")
    logger.info("=" * 60)

    try:
        # Override config with CLI flags
        if args.no_talking_heads:
            settings.use_talking_heads = False
        if args.max_talking_head_lines is not None:
            settings.max_talking_head_lines_per_video = args.max_talking_head_lines

        # Initialize repository
        repository = EpisodeRepository(settings, logger)

        # Batch processing loop
        batch_success = 0
        batch_failed = 0
        batch_results = []

        for batch_item in range(1, args.batch_count + 1):
            if args.batch_count > 1:
                logger.info("=" * 60)
                logger.info(f"=== BATCH ITEM {batch_item}/{args.batch_count} ===")
                logger.info("=" * 60)

            try:
                # Phase 0: Auto-select story if requested
                selected_topic = args.topic
                selected_story_text = None
                selected_story_title = None

                if args.auto_topic:
                    logger.info("=" * 60)
                    logger.info("PHASE 0: Story Sourcing & Virality Scoring")
                    logger.info("=" * 60)

                    story_source = StorySourceService(settings, logger)
                    virality_scorer = ViralityScorer(settings, logger)

                    # Generate candidates
                    logger.info(f"Generating {args.num_candidates} candidates for niche: {args.niche}")
                    candidates = story_source.generate_candidates_for_niche(niche=args.niche, num_candidates=args.num_candidates)

                    # Score and rank
                    logger.info("Scoring candidates for virality...")
                    ranked = virality_scorer.rank_candidates(candidates)

                    # Select top candidate
                    top_candidate, top_score = ranked[0]
                    selected_story_text = top_candidate.raw_text
                    selected_story_title = top_candidate.title
                    selected_topic = top_candidate.title  # Use title as topic for metadata

                    logger.info("=" * 60)
                    logger.info("SELECTED CANDIDATE:")
                    logger.info(f"  ID: {top_candidate.id}")
                    logger.info(f"  Title: {top_candidate.title}")
                    logger.info(f"  Overall Score: {top_score.overall_score:.3f}")
                    logger.info(f"  Breakdown: shock={top_score.shock:.2f}, rage={top_score.rage:.2f}, "
                               f"injustice={top_score.injustice:.2f}, relatability={top_score.relatability:.2f}, "
                               f"twist={top_score.twist_strength:.2f}, clarity={top_score.clarity:.2f}")
                    logger.info("=" * 60)

                    # Log top 3 for reference
                    logger.info("Top 3 candidates:")
                    for i, (candidate, score) in enumerate(ranked[:3], 1):
                        logger.info(f"  {i}. {candidate.title[:60]}... (score: {score.overall_score:.3f})")

                # Step 1: Generate story episode
                logger.info("=" * 60)
                logger.info("PHASE 1: Story Generation")
                logger.info("=" * 60)
                episode_id, video_plan = generate_story_episode(
                    selected_topic,
                    args.duration_target_seconds,
                    settings,
                    logger,
                    repository,
                    style=args.style,
                    raw_story_text=selected_story_text,
                    raw_story_title=selected_story_title,
                )

                # Step 2: Render video
                logger.info("=" * 60)
                logger.info("PHASE 2: Video Rendering")
                logger.info("=" * 60)
                
                # Organize output directory
                if args.preview:
                    output_base = Path(args.output_dir) / "preview"
                else:
                    output_base = Path(args.output_dir) / "videos"
                
                # Create episode-specific subdirectory
                from app.utils.io_utils import slugify
                topic_slug = slugify(selected_topic or video_plan.title)
                episode_output_dir = output_base / f"{episode_id}_{topic_slug}"
                
                video_renderer = VideoRenderer(settings, logger)
                video_path = video_renderer.render(video_plan, episode_output_dir)

                logger.info(f"Video rendered: {video_path}")

                # Step 3: Upload to YouTube (only if --auto-upload and not --preview)
                youtube_url = None
                should_upload = args.auto_upload and not args.preview
                
                if should_upload:
                    logger.info("=" * 60)
                    logger.info("PHASE 3: YouTube Upload")
                    logger.info("=" * 60)

                    title, description, tags, hook_line = generate_video_metadata(
                        video_plan,
                        settings,
                        logger,
                        title_template=args.title_template,
                        description_template=args.description_template,
                    )
                    
                    if hook_line:
                        logger.info(f"Generated hook line: {hook_line}")

                    uploader = YouTubeUploader(settings, logger)
                    youtube_url = uploader.upload(
                        video_path=video_path,
                        title=title,
                        description=description,
                        tags=tags,
                        privacy_status="public",
                    )
                elif args.preview:
                    logger.info("=" * 60)
                    logger.info("PREVIEW MODE - No upload performed")
                    logger.info("=" * 60)

                # Summary for this batch item
                logger.info("=" * 60)
                logger.info(f"PIPELINE COMPLETE{' (Batch ' + str(batch_item) + '/' + str(args.batch_count) + ')' if args.batch_count > 1 else ''}!")
                logger.info("=" * 60)
                logger.info(f"Episode ID: {episode_id}")
                logger.info(f"Video: {video_path.absolute()}")
                if youtube_url:
                    logger.info(f"YouTube URL: {youtube_url}")
                elif args.preview:
                    logger.info("PREVIEW MODE - Video generated but not uploaded")
                logger.info("=" * 60)

                batch_success += 1
                batch_results.append({"episode_id": episode_id, "video_path": video_path, "youtube_url": youtube_url})

            except Exception as e:
                batch_failed += 1
                logger.error(f"Batch item {batch_item} failed: {e}", exc_info=True)
                if args.batch_count > 1:
                    logger.warning(f"Continuing with next batch item...")
                else:
                    # If single run, re-raise
                    raise

        # Final batch summary
        if args.batch_count > 1:
            logger.info("=" * 60)
            logger.info("BATCH COMPLETE!")
            logger.info("=" * 60)
            logger.info(f"Success: {batch_success}/{args.batch_count}")
            logger.info(f"Failed: {batch_failed}/{args.batch_count}")
            logger.info("=" * 60)
            for i, result in enumerate(batch_results, 1):
                logger.info(f"{i}. {result['episode_id']}: {result['video_path'].name}")
                if result.get("youtube_url"):
                    logger.info(f"   YouTube: {result['youtube_url']}")

        return 0

    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        logger.error(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

