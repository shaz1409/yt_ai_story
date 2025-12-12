"""Full pipeline orchestrator - topic → story → video → YouTube upload."""

import argparse
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import Settings, settings
from app.core.logging_config import get_logger, setup_logging
from app.services.analytics_service import AnalyticsService
from app.services.character_engine import CharacterEngine
from app.services.checkpoint_manager import CheckpointManager
from app.services.dialogue_engine import DialogueEngine
from app.services.metadata_generator import MetadataGenerator
from app.services.narration_engine import NarrationEngine
from app.services.optimisation_engine import OptimisationEngine, PlannedVideo
from app.services.schedule_manager import ScheduleManager
from app.services.story_finder import StoryFinder
from app.services.story_rewriter import StoryRewriter
from app.services.story_source import StorySourceService
from app.services.video_plan_engine import VideoPlanEngine
from app.services.video_renderer import VideoRenderer
from app.services.virality_scorer import ViralityScorer
from app.services.quality_scorer import QualityScorer
from app.services.thumbnail_generator import ThumbnailGenerator
from app.services.youtube_uploader import YouTubeUploader
from app.storage.repository import EpisodeRepository
from app.utils.parallel_executor import ParallelExecutor


def generate_story_episode(
    topic: str,
    duration_seconds: int,
    settings: Settings,
    logger: Any,
    repository: EpisodeRepository,
    style: str = "courtroom_drama",
    raw_story_text: Optional[str] = None,
    raw_story_title: Optional[str] = None,
    niche: Optional[str] = None,
    primary_emotion: Optional[str] = None,
    secondary_emotion: Optional[str] = None,
    topic_hint: Optional[str] = None,
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
    story_script, pattern_type = story_rewriter.rewrite_story(
        story_text,
        story_title,
        duration_seconds,
        style,
        niche=niche,
        primary_emotion=primary_emotion,
        secondary_emotion=secondary_emotion,
        topic_hint=topic_hint,
    )
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
        niche=niche,
        primary_emotion=primary_emotion,
        secondary_emotion=secondary_emotion,
        pattern_type=pattern_type,
    )

    # Step 7: Save episode
    logger.info("Step 7: Saving episode...")
    repository.save_episode(video_plan)

    return episode_id, video_plan


# Legacy helper functions removed - now using MetadataGenerator service


