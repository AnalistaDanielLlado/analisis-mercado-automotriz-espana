"""Reusable DataFrame cleaning and validation utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

import pandas as pd
from pandas.api.types import is_numeric_dtype

from .utils import convert_numeric_columns, normalize_column_names


DuplicatePolicy = Literal["report", "drop", "error"]
MissingPolicy = Literal[
    "report",
    "drop_rows",
    "drop_columns",
    "fill",
    "ffill",
    "bfill",
    "error",
]
KeepDuplicates = Literal["first", "last", False]
ErrorPolicy = Literal["raise", "coerce", "ignore"]


@dataclass
class ValidationReport:
    """Results from non-mutating DataFrame integrity checks."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    null_counts: dict[str, int] = field(default_factory=dict)
    duplicate_count: int = 0
    checked_rules: list[str] = field(default_factory=list)


@dataclass
class CleaningResult:
    """Output of the coordinated DataFrame cleaning process."""

    dataframe: pd.DataFrame
    report: ValidationReport
    changes: dict[str, Any] = field(default_factory=dict)


def _validate_columns(
    dataframe: pd.DataFrame,
    columns: Sequence[str],
    argument_name: str,
) -> None:
    """Raise a descriptive error when configured columns are absent."""
    missing = [column for column in columns if column not in dataframe.columns]
    if missing:
        raise KeyError(
            f"{argument_name} contains columns not found in DataFrame: "
            f"{', '.join(missing)}"
        )


def normalize_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with conservatively normalized column names."""
    return normalize_column_names(dataframe)


def remove_duplicates(
    dataframe: pd.DataFrame,
    *,
    subset: Sequence[str] | None = None,
    keep: KeepDuplicates = "first",
    policy: DuplicatePolicy = "report",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Detect and optionally remove duplicate rows.

    ``report`` is the default and does not remove rows. ``drop`` applies the
    configured ``subset`` and ``keep`` policy. ``error`` raises if duplicates
    are found.
    """
    if policy not in {"report", "drop", "error"}:
        raise ValueError(f"Unsupported duplicate policy: {policy}")
    if keep not in {"first", "last", False}:
        raise ValueError(f"Unsupported duplicate keep value: {keep}")

    selected_columns = list(subset) if subset is not None else None
    if selected_columns is not None:
        _validate_columns(dataframe, selected_columns, "subset")

    duplicate_mask = dataframe.duplicated(
        subset=selected_columns,
        keep=keep,
    )
    duplicate_count = int(duplicate_mask.sum())
    changes: dict[str, Any] = {
        "policy": policy,
        "duplicates_detected": duplicate_count,
        "duplicates_removed": 0,
    }

    if duplicate_count and policy == "error":
        raise ValueError(
            f"Found {duplicate_count} duplicate rows "
            f"for subset {selected_columns or 'all columns'}."
        )

    cleaned = dataframe.copy()
    if duplicate_count and policy == "drop":
        cleaned = cleaned.drop_duplicates(
            subset=selected_columns,
            keep=keep,
        )
        changes["duplicates_removed"] = duplicate_count

    return cleaned, changes


