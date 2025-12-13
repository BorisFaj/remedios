import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from huggingface_hub import hf_hub_download


def wait_port(host: str, port: int, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(1)
    return False


def tail_log(path: Path, lines: int = 50) -> str:
    if not path.exists():
        return ""
    try:
        return "".join(path.read_text().splitlines(True)[-lines:])
    except Exception:
        return ""


def main() -> None:
    raw_model = os.getenv("WHISPER_MODEL", "/app/ggml-large-v3-turbo-q5_0.bin")
    model = Path(raw_model if raw_model.startswith("/") else f"/app/{raw_model}")
    if not model.is_file():
        model.parent.mkdir(parents=True, exist_ok=True)
        repo = os.getenv("WHISPER_MODEL_REPO", "ggerganov/whisper.cpp")
        sys.stdout.write(f"[launcher] Descargando modelo {model.name} de {repo} a {model}\n")
        sys.stdout.flush()
        path = hf_hub_download(
            repo_id=repo,
            filename=model.name,
            local_dir=str(model.parent),
            local_dir_use_symlinks=False,
        )
        src = Path(path)
        if src != model:
            model.write_bytes(src.read_bytes())
    if not model.is_file():
        sys.stderr.write(f"[launcher] Modelo no encontrado en {model}\n")
        sys.exit(1)

    port = int(os.getenv("WHISPER_SERVER_PORT", "9000"))
    lang = os.getenv("WHISPER_LANGUAGE", "es")
    threads = int(os.getenv("WHISPER_SERVER_THREADS", "2"))
    app_port = int(os.getenv("APP_PORT", "8001"))
    app_host = os.getenv("APP_HOST", "0.0.0.0")
    dump_dir = Path(os.getenv("WHISPER_DUMP", "/tmp/whisper-dump"))
    dump_dir.mkdir(parents=True, exist_ok=True)

    log_file = Path("/tmp/whisper-server.log")
    env = os.environ.copy()
    env["WHISPER_DUMP"] = str(dump_dir)

    server_cmd = [
        "/usr/local/bin/whisper-server",
        "--model",
        str(model),
        "--port",
        str(port),
        "--language",
        lang,
        "--host",
        "0.0.0.0",
        "--threads",
        str(threads),
    ]
    sys.stdout.write(f"[launcher] Arrancando whisper-server: {' '.join(server_cmd)}\n")
    sys.stdout.flush()

    log_handle = log_file.open("w")
    server = subprocess.Popen(server_cmd, stdout=log_handle, stderr=subprocess.STDOUT, env=env)

    if not wait_port("127.0.0.1", port, timeout=120):
        sys.stderr.write("[launcher] whisper-server no levantó el puerto\n")
        sys.stderr.write(tail_log(log_file))
        server.terminate()
        server.wait(timeout=5)
        sys.exit(1)

    sys.stdout.write(f"[launcher] whisper-server listo en puerto {port}\n")
    sys.stdout.flush()

    app_cmd = [
        sys.executable,
        "-m",
        "remedios.apis.audio.whispercpp.service",
        "--host",
        app_host,
        "--port",
        str(app_port),
    ]
    sys.stdout.write(f"[launcher] Arrancando audio_service: {' '.join(app_cmd)}\n")
    sys.stdout.flush()
    app = subprocess.Popen(app_cmd, env=env)

    def shutdown(signum, _frame):
        sys.stdout.write(f"[launcher] Recibida señal {signum}, apagando...\n")
        sys.stdout.flush()
        for proc in (app, server):
            proc.terminate()
        time.sleep(2)
        for proc in (app, server):
            if proc.poll() is None:
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    while True:
        if server.poll() is not None:
            sys.stderr.write("[launcher] whisper-server se ha detenido\n")
            sys.stderr.write(tail_log(log_file))
            app.terminate()
            try:
                app.wait(timeout=5)
            except subprocess.TimeoutExpired:
                app.kill()
            sys.exit(1)

        if app.poll() is not None:
            sys.stderr.write("[launcher] audio_service se ha detenido\n")
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
            sys.exit(1)

        time.sleep(1)


if __name__ == "__main__":
    main()
