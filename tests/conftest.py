"""Fixtures compartidas por los tests."""

import pytest

from nafta2go.persistence.database import create_db_engine, upgrade_to_head


@pytest.fixture
def database_url(tmp_path):
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def engine(database_url):
    upgrade_to_head(database_url)
    db = create_db_engine(database_url)
    yield db
    db.dispose()
