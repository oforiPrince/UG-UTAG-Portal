from datetime import UTC, datetime

from utag_api.database import new_id
from utag_api.models import Article, MediaAsset
from utag_api.routers.public import public_media_is_referenced


async def test_public_media_requires_a_published_reference(session_factory) -> None:  # type: ignore[no-untyped-def]
    published_asset_id = new_id()
    orphan_asset_id = new_id()
    async with session_factory() as session:
        for asset_id, filename in (
            (published_asset_id, "published.jpg"),
            (orphan_asset_id, "orphan.jpg"),
        ):
            session.add(
                MediaAsset(
                    id=asset_id,
                    storage_key=f"media/{asset_id}/{filename}",
                    original_filename=filename,
                    content_type="image/jpeg",
                    byte_size=10,
                    sha256=str(asset_id).replace("-", "").ljust(64, "0"),
                    status="ready",
                    is_private=False,
                    metadata_json={},
                )
            )
        session.add(
            Article(
                id=new_id(),
                slug="published-reference",
                title="Published reference",
                featured_media_id=published_asset_id,
                status="published",
                published_at=datetime.now(UTC),
            )
        )
        await session.commit()

        now = datetime.now(UTC)
        assert await public_media_is_referenced(session, published_asset_id, now)
        assert not await public_media_is_referenced(session, orphan_asset_id, now)
