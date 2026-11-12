"""Czeka na Ollamę, pobiera wagi modelu i dopiero wtedy uruchamia API."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

HOST = os.environ.get("OLLAMA_HOST_URL", "http://ollama:11434").rstrip("/")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")


def log(message: str) -> None:
    print(message, flush=True)


def wait_until_ready() -> None:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{HOST}/api/tags", timeout=5) as response:
                if response.status == 200:
                    log("Ollama odpowiada.")
                    return
        except Exception as exc:
            log(f"Czekam na Ollamę: {exc}")
        time.sleep(2)
    sys.exit("Ollama nie wystartowała w wyznaczonym czasie.")


def installed_models() -> set[str]:
    with urllib.request.urlopen(f"{HOST}/api/tags", timeout=30) as response:
        payload = json.load(response)
    return {item.get("name", "") for item in payload.get("models", [])}


def model_installed() -> bool:
    names = installed_models()
    return MODEL in names or f"{MODEL}:latest" in names


def pull_model() -> None:
    if model_installed():
        log(f"Model {MODEL} jest już pobrany.")
        return

    log(f"Pobieram model {MODEL}. To może potrwać kilka minut.")
    request = urllib.request.Request(
        f"{HOST}/api/pull",
        data=json.dumps({"name": MODEL, "stream": True}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=3600) as response:
            for raw in response:
                line = raw.decode().strip()
                if not line:
                    continue
                event = json.loads(line)
                if event.get("error"):
                    sys.exit(f"Pobieranie modelu nie powiodło się: {event['error']}")
                status = event.get("status", "")
                total = event.get("total")
                completed = event.get("completed")
                if total and completed is not None:
                    log(f"{status} {int(completed * 100 / total)}%")
                elif status:
                    log(status)
    except urllib.error.URLError as exc:
        sys.exit(f"Pobieranie modelu nie powiodło się: {exc}")

    if not model_installed():
        sys.exit(f"Po pobraniu brak modelu {MODEL}.")


def warmup() -> None:
    log(f"Ładuję {MODEL} do pamięci.")
    request = urllib.request.Request(
        f"{HOST}/api/generate",
        data=json.dumps(
            {
                "model": MODEL,
                "prompt": "ok",
                "stream": False,
                "keep_alive": "24h",
                "options": {"num_predict": 1, "num_ctx": 8192},
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            json.load(response)
    except Exception as exc:
        log(f"Rozgrzanie modelu nie powiodło się. Pierwsze żądanie załaduje wagi: {exc}")
        return
    log("Model jest załadowany. Startuję API.")


def main() -> None:
    wait_until_ready()
    pull_model()
    warmup()
    os.execvp(
        "uvicorn",
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    )


if __name__ == "__main__":
    main()
