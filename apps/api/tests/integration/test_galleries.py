from httpx import AsyncClient
from sqlalchemy import select

from utag_api.database import new_id
from utag_api.models import Gallery, GalleryItem, MediaAsset, User


async def test_gallery_detail_requires_access_and_returns_ordered_images(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    gallery_id = new_id()
    asset_id = new_id()
    async with session_factory() as session:
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert administrator is not None
        session.add(
            MediaAsset(
                id=asset_id,
                owner_id=administrator.id,
                storage_key=f"galleries/{asset_id}.jpg",
                original_filename="annual-forum.jpg",
                content_type="image/jpeg",
                byte_size=128,
                sha256="a" * 64,
                status="ready",
                is_private=False,
                alt_text="Members at the annual forum",
                metadata_json={},
            )
        )
        session.add(
            Gallery(
                id=gallery_id,
                slug="annual-forum",
                title="Annual forum",
                description="<p>Forum photographs.</p>",
                status="draft",
            )
        )
        session.add(
            GalleryItem(
                id=new_id(),
                gallery_id=gallery_id,
                media_asset_id=asset_id,
                position=0,
                caption="Opening session",
                allow_download=False,
            )
        )
        await session.commit()

    assert (await client.get(f"/api/v1/galleries/{gallery_id}")).status_code == 401

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    assert login.status_code == 200

    response = await client.get(f"/api/v1/galleries/{gallery_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Annual forum"
    assert response.json()["items"] == [
        {
            "id": response.json()["items"][0]["id"],
            "media_asset_id": str(asset_id),
            "media_name": "annual-forum.jpg",
            "position": 0,
            "caption": "Opening session",
            "allow_download": False,
        }
    ]

    missing = await client.get(f"/api/v1/galleries/{new_id()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "gallery_not_found"
