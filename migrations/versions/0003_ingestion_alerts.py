"""Conservar detección, seguimiento y resolución de alertas de ingesta."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_alerts",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("ingestion_runs.id")),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("ingestion_alerts")
