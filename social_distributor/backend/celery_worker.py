"""Celery worker entry-point.

Run with `celery -A celery_worker.celery worker -B -l info`. ``-B`` runs the
beat scheduler in-process, which is fine for single-deployment installations;
in HA setups, run the beat schedule in its own container instead.
"""
from app import create_app
from app.scheduler.celery_app import make_celery
from app.utils.telemetry import init_telemetry

init_telemetry(component="worker")
flask_app = create_app()
celery = make_celery(flask_app)
