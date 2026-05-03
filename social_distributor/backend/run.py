"""Development entry-point.

Run with `flask --app run.py run` or `python run.py`. In production use
`gunicorn run:app`.
"""
from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
