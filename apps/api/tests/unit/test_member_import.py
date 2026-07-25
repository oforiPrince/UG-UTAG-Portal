import io

import pytest
from openpyxl import Workbook

from utag_api.errors import ApiError
from utag_api.services.member_import import parse_member_import


def test_csv_member_import_normalizes_legacy_headers_and_roles() -> None:
    rows = parse_member_import(
        "members.csv",
        b"Email Address,Staff ID,First Name,Last Name,Rank,Groups\n"
        b"ama@example.edu.gh,UG001,Ama,Mensah,Professor,Member; Executive\n",
    )

    assert rows == [
        {
            "email": "ama@example.edu.gh",
            "staff_id": "UG001",
            "other_name": "Ama",
            "surname": "Mensah",
            "academic_rank": "Professor",
            "roles": ["executive", "member"],
        }
    ]


def test_xlsx_member_import_reads_first_sheet_without_formulas() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["email", "other_name", "surname", "roles"])
    sheet.append(["kwame@example.edu.gh", "Kwame", "Asante", "member"])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()

    rows = parse_member_import("members.xlsx", output.getvalue())

    assert rows[0]["email"] == "kwame@example.edu.gh"
    assert rows[0]["roles"] == ["member"]


def test_member_import_rejects_unapproved_formats() -> None:
    with pytest.raises(ApiError) as raised:
        parse_member_import("members.xls", b"not-an-xlsx")

    assert raised.value.code == "import_type_invalid"
