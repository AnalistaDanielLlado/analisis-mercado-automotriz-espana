"""Conservative transformations for the project's tabular datasets."""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from typing import Any, Literal, Mapping, Sequence

import pandas as pd

from .utils import normalize_column_names


ErrorPolicy = Literal["raise", "coerce"]


@dataclass(frozen=True)
class AuxiliaryRowsResult:
    """Partition of a DataFrame into analytical and auxiliary row groups."""

    observations: pd.DataFrame
    totals: pd.DataFrame
    percentages: pd.DataFrame
    auxiliary: pd.DataFrame


def _validate_columns(
    dataframe: pd.DataFrame,
    columns: Sequence[str],
    argument_name: str,
) -> None:
    missing = [column for column in columns if column not in dataframe.columns]
    if missing:
        raise KeyError(
            f"{argument_name} contains columns not found in DataFrame: "
            f"{', '.join(missing)}"
        )


def normalize_transformation_columns(
    dataframe: pd.DataFrame,
    *,
    column_mapping: Mapping[str, str] | None = None,
    suffix: str = "_normalized",
) -> pd.DataFrame:
    """Add conservatively normalized aliases while preserving source columns."""
    if not isinstance(suffix, str) or not suffix:
        raise ValueError("suffix must be a non-empty string.")

    mapping = (
        dict(column_mapping)
        if column_mapping is not None
        else {
            str(column): (
                f"{normalize_column_names(dataframe[[column]]).columns[0]}"
                f"{suffix}"
            )
            for column in dataframe.columns
        }
    )
    _validate_columns(dataframe, list(mapping), "column_mapping")

    normalized = normalize_column_names(dataframe)
    result = dataframe.copy()
    destinations: set[str] = set()
    for source, destination in mapping.items():
        if not isinstance(destination, str) or not destination:
            raise ValueError("column_mapping destinations must be non-empty strings.")
        if destination in result.columns or destination in destinations:
            raise ValueError(
                f"Normalized column destination already exists: {destination}"
            )
        normalized_source = normalize_column_names(
            dataframe[[source]]
        ).columns[0]
        result[destination] = normalized[normalized_source].values
        destinations.add(destination)
    return result


def split_auxiliary_rows(
    dataframe: pd.DataFrame,
    *,
    identifier_column: str,
    total_labels: Sequence[str] = ("Total", "TOTAL"),
    percentage_labels: Sequence[str] = ("Porcentaje", "%"),
) -> AuxiliaryRowsResult:
    """Partition rows without dropping or reordering any source rows."""
    _validate_columns(dataframe, [identifier_column], "identifier_column")
    normalize_label = lambda value: (
        value.strip().casefold() if isinstance(value, str) else value
    )
    total_set = {normalize_label(label) for label in total_labels}
    percentage_set = {normalize_label(label) for label in percentage_labels}
    overlap_labels = total_set & percentage_set
    if overlap_labels:
        raise ValueError(
            "Labels cannot be configured as both total and percentage: "
            f"{sorted(overlap_labels)}"
        )
    identifier = dataframe[identifier_column]

    normalized_identifier = identifier.map(normalize_label)
    total_mask = normalized_identifier.isin(total_set)
    percentage_mask = normalized_identifier.isin(percentage_set) & ~total_mask
    empty_mask = dataframe.isna().all(axis=1)
    text_mask = identifier.map(
        lambda value: isinstance(value, str)
        and (value.strip().startswith("*") or value.strip().lower().startswith("nota"))
    )
    auxiliary_mask = (empty_mask | text_mask) & ~total_mask & ~percentage_mask
    classified_mask = total_mask | percentage_mask | auxiliary_mask

    return AuxiliaryRowsResult(
        observations=dataframe.loc[~classified_mask].copy(),
        totals=dataframe.loc[total_mask].copy(),
        percentages=dataframe.loc[percentage_mask].copy(),
        auxiliary=dataframe.loc[auxiliary_mask].copy(),
    )


def convert_year_column(
    dataframe: pd.DataFrame,
    column: str,
    *,
    output_column: str = "year",
    errors: ErrorPolicy = "raise",
) -> pd.DataFrame:
    """Add an integer-nullable year column while preserving the source column."""
    if errors not in {"raise", "coerce"}:
        raise ValueError(f"Unsupported conversion error policy: {errors}")
    _validate_columns(dataframe, [column], "column")
    if output_column == column:
        raise ValueError("output_column must differ from the source column.")
    if output_column in dataframe.columns:
        raise ValueError(f"Output column already exists: {output_column}")

    result = dataframe.copy()
    source = result[column]
    boolean_mask = source.map(lambda value: isinstance(value, bool))
    if errors == "raise" and boolean_mask.any():
        raise ValueError(f"Boolean values are not valid years in column '{column}'.")

    numeric = pd.to_numeric(source.mask(boolean_mask), errors=errors)
    fractional = numeric.notna() & (numeric % 1 != 0)
    if fractional.any() and errors == "raise":
        raise ValueError(f"Year values must be integers in column '{column}'.")
    if fractional.any():
        numeric = numeric.mask(fractional)
    result[output_column] = numeric.astype("Int64")
    return result


