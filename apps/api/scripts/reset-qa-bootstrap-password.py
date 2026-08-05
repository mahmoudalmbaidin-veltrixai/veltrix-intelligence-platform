"""Recover only the fixed local QA bootstrap account after an interrupted seed."""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from vip_api.auth.models import User, normalize_username
from vip_api.auth.password import PasswordService
from vip_api.auth.sessions import revoke_all_user_sessions
from vip_api.core.config import get_settings
from vip_api.database.session import Database


async def reset(username: str, password: str) -> None:
    if username != "qa_platform_super_admin":
        raise SystemExit("This recovery helper is restricted to qa_platform_super_admin.")
    settings = get_settings()
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            user = await db.scalar(
                select(User).where(User.normalized_username == normalize_username(username))
            )
            if user is None:
                raise SystemExit("The QA bootstrap account does not exist.")
            user.password_hash = PasswordService(settings).hash_password(password)
            await revoke_all_user_sessions(db, user.id, "qa_seed_recovery")
            await db.commit()
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        raise SystemExit("A password is required on standard input.")
    asyncio.run(reset(args.username, password))


if __name__ == "__main__":
    main()
