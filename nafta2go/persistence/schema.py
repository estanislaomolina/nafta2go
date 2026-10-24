"""Tablas de la base. La migración 0001 debe coincidir con estas definiciones."""

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

ingestion_runs = Table(
    "ingestion_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source", String(20), nullable=False),
    Column("status", String(20), nullable=False),
    Column("started_at", DateTime, nullable=False),
    Column("finished_at", DateTime),
    Column("rules_version", String(40)),
    Column("report", JSON),
    Column("error", Text),
)

raw_captures = Table(
    "raw_captures",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", Integer, ForeignKey("ingestion_runs.id"), nullable=False, unique=True),
    Column("url", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("stored_path", Text, nullable=False),
    Column("fetched_at", DateTime, nullable=False),
    Column("source_last_modified", String(40)),
)

station_prices = Table(
    "station_prices",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", Integer, ForeignKey("ingestion_runs.id"), nullable=False),
    Column("source_row", Integer, nullable=False),
    Column("station_id", Integer, nullable=False),
    Column("company", Text, nullable=False),
    Column("brand", Text, nullable=False),
    Column("address", Text, nullable=False),
    Column("product_id", Integer, nullable=False),
    Column("fuel_type", String(20), nullable=False),
    Column("schedule_id", Integer, nullable=False),
    Column("price", Numeric(12, 3), nullable=False),
    Column("valid_from", DateTime, nullable=False),
    Column("lat", Float),
    Column("lon", Float),
    Column("valid_from_raw", String(40), nullable=False),
    Column("price_raw", String(40), nullable=False),
    Column("alerts", Text, nullable=False, server_default=""),
    UniqueConstraint(
        "run_id",
        "station_id",
        "product_id",
        "schedule_id",
        "valid_from",
        name="uq_station_prices_run_key",
    ),
    Index("ix_station_prices_run_fuel", "run_id", "fuel_type"),
)

rejected_rows = Table(
    "rejected_rows",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", Integer, ForeignKey("ingestion_runs.id"), nullable=False),
    Column("source_row", Integer, nullable=False),
    Column("reason", String(60), nullable=False),
    Column("raw", JSON, nullable=False),
    Index("ix_rejected_rows_run", "run_id"),
)

recommendations = Table(
    "recommendations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("created_at", DateTime, nullable=False),
    Column("data_run_id", Integer, ForeignKey("ingestion_runs.id"), nullable=False),
    Column("engine_version", String(40), nullable=False),
    Column("routing_provider", String(40), nullable=False),
    Column("request", JSON, nullable=False),
    Column("result", JSON, nullable=False),
)