def convert_month_column(
    dataframe: pd.DataFrame,
    column: str = "Mes",
    *,
    output_column: str = "month",
    errors: ErrorPolicy = "raise",
) -> pd.DataFrame:
    """Add numeric Spanish month values while preserving the source labels."""
    if errors not in {"raise", "coerce"}:
        raise ValueError(f"Unsupported conversion error policy: {errors}")
    _validate_columns(dataframe, [column], "column")
    if output_column == column:
        raise ValueError("output_column must differ from the source column.")
    if output_column in dataframe.columns:
        raise ValueError(f"Output column already exists: {output_column}")

    month_names = {
        name: number
        for number, name in enumerate(
            (
                "enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre",
                "diciembre",
            ),
            start=1,
        )
    }
    normalized = dataframe[column].map(
        lambda value: value.strip().casefold()
        if isinstance(value, str)
        else value
    )
    result = dataframe.copy()
    result[output_column] = normalized.map(month_names)
    invalid = result[output_column].isna() & dataframe[column].notna()
    if errors == "raise" and invalid.any():
        invalid_values = dataframe.loc[invalid, column].tolist()
        raise ValueError(f"Unknown month labels: {invalid_values}")
    result[output_column] = result[output_column].astype("Int64")
    return result


def add_contextual_year(
    dataframe: pd.DataFrame,
    year: int,
    *,
    output_column: str = "year",
) -> pd.DataFrame:
    """Add an explicitly supplied year without overwriting existing columns."""
    if isinstance(year, bool) or not isinstance(year, int):
        raise TypeError("year must be an integer and cannot be boolean.")
    if output_column in dataframe.columns:
        raise ValueError(f"Output column already exists: {output_column}")

    result = dataframe.copy()
    result[output_column] = year
    return result


def reshape_year_columns(
    dataframe: pd.DataFrame,
    *,
    id_columns: Sequence[str],
    year_columns: Sequence[str | int],
    year_name: str = "year",
    value_name: str = "value",
) -> pd.DataFrame:
    """Reshape explicitly selected year columns into a long DataFrame."""
    id_columns = list(id_columns)
    year_columns = list(year_columns)
    if len(set(id_columns)) != len(id_columns):
        raise ValueError("id_columns must not contain duplicates.")
    _validate_columns(dataframe, id_columns, "id_columns")
    _validate_columns(dataframe, year_columns, "year_columns")
    if len(set(year_columns)) != len(year_columns):
        raise ValueError("year_columns must not contain duplicates.")
    if year_name in dataframe.columns or value_name in dataframe.columns:
        raise ValueError("Output column names collide with existing columns.")
    if year_name == value_name:
        raise ValueError("year_name and value_name must be different.")

    year_values = pd.to_numeric(pd.Index(year_columns), errors="coerce")
    invalid_years = (
        pd.isna(year_values)
        | (year_values % 1 != 0)
        | pd.Index(year_columns).map(lambda value: isinstance(value, bool))
    )
    if invalid_years.any():
        invalid = [
            value for value, is_invalid in zip(year_columns, invalid_years)
            if is_invalid
        ]
        raise ValueError(f"Year columns must contain integer years: {invalid}")

    result = dataframe.melt(
        id_vars=id_columns,
        value_vars=year_columns,
        var_name=year_name,
        value_name=value_name,
        ignore_index=False,
    )
    result[year_name] = pd.to_numeric(
        result[year_name], errors="raise"
    ).astype("Int64")
    return result


def build_source_metadata(
    dataframe: pd.DataFrame,
    *,
    source_file: str | PathLike[str],
    source_sheet: str,
    dataset_group: str | None = None,
    period_type: str | None = None,
    unit: str | None = None,
    aggregation_level: str | None = None,
) -> pd.DataFrame:
    """Add explicit source metadata without inferring meanings or units."""
    if not str(source_file).strip() or not source_sheet.strip():
        raise ValueError("source_file and source_sheet must be non-empty.")

    metadata = {
        "source_file": str(source_file),
        "source_sheet": source_sheet,
        "dataset_group": dataset_group,
        "period_type": period_type,
        "unit": unit,
        "aggregation_level": aggregation_level,
    }
    metadata = {key: value for key, value in metadata.items() if value is not None}
    collisions = [column for column in metadata if column in dataframe.columns]
    if collisions:
        raise ValueError(
            f"Metadata columns already exist: {', '.join(collisions)}"
        )

    result = dataframe.copy()
    for column, value in metadata.items():
        result[column] = value
    return result
