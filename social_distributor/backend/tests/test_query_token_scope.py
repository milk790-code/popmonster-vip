"""The operator token may travel in a URL only where a header is impossible.

EventSource cannot set headers, so the SSE stream has no alternative. Every
other endpoint does -- and a token in a query string is written into every
access log it passes through. This one token exchanges for the whole fleet's
Page credentials, so the set of URLs it may legally appear in should be as
small as the constraint requires and no larger.
"""
from app.extensions import db
from app.models import User
from app.utils.auth import issue_operator_token


def _seed(app):
    with app.app_context():
        user = User(email="qt@example.test", display_name="q")
        db.session.add(user)
        db.session.commit()
        return user.id


def test_a_url_borne_token_does_not_authenticate_an_ordinary_endpoint(client, app):
    user_id = _seed(app)
    token = issue_operator_token(user_id)

    resp = client.get(f"/api/accounts?op_token={token}")
    assert resp.status_code == 401


def test_the_same_token_still_works_in_the_header(client, app):
    user_id = _seed(app)
    token = issue_operator_token(user_id)

    resp = client.get("/api/accounts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_the_sse_stream_still_accepts_it_because_it_has_no_choice(client, app):
    """If this ever starts failing, the dashboard's live status board goes
    dark -- that is the whole reason the query-string path exists."""
    user_id = _seed(app)
    token = issue_operator_token(user_id)

    resp = client.get(
        f"/api/events/stream?user_id={user_id}&op_token={token}",
        headers={"Accept": "text/event-stream"},
    )
    assert resp.status_code != 401
    resp.close()
