#!/usr/bin/env python3
import argparse
import io
import json
import os
import random
import shutil
import tarfile
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import oci


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(dt: Optional[datetime] = None) -> str:
    base = dt or _utc_now()
    return base.strftime("%Y%m%dT%H%M%SZ")


def _state_non_empty(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def _build_client(config_path: str, profile: str):
    config = oci.config.from_file(config_path, profile)
    return oci.object_storage.ObjectStorageClient(config)


def _prefix_path(prefix: str) -> str:
    return prefix.strip("/").replace("//", "/")


def _make_object_name(prefix: str, kind: str, stamp: str) -> str:
    return f"{_prefix_path(prefix)}/{kind}/{stamp}.tar.gz"


def _latest_pointer_name(prefix: str, kind: str) -> str:
    return f"{_prefix_path(prefix)}/{kind}/latest.json"


def _tar_state(state_dir: Path) -> bytes:
    buff = io.BytesIO()
    with tarfile.open(fileobj=buff, mode="w:gz") as tar:
        tar.add(state_dir, arcname="state")
    buff.seek(0)
    return buff.read()


def _write_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        fh.write(data)


def _call_with_retries(args, action_name: str, func):
    """Retry wrapper for transient OCI/network failures."""
    attempts = max(int(getattr(args, "oci_max_retries", 3)), 0) + 1
    base_sleep = max(float(getattr(args, "oci_retry_base_seconds", 2.0)), 0.1)
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as exc:
            if attempt >= attempts:
                raise
            sleep_s = base_sleep * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
            print(
                f"[retry] action={action_name} attempt={attempt}/{attempts} "
                f"error={type(exc).__name__}: {exc}; sleeping={sleep_s:.2f}s"
            )
            time.sleep(sleep_s)


def _extract_tar(tar_path: Path, target_dir: Path):
    tmp_dir = target_dir.parent / f".restore-{_ts()}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, mode="r:gz") as tar:
        tar.extractall(path=tmp_dir)
    source = tmp_dir / "state"
    if not source.exists():
        raise RuntimeError("Snapshot corrupto: no contiene carpeta 'state'")
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.move(str(source), str(target_dir))
    shutil.rmtree(tmp_dir, ignore_errors=True)


def backup(args):
    state_dir = Path(args.state_dir)
    if not _state_non_empty(state_dir):
        print(f"[backup] estado vacio en {state_dir}, no se sube snapshot")
        return 0

    client = _call_with_retries(
        args,
        "build_client",
        lambda: _build_client(args.oci_config, args.oci_profile),
    )
    stamp = _ts()
    object_name = _make_object_name(args.prefix, args.kind, stamp)
    latest_name = _latest_pointer_name(args.prefix, args.kind)

    data = _tar_state(state_dir)
    _call_with_retries(
        args,
        f"put_object:{object_name}",
        lambda: client.put_object(args.namespace, args.bucket, object_name, data),
    )

    latest_payload = json.dumps(
        {"object": object_name, "timestamp": stamp, "kind": args.kind}
    ).encode("utf-8")
    _call_with_retries(
        args,
        f"put_object:{latest_name}",
        lambda: client.put_object(args.namespace, args.bucket, latest_name, latest_payload),
    )
    print(f"[backup] subido {object_name}")

    if args.retention_days > 0:
        prune(args, client=client)
    return 0


def _list_objects(client, namespace: str, bucket: str, prefix: str, args=None):
    next_start = None
    out = []
    while True:
        if args is None:
            res = client.list_objects(
                namespace,
                bucket,
                prefix=prefix,
                start=next_start,
                fields="name,timeCreated",
            ).data
        else:
            res = _call_with_retries(
                args,
                f"list_objects:{prefix}",
                lambda: client.list_objects(
                    namespace,
                    bucket,
                    prefix=prefix,
                    start=next_start,
                    fields="name,timeCreated",
                ).data,
            )
        out.extend(res.objects or [])
        if not res.next_start_with:
            break
        next_start = res.next_start_with
    return out


def _latest_snapshot_name_by_kind(client, args, kind: str) -> Optional[str]:
    kind_prefix = f"{_prefix_path(args.prefix)}/{kind}/"
    latest_ptr = _latest_pointer_name(args.prefix, kind)
    try:
        ptr = _call_with_retries(
            args,
            f"get_object:{latest_ptr}",
            lambda: client.get_object(args.namespace, args.bucket, latest_ptr).data.content,
        )
        payload = json.loads(ptr.decode("utf-8"))
        object_name = payload.get("object")
        if object_name:
            return object_name
    except Exception:
        pass

    candidates = []
    for obj in _list_objects(client, args.namespace, args.bucket, kind_prefix, args=args):
        if obj.name.endswith(".tar.gz"):
            candidates.append(obj)
    if not candidates:
        return None
    candidates.sort(key=lambda o: o.time_created or datetime.min.replace(tzinfo=timezone.utc))
    return candidates[-1].name


def _latest_snapshot_name(client, args) -> Optional[str]:
    for kind in (args.kind, "prestop", "daily"):
        name = _latest_snapshot_name_by_kind(client, args, kind)
        if name:
            return name
    return None


def restore(args):
    state_dir = Path(args.state_dir)
    if args.mode == "if-empty" and _state_non_empty(state_dir):
        print(f"[restore] estado ya inicializado en {state_dir}, se omite restore")
        return 0

    client = _call_with_retries(
        args,
        "build_client",
        lambda: _build_client(args.oci_config, args.oci_profile),
    )
    object_name = _latest_snapshot_name(client, args)
    if not object_name:
        print("[restore] no hay snapshots disponibles")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / "state.tar.gz"
        resp = _call_with_retries(
            args,
            f"get_object:{object_name}",
            lambda: client.get_object(args.namespace, args.bucket, object_name).data.content,
        )
        _write_bytes(tar_path, resp)
        _extract_tar(tar_path, state_dir)
    print(f"[restore] restaurado {object_name} en {state_dir}")
    return 0


def prune(args, client=None):
    own_client = client or _call_with_retries(
        args,
        "build_client",
        lambda: _build_client(args.oci_config, args.oci_profile),
    )
    cutoff = _utc_now() - timedelta(days=args.retention_days)
    root_prefix = f"{_prefix_path(args.prefix)}/{args.kind}/"
    objects = _list_objects(own_client, args.namespace, args.bucket, root_prefix, args=args)

    deleted = 0
    for obj in objects:
        if obj.name.endswith("latest.json"):
            continue
        created = obj.time_created
        if created and created < cutoff:
            _call_with_retries(
                args,
                f"delete_object:{obj.name}",
                lambda: own_client.delete_object(args.namespace, args.bucket, obj.name),
            )
            deleted += 1
    print(f"[prune] eliminados={deleted} cutoff={cutoff.isoformat()}")
    return 0


def loop(args):
    last_daily = ""
    interval = max(args.interval_minutes, 1) * 60
    daily_hour = max(0, min(args.daily_hour_utc, 23))
    daily_minute = max(0, min(args.daily_minute_utc, 59))

    while True:
        now = _utc_now()
        day_key = now.strftime("%Y-%m-%d")

        if (
            now.hour == daily_hour
            and now.minute >= daily_minute
            and last_daily != day_key
        ):
            daily_args = argparse.Namespace(**vars(args))
            daily_args.kind = "daily"
            try:
                backup(daily_args)
            except Exception as exc:
                print(f"[loop] daily backup failed: {type(exc).__name__}: {exc}")
            last_daily = day_key

        checkpoint_args = argparse.Namespace(**vars(args))
        checkpoint_args.kind = "checkpoint"
        try:
            backup(checkpoint_args)
        except Exception as exc:
            print(f"[loop] checkpoint backup failed: {type(exc).__name__}: {exc}")
        time.sleep(interval)


def build_parser():
    parser = argparse.ArgumentParser(description="Snapshot/restore de estado OpenClaw")
    parser.add_argument("--state-dir", default=os.getenv("OPENCLAW_STATE_DIR", "/home/node/.openclaw"))
    parser.add_argument("--namespace", default=os.getenv("OCI_BUCKET_NAMESPACE"))
    parser.add_argument("--bucket", default=os.getenv("OCI_BUCKET_NAME"))
    parser.add_argument("--prefix", default=os.getenv("OPENCLAW_BUCKET_PREFIX", "openclaw/snapshots"))
    parser.add_argument("--oci-config", default=os.getenv("OCI_CONFIG_PATH", "/opt/oci/config"))
    parser.add_argument("--oci-profile", default=os.getenv("OCI_PROFILE", "DEFAULT"))
    parser.add_argument(
        "--oci-max-retries",
        type=int,
        default=int(os.getenv("OPENCLAW_OCI_MAX_RETRIES", "3")),
    )
    parser.add_argument(
        "--oci-retry-base-seconds",
        type=float,
        default=float(os.getenv("OPENCLAW_OCI_RETRY_BASE_SECONDS", "2")),
    )
    parser.add_argument("--retention-days", type=int, default=int(os.getenv("OPENCLAW_RETENTION_DAYS", "10")))
    parser.add_argument("--kind", default="checkpoint", choices=["checkpoint", "daily", "prestop"])

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("backup", help="Crea y sube snapshot")

    restore_parser = sub.add_parser("restore", help="Restaura snapshot")
    restore_parser.add_argument("--mode", default=os.getenv("OPENCLAW_RESTORE_MODE", "if-empty"), choices=["if-empty", "force-latest"])

    sub.add_parser("prune", help="Aplica retencion")

    loop_parser = sub.add_parser("loop", help="Loop periodico de checkpoints y backup diario")
    loop_parser.add_argument(
        "--interval-minutes",
        type=int,
        default=int(os.getenv("OPENCLAW_CHECKPOINT_INTERVAL_MINUTES", "30")),
    )
    loop_parser.add_argument(
        "--daily-hour-utc",
        type=int,
        default=int(os.getenv("OPENCLAW_DAILY_HOUR_UTC", "3")),
    )
    loop_parser.add_argument(
        "--daily-minute-utc",
        type=int,
        default=int(os.getenv("OPENCLAW_DAILY_MINUTE_UTC", "0")),
    )
    return parser


def validate_common(args):
    required = [("namespace", args.namespace), ("bucket", args.bucket), ("oci-config", args.oci_config)]
    missing = [name for name, value in required if not value]
    if missing:
        raise RuntimeError(f"Faltan parametros requeridos: {', '.join(missing)}")


def main():
    parser = build_parser()
    args = parser.parse_args()
    validate_common(args)

    handlers = {
        "backup": backup,
        "restore": restore,
        "prune": prune,
        "loop": loop,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
