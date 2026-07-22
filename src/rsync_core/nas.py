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

from modules.RetryNetworkDrive.retry_network_drive import (  # noqa: E402
    NasAuthError,
    ensure_nas_available,
    load_env_file,
)

load_env_file(REPO_ROOT / ".env")


def ensure_nas(nas_path: Path | None = None) -> Path:
    """Zapewnia dostep do NAS (mount_smbfs, bez okienka Findera) i zwraca faktyczna sciezke mountu."""
    return ensure_nas_available(nas_path=nas_path)


__all__ = ["ensure_nas", "NasAuthError"]
