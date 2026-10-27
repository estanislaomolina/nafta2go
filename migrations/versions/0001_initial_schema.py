"""Esquema inicial: ejecuciones de ingesta, capturas, precios, rechazos y recomendaciones.

Revision ID: 0001
Revises:
Create Date: 2026-10-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("rules_version", sa.String(40)),
        sa.Column("report", sa.JSON),
        sa.Column("error", sa.Text),
    )
    op.create_table(
        "raw_captures",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer,
            sa.ForeignKey("ingestion_runs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("stored_path", sa.Text, nullable=False),
        sa.Column("fetched_at", sa.DateTime, nullable=False),
        sa.Column("source_last_modified", sa.String(40)),
    )
    op.create_table(
        "station_prices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("ingestion_runs.id"), nullable=False),
        sa.Column("source_row", sa.Integer, nullable=False),
        sa.Column("station_id", sa.Integer, nullable=False),
        sa.Column("company", sa.Text, nullable=False),
        sa.Column("brand", sa.Text, nullable=False),
        sa.Column("address", sa.Text, nullable=False),
        sa.Column("product_id", sa.Integer, nullable=False),
        sa.Column("fuel_type", sa.String(20), nullable=False),
        sa.Column("schedule_id", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(12, 3), nullable=False),
        sa.Column("valid_from", sa.DateTime, nullable=False),
        sa.Column("lat", sa.Float),
        sa.Column("lon", sa.Float),
        sa.Column("valid_from_raw", sa.String(40), nullable=False),
        sa.Column("price_raw", sa.String(40), nullable=False),
        sa.Column("alerts", sa.Text, nullable=False, server_default=""),
        sa.UniqueConstraint(
            "run_id",
            "station_id",
            "product_id",
            "schedule_id",
            "valid_from",
            name="uq_station_prices_run_key",
        ),
    )
    op.create_index("ix_station_prices_run_fuel", "station_prices", ["run_id", "fuel_type"])
    op.create_table(
        "rejected_rows",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("ingestion_runs.id"), nullable=False),
        sa.Column("source_row", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(60), nullable=False),
        sa.Column("raw", sa.JSON, nullable=False),
    )
    op.create_index("ix_rejected_rows_run", "rejected_rows", ["run_id"])
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("data_run_id", sa.Integer, sa.ForeignKey("ingestion_runs.id"), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("routing_provider", sa.String(40), nullable=False),
        sa.Column("request", sa.JSON, nullable=False),
        sa.Column("result", sa.JSON, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("recommendations")
    op.drop_index("ix_rejected_rows_run", table_name="rejected_rows")
    op.drop_table("rejected_rows")
    op.drop_index("ix_station_prices_run_fuel", table_name="station_prices")
    op.drop_table("station_prices")
    op.drop_table("raw_captures")
    op.drop_table("ingestion_runs")
