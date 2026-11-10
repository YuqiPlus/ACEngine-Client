"""Error details and binary output helpers; no credentials are logged."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class AceError(RuntimeError):
    """Raised only when ``raise_for_errors=True``; inspect ``response`` to recover."""

    def __init__(self, response):
        self.response = response
        self.code = str(response.get("code", "500"))
        self.http_status = response.get("httpStatus")
        self.request_id = response.get("requestId") or response.get("meta", {}).get("requestId")
        self.task_id = response.get("meta", {}).get("taskId")
        self.idempotency_key = response.get("meta", {}).get("idempotencyKey")
        super().__init__("ACE {}: {}".format(self.code, response.get("message", "Request failed")))


@dataclass(frozen=True)
class BinaryResult:
    content: bytes
    content_type: str
    request_id: Optional[str] = None

    def save(self, path, *, overwrite=False):
        """Save only on explicit request. Existing files are protected by default."""
        target = Path(path)
        with target.open("wb" if overwrite else "xb") as output:
            output.write(self.content)
        return target
