"""Evento CLI seguro en stderr, independiente de la configuración global de logs."""

import json
import logging
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4


class CliObservation:
    def __init__(self):
        self.request_id = uuid4().hex
        self.started_at = datetime.now(UTC).isoformat()
        self.started = monotonic()
        self.exit_code, self.outcome, self.error_code = 2, "error", "internal_error"

    def emit(self):
        event = {
            "event": "query_completed",
            "channel": "cli",
            "request_id": self.request_id,
            "started_at_utc": self.started_at,
            "duration_ms": round(max(0, (monotonic() - self.started) * 1000), 3),
            "exit_code": self.exit_code,
            "outcome": self.outcome,
            "error_code": self.error_code,
        }
        # Logger aislado: un único evento aun con logging global ya configurado.
        logger = logging.Logger("nafta2go.query.telemetry", level=logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        try:
            logger.info(json.dumps(event))
        finally:
            handler.close()
