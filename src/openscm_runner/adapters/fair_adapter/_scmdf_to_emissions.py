"""
Conversion of :obj:`scmdata.ScmRun` into FaIR emissions :obj:`np.ndarray`.
"""
import datetime as dt
import os

import numpy as np
import pandas as pd
from scmdata import ScmRun


class HistoricalWorldEmms:
    """Historical world emissions class"""

    def __init__(self):
        self._loaded = False
        self._loaded_fair_history = False
        self._values = None
        self._values_fair_history = None

    @property
    def values(self):
        """Emissions values from historical joint with ssp245"""
        if not self._loaded:
            tmp = ScmRun(
                os.path.join(
                    os.path.dirname(__file__),
                    "rcmip-emissions-annual-means-v5-1-0-historical-ssp245.csv",
                ),
                lowercase_cols=True,
            )
            self._values = tmp.interpolate([dt.datetime(y, 1, 1) for y in tmp["year"]])

        self._loaded = True
        return self._values

    @property
    def values_fair_units(self):
        """Get values with FaIR's expected units, ignores species not used by FaIR"""
        if not self._loaded_fair_history:
            ssp_df_hist = self.values
            for variable in ssp_df_hist.get_unique_meta("variable"):
                in_unit = ssp_df_hist.filter(variable=variable).get_unique_meta(
                    "unit", no_duplicates=True
                )

                try:
                    _, fair_unit, context = _get_fair_col_unit_context(variable)
                except AssertionError:
                    # FaIR does not model the variable
                    if variable in [
                        "Emissions|F-Gases|HFC|HFC152a",
                        "Emissions|F-Gases|HFC|HFC236fa",
                        "Emissions|F-Gases|HFC|HFC365mfc",
                        "Emissions|F-Gases|NF3",
                        "Emissions|F-Gases|PFC|C3F8",
                        "Emissions|F-Gases|PFC|C4F10",
                        "Emissions|F-Gases|PFC|C5F12",
                        "Emissions|F-Gases|PFC|C7F16",
                        "Emissions|F-Gases|PFC|C8F18",
                        "Emissions|F-Gases|PFC|cC4F8",
                        "Emissions|F-Gases|SO2F2",
                        "Emissions|Montreal Gases|CH2Cl2",
                        "Emissions|Montreal Gases|CHCl3",
                    ]:
                        continue

                if in_unit != fair_unit:
                    ssp_df_hist = ssp_df_hist.convert_unit(
                        fair_unit, variable=variable, context=context
                    )

            self._values_fair_history = ssp_df_hist

        self._loaded_fair_history = True

        return self._values_fair_history


historical_world_emms_holder = HistoricalWorldEmms()


EMISSIONS_SPECIES_UNITS_CONTEXT = pd.DataFrame(
    (  # in fair 1.6, order is important
        ("|CO2|MAGICC Fossil and Industrial", "GtC / yr", None),
        ("|CO2|MAGICC AFOLU", "GtC / yr", None),
        ("|CH4", "MtCH4 / yr", None),
        ("|N2O", "MtN2ON / yr", None),
        ("|Sulfur", "MtS / yr", None),
        ("|CO", "MtCO / yr", None),
        ("|VOC", "MtNMVOC / yr", None),
        ("|NOx", "MtN / yr", "NOx_conversions"),
        ("|BC", "MtBC / yr", None),
        ("|OC", "MtOC / yr", None),
        ("|NH3", "MtNH3 / yr", None),
        ("|CF4", "ktCF4 / yr", None),
        ("|C2F6", "ktC2F6 / yr", None),
        ("|C6F14", "ktC6F14 / yr", None),
        ("|HFC23", "ktHFC23 / yr", None),
        ("|HFC32", "ktHFC32 / yr", None),
        ("|HFC4310mee", "ktHFC4310mee / yr", None),
        ("|HFC125", "ktHFC125 / yr", None),
        ("|HFC134a", "ktHFC134a / yr", None),
        ("|HFC143a", "ktHFC143a / yr", None),
        ("|HFC227ea", "ktHFC227ea / yr", None),
        ("|HFC245fa", "ktHFC245fa / yr", None),
        ("|SF6", "ktSF6 / yr", None),
        ("|CFC11", "ktCFC11 / yr", None),
        ("|CFC12", "ktCFC12 / yr", None),
        ("|CFC113", "ktCFC113 / yr", None),
        ("|CFC114", "ktCFC114 / yr", None),
        ("|CFC115", "ktCFC115 / yr", None),
        ("|CCl4", "ktCCl4 / yr", None),
        ("|CH3CCl3", "ktCH3CCl3 / yr", None),
        ("|HCFC22", "ktHCFC22 / yr", None),
        ("|HCFC141b", "ktHCFC141b / yr", None),
        ("|HCFC142b", "ktHCFC142b / yr", None),
        ("|Halon1211", "ktHalon1211 / yr", None),
        ("|Halon1202", "ktHalon1202 / yr", None),
        ("|Halon1301", "ktHalon1301 / yr", None),
        ("|Halon2402", "ktHalon2402 / yr", None),
        ("|CH3Br", "ktCH3Br / yr", None),
        ("|CH3Cl", "ktCH3Cl / yr", None),
    ),
    columns=["species", "in_unit", "context"],
)


