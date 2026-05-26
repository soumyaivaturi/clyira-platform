"""
Creates or resets the demo@clyira.ai account.

Usage:
    python scripts/create_demo_user.py [--password <pw>]

If the user already exists, it resets the password and unlocks the account.
If the user doesn't exist, it creates a demo company + user.

Set DATABASE_URL env var to target a specific database (defaults to local dev).
"""
import asyncio
import argparse
import re
import sys
import os

# Allow running from the repo root or from scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import bcrypt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DEMO_EMAIL = "demo@clyira.ai"
DEMO_FULL_NAME = "Demo User"
DEMO_COMPANY_NAME = "Clyira Demo"
DEMO_COMPANY_SLUG = "clyira-demo"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://clyira_admin:clyira_dev_2026@localhost:5432/clyira",
)


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _uuid() -> str:
    import uuid
    return str(uuid.uuid4())


async def run(password: str) -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # Check for existing user
        result = await db.execute(text("SELECT id, company_id FROM users WHERE email = :email"), {"email": DEMO_EMAIL})
        row = result.fetchone()

        if row:
            user_id, company_id = row
            await db.execute(
                text("""
                    UPDATE users SET
                        password_hash = :pw,
                        failed_login_attempts = 0,
                        locked_until = NULL,
                        force_password_change = FALSE
                    WHERE id = :id
                """),
                {"pw": _hash(password), "id": user_id},
            )
            await db.commit()
            print(f"[OK] Reset password for existing user: {DEMO_EMAIL}")
        else:
            # Check if demo company already exists
            r2 = await db.execute(text("SELECT id FROM companies WHERE slug = :slug"), {"slug": DEMO_COMPANY_SLUG})
            company_row = r2.fetchone()

            if company_row:
                company_id = company_row[0]
            else:
                company_id = _uuid()
                await db.execute(
                    text("""
                        INSERT INTO companies (id, name, slug, sub_sectors, agencies, markets, certifications, settings, onboarding_complete, subscription_tier, created_at, updated_at)
                        VALUES (:id, :name, :slug, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '{}'::jsonb, TRUE, 'professional', NOW(), NOW())
                    """),
                    {"id": company_id, "name": DEMO_COMPANY_NAME, "slug": DEMO_COMPANY_SLUG},
                )

            user_id = _uuid()
            await db.execute(
                text("""
                    INSERT INTO users (id, company_id, email, password_hash, full_name, role, is_active, failed_login_attempts, force_password_change, created_at, updated_at)
                    VALUES (:id, :company_id, :email, :pw, :name, 'admin', TRUE, 0, FALSE, NOW(), NOW())
                """),
                {
                    "id": user_id,
                    "company_id": company_id,
                    "email": DEMO_EMAIL,
                    "pw": _hash(password),
                    "name": DEMO_FULL_NAME,
                },
            )
            await db.commit()
            print(f"[OK] Created demo user: {DEMO_EMAIL} (company: {DEMO_COMPANY_NAME})")

    await engine.dispose()
    print(f"     Email:    {DEMO_EMAIL}")
    print(f"     Password: {password}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", default="ClyiraDemo1", help="Password for demo account")
    args = parser.parse_args()
    asyncio.run(run(args.password))
