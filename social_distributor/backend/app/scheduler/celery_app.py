"""Celery application factory.

The Celery worker shares the Flask app context so tasks can use SQLAlchemy
sessions, models, and config. ``advance_cron_targets`` is run on a 60-second
beat: it materialises the next concrete dispatch for any cron-recurring
targets.
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from ..config import config


def make_celery(flask_app=None) -> Celery:
    app = Celery(
        "social_distributor",
        broker=config.celery_broker_url,
        backend=config.celery_result_backend,
        include=["app.scheduler.tasks"],
    )
    app.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_time_limit=60 * 30,
        task_soft_time_limit=60 * 25,
        worker_prefetch_multiplier=1,
        timezone="UTC",
        enable_utc=True,
        beat_schedule={
            "advance-cron-targets": {
                "task": "app.scheduler.tasks.advance_cron_targets",
                "schedule": crontab(minute="*"),
            },
            "sweep-due-targets": {
                "task": "app.scheduler.tasks.sweep_due_targets",
                "schedule": crontab(minute="*"),
            },
            "refresh-oauth-tokens": {
                "task": "app.scheduler.tasks.refresh_oauth_tokens",
                "schedule": crontab(minute=0, hour="*/6"),
            },
            "ingest-insights": {
                "task": "app.scheduler.tasks.ingest_insights",
                "schedule": crontab(minute=15, hour="*"),
            },
            "permission-health-sweep": {
                "task": "app.scheduler.tasks.permission_health_sweep",
                "schedule": crontab(minute=30, hour=4),
            },
            "expire-overdue-transfers": {
                "task": "app.scheduler.tasks.expire_overdue_transfers",
                "schedule": crontab(minute=0, hour="*/3"),
            },
            # C2: weekly A/B engine winner backtest. Runs Sunday 03:00 UTC,
            # writes AccountGroup.preferred_variant_engine for groups with
            # statistically meaningful samples.
            "ab-variant-backtest": {
                "task": "app.scheduler.tasks.ab_variant_backtest",
                "schedule": crontab(minute=0, hour=3, day_of_week="sun"),
            },
            # C5: weekly actionable insights digest email. Monday 09:00 UTC
            # so it lands at the start of the work-week without being late.
            "weekly-insights-digest": {
                "task": "app.scheduler.tasks.weekly_insights_digest",
                "schedule": crontab(minute=0, hour=9, day_of_week="mon"),
            },
            # Instruction 2: daily token expiry scan + FB liveness probe.
            # Runs 08:00 UTC every day — early enough to catch 7-day warnings
            # before the work day starts in Asia/Taipei (UTC+8 = 16:00).
            "sweep-expiring-tokens": {
                "task": "app.scheduler.tasks.sweep_expiring_tokens",
                "schedule": crontab(minute=0, hour=8),
            },
        },
    )

    if flask_app is not None:
        class ContextTask(app.Task):
            def __call__(self, *args, **kwargs):
                with flask_app.app_context():
                    return self.run(*args, **kwargs)

        app.Task = ContextTask
    return app


celery_app = make_celery()
