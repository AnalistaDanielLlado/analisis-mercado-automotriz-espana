"""Unit tests for DataFrame cleaning and validation utilities."""

import pandas as pd
import pytest

from src.cleaning import (
    CleaningResult,
    clean_dataframe,
    convert_columns,
    handle_missing_values,
    normalize_columns,
    remove_duplicates,
    validate_dataframe,
)


def test_normalize_columns_normalizes_names_without_mutating_original() -> None:
    dataframe = pd.DataFrame(
        [[1, "Madrid"]],
        columns=["  Tipo Vehiculo  ", "Provincia Álava"],
    )

    normalized = normalize_columns(dataframe)

    assert list(normalized.columns) == ["Tipo_Vehiculo", "Provincia_Álava"]
    assert normalized.iloc[0].tolist() == [1, "Madrid"]
    assert list(dataframe.columns) == ["  Tipo Vehiculo  ", "Provincia Álava"]
    assert dataframe.iloc[0].tolist() == [1, "Madrid"]


def test_normalize_columns_rejects_normalized_duplicate_names() -> None:
    dataframe = pd.DataFrame(
        [[1, 2]],
        columns=["Tipo Vehiculo", "Tipo_Vehiculo"],
    )

    with pytest.raises(
        ValueError,
        match="Duplicate column names after normalization: Tipo_Vehiculo",
    ):
        normalize_columns(dataframe)


def test_remove_duplicates_report_detects_without_removing() -> None:
    dataframe = pd.DataFrame({"id": [1, 1, 2], "value": ["a", "a", "b"]})

    cleaned, changes = remove_duplicates(dataframe, policy="report")

    pd.testing.assert_frame_equal(cleaned, dataframe)
    assert changes == {
        "policy": "report",
        "duplicates_detected": 1,
        "duplicates_removed": 0,
    }


@pytest.mark.parametrize(
    (
        "keep",
        "expected_values",
        "expected_detected",
        "expected_removed",
    ),
    [
        ("first", ["first", "other"], 1, 1),
        ("last", ["last", "other"], 1, 1),
        (False, ["other"], 2, 2),
    ],
)
def test_remove_duplicates_drop_honors_keep(
    keep: str | bool,
    expected_values: list[str],
    expected_detected: int,
    expected_removed: int,
) -> None:
    dataframe = pd.DataFrame(
        {"id": [1, 1, 2], "value": ["first", "last", "other"]}
    )

    cleaned, changes = remove_duplicates(
        dataframe,
        subset=["id"],
        keep=keep,  # type: ignore[arg-type]
        policy="drop",
    )

    assert cleaned["value"].tolist() == expected_values
    assert changes["duplicates_detected"] == expected_detected
    assert changes["duplicates_removed"] == expected_removed


def test_remove_duplicates_drop_uses_subset() -> None:
    dataframe = pd.DataFrame(
        {"id": [1, 1], "value": ["a", "b"], "other": [10, 20]}
    )

    cleaned, changes = remove_duplicates(
        dataframe,
        subset=["id"],
        policy="drop",
    )

    assert len(cleaned) == 1
    assert changes["duplicates_detected"] == 1


def test_remove_duplicates_error_raises_for_duplicates() -> None:
    dataframe = pd.DataFrame({"id": [1, 1]})

    with pytest.raises(ValueError, match="Found 1 duplicate rows"):
        remove_duplicates(dataframe, policy="error")


def test_remove_duplicates_rejects_missing_subset_column() -> None:
    dataframe = pd.DataFrame({"id": [1]})

    with pytest.raises(KeyError, match="subset contains columns not found"):
        remove_duplicates(dataframe, subset=["missing"])


def test_handle_missing_values_report_returns_exact_null_statistics() -> None:
    dataframe = pd.DataFrame({"a": [1, None], "b": [None, 2]})

    cleaned, changes = handle_missing_values(dataframe, policy="report")

    pd.testing.assert_frame_equal(cleaned, dataframe)
    assert changes["nulls_detected"] == 2
    assert changes["null_counts"] == {"a": 1, "b": 1}
    assert changes["nulls_treated"] == 0
    assert changes["rows_removed"] == 0
    assert changes["columns_removed"] == []


def test_handle_missing_values_drop_rows_reports_rows_and_nulls_treated() -> None:
    dataframe = pd.DataFrame(
        {"a": [1, None, 3], "b": [None, 2, 3], "c": [10, 20, 30]}
    )

    cleaned, changes = handle_missing_values(
        dataframe,
        policy="drop_rows",
        subset=["a"],
    )

    assert cleaned.index.tolist() == [0, 2]
    assert changes["nulls_detected"] == 2
    assert changes["rows_removed"] == 1
    assert changes["nulls_treated"] == 1


