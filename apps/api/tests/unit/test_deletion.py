import pytest
from sqlalchemy.exc import IntegrityError

from utag_api.errors import ApiError
from utag_api.services.deletion import commit_permanent_delete


class FailingSession:
    rolled_back = False

    async def commit(self) -> None:
        raise IntegrityError("DELETE", {}, RuntimeError("foreign key conflict"))

    async def rollback(self) -> None:
        self.rolled_back = True


async def test_commit_permanent_delete_translates_concurrent_fk_conflict() -> None:
    session = FailingSession()

    with pytest.raises(ApiError) as raised:
        await commit_permanent_delete(session, "organization unit")  # type: ignore[arg-type]

    assert session.rolled_back is True
    assert raised.value.status_code == 409
    assert raised.value.code == "organization_unit_delete_blocked"
    assert raised.value.details == {
        "dependencies": [{"label": "linked record", "count": 1}],
        "guidance": "Refresh the record and remove the newly linked dependency first",
    }
