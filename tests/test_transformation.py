"""Unit tests for conservative dataset transformations."""

import pandas as pd
import pytest

from src.transformation import (
    AuxiliaryRowsResult,
    add_contextual_year,
    build_source_metadata,
    convert_month_column,
    convert_year_column,
    normalize_transformation_columns,
    reshape_year_columns,
    split_auxiliary_rows,
)


def test_normalize_transformation_columns_preserves_originals() -> None:
    dataframe = pd.DataFrame({" Tipo Vehiculo ": ["car"], "Año": [2025]})

    result = normalize_transformation_columns(dataframe)

    assert list(result.columns) == [
        " Tipo Vehiculo ",
        "Año",
        "Tipo_Vehiculo_normalized",
        "Año_normalized",
    ]
    assert result[" Tipo Vehiculo "].tolist() == ["car"]
    assert result["Tipo_Vehiculo_normalized"].tolist() == ["car"]
    assert list(dataframe.columns) == [" Tipo Vehiculo ", "Año"]


def test_normalize_transformation_columns_supports_mapping_and_detects_collision() -> None:
    dataframe = pd.DataFrame({"Provincia": ["Madrid"], "key": [1]})

    result = normalize_transformation_columns(
        dataframe,
        column_mapping={"Provincia": "province_key"},
        suffix="_key",
    )
    assert result["province_key"].tolist() == ["Madrid"]

    with pytest.raises(ValueError, match="destination already exists"):
        normalize_transformation_columns(
            dataframe,
            column_mapping={"Provincia": "key"},
        )


def test_normalize_transformation_columns_rejects_missing_column() -> None:
    with pytest.raises(KeyError, match="column_mapping"):
        normalize_transformation_columns(
            pd.DataFrame({"value": [1]}),
            column_mapping={"missing": "missing_normalized"},
        )


def test_split_auxiliary_rows_partitions_rows_and_preserves_indices() -> None:
    dataframe = pd.DataFrame(
        {"label": ["Enero", "Total", "Porcentaje", None, "* Nota"], "value": [1, 2, 3, None, None]},
        index=[10, 11, 12, 13, 14],
    )

    result = split_auxiliary_rows(dataframe, identifier_column="label")

    assert isinstance(result, AuxiliaryRowsResult)
    assert result.observations.index.tolist() == [10]
    assert result.totals.index.tolist() == [11]
    assert result.percentages.index.tolist() == [12]
    assert result.auxiliary.index.tolist() == [13, 14]


def test_split_auxiliary_rows_rejects_missing_identifier() -> None:
    with pytest.raises(KeyError, match="identifier_column"):
        split_auxiliary_rows(pd.DataFrame({"value": [1]}), identifier_column="label")


def test_split_auxiliary_rows_normalizes_configured_labels() -> None:
    dataframe = pd.DataFrame(
        {"label": [" Total ", "total", "TOTAL", " Porcentaje "]}
    )

    result = split_auxiliary_rows(dataframe, identifier_column="label")

    assert result.totals.index.tolist() == [0, 1, 2]
    assert result.percentages.index.tolist() == [3]


def test_split_auxiliary_rows_prioritizes_explicit_total_and_percentage_labels() -> None:
    dataframe = pd.DataFrame(
        {"label": ["Nota Total", "* Porcentaje", "Nota libre", "* Nota"]}
    )

    result = split_auxiliary_rows(
        dataframe,
        identifier_column="label",
        total_labels=("Nota Total",),
        percentage_labels=("* Porcentaje",),
    )

    assert result.totals.index.tolist() == [0]
    assert result.percentages.index.tolist() == [1]
    assert result.auxiliary.index.tolist() == [2, 3]
    assert result.observations.empty


