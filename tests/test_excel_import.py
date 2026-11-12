from io import BytesIO

import pytest
from openpyxl import Workbook

from app.excel_import import parse_workbook, source_key_for


def workbook_bytes(headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def test_parse_valid_input_and_export_aliases():
    content = workbook_bytes(
        ["Full Name", "Position", "Company", "Email(s)", "Verified", "Open To Work"],
        [["Avery Quinn", "Founder", "CareRoute", "avery@example.com", "false", "no"]],
    )
    rows, errors = parse_workbook(content)
    assert errors == []
    assert rows[0]["Current Position"] == "Founder"
    assert rows[0]["Current Company"] == "CareRoute"
    assert rows[0]["Email(s)"] == ["avery@example.com"]
    assert rows[0]["Verified"] is False
    assert rows[0]["Open To Work"] is False


def test_blank_name_is_row_error_but_valid_rows_continue():
    content = workbook_bytes(
        ["Full Name", "Company"],
        [["", "Missing"], ["Valid Lead", "Acme"]],
    )
    rows, errors = parse_workbook(content)
    assert [row["Full Name"] for row in rows] == ["Valid Lead"]
    assert errors == [{"row": 2, "message": "Full Name is required"}]


def test_missing_name_header_is_fatal():
    content = workbook_bytes(["Company"], [["Acme"]])
    with pytest.raises(ValueError, match="Full Name"):
        parse_workbook(content)


def test_invalid_extension_is_rejected():
    with pytest.raises(ValueError, match="xlsx"):
        parse_workbook(b"not a workbook", "leads.csv")


def test_source_key_prefers_email_then_name_company():
    assert source_key_for({"Full Name": "A", "Email(s)": ["A@Example.com"]}) == "email:a@example.com"
    first = source_key_for({"Full Name": "A  B", "Current Company": "Acme"})
    second = source_key_for({"Full Name": "A  B", "Current Company": "Acme"})
    assert first == second
    assert first.startswith("name-company:")
