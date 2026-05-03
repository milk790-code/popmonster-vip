from .accounts import bp as accounts_bp
from .audit import bp as audit_bp
from .posts import bp as posts_bp
from .schedules import bp as schedules_bp

__all__ = ["accounts_bp", "audit_bp", "posts_bp", "schedules_bp"]