def test_split_auxiliary_rows_groups_are_exclusive_with_repeated_indices() -> None:
    dataframe = pd.DataFrame(
        {"label": ["Total", "Porcentaje", "* Nota", "Enero", None]},
        index=[1, 1, 2, 2, 3],
    )

    result = split_auxiliary_rows(dataframe, identifier_column="label")
    groups = [
        result.observations,
        result.totals,
        result.percentages,
        result.auxiliary,
    ]

    assert sum(len(group) for group in groups) == len(dataframe)
    assert sum(len(group) for group in groups if len(group)) == len(dataframe)
    assert result.totals.index.tolist() == [1]
    assert result.percentages.index.tolist() == [1]
    assert result.auxiliary.index.tolist() == [2, 3]
    assert result.observations.index.tolist() == [2]


def test_split_auxiliary_rows_rejects_conflicting_labels() -> None:
    with pytest.raises(ValueError, match="both total and percentage"):
        split_auxiliary_rows(
            pd.DataFrame({"label": ["Total"]}),
            identifier_column="label",
            total_labels=("Total",),
            percentage_labels=(" total ",),
        )


def test_split_auxiliary_rows_handles_empty_dataframe() -> None:
    result = split_auxiliary_rows(
        pd.DataFrame(columns=["label", "value"]),
        identifier_column="label",
    )

    assert result.observations.empty
    assert result.totals.empty
    assert result.percentages.empty
    assert result.auxiliary.empty


def test_convert_year_column_creates_nullable_integer_without_mutation() -> None:
    dataframe = pd.DataFrame({"Años": ["2024", None]})

    result = convert_year_column(dataframe, "Años")

    assert str(result["year"].dtype) == "Int64"
    assert result["year"].tolist() == [2024, pd.NA]
    assert dataframe["Años"].iloc[0] == "2024"
    assert pd.isna(dataframe["Años"].iloc[1])


def test_convert_year_column_coerces_invalid_values() -> None:
    result = convert_year_column(
        pd.DataFrame({"year_source": ["2024", "invalid"]}),
        "year_source",
        errors="coerce",
    )

    assert result["year"].tolist() == [2024, pd.NA]


def test_convert_year_column_rejects_invalid_and_boolean_values() -> None:
    with pytest.raises(ValueError, match="Unable to parse"):
        convert_year_column(
            pd.DataFrame({"year_source": ["invalid"]}),
            "year_source",
        )
    with pytest.raises(ValueError, match="Boolean values"):
        convert_year_column(pd.DataFrame({"year_source": [True]}), "year_source")


@pytest.mark.parametrize("errors", ["raise", "coerce"])
def test_convert_year_column_rejects_or_coerces_fractional_years(
    errors: str,
) -> None:
    dataframe = pd.DataFrame({"year_source": [2024.5]})

    if errors == "raise":
        with pytest.raises(ValueError, match="must be integers"):
            convert_year_column(dataframe, "year_source", errors=errors)
    else:
        result = convert_year_column(dataframe, "year_source", errors=errors)
        assert pd.isna(result["year"].iloc[0])


def test_convert_year_column_rejects_same_output_column() -> None:
    with pytest.raises(ValueError, match="must differ"):
        convert_year_column(
            pd.DataFrame({"year_source": [2024]}),
            "year_source",
            output_column="year_source",
        )


@pytest.mark.parametrize(
    ("month", "expected"),
    [("enero", 1), (" FEBRERO ", 2), ("DICIEMBRE", 12)],
)
def test_convert_month_column_converts_spanish_months(
    month: str,
    expected: int,
) -> None:
    result = convert_month_column(pd.DataFrame({"Mes": [month]}))

    assert result["month"].tolist() == [expected]


def test_convert_month_column_rejects_unknown_labels_and_coerces_them() -> None:
    dataframe = pd.DataFrame({"Mes": ["Total", "Enero"]})

    with pytest.raises(ValueError, match="Unknown month labels"):
        convert_month_column(dataframe, errors="raise")

    result = convert_month_column(dataframe, errors="coerce")
    assert pd.isna(result["month"].iloc[0])
    assert result["month"].iloc[1] == 1


def test_convert_month_column_rejects_same_output_column() -> None:
    with pytest.raises(ValueError, match="must differ"):
        convert_month_column(
            pd.DataFrame({"Mes": ["Enero"]}),
            output_column="Mes",
        )


