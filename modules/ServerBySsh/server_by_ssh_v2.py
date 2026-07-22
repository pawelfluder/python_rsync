import getpass
import paramiko
import os
import sys
from pathlib import Path

# repo root resolution (two paths up) – consistent with other scripts
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.append(str(REPO_ROOT))

def _read_env_var(env_path: Path, key: str) -> str | None:
    """Minimal .env reader (KEY=VALUE, ignores comments and blanks)."""
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() != key:
                continue
            value = v.strip().strip('"').strip("'")
            return value or None
    except FileNotFoundError:
        return None
    return None

def _get_config_value(key: str, required: bool = True, default: str | None = None) -> str | None:
    """Odczytuje wartość konfiguracyjną z .env (REPO_ROOT/.env), potem ze zmiennej środowiskowej."""
    env_path = REPO_ROOT / ".env"
    value = _read_env_var(env_path, key) or os.getenv(key) or default
    if required and not value:
        raise RuntimeError(f"Brak konfiguracji '{key}' (ustaw w .env lub jako zmienną środowiskową).")
    return value

def get_server_host() -> str:
    return _get_config_value("server_host")

def get_server_port() -> int:
    return int(_get_config_value("server_port", required=False, default="22"))

def get_server_username() -> str:
    return _get_config_value("server_username")

def get_server_password():
    """
    Pobiera hasło do serwera.

    Priorytet:
    1) .env w katalogu repo (REPO_ROOT/.env) i zmienna `server_password`
    2) zmienna środowiskowa `server_password`
    3) prompt (getpass)
    """
    env_path = REPO_ROOT / ".env"
    password = _read_env_var(env_path, "server_password")
    if password:
        return password

    password = os.getenv("server_password")
    if password:
        return password

    return getpass.getpass(prompt="🔑 Podaj hasło do serwera: ")

def run_remote_command_with_password(password, remote_dir, command):
    """
    Wykonuje zdalne polecenie na serwerze z podanym hasłem.

    :param password: Hasło użytkownika do połączenia SSH.
    :param remote_dir: Ścieżka, do której należy przejść przed wykonaniem polecenia.
    :param command: Polecenie do wykonania na serwerze.
    :return: Wynik polecenia jako string lub None w przypadku błędu.
    """
    # konfiguracja SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # połączenie
        ssh.connect(get_server_host(), port=get_server_port(), username=get_server_username(), password=password)

        # przygotowanie pełnego polecenia
        full_command = f"cd {remote_dir} && {command}"

        # wykonanie polecenia
        stdin, stdout, stderr = ssh.exec_command(full_command)

        # sprawdzenie błędów
        error_output = stderr.read().decode()
        if error_output:
            print("❌ Błąd podczas wykonywania polecenia:", error_output)
            return None

        # zwrócenie wyniku
        return stdout.read().decode()

    finally:
        ssh.close()

def run_remote_command(remote_dir, command):
    """
    Wykonuje zdalne polecenie na serwerze z podanym hasłem.

    :param password: Hasło użytkownika do połączenia SSH.
    :param remote_dir: Ścieżka, do której należy przejść przed wykonaniem polecenia.
    :param command: Polecenie do wykonania na serwerze.
    :return: Wynik polecenia jako string lub None w przypadku błędu.
    """
    # konfiguracja SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    password = get_server_password()

    try:
        # połączenie
        ssh.connect(get_server_host(), port=get_server_port(), username=get_server_username(), password=password)

        # przygotowanie pełnego polecenia
        full_command = f"cd {remote_dir} && {command}"

        # wykonanie polecenia
        stdin, stdout, stderr = ssh.exec_command(full_command)

        # sprawdzenie błędów
        error_output = stderr.read().decode()
        if error_output:
            print("❌ Błąd podczas wykonywania polecenia:", error_output)
            return None

        # zwrócenie wyniku
        return stdout.read().decode()

    finally:
        ssh.close()
