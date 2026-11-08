"""Unit tests for the shared project utilities."""

from pathlib import Path

import pandas as pd
import pytest

from src.utils import (
    DataPaths,
    convert_numeric_columns,
    export_csv,
    get_data_paths,
    get_project_root,
    normalize_column_names,
    read_processed_csv,
)


def test_get_project_root_finds_project_markers(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / "data").mkdir(parents=True)
    (project_root / "src").mkdir()
    (project_root / "README.md").touch()
    nested_directory = project_root / "nested" / "directory"
    nested_directory.mkdir(parents=True)

    assert get_project_root(nested_directory) == project_root


def test_get_project_root_raises_when_no_valid_root_exists(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="Could not identify"):
        get_project_root(tmp_path)


def test_get_data_paths_returns_raw_and_processed_directories(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "data" / "raw"
    processed = tmp_path / "data" / "processed"
    raw.mkdir(parents=True)
    processed.mkdir()

    paths = get_data_paths(tmp_path)

    assert paths.raw == raw
    assert paths.processed == processed


def test_get_data_paths_raises_for_missing_directories(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Data directories not found"):
        get_data_paths(tmp_path)


def test_normalize_column_names_preserves_values_and_original_dataframe() -> None:
    original = pd.DataFrame(
        [[1, "Madrid"]],
        columns=["  Tipo Vehiculo  ", "Provincia Álava"],
    )

    normalized = normalize_column_names(original)

    assert list(normalized.columns) == ["Tipo_Vehiculo", "Provincia_Álava"]
    assert normalized.iloc[0].tolist() == [1, "Madrid"]
    assert list(original.columns) == ["  Tipo Vehiculo  ", "Provincia Álava"]


def test_normalize_column_names_detects_normalized_duplicates() -> None:
    dataframe = pd.DataFrame(
        [[1, 2, "Madrid"]],
        columns=["Tipo Vehiculo", "Tipo_Vehiculo", "Provincia"],
    )

    with pytest.raises(
        ValueError,
        match="Duplicate column names after normalization: Tipo_Vehiculo",
    ):
        normalize_column_names(dataframe)


def test_convert_numeric_columns_converts_selected_columns() -> None:
    dataframe = pd.DataFrame({"anio": ["2024"], "total": ["100"]})

    converted = convert_numeric_columns(dataframe, ["anio", "total"])

    assert converted["anio"].tolist() == [2024]
    assert converted["total"].tolist() == [100]
    assert dataframe["anio"].tolist() == ["2024"]


def test_convert_numeric_columns_coerces_invalid_values_to_nan() -> None:
    dataframe = pd.DataFrame({"total": ["100", "not-a-number"]})

    converted = convert_numeric_columns(dataframe, ["total"], errors="coerce")

    assert converted["total"].iloc[0] == 100
    assert pd.isna(converted["total"].iloc[1])


def test_convert_numeric_columns_raises_for_missing_columns() -> None:
    dataframe = pd.DataFrame({"total": [100]})

    with pytest.raises(KeyError, match="Columns not found: anio"):
        convert_numeric_columns(dataframe, ["anio"])


def test_export_csv_writes_expected_data_without_index(tmp_path: Path) -> None:
    dataframe = pd.DataFrame({"provincia": ["Madrid"], "total": [100]})
    output_path = tmp_path / "processed" / "result.csv"

    returned_path = export_csv(dataframe, output_path, index=False)

    assert returned_path == output_path.resolve()
    assert output_path.read_text(encoding="utf-8") == (
        "provincia,total\nMadrid,100\n"
    )


def test_read_processed_csv_reads_relative_file(tmp_path: Path) -> None:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    expected = pd.DataFrame({"anio": [2025], "total": [100]})
    expected.to_csv(processed / "result.csv", index=False)

    paths = DataPaths(raw=tmp_path / "data" / "raw", processed=processed)
    result = read_processed_csv("result.csv", data_paths=paths)

    pd.testing.assert_frame_equal(result, expected)


def test_read_processed_csv_raises_for_missing_file(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw"
    processed = tmp_path / "data" / "processed"
    raw.mkdir(parents=True)
    processed.mkdir()

    with pytest.raises(FileNotFoundError, match="Processed CSV not found"):
        read_processed_csv("missing.csv", data_paths=get_data_paths(tmp_path))
