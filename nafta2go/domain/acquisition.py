"""Fallo de adquisición con metadatos seguros para el ciclo de ingesta."""


class AcquisitionFailed(RuntimeError):
    def __init__(self, attempts: int, error_type: str):
        self.attempts = attempts
        super().__init__(f"Adquisición fallida tras {attempts} intentos ({error_type})")
