"""Parallel Executor - manages controlled parallelism for batch processing and API calls."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Optional

from app.core.config import Settings
from app.core.logging_config import get_logger


class ParallelExecutor:
    """Manages controlled parallelism for batch processing and API calls."""

    def __init__(self, settings: Settings, logger: Any):
        """
        Initialize parallel executor.

        Args:
            settings: Application settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self.max_parallel_episodes = getattr(settings, "max_parallel_episodes", 3)
        self.max_parallel_api_calls = getattr(settings, "max_parallel_api_calls", 5)

    def execute_batch(
        self,
        tasks: list[Callable],
        task_names: Optional[list[str]] = None,
        max_workers: Optional[int] = None,
    ) -> list[tuple[Any, Optional[Exception]]]:
        """
        Execute a batch of tasks in parallel with controlled concurrency.

        Args:
            tasks: List of callable tasks to execute
            task_names: Optional list of task names for logging
            max_workers: Maximum number of parallel workers (defaults to max_parallel_episodes)

        Returns:
            List of tuples: (result, exception) for each task
        """
        if not tasks:
            return []

        max_workers = max_workers or self.max_parallel_episodes

        # If max_workers is 1, execute sequentially (for backward compatibility)
        if max_workers == 1:
            self.logger.info("Sequential execution mode (max_parallel_episodes=1)")
            results = []
            for i, task in enumerate(tasks):
                task_name = task_names[i] if task_names and i < len(task_names) else f"task_{i+1}"
                self.logger.info(f"Executing {task_name}...")
                start_time = time.time()
                try:
                    result = task()
                    elapsed = time.time() - start_time
                    self.logger.info(f"✅ {task_name} completed in {elapsed:.2f}s")
                    results.append((result, None))
                except Exception as e:
                    elapsed = time.time() - start_time
                    self.logger.error(f"❌ {task_name} failed after {elapsed:.2f}s: {e}")
                    results.append((None, e))
            return results

        # Parallel execution
        self.logger.info(f"Parallel execution mode: {len(tasks)} tasks with max {max_workers} workers")
        start_time = time.time()
        results = [None] * len(tasks)
        completed_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_index = {}
            for i, task in enumerate(tasks):
                task_name = task_names[i] if task_names and i < len(task_names) else f"task_{i+1}"
                future = executor.submit(task)
                future_to_index[future] = (i, task_name)

            # Process completed tasks
            for future in as_completed(future_to_index):
                index, task_name = future_to_index[future]
                completed_count += 1
                try:
                    result = future.result()
                    elapsed = time.time() - start_time
                    self.logger.info(
                        f"✅ {task_name} completed ({completed_count}/{len(tasks)}) in {elapsed:.2f}s"
                    )
                    results[index] = (result, None)
                except Exception as e:
                    elapsed = time.time() - start_time
                    self.logger.error(
                        f"❌ {task_name} failed ({completed_count}/{len(tasks)}) after {elapsed:.2f}s: {e}"
                    )
                    results[index] = (None, e)

        total_elapsed = time.time() - start_time
        successful = sum(1 for r in results if r and r[1] is None)
        self.logger.info(
            f"Batch complete: {successful}/{len(tasks)} successful in {total_elapsed:.2f}s "
            f"(parallelism: {max_workers} workers)"
        )

        return results

    def execute_api_calls(
        self,
        tasks: list[Callable],
        task_names: Optional[list[str]] = None,
        episode_id: Optional[str] = None,
        max_workers: Optional[int] = None,
    ) -> list[tuple[Any, Optional[Exception]]]:
        """
        Execute a batch of API calls in parallel with controlled concurrency.

        This is for intra-episode parallelism (e.g., multiple TTS calls, multiple image generations).

        Args:
            tasks: List of callable tasks to execute (each should respect RateLimiter internally)
            task_names: Optional list of task names for logging
            episode_id: Optional episode ID for logging context
            max_workers: Maximum number of parallel workers (defaults to max_parallel_api_calls)

        Returns:
            List of tuples: (result, exception) for each task
        """
        if not tasks:
            return []

        max_workers = max_workers or self.max_parallel_api_calls

        # If max_workers is 1, execute sequentially
        if max_workers == 1:
            results = []
            for i, task in enumerate(tasks):
                task_name = task_names[i] if task_names and i < len(task_names) else f"api_call_{i+1}"
                log_prefix = f"[{episode_id}] " if episode_id else ""
                try:
                    result = task()
                    results.append((result, None))
                except Exception as e:
                    self.logger.error(f"{log_prefix}❌ {task_name} failed: {e}")
                    results.append((None, e))
            return results

        # Parallel execution
        log_prefix = f"[{episode_id}] " if episode_id else ""
        self.logger.debug(
            f"{log_prefix}Parallel API calls: {len(tasks)} tasks with max {max_workers} workers"
        )
        start_time = time.time()
        results = [None] * len(tasks)
        completed_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_index = {}
            for i, task in enumerate(tasks):
                task_name = task_names[i] if task_names and i < len(task_names) else f"api_call_{i+1}"
                future = executor.submit(task)
                future_to_index[future] = (i, task_name)

            # Process completed tasks
            for future in as_completed(future_to_index):
                index, task_name = future_to_index[future]
                completed_count += 1
                try:
                    result = future.result()
                    elapsed = time.time() - start_time
                    self.logger.debug(
                        f"{log_prefix}✅ {task_name} completed ({completed_count}/{len(tasks)}) in {elapsed:.2f}s"
                    )
                    results[index] = (result, None)
                except Exception as e:
                    elapsed = time.time() - start_time
                    self.logger.warning(
                        f"{log_prefix}❌ {task_name} failed ({completed_count}/{len(tasks)}) after {elapsed:.2f}s: {e}"
                    )
                    results[index] = (None, e)

        total_elapsed = time.time() - start_time
        successful = sum(1 for r in results if r and r[1] is None)
        self.logger.debug(
            f"{log_prefix}API batch complete: {successful}/{len(tasks)} successful in {total_elapsed:.2f}s"
        )

        return results

