"""Simple task queue with background workers - no Celery/Redis needed."""
import queue
import threading
import time
from typing import Callable, Any, Dict
from logging_config import logger


class Task:
    """Représente une tâche à exécuter."""

    def __init__(self, task_id: str, func: Callable, args: tuple = (), kwargs: dict = None):
        """Initialiser une tâche.

        Args:
            task_id: Identifiant unique de la tâche
            func: Fonction à exécuter
            args: Arguments positionnels
            kwargs: Arguments nommés
        """
        self.task_id = task_id
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.result = None
        self.status = "pending"  # pending, running, completed, failed
        self.error = None

    def execute(self):
        """Exécuter la tâche."""
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
    """Queue de tâches légère avec workers."""

    def __init__(self, num_workers: int = 1, batch_delay: int = 2):
        """Initialiser la queue.

        Args:
            num_workers: Nombre de workers
            batch_delay: Délai entre traitements (secondes)
        """
        self.num_workers = num_workers
        self.batch_delay = batch_delay
        self.queue = queue.Queue()
        self.tasks: Dict[str, Task] = {}
        self.workers = []
        self.running = False

    def start(self):
        """Démarrer les workers."""
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
        """Arrêter les workers."""
        self.running = False
        logger.info("Stopping task queue")

    def submit(self, task_id: str, func: Callable, args: tuple = (), kwargs: dict = None) -> Task:
        """Soumettre une tâche.

        Args:
            task_id: Identifiant unique
            func: Fonction à exécuter
            args: Arguments
            kwargs: Kwargs

        Returns:
            Task object
        """
        task = Task(task_id, func, args, kwargs)
        self.tasks[task_id] = task
        self.queue.put(task)
        logger.debug(f"[TASK] {task_id} submitted (queue size: {self.queue.qsize()})")
        return task

    def get_task(self, task_id: str) -> Task:
        """Récupérer une tâche par ID."""
        return self.tasks.get(task_id)

    def get_queue_size(self) -> int:
        """Taille actuelle de la queue."""
        return self.queue.qsize()

    def _worker_loop(self):
        """Boucle principale du worker."""
        while self.running:
            try:
                # Récupérer tâche avec timeout
                task = self.queue.get(timeout=1)

                # Exécuter
                task.execute()

                # Délai entre tâches
                if self.batch_delay > 0:
                    logger.debug(f"Worker sleeping {self.batch_delay}s...")
                    time.sleep(self.batch_delay)

                self.queue.task_done()

            except queue.Empty:
                # Pas de tâche, continuer
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")


# Instance globale de queue
_task_queue = None


def get_task_queue(num_workers: int = 1, batch_delay: int = 2) -> TaskQueue:
    """Obtenir ou créer la queue globale."""
    global _task_queue

    if _task_queue is None:
        _task_queue = TaskQueue(num_workers=num_workers, batch_delay=batch_delay)
        _task_queue.start()

    return _task_queue


def submit_task(task_id: str, func: Callable, args: tuple = (), kwargs: dict = None) -> Task:
    """Soumettre une tâche à la queue globale."""
    queue_instance = get_task_queue()
    return queue_instance.submit(task_id, func, args, kwargs)
