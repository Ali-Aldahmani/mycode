"""initial schema: users, challenges, submissions, progress

Revision ID: 0001
Revises:
Create Date: 2026-10-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "challenges",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(96), nullable=False),
        sa.Column("order", sa.Integer, nullable=False),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("method", sa.String(96), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("language", sa.String(32), nullable=False),
        sa.Column("library", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("task", sa.Text, nullable=False),
        sa.Column("inputs", JSONType, nullable=False),
        sa.Column("target", JSONType, nullable=False),
        sa.Column("starter_code", sa.Text, nullable=False),
        sa.Column("hint_1", sa.Text, nullable=False),
        sa.Column("hint_2", sa.Text, nullable=False),
        sa.Column("example", JSONType, nullable=False),
        sa.Column("reference_solution", sa.Text, nullable=False),
        sa.Column("why", sa.Text, nullable=False),
        sa.Column("docs_url", sa.String(300), nullable=False),
        sa.Column("checker_type", sa.String(48), nullable=False),
        sa.Column("checker_options", JSONType, nullable=False),
        sa.Column("visual_type", sa.String(48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_challenges_slug", "challenges", ["slug"], unique=True)
    op.create_index("ix_challenges_order", "challenges", ["order"], unique=True)

    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("challenge_id", sa.Integer, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("score", sa.Integer, nullable=True),
        sa.Column("hints_used", sa.JSON, nullable=False),
        sa.Column("used_example", sa.Boolean, nullable=False),
        sa.Column("used_hint_1", sa.Boolean, nullable=False),
        sa.Column("used_hint_2", sa.Boolean, nullable=False),
        sa.Column("attempt_number", sa.Integer, nullable=True),
        sa.Column("round", sa.Integer, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("runtime_ms", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"])
    op.create_index("ix_submissions_challenge_id", "submissions", ["challenge_id"])

    op.create_table(
        "progress",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("challenge_id", sa.Integer, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("best_score", sa.Integer, nullable=True),
        sa.Column("solved", sa.Boolean, nullable=False),
        sa.Column("unlocked", sa.Boolean, nullable=False),
        sa.Column("help_used", sa.JSON, nullable=False),
        sa.Column("solved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "challenge_id", name="uq_progress_user_challenge"),
    )
    op.create_index("ix_progress_user_id", "progress", ["user_id"])
    op.create_index("ix_progress_challenge_id", "progress", ["challenge_id"])


def downgrade() -> None:
    op.drop_table("progress")
    op.drop_table("submissions")
    op.drop_table("challenges")
    op.drop_table("users")
