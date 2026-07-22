"""Budowanie i wykonywanie rsync - flagi progresu i retry przy problemach z polaczeniem."""

import subprocess
import time
from pathlib import Path

from rsync_core.nas import ensure_nas


def rsync_supports_info_flags() -> bool:
    """Sprawdza, czy rsync wspiera flagi --info=progress2 i --info=name0."""
    try:
        result = subprocess.run(["rsync", "--version"], check=False, capture_output=True, text=True)
        if result.returncode != 0:
            return False
        first_line = (result.stdout.splitlines() or [""])[0].lower()
        return "version 3." in first_line or "version 4." in first_line
    except Exception:
        return False


def build_rsync_progress_flags() -> list[str]:
    """Zwraca kompatybilne flagi postepu dla zainstalowanej wersji rsync."""
    if rsync_supports_info_flags():
        return ["--progress", "--info=progress2", "--info=name0"]
    return ["--progress"]


def run_rsync_with_live_output(cmd: list[str], retry: bool = True, retry_delay: int = 10) -> bool:
    """Uruchamia rsync i przekazuje output bezposrednio do terminala.

    Args:
        retry: Jesli True, retry'uje w nieskonczonosc przy bledach polaczenia
        retry_delay: Czas oczekiwania miedzy probami (w sekundach)
    """
    attempt = 1
    while True:
        print(f"  ▶ {' '.join(cmd)} (prob {attempt})", flush=True)
        try:
            completed = subprocess.run(cmd, check=False, stdout=None, stderr=None)
            if completed.returncode == 0:
                print("  ✅ rsync zakonczyl pomyslnie", flush=True)
                return True

            # Kody bledow ktore wskazuja na problem z polaczeniem/siecia
            # i warto retry'owac:
            # 11 - error in file IO (pliki znikaja podczas transferu)
            # 12 - error in rsync protocol data stream (polaczenie przerwane)
            # 23 - partial transfer (niektore pliki nie zostaly przeniesione)
            # 24 - vanished source files (pliki zniknely podczas transferu)
            # 30 - timeout in data transfer
            retryable_codes = [11, 12, 23, 24, 30]

            if retry and completed.returncode in retryable_codes:
                print(f"  ⚠️ rsync zakonczyl sie kodem {completed.returncode} - prawdopodobnie problem z polaczeniem", flush=True)
                print(f"  🔄 Sprawdzam dostepnosc QNAP i probuje ponownie za {retry_delay}s...", flush=True)

                # Sprawdz czy NAS jest nadal dostepny
                target_path = Path("/Volumes/qnap")
                if not target_path.exists():
                    print("  ⚠️ QNAP niedostepny - probuje podlaczyc...", flush=True)
                    ensure_nas(target_path)
                else:
                    print(f"  ℹ️ QNAP dostepny, czekam {retry_delay}s i probuje ponownie...", flush=True)
                    time.sleep(retry_delay)

                attempt += 1
                continue

            # Inne kody bledow - nie retry'ujemy
            print(f"  ❌ rsync zakonczyl sie kodem: {completed.returncode}", flush=True)
            return False

        except Exception as exc:
            if retry:
                print(f"  ⚠️ Blad uruchamiania rsync: {exc}", flush=True)
                print(f"  🔄 Probujemy ponownie za {retry_delay}s...", flush=True)
                time.sleep(retry_delay)
                attempt += 1
                continue
            else:
                print(f"  ❌ Blad uruchamiania rsync: {exc}", flush=True)
                return False
