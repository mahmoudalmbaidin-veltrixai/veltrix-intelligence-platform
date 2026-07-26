"""Argon2id password hashing and policy enforcement."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

from vip_api.core.config import Settings


class PasswordService:
    def __init__(self, settings: Settings) -> None:
        self.minimum = settings.PASSWORD_MIN_LENGTH
        self.maximum = settings.PASSWORD_MAX_LENGTH
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65_536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._dummy_hash = self._hasher.hash("vip-dummy-password-verification-value")

    def validate_password(self, password: str) -> None:
        if len(password) < self.minimum or len(password) > self.maximum:
            raise ValueError(
                f"Password must be between {self.minimum} and {self.maximum} characters."
            )

    def hash_password(self, password: str) -> str:
        self.validate_password(password)
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        if len(password) > self.maximum:
            return False
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def verify_unknown_user(self, password: str) -> None:
        self.verify_password(password, self._dummy_hash)

    def needs_rehash(self, password_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True
