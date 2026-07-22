"""Walidacja par source -> destination i pytania t/n, wspolne dla wszystkich rsync_* entry-pointow."""

from pathlib import Path


def ask_yes_no(prompt: str) -> bool:
    """Uniwersalne pytanie t/n."""
    while True:
        response = input(prompt).strip().lower()
        if response in ["t", "tak", "y", "yes"]:
            return True
        if response in ["n", "nie", "no"]:
            return False
        print("   Prosze wpisac 't' (tak) lub 'n' (nie)")


def ask_yes_no_default_no(prompt: str) -> bool:
    """Pytanie t/n, gdzie Enter oznacza NIE."""
    while True:
        response = input(prompt).strip().lower()
        if response == "":
            return False
        if response in ["t", "tak", "y", "yes"]:
            return True
        if response in ["n", "nie", "no"]:
            return False
        print("   Prosze wpisac 't' (tak) lub 'n' (nie)")


def is_suspicious_destructive_path(path: Path) -> bool:
    """Chroni przed potencjalnie niebezpiecznymi sciezkami."""
    resolved = path.resolve()
    if resolved == Path("/"):
        return True

    # Zbyt krotkie sciezki systemowe sa ryzykowne dla operacji destrukcyjnych.
    parts = [part for part in resolved.parts if part not in ["/"]]
    return len(parts) < 3


def validate_pair(source_path: Path, target_path: Path) -> tuple[bool, str]:
    """Waliduje pare source/target zanim ruszy synchronizacja."""
    if not str(source_path).strip():
        return False, "Pusta sciezka source"
    if not str(target_path).strip():
        return False, "Pusta sciezka target"

    source_resolved = source_path.resolve()
    target_resolved = target_path.resolve()

    if source_resolved == Path("/"):
        return False, "Source nie moze byc '/'"
    if target_resolved == Path("/"):
        return False, "Target nie moze byc '/'"

    if is_suspicious_destructive_path(source_resolved):
        return False, f"Podejrzanie krotka sciezka source: {source_resolved}"
    if is_suspicious_destructive_path(target_resolved):
        return False, f"Podejrzanie krotka sciezka target: {target_resolved}"

    if source_resolved == target_resolved:
        return False, "Source i target wskazuja ten sam katalog"

    if not source_resolved.exists():
        return False, f"Source nie istnieje: {source_resolved}"

    return True, ""


def confirm_pair(source_path: Path, target_path: Path) -> bool:
    """Pokazuje finalne sciezki i pyta o potwierdzenie TYLKO gdy target istnieje i ma dane.

    Feature: Smart Confirmation
    - Gdy target NIE istnieje: automatycznie kontynuuje (nowy folder - bezpieczne)
    - Gdy target istnieje ale jest pusty: automatycznie kontynuuje (pusty folder - bezpieczne)
    - Gdy target istnieje i ma dane: pyta o potwierdzenie (ochrona przed nadpisaniem)
    """
    target_resolved = target_path.resolve()

    target_has_data = False
    if target_resolved.exists():
        try:
            has_entries = next(target_resolved.iterdir(), None) is not None
            target_has_data = has_entries
        except (PermissionError, OSError):
            # Nie mozna odczytac - zakladamy ze ma dane dla bezpieczenstwa
            target_has_data = True

    print("\n🔐 Potwierdzenie pary synchronizacji:", flush=True)
    print(f"   Source: {source_path.resolve()}", flush=True)
    print(f"   Target: {target_path.resolve()}", flush=True)

    if not target_has_data:
        print("   🟢 Target nie istnieje lub jest pusty - kontynuacja automatyczna", flush=True)
        return True

    print("   ⚠️ Target istnieje i zawiera dane!", flush=True)
    return ask_yes_no_default_no("   Kontynuowac te synchronizacje? (t/n, domyslnie n): ")