def _get_fair_col_unit_context(variable):
    row = EMISSIONS_SPECIES_UNITS_CONTEXT["species"].apply(
        lambda x: variable.endswith(x)  # pylint: disable=W0108
    )
    in_unit = EMISSIONS_SPECIES_UNITS_CONTEXT[row]["in_unit"]
    if in_unit.shape[0] != 1:
        raise AssertionError(in_unit)

    fair_col = int(row[row].index.values) + 1  # first col is time
    in_unit = in_unit.iloc[0]
    context = EMISSIONS_SPECIES_UNITS_CONTEXT[row]["context"].iloc[0]

    return fair_col, in_unit, context


def scmdf_to_emissions(
    scmrun, startyear=1750, endyear=2100, scen_startyear=2015
):  # pylint: disable=R0914
    """
    Convert an :obj:`scmdata.ScmRun` into a FaIR emissions :obj:`np.ndarray`

    Interpolates linearly if required and fills in montreal gases based on ssp245.
    between non-consecutive years in the SCEN file. Fills in Montreal gases
    from SSP2-4.5.

    Parameters
    ----------
    scmrun : :obj:`ScmRun`
        :obj:`ScmRun` instance to convert to FaIR emissions array.
    startyear : int
        First year of output array to produce.
    endyear : int
        Last year of output array to produce.
    scen_startyear : int
        First year of the future scenario corresponding to :obj:`ScmRun`.

    Returns
    -------
    np.ndarray
        FaIR emissions array of size (nt, 40).

    Raises
    ------
    AssertionError
        If there is more than one model-scenario pair in the provided :obj:`ScmRun`.
    """
    n_cols = 40
    nt = endyear - startyear + 1

    data_out = np.ones((nt, n_cols)) * np.nan
    data_out[:, 0] = np.arange(startyear, endyear + 1)

    if scmrun.meta[["model", "scenario"]].drop_duplicates().shape[0] != 1:
        raise AssertionError("Should only have one model-scenario pair")

    scmrun = scmrun.interpolate(
        [dt.datetime(y, 1, 1) for y in range(scen_startyear, endyear + 1)]
    )

    years = scmrun["year"].values
    first_scenyear = years[0]
    first_scen_row = int(first_scenyear - startyear)

    # if correct units and interpolation were guaranteed we could do this for scenario too which is quicker
    hist_df = historical_world_emms_holder.values_fair_units.filter(
        year=range(startyear, scen_startyear)
    ).timeseries()

    future_df = historical_world_emms_holder.values_fair_units.filter(
        year=range(scen_startyear, endyear + 1)
    ).timeseries()

    for species in EMISSIONS_SPECIES_UNITS_CONTEXT["species"]:
        fair_col, _, _ = _get_fair_col_unit_context(species)

        hist_df_row = hist_df.index.get_level_values("variable").str.endswith(species)

        data_out[:first_scen_row, fair_col] = hist_df[hist_df_row].values.squeeze()

        future_df_row = future_df.index.get_level_values("variable").str.endswith(
            species
        )
        data_out[first_scen_row:, fair_col] = future_df[future_df_row].values.squeeze()

    for var_df in scmrun.groupby("variable"):
        variable = var_df.get_unique_meta("variable", no_duplicates=True)

        # Skip aggregate emissions and emissons not handled by FaIR
        if (
            variable.split("Emissions")[1]
            not in EMISSIONS_SPECIES_UNITS_CONTEXT.species.values
        ):
            continue

        in_unit = var_df.get_unique_meta("unit", no_duplicates=True)

        fair_col, fair_unit, context = _get_fair_col_unit_context(variable)

        if in_unit != fair_unit:
            var_df_fair_unit = var_df.convert_unit(fair_unit, context=context)
        else:
            var_df_fair_unit = var_df

        data_out[first_scen_row:, fair_col] = var_df_fair_unit.values.squeeze()

    return data_out
