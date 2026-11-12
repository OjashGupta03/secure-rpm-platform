"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-24

Bootstraps the full initial schema from the SQLAlchemy model metadata directly, rather
than hand-written create_table calls — a deliberate shortcut for a prototype's very
first migration. Every subsequent migration should be a normal incremental Alembic
revision (autogenerate against a running DB) once this baseline is applied.
"""
from alembic import op

from app.db.base import Base
from app.models import *  # noqa: F401,F403 — ensures every model is registered

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