def test_handle_missing_values_drop_rows_scopes_nulls_to_columns() -> None:
    dataframe = pd.DataFrame(
        {"a": [1, None, 3], "b": [None, 2, 3]}
    )

    cleaned, changes = handle_missing_values(
        dataframe,
        policy="drop_rows",
        columns=["a"],
        subset=["b"],
    )

    assert cleaned.index.tolist() == [1, 2]
    assert changes["nulls_detected"] == 1
    assert changes["rows_removed"] == 1
    assert changes["nulls_treated"] == 0


def test_handle_missing_values_drop_columns_removes_only_null_columns() -> None:
    dataframe = pd.DataFrame(
        {"with_null": [1, None], "without_null": [2, 3], "other": [4, 5]}
    )

    cleaned, changes = handle_missing_values(
        dataframe,
        policy="drop_columns",
        columns=["with_null", "without_null"],
    )

    assert list(cleaned.columns) == ["without_null", "other"]
    assert changes["nulls_detected"] == 1
    assert changes["nulls_treated"] == 1
    assert changes["columns_removed"] == ["with_null"]


def test_handle_missing_values_fill_replaces_selected_nulls() -> None:
    dataframe = pd.DataFrame({"a": [1, None], "b": [None, None]})

    cleaned, changes = handle_missing_values(
        dataframe,
        policy="fill",
        columns=["a", "b"],
        value=0,
    )

    assert cleaned[["a", "b"]].isna().sum().sum() == 0
    assert changes["nulls_detected"] == 3
    assert changes["nulls_treated"] == 3


def test_handle_missing_values_ffill_counts_only_filled_nulls() -> None:
    dataframe = pd.DataFrame({"value": [None, 1, None]})

    cleaned, changes = handle_missing_values(
        dataframe,
        policy="ffill",
        columns=["value"],
    )

    assert pd.isna(cleaned["value"].iloc[0])
    assert cleaned["value"].iloc[1] == 1.0
    assert cleaned["value"].iloc[2] == 1.0
    assert changes["nulls_detected"] == 2
    assert changes["nulls_treated"] == 1


def test_handle_missing_values_bfill_counts_only_filled_nulls() -> None:
    dataframe = pd.DataFrame({"value": [None, 1, None]})

    cleaned, changes = handle_missing_values(
        dataframe,
        policy="bfill",
        columns=["value"],
    )

    assert cleaned["value"].iloc[0] == 1.0
    assert cleaned["value"].iloc[1] == 1.0
    assert pd.isna(cleaned["value"].iloc[2])
    assert changes["nulls_detected"] == 2
    assert changes["nulls_treated"] == 1


def test_handle_missing_values_error_rejects_nulls() -> None:
    dataframe = pd.DataFrame({"value": [1, None]})

    with pytest.raises(ValueError, match="Found 1 missing values"):
        handle_missing_values(dataframe, policy="error")


@pytest.mark.parametrize(
    ("policy", "kwargs"),
    [
        ("drop_rows", {}),
        ("drop_columns", {}),
        ("fill", {}),
        ("ffill", {}),
        ("bfill", {}),
    ],
)
def test_handle_missing_values_requires_explicit_targets(
    policy: str,
    kwargs: dict[str, object],
) -> None:
    dataframe = pd.DataFrame({"value": [1, None]})

    with pytest.raises(ValueError, match="requires"):
        handle_missing_values(dataframe, policy=policy, **kwargs)


def test_handle_missing_values_fill_requires_value() -> None:
    dataframe = pd.DataFrame({"value": [1, None]})

    with pytest.raises(ValueError, match="explicit non-None value"):
        handle_missing_values(
            dataframe,
            policy="fill",
            columns=["value"],
        )


def test_handle_missing_values_rejects_missing_columns() -> None:
    dataframe = pd.DataFrame({"value": [1]})

    with pytest.raises(KeyError, match="columns contains columns not found"):
        handle_missing_values(
            dataframe,
            policy="fill",
            columns=["missing"],
            value=0,
        )


def test_convert_columns_converts_numeric_columns_without_mutation() -> None:
    dataframe = pd.DataFrame({"year": ["2024"], "value": ["100"]})

    converted = convert_columns(dataframe, numeric_columns=["year", "value"])

    assert converted["year"].tolist() == [2024]
    assert converted["value"].tolist() == [100]
    pd.testing.assert_frame_equal(converted.astype(str), dataframe)


def test_convert_columns_applies_dtype_map() -> None:
    dataframe = pd.DataFrame({"value": [1, 2]})

    converted = convert_columns(
        dataframe,
        dtype_map={"value": "float64"},
    )

    assert str(converted["value"].dtype) == "float64"
    assert str(dataframe["value"].dtype) == "int64"


def test_convert_columns_raises_for_invalid_numeric_conversion() -> None:
    dataframe = pd.DataFrame({"value": ["not-a-number"]})

    with pytest.raises(ValueError, match="Unable to parse string"):
        convert_columns(dataframe, numeric_columns=["value"])