def test_add_contextual_year_adds_year_without_mutation() -> None:
    dataframe = pd.DataFrame({"month": [1, 2]})

    result = add_contextual_year(dataframe, 2025)

    assert result["year"].tolist() == [2025, 2025]
    assert "year" not in dataframe.columns


@pytest.mark.parametrize("year", [True, False, "2025"])
def test_add_contextual_year_rejects_non_integer_year(year: object) -> None:
    with pytest.raises(TypeError, match="integer"):
        add_contextual_year(pd.DataFrame({"value": [1]}), year)  # type: ignore[arg-type]


def test_add_contextual_year_rejects_existing_output_column() -> None:
    with pytest.raises(ValueError, match="already exists"):
        add_contextual_year(pd.DataFrame({"year": [2025]}), 2025)


def test_reshape_year_columns_preserves_identifiers_values_and_index() -> None:
    dataframe = pd.DataFrame(
        {"Provincias": ["Madrid", "Total"], "1990": [10, 100], "1991": [11, 110]},
        index=[4, 5],
    )

    result = reshape_year_columns(
        dataframe,
        id_columns=["Provincias"],
        year_columns=["1990", "1991"],
    )

    assert result.index.tolist() == [4, 5, 4, 5]
    assert result["year"].tolist() == [1990, 1990, 1991, 1991]
    assert result["value"].tolist() == [10, 100, 11, 110]
    assert result["Provincias"].tolist() == ["Madrid", "Total", "Madrid", "Total"]
    pd.testing.assert_frame_equal(dataframe, pd.DataFrame(
        {"Provincias": ["Madrid", "Total"], "1990": [10, 100], "1991": [11, 110]},
        index=[4, 5],
    ))


def test_reshape_year_columns_rejects_missing_or_duplicate_year_columns() -> None:
    dataframe = pd.DataFrame({"id": ["a"], "1990": [1]})

    with pytest.raises(KeyError, match="year_columns"):
        reshape_year_columns(dataframe, id_columns=["id"], year_columns=["missing"])
    with pytest.raises(ValueError, match="must not contain duplicates"):
        reshape_year_columns(dataframe, id_columns=["id"], year_columns=["1990", "1990"])


def test_reshape_year_columns_rejects_fractional_year_column() -> None:
    dataframe = pd.DataFrame({"id": ["a"], "2024.5": [1]})

    with pytest.raises(ValueError, match="integer years"):
        reshape_year_columns(
            dataframe,
            id_columns=["id"],
            year_columns=["2024.5"],
        )


def test_reshape_year_columns_rejects_duplicate_identifier_columns() -> None:
    dataframe = pd.DataFrame({"id": ["a"], "1990": [1]})

    with pytest.raises(ValueError, match="id_columns must not contain duplicates"):
        reshape_year_columns(
            dataframe,
            id_columns=["id", "id"],
            year_columns=["1990"],
        )


def test_build_source_metadata_adds_traceability_without_mutation() -> None:
    dataframe = pd.DataFrame({"value": [1, 2]})

    result = build_source_metadata(
        dataframe,
        source_file="source.xlsx",
        source_sheet="data",
        dataset_group="A",
        unit="vehicles",
    )

    assert result["source_file"].tolist() == ["source.xlsx", "source.xlsx"]
    assert result["source_sheet"].tolist() == ["data", "data"]
    assert result["dataset_group"].tolist() == ["A", "A"]
    assert result["unit"].tolist() == ["vehicles", "vehicles"]
    assert list(dataframe.columns) == ["value"]


def test_build_source_metadata_rejects_collisions_and_empty_source() -> None:
    with pytest.raises(ValueError, match="must be non-empty"):
        build_source_metadata(
            pd.DataFrame({"value": [1]}),
            source_file="",
            source_sheet="data",
        )
    with pytest.raises(ValueError, match="already exist"):
        build_source_metadata(
            pd.DataFrame({"source_file": ["old"]}),
            source_file="source.xlsx",
            source_sheet="data",
        )
