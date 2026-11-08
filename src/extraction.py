"""Read-only extraction helpers for the project's Excel sources."""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import pandas as pd

from .utils import read_excel_sheet as _read_excel_sheet


def list_excel_sheets(path: str | PathLike[str]) -> list[str]:
    """Return the worksheet names available in an Excel file.

    Args:
        path: Path to the Excel workbook.

    Raises:
        FileNotFoundError: If the workbook does not exist.
        ValueError: If the file is not a valid Excel workbook.
    """
    excel_path = Path(path)
    if not excel_path.is_file():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    try:
        with pd.ExcelFile(excel_path) as workbook:
            return workbook.sheet_names
    except (BadZipFile, OSError, ValueError) as exc:
        raise ValueError(
            f"Could not read a valid Excel workbook from '{excel_path}'."
        ) from exc


def read_excel_sheet(
    path: str | PathLike[str],
    sheet_name: str | int,
    *,
    header: int = 2,
    **kwargs: Any,
) -> pd.DataFrame:
    """Read one Excel worksheet without applying data transformations.

    Args:
        path: Path to the Excel workbook.
        sheet_name: Worksheet name or zero-based worksheet position.
        header: Row used as the column header, defaulting to the third row.
        **kwargs: Additional arguments passed to :func:`pandas.read_excel`.

    Raises:
        FileNotFoundError: If the workbook does not exist.
        ValueError: If the requested worksheet does not exist.
        TypeError: If ``sheet_name`` is not a string or integer, or is boolean.
    """
    if isinstance(sheet_name, bool) or not isinstance(sheet_name, (str, int)):
        raise TypeError(
            "sheet_name must be a worksheet name or integer index; "
            "boolean values are not supported."
        )

    excel_path = Path(path)
    sheet_names = list_excel_sheets(excel_path)
    if isinstance(sheet_name, str) and sheet_name not in sheet_names:
        raise ValueError(
            f"Excel sheet not found: '{sheet_name}' in '{excel_path}'."
        )
    if isinstance(sheet_name, int) and not 0 <= sheet_name < len(sheet_names):
        raise ValueError(
            f"Excel sheet index out of range: {sheet_name} "
            f"for '{excel_path}'."
        )

    return _read_excel_sheet(
        excel_path,
        sheet_name=sheet_name,
        header=header,
        **kwargs,
    )
