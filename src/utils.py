"""Common filesystem and tabular-data utilities for the project."""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, Literal

import pandas as pd


@dataclass(frozen=True)
class DataPaths:
    """Canonical locations of the project's raw and processed data."""

    raw: Path
    processed: Path


def get_project_root(start: str | PathLike[str] | None = None) -> Path:
    """Return the repository root discovered from a starting path.

    The search walks upwards until it finds either a Git directory or the
    repository's expected ``src``, ``data`` and ``README.md`` markers.

    Args:
        start: Directory or file from which to start searching. Defaults to
            the current working directory.

    Raises:
        FileNotFoundError: If no project root can be identified.
    """
    start_path = Path.cwd() if start is None else Path(start)
    start_path = start_path if start_path.is_dir() else start_path.parent

    for candidate in (start_path, *start_path.parents):
        has_git_marker = (candidate / ".git").exists()
        has_project_markers = all(
            (candidate / marker).exists()
            for marker in ("README.md", "data", "src")
        )
        if has_git_marker or has_project_markers:
            return candidate

    raise FileNotFoundError(
        f"Could not identify the project root from '{start_path}'."
    )


def get_data_paths(
    project_root: str | PathLike[str] | None = None,
) -> DataPaths:
    """Return the canonical raw and processed data directories.

    Args:
        project_root: Optional project root. If omitted, it is discovered by
            :func:`get_project_root`.

    Raises:
        FileNotFoundError: If the project root or data directories do not
            exist.
    """
    root = (
        get_project_root()
        if project_root is None
        else Path(project_root).resolve()
    )
    raw = root / "data" / "raw"
    processed = root / "data" / "processed"

    missing = [path for path in (raw, processed) if not path.is_dir()]
    if missing:
        missing_paths = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Data directories not found: {missing_paths}")

    return DataPaths(raw=raw, processed=processed)


def read_excel_sheet(
    path: str | PathLike[str],
    sheet_name: str | int = 0,
    **kwargs: Any,
) -> pd.DataFrame:
    """Read one Excel worksheet into a DataFrame.

    Additional keyword arguments are passed directly to
    :func:`pandas.read_excel`, allowing callers to configure options such as
    ``skiprows`` without duplicating this wrapper.
    """
    excel_path = Path(path)
    if not excel_path.is_file():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    try:
        return pd.read_excel(excel_path, sheet_name=sheet_name, **kwargs)
    except ValueError as exc:
        raise ValueError(
            f"Could not read sheet '{sheet_name}' from '{excel_path}'."
        ) from exc
    except OSError as exc:
        raise OSError(f"Could not read Excel file '{excel_path}'.") from exc


def read_processed_csv(
    filename: str | PathLike[str],
    data_paths: DataPaths | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Read a processed CSV from the project's processed-data directory.

    Absolute paths are accepted for callers that already resolved a location;
    relative paths are interpreted relative to ``data/processed``.
    """
    csv_path = Path(filename)
    if not csv_path.is_absolute():
        paths = data_paths if data_paths is not None else get_data_paths()
        csv_path = paths.processed / csv_path

    if not csv_path.is_file():
        raise FileNotFoundError(f"Processed CSV not found: {csv_path}")

    try:
        return pd.read_csv(csv_path, **kwargs)
    except (pd.errors.ParserError, UnicodeError) as exc:
        raise ValueError(f"Could not parse processed CSV '{csv_path}'.") from exc
    except OSError as exc:
        raise OSError(f"Could not read processed CSV '{csv_path}'.") from exc


def normalize_column_names(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with conservatively normalized column names.

    Leading and trailing whitespace is removed and internal whitespace is
    replaced by underscores. Existing casing, accents and punctuation are
    preserved deliberately. If different original names produce the same
    normalized name, a ``ValueError`` is raised instead of silently creating
    duplicate columns.

    Raises:
        ValueError: If normalized column names are duplicated.
    """
    normalized = dataframe.copy()
    normalized_columns = (
        normalized.columns.astype(str)
        .str.strip()
        .str.replace(r"\s+", "_", regex=True)
    )
    duplicated = normalized_columns[normalized_columns.duplicated(keep=False)]
    if not duplicated.empty:
        duplicate_names = ", ".join(dict.fromkeys(duplicated.tolist()))
        raise ValueError(
            "Duplicate column names after normalization: "
            f"{duplicate_names}"
        )

    normalized.columns = normalized_columns
    return normalized


def convert_numeric_columns(
    dataframe: pd.DataFrame,
    columns: list[str] | tuple[str, ...],
    errors: Literal["raise", "coerce", "ignore"] = "coerce",
) -> pd.DataFrame:
    """Return a copy with selected columns converted using pandas.

    Args:
        dataframe: Input DataFrame.
        columns: Column names to convert.
        errors: Error policy accepted by :func:`pandas.to_numeric`.

    Raises:
        KeyError: If any requested column is absent.
        ValueError: If ``errors`` is not a supported pandas option.
    """
    missing = [column for column in columns if column not in dataframe.columns]
    if missing:
        raise KeyError(f"Columns not found: {', '.join(missing)}")
    if errors not in {"raise", "coerce", "ignore"}:
        raise ValueError(f"Unsupported numeric conversion error policy: {errors}")

    converted = dataframe.copy()
    for column in columns:
        converted[column] = pd.to_numeric(converted[column], errors=errors)
    return converted


def export_csv(
    dataframe: pd.DataFrame,
    path: str | PathLike[str],
    *,
    encoding: str = "utf-8",
    index: bool = False,
) -> Path:
    """Export a DataFrame to CSV and return the resolved output path."""
    output_path = Path(path).resolve()
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(output_path, encoding=encoding, index=index)
    except OSError as exc:
        raise OSError(f"Could not export CSV to '{output_path}'.") from exc
    return output_path