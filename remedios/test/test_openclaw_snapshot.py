import argparse
import io
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from remedios.services.openclaw import openclaw_snapshot as snapshot


def test_call_with_retries_eventually_succeeds(monkeypatch):
    args = argparse.Namespace(oci_max_retries=2, oci_retry_base_seconds=0.01)
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("temporary failure")
        return "ok"

    monkeypatch.setattr(snapshot.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(snapshot.time, "sleep", lambda _: None)

    assert snapshot._call_with_retries(args, "put_object:test", flaky) == "ok"
    assert calls["count"] == 3


def test_loop_continues_after_backup_error(monkeypatch):
    fixed_now = datetime(2026, 2, 12, 3, 5, tzinfo=timezone.utc)
    args = argparse.Namespace(
        interval_minutes=1,
        daily_hour_utc=3,
        daily_minute_utc=0,
        kind="checkpoint",
    )

    calls = {"count": 0}

    def always_fail(_):
        calls["count"] += 1
        raise RuntimeError("dns glitch")

    monkeypatch.setattr(snapshot, "_utc_now", lambda: fixed_now)
    monkeypatch.setattr(snapshot, "backup", always_fail)

    def stop_loop(_):
        raise StopIteration

    monkeypatch.setattr(snapshot.time, "sleep", stop_loop)

    with pytest.raises(StopIteration):
        snapshot.loop(args)

    # daily + checkpoint were both attempted, despite failures.
    assert calls["count"] >= 2


def test_extract_tar_replaces_contents_inside_existing_mount(tmp_path: Path):
    target_dir = tmp_path / "state"
    target_dir.mkdir()
    (target_dir / "stale.txt").write_text("old", encoding="utf-8")
    (target_dir / "nested").mkdir()
    (target_dir / "nested" / "old.txt").write_text("old", encoding="utf-8")

    tar_path = tmp_path / "snapshot.tar.gz"
    with tarfile.open(tar_path, mode="w:gz") as tar:
        payload = b"fresh"
        info = tarfile.TarInfo("state/fresh.txt")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))

    snapshot._extract_tar(tar_path, target_dir)

    assert sorted(p.name for p in target_dir.iterdir()) == ["fresh.txt"]
    assert (target_dir / "fresh.txt").read_text(encoding="utf-8") == "fresh"
