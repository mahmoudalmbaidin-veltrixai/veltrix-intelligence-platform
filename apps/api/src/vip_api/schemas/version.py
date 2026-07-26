"""Public build/version schema."""

from pydantic import BaseModel


class VersionResponse(BaseModel):
    name: str
    version: str
    environment: str
    commit_sha: str | None = None
    build_timestamp: str | None = None
