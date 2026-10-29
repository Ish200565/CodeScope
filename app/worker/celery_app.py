from celery import Celery

from app.config import settings

celery_app = Celery("codescope", broker=settings.redis_url, include=["app.worker.tasks"])

celery_app.conf.update(
    task_acks_late=True,                 # ack after finishing, so crashed jobs return to the queue
    task_reject_on_worker_lost=True,     # requeue if the worker process dies mid-task
    worker_prefetch_multiplier=1,        # don't hoard jobs: fair for long tasks
    task_time_limit=600,                 # hard cap per task (seconds)
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 900},  # must exceed the longest task
    timezone="UTC",
)