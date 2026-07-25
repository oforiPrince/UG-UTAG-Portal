from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.errors import ApiError
from utag_api.models import (
    MediaAsset,
    Permission,
    Role,
    RolePermission,
    UserPermissionGrant,
    UserRole,
)
from utag_api.permissions import PERMISSIONS, ROLE_GRANTS


@dataclass(slots=True)
class UserAccess:
    roles: set[str] = field(default_factory=set)
    role_permissions: set[str] = field(default_factory=set)
    extra_permissions: set[str] = field(default_factory=set)

    @property
    def effective_permissions(self) -> set[str]:
        return self.role_permissions | self.extra_permissions


async def load_user_access_map(db: AsyncSession, user_ids: list[UUID]) -> dict[UUID, UserAccess]:
    unique_user_ids = list(dict.fromkeys(user_ids))
    result = {user_id: UserAccess() for user_id in unique_user_ids}
    if not unique_user_ids:
        return result

    role_grants = await db.execute(
        select(UserRole.user_id, Role.key, Permission.key)
        .join(Role, Role.id == UserRole.role_id)
        .outerjoin(RolePermission, RolePermission.role_id == Role.id)
        .outerjoin(Permission, Permission.id == RolePermission.permission_id)
        .where(UserRole.user_id.in_(unique_user_ids))
    )
    for user_id, role_key, permission_key in role_grants:
        access = result[user_id]
        access.roles.add(role_key)
        if permission_key:
            access.role_permissions.add(permission_key)

    extra_grants = await db.execute(
        select(UserPermissionGrant.user_id, Permission.key)
        .join(Permission, Permission.id == UserPermissionGrant.permission_id)
        .where(UserPermissionGrant.user_id.in_(unique_user_ids))
    )
    for user_id, permission_key in extra_grants:
        result[user_id].extra_permissions.add(permission_key)
    return result


async def load_user_access(db: AsyncSession, user_id: UUID) -> UserAccess:
    return (await load_user_access_map(db, [user_id]))[user_id]


async def require_public_profile_image(db: AsyncSession, asset_id: UUID) -> MediaAsset:
    asset = await db.get(MediaAsset, asset_id)
    if (
        asset is None
        or asset.status != "ready"
        or asset.is_private
        or not asset.content_type.startswith("image/")
    ):
        raise ApiError(
            422,
            "profile_image_invalid",
            "Choose a ready public image for the profile photo",
        )
    return asset


async def seed_authorization(db: AsyncSession) -> None:
    permission_rows = {item.key: item for item in (await db.scalars(select(Permission))).all()}
    for definition in PERMISSIONS:
        row = permission_rows.get(definition.key)
        if row is None:
            row = Permission(key=definition.key, description=definition.description)
            db.add(row)
            permission_rows[definition.key] = row
        else:
            row.description = definition.description

    role_rows = {item.key: item for item in (await db.scalars(select(Role))).all()}
    for role_key in ROLE_GRANTS:
        role = role_rows.get(role_key)
        if role is None:
            role = Role(
                key=role_key,
                name=role_key.replace("_", " ").title(),
                description=f"Built-in {role_key} role",
                is_system=True,
            )
            db.add(role)
            role_rows[role_key] = role

    await db.flush()
    existing_grants = set(
        (await db.execute(select(RolePermission.role_id, RolePermission.permission_id))).all()
    )
    for role_key, grants in ROLE_GRANTS.items():
        role = role_rows[role_key]
        for permission_key in grants:
            permission = permission_rows[permission_key]
            pair = (role.id, permission.id)
            if pair not in existing_grants:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    await db.commit()


def strong_password_errors(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 8:
        errors.append("Use at least 8 characters")
    if not any(character.isupper() for character in password):
        errors.append("Add an uppercase letter")
    if not any(character.islower() for character in password):
        errors.append("Add a lowercase letter")
    if not any(character.isdigit() for character in password):
        errors.append("Add a number")
    return errors