def test_convert_columns_coerces_invalid_numeric_values_when_requested() -> None:
    dataframe = pd.DataFrame({"value": ["100", "invalid"]})

    converted = convert_columns(
        dataframe,
        numeric_columns=["value"],
        errors="coerce",
    )

    assert converted["value"].iloc[0] == 100
    assert pd.isna(converted["value"].iloc[1])
    assert dataframe["value"].tolist() == ["100", "invalid"]


def test_convert_columns_raises_for_missing_columns() -> None:
    dataframe = pd.DataFrame({"value": [1]})

    with pytest.raises(KeyError, match="Columns not found: missing"):
        convert_columns(dataframe, numeric_columns=["missing"])


def test_validate_dataframe_reports_valid_dataframe_without_mutation() -> None:
    dataframe = pd.DataFrame(
        {"id": [1, 2], "value": [10, 20], "label": ["a", "b"]}
    )
    original = dataframe.copy(deep=True)

    report = validate_dataframe(
        dataframe,
        required_columns=["id", "value"],
        non_null_columns=["value"],
        unique_columns=["id"],
        numeric_columns=["value"],
    )

    assert report.valid is True
    assert report.errors == []
    assert report.duplicate_count == 0
    assert report.checked_rules == [
        "required_columns",
        "non_null_columns",
        "unique_columns",
        "numeric_columns",
    ]
    pd.testing.assert_frame_equal(dataframe, original)


def test_validate_dataframe_reports_missing_required_columns() -> None:
    dataframe = pd.DataFrame({"id": [1]})

    report = validate_dataframe(
        dataframe,
        required_columns=["id", "missing"],
    )

    assert report.valid is False
    assert report.errors == ["Required columns not found: missing"]


def test_validate_dataframe_reports_nulls_duplicate_rows_and_non_numeric() -> None:
    dataframe = pd.DataFrame(
        {"id": [1, 1], "required": [None, 2], "value": ["10", "20"]}
    )

    report = validate_dataframe(
        dataframe,
        non_null_columns=["required"],
        unique_columns=["id"],
        numeric_columns=["value"],
    )

    assert report.valid is False
    assert report.duplicate_count == 1
    assert report.errors == [
        "Columns contain nulls: required",
        "Columns ['id'] contain 1 duplicate rows.",
        "Columns are not numeric: value",
    ]
    assert report.null_counts == {"id": 0, "required": 1, "value": 0}


def test_validate_dataframe_supports_composite_unique_columns() -> None:
    dataframe = pd.DataFrame(
        {"year": [2024, 2024, 2025], "province": ["A", "A", "A"]}
    )

    report = validate_dataframe(
        dataframe,
        unique_columns=[["year", "province"]],
    )

    assert report.valid is False
    assert report.duplicate_count == 1


def test_validate_dataframe_rejects_missing_validation_columns() -> None:
    dataframe = pd.DataFrame({"id": [1]})

    with pytest.raises(KeyError, match="numeric_columns contains columns not found"):
        validate_dataframe(dataframe, numeric_columns=["missing"])


def test_clean_dataframe_coordinates_cleaning_and_validation() -> None:
    dataframe = pd.DataFrame(
        {
            " Tipo Vehiculo ": ["car", "car", "van"],
            " value ": ["10", "10", None],
        }
    )
    original = dataframe.copy(deep=True)

    result = clean_dataframe(
        dataframe,
        duplicate_subset=["Tipo_Vehiculo", "value"],
        duplicate_policy="drop",
        missing_policy="drop_rows",
        missing_subset=["value"],
        numeric_columns=["value"],
        required_columns=["Tipo_Vehiculo", "value"],
        non_null_columns=["value"],
        unique_columns=["Tipo_Vehiculo"],
        numeric_validation_columns=["value"],
    )

    assert isinstance(result, CleaningResult)
    assert result.dataframe.to_dict("records") == [
        {"Tipo_Vehiculo": "car", "value": 10}
    ]
    assert result.report.valid is True
    assert result.report.errors == []
    assert result.changes["duplicates"]["duplicates_removed"] == 1
    assert result.changes["missing_values"]["rows_removed"] == 1
    assert result.changes["rows_initial"] == 3
    assert result.changes["rows_final"] == 1
    pd.testing.assert_frame_equal(dataframe, original)


def test_clean_dataframe_records_report_and_changes_for_non_destructive_policies() -> None:
    dataframe = pd.DataFrame({"id": [1, 1], "value": [10, 10]})

    result = clean_dataframe(
        dataframe,
        duplicate_policy="report",
        missing_policy="report",
        required_columns=["id", "value"],
        unique_columns=["id"],
    )

    assert result.report.valid is False
    assert result.report.duplicate_count == 1
    assert result.changes["duplicates"]["duplicates_detected"] == 1
    assert result.changes["missing_values"]["nulls_detected"] == 0
    pd.testing.assert_frame_equal(result.dataframe, dataframe)
