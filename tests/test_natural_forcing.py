import pandas as pd
import pytest
from openscm_runner.natural_forcing import read_natural_forcing
from pandas.testing import assert_frame_equal


@pytest.fixture
def forcing(tmp_path):
    path = tmp_path / "forcing.csv"
    rows = [
        {
            "Scenario": scenario,
            "Region": "World",
            "Variable": f"Effective Radiative Forcing|Natural|{component}",
            "Unit": "W/m^2",
            "1750": first,
            "1751": second,
        }
        for scenario, component, first, second in [
            ("historical", "Solar", 0.0736213936942088, 0.0552751046317088),
            ("historical", "Volcanic", 0.200568231, 0.209059326),
            ("other", "Solar", 99.0, 99.0),
        ]
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_historical_rows_preserve_values_and_annual_alignment(forcing):
    expected = pd.DataFrame(
        {
            "Solar": [0.0736213936942088, 0.0552751046317088],
            "Volcanic": [0.200568231, 0.209059326],
        },
        index=pd.Index([1750, 1751], name="year"),
    )
    assert_frame_equal(read_natural_forcing(forcing, [1750, 1751]), expected)


@pytest.mark.parametrize("problem", ["duplicate", "missing", "unit", "nan"])
def test_invalid_historical_rows_are_rejected(forcing, problem):
    frame = pd.read_csv(forcing)
    if problem == "duplicate":
        frame = pd.concat([frame, frame.iloc[:1]])
    elif problem == "missing":
        frame = frame.iloc[1:]
    elif problem == "unit":
        frame.loc[0, "Unit"] = "K"
    else:
        frame.loc[0, "1750"] = float("nan")
    frame.to_csv(forcing, index=False)
    with pytest.raises(ValueError):
        read_natural_forcing(forcing, [1750, 1751])


@pytest.mark.parametrize("years", [[], [1751, 1750], [1750, 1752], [1752], [True]])
def test_invalid_or_unavailable_years_are_rejected(forcing, years):
    with pytest.raises(ValueError):
        read_natural_forcing(forcing, years)
