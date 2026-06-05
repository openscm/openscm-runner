"""
Loader for a FaIR 2.x native calibration bundle.

A *calibration bundle* is a directory of CSVs as published with the
AR7-relevant FaIR 2.x calibration on Zenodo (e.g.
https://zenodo.org/records/18828694). The bundle contains a parameter
posterior, per-species configuration, and several scale factors --
all model-specific calibration that has no canonical RCMIP3
equivalent. Scenario inputs (emissions, concentrations) and per-
scenario forcings (solar, volcanic, land-use albedo, irrigation) come
from the canonical RCMIP3 Zenodo bundle (record 20430630) instead,
loaded separately via the adapter's ``rcmip3_bundle_path``.

Both the parameter posterior and species_configs file are strictly
required; the optional scale-factor / lifetime tuning files are
returned as ``None`` when absent so the adapter can decide whether
to fall back to FaIR's defaults.

This module deliberately knows nothing about the :class:`fair.FAIR`
object itself; it just locates and reads the bundle files. The adapter
in :mod:`.fair2_adapter` does the FAIR setup.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)


# Filenames as published on Zenodo record 18828694 (the AR7-relevant
# Smith calibration). Scenario inputs and forcings come from RCMIP3
# (Zenodo 20430630) -- they are NOT listed here.
_BUNDLE_FILES = {
    "parameters": "calibrated_constrained_parameters.csv",
    "species_configs": "species_configs_properties.csv",
    "landuse_scale_factor": "landuse_scale_factor.csv",
    "lapsi_scale_factor": "lapsi_scale_factor.csv",
    "ch4_lifetime": "CH4_lifetime.csv",
    "warming_baselines": "warming_baselines.csv",
}

# These must exist for the loader to consider the bundle usable.
_REQUIRED = ("parameters", "species_configs")


class NativeFairCalibration:
    """
    A FaIR 2.x calibration bundle on disk.

    Parameters
    ----------
    path
        Directory containing the bundle CSVs (e.g. an extracted
        download from the Zenodo record).

    Raises
    ------
    FileNotFoundError
        ``path`` does not exist, or one of the required bundle files
        (parameter posterior, species configs) is missing.
    """

    FILES = _BUNDLE_FILES

    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(
                f"FaIR 2.x calibration bundle not found at {self.path}"
            )
        if not self.path.is_dir():
            raise FileNotFoundError(
                f"FaIR 2.x calibration bundle path is not a directory: {self.path}"
            )
        missing = [
            key for key in _REQUIRED if not (self.path / self.FILES[key]).exists()
        ]
        if missing:
            missing_files = [self.FILES[key] for key in missing]
            raise FileNotFoundError(
                "FaIR 2.x calibration bundle is missing required files: "
                f"{missing_files} (looking in {self.path})"
            )

        self._parameters_cache: pd.DataFrame | None = None

    def file(self, key: str) -> Path | None:
        """
        Path to a named bundle file, or ``None`` if the file is absent.

        Use ``key`` from :attr:`FILES`.
        """
        candidate = self.path / self.FILES[key]
        return candidate if candidate.exists() else None

    @property
    def parameters(self) -> pd.DataFrame:
        """
        The calibrated parameter posterior, one row per ensemble member.

        The first column of the CSV is the per-member config label
        (typically a random seed). We read it as the DataFrame index
        so the index matches what :meth:`fair.FAIR.override_defaults`
        expects: it iterates ``self.configs`` and looks each one up as
        a row label in this DataFrame. Cached on first access.
        """
        if self._parameters_cache is None:
            self._parameters_cache = pd.read_csv(
                self.file("parameters"), index_col=0
            )
        return self._parameters_cache

    @property
    def n_members(self) -> int:
        """Number of ensemble members in the parameter posterior."""
        return len(self.parameters)

    def select_members(self, member_indices=None) -> pd.DataFrame:
        """
        Return a subset of :attr:`parameters` by zero-based row index.

        ``member_indices=None`` returns the full posterior. Otherwise
        ``member_indices`` is any sequence of ``int`` accepted by
        :meth:`pandas.DataFrame.iloc`.
        """
        params = self.parameters
        if member_indices is None:
            return params
        selected = params.iloc[list(member_indices)]
        if selected.empty:
            raise ValueError(
                f"member_indices selected zero members out of {len(params)} "
                "available; check the indices"
            )
        return selected
