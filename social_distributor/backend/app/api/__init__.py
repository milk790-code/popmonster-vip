from .accounts import bp as accounts_bp
from .audit import bp as audit_bp
from .events import bp as events_bp
from .groups import bp as groups_bp
from .hashtags import bp as hashtags_bp
from .insights import bp as insights_bp
from .permissions import bp as permissions_bp
from .posts import bp as posts_bp
from .rebroadcast import bp as rebroadcast_bp
from .schedules import bp as schedules_bp
from .transfers import bp as transfers_bp
from .uploads import bp as uploads_bp

__all__ = [
    "accounts_bp",
    "audit_bp",
    "events_bp",
    "groups_bp",
    "hashtags_bp",
    "insights_bp",
    "permissions_bp",
    "posts_bp",
    "rebroadcast_bp",
    "schedules_bp",
    "transfers_bp",
    "uploads_bp",
]
