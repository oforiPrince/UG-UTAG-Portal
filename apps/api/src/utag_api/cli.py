import argparse
import asyncio
from pathlib import Path

from sqlalchemy import select

from utag_api.config import get_settings
from utag_api.database import SessionFactory, new_id
from utag_api.demo_data import seed_demo_data
from utag_api.models import Role, User, UserRole
from utag_api.security import hash_password, normalize_email
from utag_api.seed_data import reconcile_organization, seed_portal_defaults
from utag_api.services.identity import seed_authorization, strong_password_errors
from utag_api.services.member_roster import parse_member_roster, sync_member_roster
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


async def reconcile_organization_data(
    *,
    apply: bool,
    prune_unlinked: bool,
) -> None:
    async with SessionFactory() as db:
        result = await reconcile_organization(db, prune_unlinked=prune_unlinked)
        if apply:
            await db.commit()
        else:
            await db.rollback()

    mode = "Applied" if apply else "Dry run"
    qualifier = "" if apply else "would be "
    if apply and prune_unlinked:
        pruned_count = result.legacy_units_pruned
        prune_label = "pruned"
    else:
        pruned_count = result.legacy_units_prunable
        prune_label = "eligible for pruning"
    print(
        f"{mode}: {result.canonical_created} canonical units {qualifier}created, "
        f"{result.canonical_updated} canonical units {qualifier}corrected, "
        f"{result.users_relinked} member affiliations {qualifier}relinked, "
        f"{result.announcement_audiences_relinked} announcement audiences "
        f"{qualifier}relinked, "
        f"{result.document_audiences_relinked} document audiences {qualifier}relinked, "
        f"{pruned_count} legacy units {prune_label}, "
        f"{result.legacy_units_retained} linked legacy units retained, "
        f"and {result.unresolved_users} member affiliations require manual review."
    )
    if result.unresolved_user_ids:
        sample = ", ".join(str(user_id) for user_id in result.unresolved_user_ids[:20])
        suffix = " …" if len(result.unresolved_user_ids) > 20 else ""
        print(f"Member IDs requiring review: {sample}{suffix}")
    if apply:
        await reconcile_chat_groups()


async def sync_member_roster_data(*, workbook: Path, apply: bool) -> None:
    if not workbook.is_file():
        raise FileNotFoundError(f"Roster workbook not found: {workbook}")
    rows = parse_member_roster(workbook)
    async with SessionFactory() as db:
        administrator_id = await db.scalar(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(User.status == "active", Role.key == "administrator")
            .limit(1)
        )
        result = await sync_member_roster(db, rows, created_by_id=administrator_id)
        if apply:
            await db.commit()
        else:
            await db.rollback()

    mode = "Applied" if apply else "Dry run"
    qualifier = "" if apply else "would be "
    print(
        f"{mode}: {result.units_created} organization units {qualifier}created, "
        f"{result.units_updated} organization units {qualifier}corrected, "
        f"{result.members_relinked} member affiliations {qualifier}relinked, "
        f"{result.titles_filled} titles {qualifier}filled, "
        f"{result.ranks_filled} ranks {qualifier}filled, "
        f"{result.staff_ids_filled} staff IDs {qualifier}filled, "
        f"{result.members_created} members {qualifier}created, "
        f"{result.members_unchanged} matched members already current, "
        f"{result.units_pruned} leftover units {qualifier}pruned, "
        f"{result.units_retained} leftover units retained, "
        f"{result.chat_groups_created} school/department chat groups "
        f"{qualifier}created, "
        f"{result.chat_memberships_added} chat memberships {qualifier}added, "
        f"{result.chat_memberships_removed} outdated chat memberships "
        f"{qualifier}closed, "
        f"{result.unmatched_existing_members} existing accounts were not in the roster, "
        f"{len(result.conflicts)} conflicts, "
        f"and {len(result.row_issues)} row issues."
    )
    if result.conflicts:
        print("Conflicts:")
        for item in result.conflicts[:50]:
            print(f"  {item}")
        if len(result.conflicts) > 50:
            print(f"  … {len(result.conflicts) - 50} more")
    if result.row_issues:
        print("Row issues:")
        for item in result.row_issues[:50]:
            print(f"  {item}")
        if len(result.row_issues) > 50:
            print(f"  … {len(result.row_issues) - 50} more")
    if result.retained_units:
        print("Retained leftover units:")
        for item in result.retained_units[:50]:
            print(f"  {item}")
        if len(result.retained_units) > 50:
            print(f"  … {len(result.retained_units) - 50} more")
    if apply:
        await reconcile_chat_groups()


def main() -> None:
    parser = argparse.ArgumentParser(description="UG UTAG API management commands")
    parser.add_argument(
        "command",
        choices=[
            "seed",
            "seed-demo",
            "sync-chat-groups",
            "reconcile-organization",
            "sync-member-roster",
            "backfill-media-variants",
        ],
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit roster or organization changes; otherwise they are rolled back as a dry run.",
    )
    parser.add_argument(
        "--prune-unlinked",
        action="store_true",
        help="Delete imported legacy organization rows only after all known linkages are removed.",
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        help="Path to the member roster CSV or XLSX used by sync-member-roster.",
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
    if args.command == "reconcile-organization":
        asyncio.run(
            reconcile_organization_data(
                apply=args.apply,
                prune_unlinked=args.prune_unlinked,
            )
        )
    if args.command == "sync-member-roster":
        if args.workbook is None:
            parser.error("sync-member-roster requires --workbook")
        asyncio.run(
            sync_member_roster_data(workbook=args.workbook, apply=args.apply)
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
