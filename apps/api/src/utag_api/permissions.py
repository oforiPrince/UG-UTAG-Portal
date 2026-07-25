from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    key: str
    description: str


PERMISSIONS = (
    PermissionDefinition("dashboard.view", "View the authenticated dashboard"),
    PermissionDefinition("members.view", "View member records"),
    PermissionDefinition("members.manage", "Create and update members"),
    PermissionDefinition("members.create", "Create and import member accounts"),
    PermissionDefinition("members.update", "Update member profile records"),
    PermissionDefinition(
        "members.lifecycle", "Deactivate, reactivate, and archive member accounts"
    ),
    PermissionDefinition("members.credentials", "Reset member access and revoke member sessions"),
    PermissionDefinition("members.roles", "Assign privileged roles and manage administrators"),
    PermissionDefinition("members.permissions", "Grant and revoke individual member permissions"),
    PermissionDefinition("members.export", "Export member data"),
    PermissionDefinition("organization.manage", "Manage colleges, schools, and departments"),
    PermissionDefinition("executives.manage", "Manage executive appointments"),
    PermissionDefinition("content.view", "View editorial workspaces"),
    PermissionDefinition("content.edit", "Create and edit content"),
    PermissionDefinition("content.publish", "Publish and withdraw content"),
    PermissionDefinition("events.manage", "Manage events and registrations"),
    PermissionDefinition("documents.view", "View authorized documents"),
    PermissionDefinition("documents.manage", "Create and version documents"),
    PermissionDefinition("media.manage", "Upload and manage media"),
    PermissionDefinition("notifications.manage", "Send association notifications"),
    PermissionDefinition("chat.use", "Use direct and group messaging"),
    PermissionDefinition("adverts.manage", "Manage advertising inventory and orders"),
    PermissionDefinition("analytics.view", "View association analytics"),
    PermissionDefinition("audit.view", "View security and activity audit events"),
    PermissionDefinition("settings.manage", "Manage portal settings and feature flags"),
    PermissionDefinition("jobs.manage", "Manage imports, exports, and background jobs"),
)

ROLE_GRANTS: dict[str, set[str]] = {
    "member": {"dashboard.view", "documents.view", "chat.use"},
    "executive": {
        "dashboard.view",
        "members.view",
        "content.view",
        "documents.view",
        "chat.use",
        "analytics.view",
    },
    "editor": {
        "dashboard.view",
        "content.view",
        "content.edit",
        "media.manage",
        "documents.view",
        "chat.use",
    },
    "publisher": {
        "dashboard.view",
        "content.view",
        "content.edit",
        "content.publish",
        "events.manage",
        "media.manage",
        "documents.view",
        "notifications.manage",
        "chat.use",
    },
    "secretary": {
        "dashboard.view",
        "members.view",
        "members.manage",
        "members.create",
        "members.update",
        "members.lifecycle",
        "members.credentials",
        "members.export",
        "organization.manage",
        "executives.manage",
        "content.view",
        "content.edit",
        "content.publish",
        "events.manage",
        "documents.view",
        "documents.manage",
        "media.manage",
        "notifications.manage",
        "chat.use",
        "analytics.view",
        "jobs.manage",
    },
    "administrator": {permission.key for permission in PERMISSIONS},
}

NON_DELEGABLE_DIRECT_PERMISSIONS = frozenset({"members.roles", "members.permissions"})
