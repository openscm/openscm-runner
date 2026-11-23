"""
Unit tests of downloading the MAGICC AR6 adapter pieces (no network)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pooch
import pytest
import requests

from openscm_runner.adapters.magicc_ar6 import download as download_module
from openscm_runner.adapters.magicc_ar6.download import (
    MAGICC_V753_DOWNLOAD,
    MAGICCAR6AdapterPieces,
    MAGICCDownloadError,
    download,
    get_magicc_ar6_adapter_pieces,
)

# These are the MAGICC AR6 adapters' tests (see docs/testing.md)
pytestmark = pytest.mark.magicc_ar6

TOKEN = "not-a-real-token"  # noqa: S105


def raise_http_error(url: str, *args: Any, **kwargs: Any) -> None:
    response = requests.Response()
    response.status_code = 400
    response._content = b'{"error":"Invalid token"}'
    # Like requests' own messages, includes the URL
    raise requests.HTTPError(f"400 Client Error for url: {url}", response=response)  # noqa: TRY003


def raise_connection_error(url: str, *args: Any, **kwargs: Any) -> None:
    raise requests.ConnectionError(f"Max retries exceeded with url: {url}")  # noqa: TRY003


@pytest.mark.parametrize(
    "retrieve, match",
    (
        pytest.param(raise_http_error, "HTTP status 400", id="http-error"),
        pytest.param(raise_connection_error, "ConnectionError", id="connection-error"),
    ),
)
def test_download_errors_dont_include_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retrieve: Any, match: str
) -> None:
    monkeypatch.setattr(pooch, "retrieve", retrieve)

    with pytest.raises(MAGICCDownloadError, match=match) as excinfo:
        download(MAGICC_V753_DOWNLOAD, token=TOKEN, cache_dir=tmp_path)

    assert TOKEN not in str(excinfo.value)
    # Not chained either (tracebacks would show the original message)
    assert excinfo.value.__suppress_context__


def test_download_keeps_url_out_of_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def retrieve(url: str, *args: Any, **kwargs: Any) -> None:
        pooch.get_logger().info("Downloading from %s", url)

    monkeypatch.setattr(pooch, "retrieve", retrieve)
    level = pooch.get_logger().level

    with caplog.at_level("INFO", logger="pooch"):
        download(MAGICC_V753_DOWNLOAD, token=TOKEN, cache_dir=tmp_path)

    assert TOKEN not in caplog.text
    # The logger is put back as it was
    assert pooch.get_logger().level == level


def test_default_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    downloaded_to = []

    def fake_download(item: Any, *, token: str, cache_dir: Path) -> Path:
        downloaded_to.append(cache_dir)
        return cache_dir / item.extract_dir

    monkeypatch.setattr(pooch, "os_cache", lambda name: tmp_path / name)
    monkeypatch.setattr(download_module, "download", fake_download)

    res = get_magicc_ar6_adapter_pieces(TOKEN)

    expected_dir = tmp_path / "openscm-runner" / "magicc-ar6"
    assert downloaded_to == [expected_dir, expected_dir]
    assert res == MAGICCAR6AdapterPieces(
        magicc_root=expected_dir / "magicc-v7.5.3",
        ar6_probabilistic_distribution=expected_dir
        / "magicc-ar6-0fd0f62-f023edb-drawnset"
        / "0fd0f62-derived-metrics-id-f023edb-drawnset.json",
    )


def test_given_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    downloaded_to = []

    def fake_download(item: Any, *, token: str, cache_dir: Path) -> Path:
        downloaded_to.append(cache_dir)
        return cache_dir / item.extract_dir

    def os_cache(name: str) -> Path:
        raise AssertionError("The default cache directory shouldn't be used")  # noqa: TRY003

    monkeypatch.setattr(pooch, "os_cache", os_cache)
    monkeypatch.setattr(download_module, "download", fake_download)

    res = get_magicc_ar6_adapter_pieces(TOKEN, cache_dir=tmp_path)

    assert downloaded_to == [tmp_path, tmp_path]
    assert res.magicc_root == tmp_path / "magicc-v7.5.3"
