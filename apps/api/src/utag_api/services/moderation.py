from utag_api.errors import ApiError

PUBLICATION_STATES = {"scheduled", "published", "archived", "withdrawn"}


def ensure_publish_permission(permissions: set[str], status: str | None) -> None:
    if status in PUBLICATION_STATES and "content.publish" not in permissions:
        raise ApiError(403, "permission_denied", "Publishing permission is required")