def handle_missing_values(
    dataframe: pd.DataFrame,
    *,
    policy: MissingPolicy = "report",
    columns: Sequence[str] | None = None,
    subset: Sequence[str] | None = None,
    value: Any = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Report or apply an explicit policy for missing values.

    Destructive policies require explicit target parameters:

    - ``drop_rows`` requires ``subset``.
    - ``drop_columns``, ``fill``, ``ffill`` and ``bfill`` require
      ``columns``.
    """
    valid_policies = {
        "report",
        "drop_rows",
        "drop_columns",
        "fill",
        "ffill",
        "bfill",
        "error",
    }
    if policy not in valid_policies:
        raise ValueError(f"Unsupported missing-value policy: {policy}")

    selected_columns = list(columns) if columns is not None else None
    selected_subset = list(subset) if subset is not None else None
    if selected_columns is not None:
        _validate_columns(dataframe, selected_columns, "columns")
    if selected_subset is not None:
        _validate_columns(dataframe, selected_subset, "subset")

    target = dataframe if selected_columns is None else dataframe[selected_columns]
    null_counts = target.isna().sum().astype(int).to_dict()
    detected = int(target.isna().sum().sum())
    changes: dict[str, Any] = {
        "policy": policy,
        "nulls_detected": detected,
        "null_counts": null_counts,
        "nulls_treated": 0,
        "rows_removed": 0,
        "columns_removed": [],
    }

    if policy == "error" and detected:
        raise ValueError(f"Found {detected} missing values.")
    if policy == "drop_rows" and selected_subset is None:
        raise ValueError("drop_rows requires an explicit subset.")
    if policy in {"drop_columns", "fill", "ffill", "bfill"}:
        if not selected_columns:
            raise ValueError(
                f"{policy} requires explicit columns."
            )
    if policy == "fill" and value is None:
        raise ValueError("fill requires an explicit non-None value.")

    cleaned = dataframe.copy()
    if policy == "drop_rows":
        before = len(cleaned)
        cleaned = cleaned.dropna(subset=selected_subset)
        changes["rows_removed"] = before - len(cleaned)
    elif policy == "drop_columns":
        columns_to_remove = [
            column
            for column in selected_columns
            if dataframe[column].isna().any()
        ]
        cleaned = cleaned.drop(columns=columns_to_remove)
        changes["columns_removed"] = columns_to_remove
    elif policy == "fill":
        cleaned[selected_columns] = cleaned[selected_columns].fillna(value)
    elif policy == "ffill":
        cleaned[selected_columns] = cleaned[selected_columns].ffill()
    elif policy == "bfill":
        cleaned[selected_columns] = cleaned[selected_columns].bfill()

    if policy in {"fill", "ffill", "bfill"}:
        remaining = int(cleaned[selected_columns].isna().sum().sum())
        changes["nulls_treated"] = detected - remaining
    elif policy == "drop_rows":
        remaining_target = (
            cleaned
            if selected_columns is None
            else cleaned[selected_columns]
        )
        remaining = int(remaining_target.isna().sum().sum())
        changes["nulls_treated"] = detected - remaining
    elif policy == "drop_columns":
        removed_target = dataframe[changes["columns_removed"]]
        changes["nulls_treated"] = int(removed_target.isna().sum().sum())

    return cleaned, changes


def convert_columns(
    dataframe: pd.DataFrame,
    *,
    numeric_columns: Sequence[str] | None = None,
    dtype_map: Mapping[str, Any] | None = None,
    errors: ErrorPolicy = "raise",
) -> pd.DataFrame:
    """Convert explicitly configured columns without inferring types."""
    if errors not in {"raise", "coerce", "ignore"}:
        raise ValueError(f"Unsupported conversion error policy: {errors}")

    converted = dataframe.copy()
    if numeric_columns:
        converted = convert_numeric_columns(
            converted,
            list(numeric_columns),
            errors=errors,
        )

    if dtype_map:
        _validate_columns(converted, list(dtype_map), "dtype_map")
        if errors == "coerce":
            raise ValueError(
                "errors='coerce' is only supported for numeric_columns; "
                "dtype_map supports 'raise' or 'ignore'."
            )
        try:
            converted = converted.astype(dict(dtype_map), errors=errors)
        except (TypeError, ValueError) as exc:
            raise ValueError("Could not convert columns using dtype_map.") from exc

    return converted


def validate_dataframe(
    dataframe: pd.DataFrame,
    *,
    required_columns: Sequence[str] | None = None,
    non_null_columns: Sequence[str] | None = None,
    unique_columns: Sequence[str] | Sequence[Sequence[str]] | None = None,
    numeric_columns: Sequence[str] | None = None,
) -> ValidationReport:
    """Validate configured DataFrame integrity rules without mutation."""
    errors: list[str] = []
    checked_rules: list[str] = []
    null_counts = dataframe.isna().sum().astype(int).to_dict()

    if required_columns is not None:
        checked_rules.append("required_columns")
        missing = [
            column
            for column in required_columns
            if column not in dataframe.columns
        ]
        if missing:
            errors.append(f"Required columns not found: {', '.join(missing)}")

    if non_null_columns is not None:
        checked_rules.append("non_null_columns")
        _validate_columns(dataframe, non_null_columns, "non_null_columns")
        invalid = [
            column for column in non_null_columns if dataframe[column].isna().any()
        ]
        if invalid:
            errors.append(f"Columns contain nulls: {', '.join(invalid)}")

    if unique_columns is not None:
        checked_rules.append("unique_columns")
        if all(isinstance(column, str) for column in unique_columns):
            unique_groups = [list(unique_columns)]  # type: ignore[arg-type]
        else:
            unique_groups = [list(group) for group in unique_columns]  # type: ignore[arg-type]
        duplicate_counts: list[int] = []
        for group in unique_groups:
            _validate_columns(dataframe, group, "unique_columns")
            count = int(dataframe.duplicated(subset=group).sum())
            duplicate_counts.append(count)
            if count:
                errors.append(
                    f"Columns {group} contain {count} duplicate rows."
                )
        duplicate_count = sum(duplicate_counts)
    else:
        duplicate_count = 0

    if numeric_columns is not None:
        checked_rules.append("numeric_columns")
        _validate_columns(dataframe, numeric_columns, "numeric_columns")
        invalid = [
            column
            for column in numeric_columns
            if not is_numeric_dtype(dataframe[column])
        ]
        if invalid:
            errors.append(f"Columns are not numeric: {', '.join(invalid)}")

    return ValidationReport(
        valid=not errors,
        errors=errors,
        null_counts=null_counts,
        duplicate_count=duplicate_count,
        checked_rules=checked_rules,
    )


def clean_dataframe(
    dataframe: pd.DataFrame,
    *,
    duplicate_subset: Sequence[str] | None = None,
    duplicate_keep: KeepDuplicates = "first",
    duplicate_policy: DuplicatePolicy = "report",
    missing_policy: MissingPolicy = "report",
    missing_columns: Sequence[str] | None = None,
    missing_subset: Sequence[str] | None = None,
    missing_value: Any = None,
    numeric_columns: Sequence[str] | None = None,
    dtype_map: Mapping[str, Any] | None = None,
    conversion_errors: ErrorPolicy = "raise",
    required_columns: Sequence[str] | None = None,
    non_null_columns: Sequence[str] | None = None,
    unique_columns: Sequence[str] | Sequence[Sequence[str]] | None = None,
    numeric_validation_columns: Sequence[str] | None = None,
) -> CleaningResult:
    """Coordinate configured cleaning operations and final validation."""
    cleaned = normalize_columns(dataframe)
    changes: dict[str, Any] = {
        "rows_initial": len(dataframe),
        "columns_initial": list(dataframe.columns),
    }

    cleaned, duplicate_changes = remove_duplicates(
        cleaned,
        subset=duplicate_subset,
        keep=duplicate_keep,
        policy=duplicate_policy,
    )
    changes["duplicates"] = duplicate_changes

    cleaned, missing_changes = handle_missing_values(
        cleaned,
        policy=missing_policy,
        columns=missing_columns,
        subset=missing_subset,
        value=missing_value,
    )
    changes["missing_values"] = missing_changes

    cleaned = convert_columns(
        cleaned,
        numeric_columns=numeric_columns,
        dtype_map=dtype_map,
        errors=conversion_errors,
    )
    changes["rows_final"] = len(cleaned)
    changes["columns_final"] = list(cleaned.columns)

    report = validate_dataframe(
        cleaned,
        required_columns=required_columns,
        non_null_columns=non_null_columns,
        unique_columns=unique_columns,
        numeric_columns=numeric_validation_columns,
    )
    return CleaningResult(
        dataframe=cleaned,
        report=report,
        changes=changes,
    )