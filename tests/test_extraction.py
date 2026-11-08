"""Unit tests for Excel extraction helpers."""

from pathlib import Path

import pandas as pd
import pytest

from src.extraction import list_excel_sheets, read_excel_sheet


def _create_workbook(path: Path) -> None:
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"year": [2024], "total": [100]}).to_excel(
            writer,
            sheet_name="data",
            index=False,
            startrow=2,
        )
        pd.DataFrame({"name": ["Madrid"]}).to_excel(
            writer,
            sheet_name="other",
            index=False,
        )


def test_read_excel_sheet_reads_requested_sheet_with_default_header(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "source.xlsx"
    _create_workbook(workbook)

    result = read_excel_sheet(workbook, "data")

    expected = pd.DataFrame({"year": [2024], "total": [100]})
    pd.testing.assert_frame_equal(result, expected)


def test_read_excel_sheet_accepts_configurable_header(tmp_path: Path) -> None:
    workbook = tmp_path / "source.xlsx"
    pd.DataFrame({"year": [2024], "total": [100]}).to_excel(
        workbook,
        sheet_name="data",
        index=False,
    )

    result = read_excel_sheet(workbook, "data", header=0)

    expected = pd.DataFrame({"year": [2024], "total": [100]})
    pd.testing.assert_frame_equal(result, expected)


def test_read_excel_sheet_reads_first_sheet_by_index(tmp_path: Path) -> None:
    workbook = tmp_path / "source.xlsx"
    _create_workbook(workbook)

    result = read_excel_sheet(workbook, 0)

    expected = pd.DataFrame({"year": [2024], "total": [100]})
    pd.testing.assert_frame_equal(result, expected)


def test_list_excel_sheets_returns_available_sheet_names(tmp_path: Path) -> None:
    workbook = tmp_path / "source.xlsx"
    _create_workbook(workbook)

    assert list_excel_sheets(workbook) == ["data", "other"]


def test_read_excel_sheet_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Excel file not found"):
        read_excel_sheet(tmp_path / "missing.xlsx", "data")


def test_list_excel_sheets_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Excel file not found"):
        list_excel_sheets(tmp_path / "missing.xlsx")


def test_read_excel_sheet_raises_for_missing_sheet(tmp_path: Path) -> None:
    workbook = tmp_path / "source.xlsx"
    _create_workbook(workbook)

    with pytest.raises(ValueError, match="Excel sheet not found"):
        read_excel_sheet(workbook, "missing")


@pytest.mark.parametrize("sheet_name", [-1, 2])
def test_read_excel_sheet_rejects_out_of_range_index(
    tmp_path: Path,
    sheet_name: int,
) -> None:
    workbook = tmp_path / "source.xlsx"
    _create_workbook(workbook)

    with pytest.raises(ValueError, match="Excel sheet index out of range"):
        read_excel_sheet(workbook, sheet_name)


@pytest.mark.parametrize("sheet_name", [True, False])
def test_read_excel_sheet_rejects_boolean_index(
    tmp_path: Path,
    sheet_name: bool,
) -> None:
    workbook = tmp_path / "source.xlsx"
    _create_workbook(workbook)

    with pytest.raises(TypeError, match="boolean values are not supported"):
        read_excel_sheet(workbook, sheet_name)


def test_list_excel_sheets_rejects_invalid_excel_file(tmp_path: Path) -> None:
    invalid_file = tmp_path / "invalid.xlsx"
    invalid_file.write_text("not an Excel workbook", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Could not read a valid Excel workbook",
    ):
        list_excel_sheets(invalid_file)


def test_read_excel_sheet_rejects_invalid_excel_file(tmp_path: Path) -> None:
    invalid_file = tmp_path / "invalid.xlsx"
    invalid_file.write_text("not an Excel workbook", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Could not read a valid Excel workbook",
    ):
        read_excel_sheet(invalid_file, "data")


def test_read_excel_sheet_does_not_modify_source_workbook(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "source.xlsx"
    _create_workbook(workbook)
    before = workbook.read_bytes()

    result = read_excel_sheet(workbook, "data")
    after = workbook.read_bytes()

    assert result.to_dict("records") == [{"year": 2024, "total": 100}]
    assert after == before
