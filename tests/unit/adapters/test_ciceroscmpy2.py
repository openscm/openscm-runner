"""
Unit tests for the CICEROSCMPY2 adapter (Phase F: FaIR-mirror shape).

These tests do not require ciceroscm 2.x to be installed and do not
run real CICERO-SCM simulations. They cover:

- adapter is importable and registered under the CICERO-SCM-PY2 name
- the adapter raises ImportError with a clear message if ciceroscm is
  not installed, or if a major version other than 2.x is installed
- the adapter rejects cfgs missing required sidecar keys (the
  scenarios-driven cfg surface: distribution_json + the file paths
  resolved by ``from_native_distribution``)
- ``from_native_distribution`` resolves canonical filenames inside
  the calibration directory and errors clearly on missing /
  ambiguous matches
- ``_resolve_protocol_spec`` reads ``protocol_*`` meta columns and
  defaults to the non-idealised settings when they're absent
- the adapter raises NotImplementedError when output_config is set

End-to-end runs against a real distribution JSON live in
``tests/integration/test_ciceroscmpy2.py`` and are gated on the
``CICEROSCMPY2_CALIBRATION_PATH`` env var.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from openscm_runner.adapters import CICEROSCMPY2, get_adapter, get_adapters_classes
from openscm_runner.adapters.ciceroscm_py2_adapter._compat import (
    HAS_CICEROSCM_PY2,
)

# Skip tests that instantiate CICEROSCMPY2() (which calls _init_model
# and imports the underlying ciceroscm package) when ciceroscm>=2
# isn't available. CI installs `--all-extras` but pip can only have
# one major version of `ciceroscm` at a time; `HAS_CICEROSCM_PY2` is
# False when ciceroscm 1.x is the resolved version, so the skip
# fires cleanly instead of raising the documented ImportError.
cicero_skip = pytest.mark.skipif(
    not HAS_CICEROSCM_PY2, reason="ciceroscm>=2 not installed",
)


# Required sidecar keys after the Phase F rewrite. Tests parametrised
# on this list verify the adapter rejects cfgs missing any one of them.
_REQUIRED_CFG_KEYS = (
    "distribution_json",
    "gaspam_file",
    "historical_em_file",
    "historical_conc_file",
    "nat_ch4_file",
    "nat_n2o_file",
    "rf_solar_file",
    "rf_volc_file",
    "rf_luc_file",
)


def _make_full_cfg(tmp_path) -> dict:
    """Build a cfg dict with all required keys pointing at tmp paths."""
    cfg = {"distribution_json": str(tmp_path / "distribution.json")}
    for key in _REQUIRED_CFG_KEYS:
        if key == "distribution_json":
            continue
        cfg[key] = str(tmp_path / f"{key}.txt")
    return cfg


# ---------------------------------------------------------------------------
# Registration + install detection
# ---------------------------------------------------------------------------


@cicero_skip
def test_ciceroscmpy2_is_registered():
    assert CICEROSCMPY2.model_name == "CICERO-SCM-PY2"
    assert CICEROSCMPY2 in get_adapters_classes()
    assert isinstance(get_adapter("CICERO-SCM-PY2"), CICEROSCMPY2)
    assert isinstance(get_adapter("cicero-scm-py2"), CICEROSCMPY2)


def test_ciceroscmpy2_raises_when_ciceroscm_not_installed():
    with patch(
        "openscm_runner.adapters.ciceroscm_py2_adapter."
        "ciceroscmpy2_adapter.HAS_CICEROSCM_PY2",
        False,
    ):
        with pytest.raises(ImportError, match="ciceroscm is not installed"):
            CICEROSCMPY2()


def test_ciceroscmpy2_raises_when_wrong_major_version():
    with patch(
        "openscm_runner.adapters.ciceroscm_py2_adapter."
        "ciceroscmpy2_adapter._ciceroscm_major_version",
        return_value=1,
    ):
        with pytest.raises(ImportError, match="requires >=2"):
            CICEROSCMPY2()


# ---------------------------------------------------------------------------
# cfg sidecar validation
# ---------------------------------------------------------------------------


@cicero_skip
def test_ciceroscmpy2_run_rejects_output_config(tmp_path):
    adapter = CICEROSCMPY2()
    with pytest.raises(NotImplementedError, match="output_config"):
        adapter._run(
            scenarios=None,
            cfgs=[_make_full_cfg(tmp_path)],
            output_variables=("Surface Air Temperature Change",),
            output_config=("foo",),
        )


@cicero_skip
@pytest.mark.parametrize("missing_key", _REQUIRED_CFG_KEYS)
def test_ciceroscmpy2_rejects_cfg_missing_required_sidecar(
    tmp_path, missing_key,
):
    """
    Each required sidecar key, dropped one at a time, must produce a
    ValueError whose message names the missing key. Catches the case
    where a caller hand-builds a cfg without using
    ``from_native_distribution`` and forgets one of the canonical
    file paths.
    """
    adapter = CICEROSCMPY2()
    cfg = _make_full_cfg(tmp_path)
    cfg.pop(missing_key)
    with pytest.raises(ValueError, match=missing_key):
        adapter._run(
            scenarios=None,
            cfgs=[cfg],
            output_variables=("Surface Air Temperature Change",),
            output_config=None,
        )


@cicero_skip
def test_ciceroscmpy2_rejects_missing_distribution_json(tmp_path):
    """
    After sidecar-key validation, the path is checked for existence
    so the user gets a clear FileNotFoundError rather than a JSON
    decode error from deep inside upstream.
    """
    adapter = CICEROSCMPY2()
    cfg = _make_full_cfg(tmp_path)
    # All paths are tmp_path / "<key>.txt" — none exist on disk. The
    # distribution_json existence check fires first.
    with pytest.raises(FileNotFoundError, match="distribution_json"):
        adapter._run(
            scenarios=None,
            cfgs=[cfg],
            output_variables=("Surface Air Temperature Change",),
            output_config=None,
        )


@cicero_skip
def test_ciceroscmpy2_rejects_empty_member_indices(tmp_path):
    """
    An explicit empty member_indices is almost certainly a user
    mistake; reject with a clear error rather than silently producing
    a zero-member run.
    """
    samples_json = tmp_path / "samples.json"
    samples_json.write_text("[{\"pamset_udm\": {}, \"pamset_emiconc\": {}}]")
    adapter = CICEROSCMPY2()
    cfg = _make_full_cfg(tmp_path)
    cfg["distribution_json"] = str(samples_json)
    cfg["member_indices"] = []
    with pytest.raises(ValueError, match="member_indices"):
        adapter._run(
            scenarios=None,
            cfgs=[cfg],
            output_variables=("Surface Air Temperature Change",),
            output_config=None,
        )


# ---------------------------------------------------------------------------
# from_native_distribution (canonical-filename resolution)
# ---------------------------------------------------------------------------


def _populate_minimal_calibration_dir(cal_dir) -> None:
    """
    Write empty files matching every canonical filename the adapter
    expects, plus a parameter posterior JSON. Test fixtures only;
    file contents are irrelevant because we don't dispatch a run.

    Canonical filenames match
    :data:`ciceroscmpy2_adapter._DEFAULT_CANONICAL_FILES` exactly.
    """
    from openscm_runner.adapters.ciceroscm_py2_adapter.ciceroscmpy2_adapter import (
        _DEFAULT_CANONICAL_FILES,
    )
    for fname in _DEFAULT_CANONICAL_FILES.values():
        (cal_dir / fname).write_text("")
    (cal_dir / "draw_samples_500.json").write_text("")


@cicero_skip
def test_from_native_distribution_resolves_canonical_files(tmp_path):
    """
    Given a calibration directory with canonical filenames, the
    classmethod resolves every required key without explicit
    overrides.
    """
    from openscm_runner.adapters.ciceroscm_py2_adapter.ciceroscmpy2_adapter import (
        _DEFAULT_CANONICAL_FILES,
    )

    cal_dir = tmp_path / "rcmip-march2026"
    cal_dir.mkdir()
    _populate_minimal_calibration_dir(cal_dir)

    adapter = CICEROSCMPY2.from_native_distribution(cal_dir)
    cfg = adapter.cfgs[0]

    for key, fname in _DEFAULT_CANONICAL_FILES.items():
        assert cfg[key].endswith(fname), (
            f"{key!r} should resolve to canonical filename "
            f"{fname!r}; got {cfg[key]!r}"
        )
    assert cfg["distribution_json"].endswith("draw_samples_500.json")
    # No optional keys after dropping rf_luc_constant_zero_file; the
    # idealised LUC zero is built at runtime as a DataFrame, not picked
    # up from a separate bundle file (mirrors FaIR's runtime mask).


def test_from_native_distribution_errors_on_missing_canonical_file(tmp_path):
    """
    Drop one required canonical file — the resolver names it in the
    error.
    """
    cal_dir = tmp_path / "rcmip-march2026"
    cal_dir.mkdir()
    _populate_minimal_calibration_dir(cal_dir)
    (cal_dir / "historical_em_gases_vupdate_2024_WMO_added_new.txt").unlink()

    with pytest.raises(FileNotFoundError, match="historical_em_file"):
        CICEROSCMPY2.from_native_distribution(cal_dir)


def test_from_native_distribution_errors_when_not_a_directory(tmp_path):
    not_a_dir = tmp_path / "not_a_dir"
    not_a_dir.write_text("")
    with pytest.raises(FileNotFoundError, match="not a directory"):
        CICEROSCMPY2.from_native_distribution(not_a_dir)


def test_from_native_distribution_errors_when_path_missing(tmp_path):
    missing = tmp_path / "missing_dir"
    with pytest.raises(FileNotFoundError, match="not found"):
        CICEROSCMPY2.from_native_distribution(missing)


@cicero_skip
def test_from_native_distribution_explicit_distribution_json_overrides_default(
    tmp_path,
):
    """
    When the caller passes ``distribution_json=...`` explicitly the
    classmethod uses it even if the directory has a glob match.
    """
    cal_dir = tmp_path / "rcmip-march2026"
    cal_dir.mkdir()
    _populate_minimal_calibration_dir(cal_dir)
    other_dist = tmp_path / "other_distribution.json"
    other_dist.write_text("")

    adapter = CICEROSCMPY2.from_native_distribution(
        cal_dir, distribution_json=other_dist,
    )
    assert adapter.cfgs[0]["distribution_json"] == str(other_dist)


@cicero_skip
def test_from_native_distribution_cfg_overrides_take_precedence(tmp_path):
    """
    Keyword arguments to ``from_native_distribution`` become cfg keys
    that override the canonical filename result.
    """
    cal_dir = tmp_path / "rcmip-march2026"
    cal_dir.mkdir()
    _populate_minimal_calibration_dir(cal_dir)
    custom_gaspam = tmp_path / "custom_gaspam.txt"
    custom_gaspam.write_text("")

    adapter = CICEROSCMPY2.from_native_distribution(
        cal_dir, gaspam_file=str(custom_gaspam),
    )
    assert adapter.cfgs[0]["gaspam_file"] == str(custom_gaspam)


@cicero_skip
def test_from_native_distribution_override_skips_missing_canonical_file(tmp_path):
    """
    Partial override: when the user supplies a cfg-level override for
    one of the canonical keys, the classmethod skips the existence
    check for that key. This lets callers mix-and-match (point cal_dir
    at a mostly-canonical bundle but substitute one file from
    elsewhere, e.g. testing an alternate historical_em baseline).
    """
    cal_dir = tmp_path / "partial_bundle"
    cal_dir.mkdir()
    _populate_minimal_calibration_dir(cal_dir)
    # Drop the historical_em file from the calibration directory.
    (cal_dir / "historical_em_gases_vupdate_2024_WMO_added_new.txt").unlink()

    custom_hist_em = tmp_path / "custom_historical_em.txt"
    custom_hist_em.write_text("")

    # Without the override, this errors (the canonical file is missing).
    with pytest.raises(FileNotFoundError, match="historical_em_file"):
        CICEROSCMPY2.from_native_distribution(cal_dir)

    # With the override, the missing-canonical check is skipped.
    adapter = CICEROSCMPY2.from_native_distribution(
        cal_dir, historical_em_file=str(custom_hist_em),
    )
    assert adapter.cfgs[0]["historical_em_file"] == str(custom_hist_em)
    # Other canonical files are still resolved from cal_dir.
    assert adapter.cfgs[0]["gaspam_file"].endswith(
        "gases_vupdate_2024_WMO_added_new.txt"
    )


# ---------------------------------------------------------------------------
# _resolve_protocol_spec (simplified surface after Phase F)
# ---------------------------------------------------------------------------


def test_resolve_protocol_spec_reads_metadata_cols_when_present():
    """
    The resolver reads ``protocol_natural_forcing`` and
    ``protocol_land_use_forcing`` from the scenarios ScmRun's meta
    columns. Returned dict shape is ``{natural_forcing,
    land_use_forcing}`` (no ``mode`` field after Phase F; driving
    mode is adapter-level, not per-scenario).
    """
    import pandas as pd
    from scmdata import ScmRun

    from openscm_runner.adapters.ciceroscm_py2_adapter.ciceroscmpy2_adapter import (
        _resolve_protocol_spec,
    )

    df = pd.DataFrame(
        [
            {"model": "m", "scenario": "esm-ssp245", "region": "World",
             "variable": "Emissions|CO2|MAGICC Fossil and Industrial",
             "unit": "Mt CO2/yr",
             "protocol_natural_forcing": "on",
             "protocol_land_use_forcing": "historical",
             "2020": 1.0},
            {"model": "m", "scenario": "esm-allGHG-piControl", "region": "World",
             "variable": "Emissions|CO2|MAGICC Fossil and Industrial",
             "unit": "Mt CO2/yr",
             "protocol_natural_forcing": "off",
             "protocol_land_use_forcing": "constant_zero",
             "2020": 0.0},
        ]
    )
    run = ScmRun(df)
    assert _resolve_protocol_spec(run, "esm-ssp245") == {
        "natural_forcing": "on",
        "land_use_forcing": "historical",
    }
    assert _resolve_protocol_spec(run, "esm-allGHG-piControl") == {
        "natural_forcing": "off",
        "land_use_forcing": "constant_zero",
    }


def test_resolve_protocol_spec_defaults_when_meta_missing():
    """
    No metadata on the ScmRun -> non-idealised defaults (no
    name-pattern fallback in Phase F; idealised users must set the
    meta columns explicitly or override at the cfg level).
    """
    import pandas as pd
    from scmdata import ScmRun

    from openscm_runner.adapters.ciceroscm_py2_adapter.ciceroscmpy2_adapter import (
        _resolve_protocol_spec,
    )

    df = pd.DataFrame([
        {"model": "m", "scenario": "ssp245", "region": "World",
         "variable": "Emissions|CO2|MAGICC Fossil and Industrial",
         "unit": "Mt CO2/yr", "2020": 1.0},
    ])
    run = ScmRun(df)

    assert _resolve_protocol_spec(run, "ssp245") == {
        "natural_forcing": "on",
        "land_use_forcing": "historical",
    }
    # esm-flat10 lacks metadata too; resolver returns the same
    # non-idealised default. Caller must opt into idealised treatment.
    assert _resolve_protocol_spec(run, "esm-flat10") == {
        "natural_forcing": "on",
        "land_use_forcing": "historical",
    }


def test_resolve_protocol_spec_handles_non_scmrun_input():
    """
    A stub object without ``.meta`` should default to non-idealised
    without raising.
    """
    from openscm_runner.adapters.ciceroscm_py2_adapter.ciceroscmpy2_adapter import (
        _resolve_protocol_spec,
    )

    class _Stub:
        pass

    spec = _resolve_protocol_spec(_Stub(), "esm-flat10")
    assert spec == {"natural_forcing": "on", "land_use_forcing": "historical"}


