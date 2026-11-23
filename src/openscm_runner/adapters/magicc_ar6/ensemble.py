"""
The AR6 probabilistic distribution (ensemble) for MAGICC
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .running import EnsembleMember

AR6_PROBABILISTIC_DISTRIBUTION_SHA256 = (
    "7f85ee0cae35e330612499e44c31493cc437d79e789462aae010943788bc9c4f"
)
"""
sha256 of the AR6 probabilistic distribution file, as downloaded from magicc.org

(`0fd0f62-derived-metrics-id-f023edb-drawnset.json`)
"""

AR6_N_ENSEMBLE_MEMBERS = 600
"""Number of members in the AR6 probabilistic distribution"""


def load_ar6_ensemble(path: Path) -> tuple[EnsembleMember, ...]:
    """
    Load the AR6 probabilistic distribution

    Parameters
    ----------
    path
        Path to the distribution's JSON file

    Returns
    -------
    :
        Ensemble members.
        The IDs are the distribution's `paraset_id`s.
        The configuration keys are lower case.

    Raises
    ------
    ValueError
        The file isn't the AR6 probabilistic distribution
        (its hash doesn't match)
    """
    contents = Path(path).read_bytes()
    sha256 = hashlib.sha256(contents).hexdigest()
    if sha256 != AR6_PROBABILISTIC_DISTRIBUTION_SHA256:
        msg = (
            f"{path} isn't the AR6 probabilistic distribution: its sha256 is "
            f"{sha256}, expected {AR6_PROBABILISTIC_DISTRIBUTION_SHA256}"
        )
        raise ValueError(msg)

    configurations = json.loads(contents)["configurations"]
    if len(configurations) != AR6_N_ENSEMBLE_MEMBERS:  # pragma: no cover
        # Can't happen given the hash check
        raise AssertionError(len(configurations))

    return tuple(
        EnsembleMember(
            id=str(c["paraset_id"]),
            configuration={k.lower(): v for k, v in c["nml_allcfgs"].items()},
        )
        for c in configurations
    )
