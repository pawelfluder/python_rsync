# filepath: /Users/pawelfluder/03_synch/01_files_programming/03_github/PythonScripts/src/ServerBySsh/server_by_ssh_v1.py
import os
import paramiko
import getpass

def get_server_host() -> str:
    host = os.getenv("server_host")
    if not host:
        raise RuntimeError("Ustaw zmienną środowiskową server_host (np. w pliku .env w katalogu repo).")
    return host

def get_server_port() -> int:
    return int(os.getenv("server_port", "22"))

def get_server_username() -> str:
    username = os.getenv("server_username")
    if not username:
        raise RuntimeError("Ustaw zmienną środowiskową server_username (np. w pliku .env w katalogu repo).")
    return username

def get_server_password():
    """
    Pobiera hasło do serwera od użytkownika.
    """
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