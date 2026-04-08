"""Simple task queue with background workers - no Celery/Redis needed."""
import queue
import threading
import time
from typing import Callable, Any, Dict
from logging_config import logger


class Task:
    """Represents a task to be executed."""

    def __init__(self, task_id: str, func: Callable, args: tuple = (), kwargs: dict = None):
        """Initialize a task.

        Args:
            task_id: Unique task identifier
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments
        """
        self.task_id = task_id
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.result = None
        self.status = "pending"  # pending, running, completed, failed
        self.error = None

    def execute(self):
        """Execute the task."""
        try:
            self.status = "running"
            logger.debug(f"[TASK] {self.task_id} executing...")
            self.result = self.func(*self.args, **self.kwargs)
            self.status = "completed"
            logger.info(f"[TASK] {self.task_id} completed")
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            logger.error(f"[TASK] {self.task_id} failed: {e}")


class TaskQueue:
    """Lightweight task queue with background workers."""

    def __init__(self, num_workers: int = 1, batch_delay: int = 2, respect_api_quota: bool = True):
        """Initialize the task queue.

        Args:
            num_workers: Number of worker threads
            batch_delay: Minimum delay between task executions (seconds)
            respect_api_quota: If True, adjusts delay to respect API rate limit (5 calls/min)
        """
        self.num_workers = num_workers
        self.batch_delay = batch_delay
        self.respect_api_quota = respect_api_quota
        self.queue = queue.Queue()
        self.tasks: Dict[str, Task] = {}
        self.workers = []
        self.running = False

    def start(self):
        """Start the worker threads."""
        if self.running:
            logger.warning("Task queue already running")
            return

        self.running = True
        logger.info(f"Starting task queue with {self.num_workers} worker(s)")

        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"TaskWorker-{i+1}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

    def stop(self):
        """Stop the worker threads."""
        self.running = False
        logger.info("Stopping task queue")

    def submit(self, task_id: str, func: Callable, args: tuple = (), kwargs: dict = None) -> Task:
        """Submit a task to the queue.

        Args:
            task_id: Unique task identifier
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Task object
        """
        task = Task(task_id, func, args, kwargs)
        self.tasks[task_id] = task
        self.queue.put(task)
        logger.debug(f"[TASK] {task_id} submitted (queue size: {self.queue.qsize()})")
        return task

    def get_task(self, task_id: str) -> Task:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def get_queue_size(self) -> int:
        """Get the current queue size."""
        return self.queue.qsize()

    def _calculate_adaptive_delay(self) -> float:
        """Calculate adaptive delay based on API quota remaining.

        Returns:
            Delay in seconds (min batch_delay, max 12s to respect 5 calls/min limit)
        """
        if not self.respect_api_quota:
            return self.batch_delay

        try:
            from optimization import get_call_counter
            counter = get_call_counter()
            remaining = counter.get_remaining_quota()

            # If quota exhausted, wait longer (up to 12s = 60/5)
            if remaining <= 0:
                return 12  # Wait ~12s to allow quota to regenerate
            elif remaining == 1:
                return 10  # Almost exhausted, be conservative
            elif remaining == 2:
                return 8
            else:
                # Quota available, use minimal delay
                return max(self.batch_delay, 2)
        except Exception as e:
            logger.debug(f"Error calculating adaptive delay: {e}")
            return self.batch_delay

    def _worker_loop(self):
        """Main worker loop."""
        while self.running:
            try:
                # Get task with timeout
                task = self.queue.get(timeout=1)

                # Execute task
                task.execute()

                # Adaptive delay between tasks (respects API quota)
                delay = self._calculate_adaptive_delay()
                if delay > 0:
                    logger.debug(f"Worker sleeping {delay}s (respecting API quota)...")
                    time.sleep(delay)

                self.queue.task_done()

            except queue.Empty:
                # No task, continue waiting
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")


# Global task queue instance with thread safety
_task_queue = None
_queue_lock = threading.Lock()


def get_task_queue(num_workers: int = 1, batch_delay: int = 2) -> TaskQueue:
    """Get or create the global task queue (thread-safe)."""
    global _task_queue

    if _task_queue is None:
        with _queue_lock:
            if _task_queue is None:  # Double-check locking
                _task_queue = TaskQueue(num_workers=num_workers, batch_delay=batch_delay)
                _task_queue.start()

    return _task_queue
