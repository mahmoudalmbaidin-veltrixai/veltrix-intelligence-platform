"""Opaque token generation and domain-separated hashing."""

from dataclasses import dataclass
from hashlib import sha256
from secrets import token_urlsafe


def generate_token() -> str:
    return token_urlsafe(32)


def hash_token(token: str, purpose: str) -> str:
    return sha256(f"vip:{purpose}:".encode() + token.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class SessionTokens:
    access: str
    refresh: str
    csrf: str


def generate_session_tokens() -> SessionTokens:
    return SessionTokens(access=generate_token(), refresh=generate_token(), csrf=generate_token())