def _process_single_episode(
    item_idx: int,
    num_iterations: int,
    planned_videos: list,
    args: argparse.Namespace,
    settings: Settings,
    logger: Any,
    repository: EpisodeRepository,
    checkpoint_manager: Optional[CheckpointManager],
    analytics_service: AnalyticsService,
    scheduled_slots: Optional[list],
) -> dict:
    """
    Process a single episode (extracted for parallel execution).
    
    Args:
        item_idx: Batch item index (1-based)
        num_iterations: Total number of episodes in batch
        planned_videos: List of planned videos (if optimisation enabled)
        args: Command-line arguments
        settings: Application settings
        logger: Logger instance
        repository: Episode repository
        checkpoint_manager: Optional checkpoint manager
        analytics_service: Analytics service
        scheduled_slots: Optional list of scheduled publish times
        
    Returns:
        Dictionary with episode_id, video_path, youtube_url, duration_seconds
    """
    episode_start_time = time.time()
    
    if num_iterations > 1:
        logger.info("=" * 60)
        logger.info(f"=== BATCH ITEM {item_idx}/{num_iterations} ===")
        logger.info("=" * 60)

    try:
        # Get planned video if optimisation is enabled
        planned_video = planned_videos[item_idx - 1] if planned_videos else None
        
        # Phase 0: Auto-select story if requested
        selected_topic = args.topic
        selected_story_text = None
        selected_story_title = None
        selected_niche = args.niche
        selected_style = args.style

        # Override with planned video attributes if optimisation is enabled
        if planned_video:
            selected_niche = planned_video.niche
            selected_style = planned_video.style
            selected_topic = planned_video.topic_hint  # Use topic_hint if available
            logger.info(f"Using planned video: {planned_video.niche}/{planned_video.pattern_type}/{planned_video.primary_emotion}")

        # Use auto-topic logic if auto-topic flag is set OR if we have a planned video (optimisation mode)
        if args.auto_topic or planned_video:
            logger.info("=" * 60)
            logger.info("PHASE 0: Story Sourcing & Virality Scoring")
            logger.info("=" * 60)

            story_source = StorySourceService(settings, logger)
            virality_scorer = ViralityScorer(settings, logger)

            # Generate candidates
            logger.info(f"Generating {args.num_candidates} candidates for niche: {selected_niche}")
            candidates = story_source.generate_candidates_for_niche(niche=selected_niche, num_candidates=args.num_candidates)

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

        # Assign scheduled publish time if daily mode is enabled
        scheduled_publish_at = None
        if args.daily_mode and scheduled_slots:
            scheduled_publish_at = scheduled_slots[item_idx - 1]
            logger.info(f"Assigned scheduled publish time: {scheduled_publish_at.isoformat()}")

        # Step 1: Generate story episode
        logger.info("=" * 60)
        logger.info("PHASE 1: Story Generation")
        logger.info("=" * 60)
        # Pass beat-based inputs if we have a planned video
        beat_inputs = {}
        if planned_video:
            beat_inputs = {
                "niche": planned_video.niche,
                "primary_emotion": planned_video.primary_emotion,
                "secondary_emotion": planned_video.secondary_emotion,
                "topic_hint": planned_video.topic_hint or selected_topic or f"{selected_niche} story",
            }

        episode_id, video_plan = generate_story_episode(
            selected_topic or f"{selected_niche} story",
            args.duration_target_seconds,
            settings,
            logger,
            repository,
            style=selected_style,
            raw_story_text=selected_story_text,
            raw_story_title=selected_story_title,
            **beat_inputs,
        )

        # Set planned_publish_at in metadata if scheduled time was assigned
        if scheduled_publish_at and video_plan.metadata:
            video_plan.metadata.planned_publish_at = scheduled_publish_at
            logger.info(f"Set planned_publish_at in metadata: {scheduled_publish_at.isoformat()}")
            # Save episode with scheduled time before rendering
            repository.save_episode(video_plan)
            logger.info("Saved episode with scheduled publish time")

        # Step 2: Render video (skip in dry-run mode)
        video_path = None
        
        # Check for resume checkpoint
        if checkpoint_manager and checkpoint_manager.has_checkpoint(episode_id, CheckpointManager.STAGE_VIDEO_RENDERED):
            logger.info(f"Resuming from checkpoint: {episode_id} at video_rendered stage")
            checkpoint_data = checkpoint_manager.load_checkpoint(episode_id, CheckpointManager.STAGE_VIDEO_RENDERED)
            if checkpoint_data and checkpoint_data.get("video_path"):
                video_path = Path(checkpoint_data["video_path"])
                if video_path.exists():
                    logger.info(f"Using cached video from checkpoint: {video_path}")
                else:
                    logger.warning("Checkpoint video path not found, re-rendering...")
                    video_path = None
        
        if args.dry_run:
            logger.info("=" * 60)
            logger.info("DRY-RUN MODE - Skipping video rendering")
            logger.info("=" * 60)
            logger.info("VideoPlan generated successfully:")
            logger.info(f"  Episode ID: {episode_id}")
            logger.info(f"  Title: {video_plan.title}")
            logger.info(f"  Scenes: {len(video_plan.scenes)}")
            logger.info(f"  Characters: {len(video_plan.characters)}")
            logger.info(f"  Duration target: {video_plan.metadata.duration_target_seconds if video_plan.metadata else 'N/A'}s")
            if video_plan.character_spoken_lines:
                logger.info(f"  Character spoken lines: {len(video_plan.character_spoken_lines)}")
            if video_plan.b_roll_scenes:
                logger.info(f"  B-roll scenes: {len(video_plan.b_roll_scenes)}")
            logger.info("=" * 60)
            logger.info("DRY-RUN complete - no video rendered, no upload performed")
        else:
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
            
            if not video_path:
                video_renderer = VideoRenderer(settings, logger)
                video_path, image_scores = video_renderer.render(video_plan, episode_output_dir)
                logger.info(f"Video rendered: {video_path}")
                logger.info(f"Collected {len(image_scores)} image quality scores")
                
                # Save checkpoint
                if checkpoint_manager:
                    checkpoint_manager.save_checkpoint(
                        episode_id,
                        CheckpointManager.STAGE_VIDEO_RENDERED,
                        {"video_path": str(video_path)},
                    )
            else:
                logger.info(f"Using video from checkpoint: {video_path}")
            
            # Re-save episode with updated metadata (now includes rendering info)
            logger.info("Saving updated episode with rendering metadata...")
            repository.save_episode(video_plan)

            # Step 2.5: Compute and log quality scores (non-critical)
            try:
                quality_scorer = QualityScorer(settings, logger)
                # Use collected image scores if available, otherwise None (will default to moderate)
                image_scores_for_quality = image_scores if 'image_scores' in locals() else None
                scores = quality_scorer.compute_quality_scores(
                    video_plan=video_plan,
                    episode_metadata=video_plan.metadata,
                    image_scores=image_scores_for_quality,
                    content_metrics=None,
                )
                quality_scorer.log_quality_metrics(
                    episode_id=episode_id,
                    scores=scores,
                    video_plan=video_plan,
                    metadata=video_plan.metadata,
                )
                logger.info(f"Quality scores: overall={scores['overall_score']:.1f}, "
                          f"visual={scores['visual_score']:.1f}, "
                          f"content={scores['content_score']:.1f}, "
                          f"technical={scores['technical_score']:.1f}")
            except Exception as e:
                logger.warning(f"Quality scoring failed (non-critical): {e}")

            # Step 2.6: Generate thumbnail (if enabled)
            thumbnail_path = None
            if getattr(settings, "thumbnail_enabled", True):
                try:
                    logger.info("=" * 60)
                    logger.info("PHASE 2.5: Thumbnail Generation")
                    logger.info("=" * 60)
                    thumbnail_generator = ThumbnailGenerator(settings, logger)
                    thumbnail_path = thumbnail_generator.generate_thumbnail(
                        video_plan=video_plan,
                        video_path=video_path,
                        episode_id=episode_id,
                    )
                    if thumbnail_path:
                        logger.info(f"✅ Thumbnail generated: {thumbnail_path}")
                    else:
                        logger.warning("Thumbnail generation returned None (may be disabled or failed)")
                except Exception as e:
                    logger.warning(f"Thumbnail generation failed (non-critical): {e}")
                    thumbnail_path = None

        # Step 3: Upload to YouTube (only if --auto-upload and not --preview and not --dry-run)
        youtube_url = None
        should_upload = args.auto_upload and not args.preview and not args.dry_run
        
        # Get scheduled publish time from metadata if set
        scheduled_publish_at = None
        if video_plan.metadata and video_plan.metadata.planned_publish_at:
            scheduled_publish_at = video_plan.metadata.planned_publish_at
            logger.info(f"Scheduled publish time found in metadata: {scheduled_publish_at}")
        
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
                scheduled_publish_at=scheduled_publish_at,
                thumbnail_path=thumbnail_path,
            )
            
            # Update metadata with YouTube info and re-save after upload
            if video_plan.metadata:
                # Extract video ID from URL
                if youtube_url and "watch?v=" in youtube_url:
                    video_id = youtube_url.split("watch?v=")[1].split("&")[0]
                    video_plan.metadata.youtube_video_id = video_id
                    video_plan.metadata.published_at = datetime.now()
                    if scheduled_publish_at:
                        video_plan.metadata.planned_publish_at = scheduled_publish_at
                        # Set published_hour_local from scheduled time
                        video_plan.metadata.published_hour_local = scheduled_publish_at.hour
                    logger.info(f"Updated metadata with YouTube video ID: {video_id}")
                    
                    # Record in analytics
                    analytics_service.record_video_upload(
                        episode_id=episode_id,
                        youtube_video_id=video_id,
                        title=title,
                        niche=video_plan.metadata.niche if video_plan.metadata else None,
                        style=video_plan.style,
                        published_at=scheduled_publish_at or datetime.now(),
                    )
                    logger.info(f"Recorded video in analytics: {episode_id}")
            
            # Re-save episode with YouTube metadata
            logger.info("Saving episode with YouTube upload metadata...")
            repository.save_episode(video_plan)
        elif args.preview:
            logger.info("=" * 60)
            logger.info("PREVIEW MODE - No upload performed")
            if scheduled_publish_at:
                logger.info(f"Planned publish time (not used in preview): {scheduled_publish_at}")
            logger.info("=" * 60)

        # Summary for this batch item
        episode_elapsed = time.time() - episode_start_time
        logger.info("=" * 60)
        logger.info(f"PIPELINE COMPLETE{' (Batch ' + str(item_idx) + '/' + str(num_iterations) + ')' if num_iterations > 1 else ''}!")
        logger.info("=" * 60)
        logger.info(f"Episode ID: {episode_id}")
        logger.info(f"Episode duration: {episode_elapsed:.2f}s")
        if args.dry_run:
            logger.info("DRY-RUN MODE - VideoPlan generated, no video rendered")
        elif video_path:
            logger.info(f"Video: {video_path.absolute()}")
        if youtube_url:
            logger.info(f"YouTube URL: {youtube_url}")
        elif args.preview:
            logger.info("PREVIEW MODE - Video generated but not uploaded")
        logger.info("=" * 60)

        return {
            "episode_id": episode_id,
            "video_path": video_path,
            "youtube_url": youtube_url,
            "duration_seconds": episode_elapsed,
        }

    except Exception as e:
        episode_elapsed = time.time() - episode_start_time
        logger.error(f"Episode {item_idx} failed after {episode_elapsed:.2f}s: {e}", exc_info=True)
        raise


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
        "--dry-run",
        action="store_true",
        help="Dry-run mode: generate VideoPlan and log what would happen, but skip rendering and upload (for testing)",
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
    parser.add_argument(
        "--daily-mode",
        action="store_true",
        help="Daily batch mode: force optimisation, auto-assign time slots, enable auto-upload with scheduling",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date for scheduling (YYYY-MM-DD). Defaults to today if not provided.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint if pipeline failed (experimental)",
    )

    args = parser.parse_args()

    # Daily mode validation and overrides
    if args.daily_mode:
        # Force optimisation mode
        settings.use_optimisation = True
        # Require batch-count
        if args.batch_count < 1:
            parser.error("--daily-mode requires --batch-count >= 1")
        # Disable preview (daily mode always uploads)
        if args.preview:
            parser.error("--daily-mode and --preview are mutually exclusive. Daily mode always uploads (scheduled).")
        # Force auto-upload
        args.auto_upload = True
        logger_temp = get_logger(__name__)
        logger_temp.info("Daily mode enabled: forcing optimisation, auto-upload, and scheduling")

    # Validate mutually exclusive flags
    if args.preview and args.auto_upload:
        parser.error("--preview and --auto-upload are mutually exclusive. Use --preview to generate without upload.")
    if args.dry_run and (args.preview or args.auto_upload):
        parser.error("--dry-run is mutually exclusive with --preview and --auto-upload. Dry-run skips rendering and upload.")

    # Validate arguments
    # Allow no topic if optimisation is enabled
    if not args.auto_topic and not args.topic and not settings.use_optimisation:
        parser.error("Either --topic or --auto-topic must be provided (or enable optimisation mode)")

    # Parse date if provided
    target_date = date.today()
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            parser.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD format.")

    # Setup logging
    topic_for_logging = args.topic or f"auto-{args.niche}"
    setup_logging(log_level=settings.log_level)
    logger = get_logger(__name__, topic=topic_for_logging)

    logger.info("=" * 60)
    logger.info("AI Story Shorts Factory - Full Pipeline")
    
    # Check if optimisation mode is enabled
    use_optimisation = settings.use_optimisation and not args.topic
    
    if args.daily_mode:
        logger.info("Mode: DAILY BATCH MODE")
        logger.info(f"Target date: {target_date}")
        logger.info(f"Batch count: {args.batch_count}")
        logger.info("(Forcing optimisation, auto-upload with scheduling)")
    elif use_optimisation:
        logger.info("Optimisation mode active")
        logger.info("(Using OptimisationEngine to select optimal video plans)")
    elif args.auto_topic:
        logger.info(f"Mode: AUTO-TOPIC (niche: {args.niche}, candidates: {args.num_candidates})")
    else:
        logger.info(f"Topic: {args.topic}")
    
    logger.info(f"Style: {args.style}")
    logger.info(f"Duration: {args.duration_target_seconds}s")
    logger.info(f"Batch count: {args.batch_count}")
    if args.dry_run:
        logger.info("Mode: DRY-RUN (generate VideoPlan only, no rendering/upload)")
    elif args.preview:
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
        
        # Initialize analytics service
        analytics_service = AnalyticsService(settings, logger)
        
        # Initialize checkpoint manager if resume is enabled
        checkpoint_manager = None
        if args.resume:
            checkpoint_manager = CheckpointManager(settings, logger)
            logger.info("Resume mode enabled - will save checkpoints and can resume on failure")

        # Initialize schedule manager if daily mode is enabled
        schedule_manager = None
        scheduled_slots = []
        if args.daily_mode:
            # Use configurable timezone and posting hours from settings
            timezone_str = settings.timezone
            posting_hours = settings.daily_posting_hours
            schedule_manager = ScheduleManager(timezone=timezone_str, posting_hours=posting_hours)
            scheduled_slots = schedule_manager.get_daily_slots(target_date, args.batch_count)
            logger.info(f"Using timezone: {timezone_str}")
            logger.info(f"Using posting hours: {posting_hours}")
            logger.info("=" * 60)
            logger.info("SCHEDULING: Assigned time slots")
            logger.info("=" * 60)
            for i, slot in enumerate(scheduled_slots, 1):
                logger.info(f"  Slot {i}: {slot.isoformat()}")
            logger.info("=" * 60)

        # Get planned videos if optimisation is enabled
        planned_videos = []
        if use_optimisation:
            logger.info("=" * 60)
            logger.info("OPTIMISATION: Selecting batch plan...")
            logger.info("=" * 60)
            
            optimisation_engine = OptimisationEngine(settings, repository, logger)
            planned_videos = optimisation_engine.select_batch_plan(
                batch_count=args.batch_count,
                fallback_niche=args.niche
            )
            
            logger.info("=" * 60)
            logger.info("Planned batch:")
            logger.info("=" * 60)
            for i, planned in enumerate(planned_videos, 1):
                logger.info(f"  {i}. Niche: {planned.niche}, Style: {planned.style}")
                logger.info(f"     Pattern: {planned.pattern_type}, Emotion: {planned.primary_emotion}")
                if planned.secondary_emotion:
                    logger.info(f"     Secondary: {planned.secondary_emotion}")
                if planned.topic_hint:
                    logger.info(f"     Hint: {planned.topic_hint}")
            logger.info("=" * 60)

        # Determine number of iterations
        num_iterations = len(planned_videos) if planned_videos else args.batch_count

        # Initialize parallel executor
        parallel_executor = ParallelExecutor(settings, logger)
        max_parallel = settings.max_parallel_episodes
        
        if num_iterations > 1:
            logger.info(f"Batch processing: {num_iterations} episodes with max parallelism: {max_parallel}")
        else:
            logger.info("Single episode processing (no parallelism)")

        # Prepare episode processing tasks
        episode_tasks = []
        episode_task_names = []
        
        for batch_item in range(1, num_iterations + 1):
            # Create a closure to capture batch_item and other variables
            def create_episode_task(item_idx: int):
                def process_episode():
                    return _process_single_episode(
                        item_idx=item_idx,
                        num_iterations=num_iterations,
                        planned_videos=planned_videos,
                        args=args,
                        settings=settings,
                        logger=logger,
                        repository=repository,
                        checkpoint_manager=checkpoint_manager,
                        analytics_service=analytics_service,
                        scheduled_slots=scheduled_slots if args.daily_mode else None,
                    )
                return process_episode
            
            episode_tasks.append(create_episode_task(batch_item))
            episode_task_names.append(f"episode_{batch_item}")

        # Execute episodes in parallel (or sequentially if max_parallel_episodes=1)
        batch_start_time = time.time()
        episode_results = parallel_executor.execute_batch(
            episode_tasks,
            task_names=episode_task_names,
            max_workers=max_parallel,
        )
        
        batch_elapsed = time.time() - batch_start_time
        
        # Process results
        batch_success = 0
        batch_failed = 0
        batch_results = []
        
        for i, (result, exception) in enumerate(episode_results):
            batch_item = i + 1
            if exception:
                batch_failed += 1
                logger.error(f"Batch item {batch_item} failed: {exception}", exc_info=True)
            elif result:
                batch_success += 1
                batch_results.append(result)
            else:
                batch_failed += 1
                logger.error(f"Batch item {batch_item} returned no result")

        # OLD SEQUENTIAL LOOP REMOVED - now using parallel executor above
        # The episode processing logic is in _process_single_episode() function

        # Final batch summary
        if num_iterations > 1:
            logger.info("=" * 60)
            logger.info("BATCH COMPLETE!")
            logger.info("=" * 60)
            logger.info(f"Total batch time: {batch_elapsed:.2f}s")
            logger.info(f"Success: {batch_success}/{num_iterations}")
            logger.info(f"Failed: {batch_failed}/{num_iterations}")
            logger.info(f"Parallelism: {max_parallel} workers")
            logger.info("=" * 60)
            for i, result in enumerate(batch_results, 1):
                episode_id = result.get("episode_id", "unknown")
                video_path = result.get("video_path")
                duration = result.get("duration_seconds", 0)
                logger.info(f"{i}. {episode_id}: {video_path.name if video_path else 'N/A'} (duration: {duration:.2f}s)")
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

