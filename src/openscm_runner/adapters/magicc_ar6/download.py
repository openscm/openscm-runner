"""
Downloading MAGICC v7.5.3 and the AR6 probabilistic distribution from magicc.org
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from openscm_runner.optional_dependencies import import_optional_dependency

DOWNLOAD_URL = "https://magicc.org/api/download?type={type}&token={token}"
"""URL to download from (get a token by logging in at magicc.org)"""


@dataclass(frozen=True)
class MAGICCDownload:
    """Something to download from magicc.org"""

    type: str
    """magicc.org's name for it (the `type` in the URL)"""

    archive_name: str
    """Name of the archive we save"""

    archive_sha256: str
    """sha256 of the archive"""

    extract_dir: str
    """Directory to extract the archive into (relative to the archive)"""


# If magicc.org starts serving something else under these names
# (e.g. a newer MAGICC), the hash check fails rather than silently changing things.
# The archives are .tar.gz files, but they are served with `Content-Encoding: gzip`,
# so requests decompresses them as they download: we save (and hash) the .tar.
MAGICC_V753_DOWNLOAD = MAGICCDownload(
    type="MAGICC7",
    archive_name="magicc-v7.5.3.tar",
    archive_sha256="948f9fdc37d91d01c93df8f147f4f125db9668afef55710eb84f6db7ae2ee75b",
    extract_dir="magicc-v7.5.3",
)
"""MAGICC v7.5.3"""

AR6_PROBABILISTIC_DISTRIBUTION_DOWNLOAD = MAGICCDownload(
    type="AR6_PROBABILISTIC",
    archive_name="magicc-ar6-0fd0f62-f023edb-drawnset.tar",
    archive_sha256="b289ca718cbc6d9dc06d95a389fb515c46eacedafcfe09aa0dca8d35c50767a8",
    extract_dir="magicc-ar6-0fd0f62-f023edb-drawnset",
)
"""The AR6 probabilistic distribution"""

AR6_PROBABILISTIC_DISTRIBUTION_FILE = "0fd0f62-derived-metrics-id-f023edb-drawnset.json"
"""Name of the AR6 probabilistic distribution file in its archive"""


class MAGICCDownloadError(RuntimeError):
    """Raised when downloading from magicc.org fails"""


@dataclass(frozen=True)
class MAGICCAR6AdapterPieces:
    """Where the pieces the MAGICC AR6 adapters need are"""

    magicc_root: Path
    """Root of the MAGICC v7.5.3 installation (with `bin` and `run` directories)"""

    ar6_probabilistic_distribution: Path
    """Path to the AR6 probabilistic distribution"""


def download(item: MAGICCDownload, *, token: str, cache_dir: Path) -> Path:
    """
    Download and extract something from magicc.org

    Nothing is downloaded if the archive is already in `cache_dir`
    (and its hash matches).

    Parameters
    ----------
    item
        What to download

    token
        magicc.org download token

    cache_dir
        Directory to save the archive in

    Returns
    -------
    :
        Directory the archive was extracted into

    Raises
    ------
    MAGICCDownloadError
        The download failed (e.g. the token is invalid)
    """
    pooch = import_optional_dependency(
        "pooch", requirement="pooch", callable_name="download", extra="magicc-ar6"
    )
    requests = import_optional_dependency(
        "requests", requirement="requests", callable_name="download", extra="magicc-ar6"
    )

    # The URL includes the token, so keep it out of pooch's logs
    logger = pooch.get_logger()
    level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        pooch.retrieve(
            DOWNLOAD_URL.format(type=item.type, token=token),
            known_hash=f"sha256:{item.archive_sha256}",
            fname=item.archive_name,
            path=cache_dir,
            processor=pooch.Untar(extract_dir=item.extract_dir),
            # magicc.org can be slow to respond
            downloader=pooch.HTTPDownloader(timeout=60),
        )
    except requests.RequestException as exc:
        # requests' messages include the URL (and so the token),
        # so we don't pass them on (and don't chain the exception)
        response = getattr(exc, "response", None)
        details = (
            f"HTTP status {response.status_code}: {response.text[:200]}"
            if response is not None
            else type(exc).__name__
        )
        msg = f"Downloading {item.type} from magicc.org failed ({details})"
        raise MAGICCDownloadError(msg) from None
    finally:
        logger.setLevel(level)

    return Path(cache_dir) / item.extract_dir


def get_magicc_ar6_adapter_pieces(
    token: str, *, cache_dir: Path | None = None
) -> MAGICCAR6AdapterPieces:
    """
    Get the pieces the MAGICC AR6 adapters need, downloading them from magicc.org

    Parameters
    ----------
    token
        magicc.org download token

    cache_dir
        Directory to save the downloads in.
        If `None`, the operating system's cache directory for openscm-runner.

    Returns
    -------
    :
        Where the pieces are
    """
    if cache_dir is None:
        pooch = import_optional_dependency(
            "pooch",
            requirement="pooch",
            callable_name="get_magicc_ar6_adapter_pieces",
            extra="magicc-ar6",
        )
        cache_dir = Path(pooch.os_cache("openscm-runner")) / "magicc-ar6"

    magicc_root = download(MAGICC_V753_DOWNLOAD, token=token, cache_dir=cache_dir)
    distribution_dir = download(
        AR6_PROBABILISTIC_DISTRIBUTION_DOWNLOAD, token=token, cache_dir=cache_dir
    )

    return MAGICCAR6AdapterPieces(
        magicc_root=magicc_root,
        ar6_probabilistic_distribution=distribution_dir
        / AR6_PROBABILISTIC_DISTRIBUTION_FILE,
    )
