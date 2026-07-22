import subprocess
import time
from pathlib import Path


NAS_PATH = Path("/Volumes/qnap")
NAS_MOUNT_PATH = "//pawelfluder@100.117.139.83/qnap"
NAS_RETRY_DELAY = 10


def ensure_nas_available(
    nas_path: Path = NAS_PATH,
    mount_path: str = NAS_MOUNT_PATH,
    retry_delay: int = NAS_RETRY_DELAY,
) -> None:
    """Blokuje do czasu uzyskania dostępu do NAS."""
    attempt = 1
    while True:
        if nas_path.exists():
            if attempt > 1:
                print(f"✓ NAS znowu dostępny: {nas_path}")
            return

        print(f"⚠ NAS niedostępny (próba {attempt}): {nas_path}")
        try:
            subprocess.run(
                ["open", f"smb://{mount_path.lstrip('/')}"],
                check=False,
                capture_output=True,
                timeout=15,
            )
            print("  Wysłano żądanie montowania w Finderze.")
        except Exception as exc:
            print(f"  Błąd przy montowaniu: {exc}")

        print(f"  Czekam {retry_delay}s i próbuję ponownie...")
        time.sleep(retry_delay)
        attempt += 1


def ensure_nas_readable(file_path: Path) -> None:
    """Blokuje do czasu, aż plik na NAS będzie dostępny do odczytu."""
    attempt = 1
    while True:
        try:
            if file_path.exists():
                file_path.stat().st_size
                return
        except (OSError, FileNotFoundError):
            pass

        print(f"⚠ Plik niedostępny (próba {attempt}): {file_path}")
        ensure_nas_available()
        print(f"  Czekam {NAS_RETRY_DELAY}s na pojawienie się pliku...")
        time.sleep(NAS_RETRY_DELAY)
        attempt += 1
