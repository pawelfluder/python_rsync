# Opis: clean_docker_v2.txt

import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SRC_ROOT = REPO_ROOT / "src"

sys.path.append(str(SRC_ROOT))

from rsync_core.validation import ask_yes_no_default_no

DOCKER_STARTUP_WAIT_SECONDS = 10


def docker_available() -> bool:
    """Sprawdza, czy binarka docker jest dostepna w PATH."""
    return shutil.which("docker") is not None


def run_docker(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Uruchamia polecenie docker i zwraca CompletedProcess (stdout/stderr jako tekst)."""
    cmd = ["docker", *args]
    print(f"  $ {' '.join(cmd)}", flush=True)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check,
    )


def print_command_output(result: subprocess.CompletedProcess[str]) -> None:
    """Wypisuje stdout/stderr z wyniku polecenia docker."""
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if stdout:
        print(stdout, flush=True)
    if stderr:
        print(stderr, flush=True)
    if result.returncode != 0:
        print(f"  ⚠️ Kod wyjscia: {result.returncode}", flush=True)


def list_ids(args: list[str]) -> list[str]:
    """Zwraca liste ID/nazw z wyjscia docker (po jednej na linie)."""
    result = run_docker(args)
    if result.returncode != 0:
        print_command_output(result)
        return []
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


def print_docker_summary(title: str) -> None:
    """Pokazuje aktualny stan Dockera (kontenery, obrazy, wolumeny, sieci, builder)."""
    print(f"\n📊 {title}", flush=True)

    print("\n🐳 Kontenery (docker ps -a):", flush=True)
    print_command_output(run_docker(["ps", "-a"]))

    print("\n🖼️ Obrazy (docker images -a):", flush=True)
    print_command_output(run_docker(["images", "-a"]))

    print("\n💾 Wolumeny (docker volume ls):", flush=True)
    print_command_output(run_docker(["volume", "ls"]))

    print("\n🌐 Sieci (docker network ls):", flush=True)
    print_command_output(run_docker(["network", "ls"]))

    print("\n🧱 Builder cache (docker builder du):", flush=True)
    print_command_output(run_docker(["builder", "du"]))


def confirm_full_cleanup() -> bool:
    """Podwojne potwierdzenie destrukcyjnego czyszczenia Dockera."""
    print(
        "\n⚠️ To usunie DOSLOWNIE WSZYSTKO z Dockera na tej maszynie:\n"
        "   - zatrzyma i usunie wszystkie kontenery\n"
        "   - usunie wszystkie obrazy\n"
        "   - usunie wszystkie wolumeny\n"
        "   - usunie nieuzywane sieci\n"
        "   - wyczysci caly builder cache\n",
        flush=True,
    )
    first = ask_yes_no_default_no(
        "➡️ Wyczyscic caly Docker? (t/n, domyslnie n): "
    )
    if not first:
        return False

    second = ask_yes_no_default_no(
        "   Potwierdzenie 2/2: na pewno usunac WSZYSTKO z Dockera? (t/n, domyslnie n): "
    )
    return second


def stop_all_containers() -> None:
    """Zatrzymuje wszystkie uruchomione kontenery."""
    print("\n🛑 Zatrzymuje wszystkie kontenery...", flush=True)
    running = list_ids(["ps", "-q"])
    if not running:
        print("  ℹ️ Brak uruchomionych kontenerow", flush=True)
        return
    print_command_output(run_docker(["stop", *running]))


def remove_all_containers() -> None:
    """Usuwa wszystkie kontenery (running i stopped)."""
    print("\n🗑️ Usuwam wszystkie kontenery...", flush=True)
    containers = list_ids(["ps", "-aq"])
    if not containers:
        print("  ℹ️ Brak kontenerow do usuniecia", flush=True)
        return
    print_command_output(run_docker(["rm", "-f", *containers]))


def remove_all_volumes() -> None:
    """Usuwa wszystkie wolumeny (jawnie, bo 'system prune --volumes' potrafi pomijac nazwane wolumeny)."""
    print("\n🗑️ Usuwam wszystkie wolumeny...", flush=True)
    volumes = list_ids(["volume", "ls", "-q"])
    if not volumes:
        print("  ℹ️ Brak wolumenow do usuniecia", flush=True)
        return
    print_command_output(run_docker(["volume", "rm", "-f", *volumes]))


def remove_all_images() -> None:
    """Usuwa wszystkie obrazy (jawnie, bo 'system prune -a' potrafi pomijac niektore obrazy)."""
    print("\n🗑️ Usuwam wszystkie obrazy...", flush=True)
    images = list_ids(["images", "-aq"])
    if not images:
        print("  ℹ️ Brak obrazow do usuniecia", flush=True)
        return
    print_command_output(run_docker(["rmi", "-f", *images]))


def prune_everything() -> None:
    """Pelne czyszczenie: system prune -a --volumes + volume/image rm (jawnie) + builder prune -a."""
    print("\n🧹 docker system prune -a --volumes --force...", flush=True)
    print_command_output(run_docker(["system", "prune", "-a", "--volumes", "--force"]))

    remove_all_volumes()
    remove_all_images()

    print("\n🧱 docker builder prune -a --force...", flush=True)
    print_command_output(run_docker(["builder", "prune", "-a", "--force"]))


def docker_daemon_responding() -> subprocess.CompletedProcess[str]:
    """Sprawdza, czy docker daemon odpowiada (docker version)."""
    return run_docker(["version", "--format", "{{.Server.Version}}"])


def try_start_docker_desktop() -> None:
    """Probuje uruchomic aplikacje Docker Desktop na macOS (open -a Docker)."""
    print("\n🚀 Probuje uruchomic aplikacje Docker Desktop...", flush=True)
    result = subprocess.run(
        ["open", "-a", "Docker"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print_command_output(result)
        return
    print(f"  ⏳ Czekam {DOCKER_STARTUP_WAIT_SECONDS}s na uruchomienie daemona...", flush=True)
    time.sleep(DOCKER_STARTUP_WAIT_SECONDS)


def ensure_docker_daemon_running() -> subprocess.CompletedProcess[str]:
    """Sprawdza daemon; jesli nie odpowiada, probuje uruchomic Docker Desktop i sprawdza ponownie."""
    version = docker_daemon_responding()
    if version.returncode == 0:
        return version

    print("⚠️ Docker daemon nie odpowiada - probuje uruchomic Docker Desktop.", flush=True)
    try_start_docker_desktop()

    return docker_daemon_responding()


def main() -> None:
    """Glowna funkcja skryptu - pelne czyszczenie Dockera po potwierdzeniu."""
    print("🐳 clean_docker_v2 - pelne czyszczenie Dockera", flush=True)

    if not docker_available():
        print("❌ Nie znaleziono polecenia 'docker' w PATH.", flush=True)
        sys.exit(1)

    version = ensure_docker_daemon_running()
    if version.returncode != 0:
        print("❌ Docker daemon nie odpowiada. Uruchom Dockera i sprobuj ponownie.", flush=True)
        print_command_output(version)
        sys.exit(1)

    print(f"✅ Docker daemon OK (server { (version.stdout or '').strip() or '?' })", flush=True)
    print_docker_summary("Stan przed czyszczeniem")

    if not confirm_full_cleanup():
        print("ℹ️ Anulowano na zyczenie uzytkownika - nic nie usunieto.", flush=True)
        return

    stop_all_containers()
    remove_all_containers()
    prune_everything()

    print_docker_summary("Stan po czyszczeniu")
    print("\n✅ Czyszczenie Dockera zakonczone.", flush=True)


if __name__ == "__main__":
    main()
