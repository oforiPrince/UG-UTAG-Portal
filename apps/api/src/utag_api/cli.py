import argparse
import asyncio

from sqlalchemy import select

from utag_api.config import get_settings
from utag_api.database import SessionFactory, new_id
from utag_api.demo_data import seed_demo_data
from utag_api.models import Role, User, UserRole
from utag_api.security import hash_password, normalize_email
from utag_api.seed_data import seed_portal_defaults
from utag_api.services.identity import seed_authorization, strong_password_errors
from utag_api.services.system_chat_groups import (
    SystemChatSyncResult,
    sync_system_chat_groups,
)


async def reconcile_chat_groups() -> SystemChatSyncResult:
    async with SessionFactory() as db:
        users = (await db.scalars(select(User))).all()
        administrator_id = await db.scalar(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(User.status == "active", Role.key == "administrator")
            .limit(1)
        )
        result = await sync_system_chat_groups(
            db,
            users,
            created_by_id=administrator_id,
        )
        await db.commit()
        return result


async def seed() -> None:
    settings = get_settings()
    async with SessionFactory() as db:
        await seed_authorization(db)
        await seed_portal_defaults(db)

        if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
            password = settings.bootstrap_admin_password.get_secret_value()
            errors = strong_password_errors(password)
            if errors:
                raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD is too weak: " + "; ".join(errors))
            email = normalize_email(settings.bootstrap_admin_email)
            user = await db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    id=new_id(),
                    email=email,
                    password_hash=hash_password(password),
                    status="active",
                    title="",
                    other_name="Portal",
                    surname="Administrator",
                    email_verified=True,
                )
                db.add(user)
                await db.flush()
            administrator = await db.scalar(select(Role).where(Role.key == "administrator"))
            if administrator and not await db.scalar(
                select(UserRole.id).where(
                    UserRole.user_id == user.id, UserRole.role_id == administrator.id
                )
            ):
                from datetime import UTC, datetime

                db.add(
                    UserRole(
                        id=new_id(),
                        user_id=user.id,
                        role_id=administrator.id,
                        assigned_by_id=user.id,
                        assigned_at=datetime.now(UTC),
                    )
                )
            await db.commit()
    await reconcile_chat_groups()


async def seed_demo() -> None:
    settings = get_settings()
    if settings.environment not in {"development", "test"}:
        raise RuntimeError("Demo accounts can only be seeded in development or test")
    if settings.demo_data_password is None:
        raise RuntimeError("Set DEMO_DATA_PASSWORD before running seed-demo")
    password = settings.demo_data_password.get_secret_value()
    errors = strong_password_errors(password)
    if errors:
        raise RuntimeError("DEMO_DATA_PASSWORD is too weak: " + "; ".join(errors))
    async with SessionFactory() as db:
        result = await seed_demo_data(db, password)
    await reconcile_chat_groups()
    print(
        f"Seeded {result.accounts} demo accounts and "
        f"{result.executive_appointments} executive appointments"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="UG UTAG API management commands")
    parser.add_argument(
        "command",
        choices=["seed", "seed-demo", "sync-chat-groups", "backfill-media-variants"],
    )
    args = parser.parse_args()
    if args.command == "seed":
        asyncio.run(seed())
    if args.command == "seed-demo":
        asyncio.run(seed_demo())
    if args.command == "sync-chat-groups":
        result = asyncio.run(reconcile_chat_groups())
        print(
            f"System chat groups synchronized: {result.groups_created} created, "
            f"{result.memberships_added} memberships added, "
            f"{result.memberships_removed} memberships removed"
        )
    if args.command == "backfill-media-variants":
        from utag_api.models import MediaAsset
        from utag_api.worker.tasks import ensure_media_variants

        async def collect_ids() -> list[str]:
            async with SessionFactory() as db:
                rows = (
                    await db.scalars(
                        select(MediaAsset.id).where(
                            MediaAsset.status == "ready",
                            MediaAsset.content_type.startswith("image/"),
                        )
                    )
                ).all()
                return [str(row) for row in rows]

        ids = asyncio.run(collect_ids())
        for asset_id in ids:
            ensure_media_variants(asset_id)
        print(f"Ensured display variants for {len(ids)} ready image assets")


if __name__ == "__main__":
    main()
