from sqlalchemy import select

from utag_api.models import User
from utag_api.services.query import apply_sort, paginate_sequence


def test_paginate_sequence_slices_items_and_counts_pages() -> None:
    result = paginate_sequence(list(range(16)), page=2, page_size=15)

    assert result.items == [15]
    assert result.page == 2
    assert result.page_size == 15
    assert result.total == 16
    assert result.pages == 2


def test_apply_sort_uses_only_allowlisted_columns() -> None:
    sorted_statement = apply_sort(
        select(User),
        sort_by="email",
        sort_dir="desc",
        allowed={"email": User.email},
        default=(User.surname.asc(),),
    )
    rejected_statement = apply_sort(
        select(User),
        sort_by="email; drop table users",
        sort_dir="desc",
        allowed={"email": User.email},
        default=(User.surname.asc(),),
    )

    assert "ORDER BY users.email DESC" in str(sorted_statement)
    assert "ORDER BY users.surname ASC" in str(rejected_statement)
    assert "drop table" not in str(rejected_statement).lower()
