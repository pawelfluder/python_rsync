"""Wspolne polaczenie z NAS dla rsync_core - wywoluje ensure_nas_available() bez okienka Findera."""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
PYTHON_MODULES_ROOT = REPO_ROOT.parent / "python_modules"

# Oba foldery "modules/" (tu w python_rsync i w python_modules) laczą się w jeden
# namespace package (PEP 420, brak __init__.py) - stad import ponizej dziala
# niezaleznie od tego, w ktorym repo retry_network_drive faktycznie lezy.
for _path in (REPO_ROOT, PYTHON_MODULES_ROOT):
    if str(_path) not in sys.path:
        sys.path.append(str(_path))

# python_modules/modules/retry_network_drive/ trzyma cala historie wersji
# (_v1.py ... _v7.py, jak retry_network_drive_v*.py w innych repo) - v7 to
# aktualna, wspolna wersja: dodaje NAS_SUDO_PASSWORD (haslo do sudo z .env
# zamiast promptu) i chown mount pointu po sudo mkdir (naprawia
# "Operation not permitted" przy mount_smbfs po elevated mkdir).
from modules.retry_network_drive.retry_network_drive_v7 import (  # noqa: E402
    NasAuthError,
    ensure_nas_available,
    load_env_file,
)

load_env_file(REPO_ROOT / ".env")


def ensure_nas(nas_path: Path | None = None) -> Path:
    """Zapewnia dostep do NAS (mount_smbfs, bez okienka Findera) i zwraca faktyczna sciezke mountu."""
    return ensure_nas_available(nas_path=nas_path)


__all__ = ["ensure_nas", "NasAuthError"]
