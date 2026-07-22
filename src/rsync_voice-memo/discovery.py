"""Wykrywanie lokalnego katalogu Voice Memos zsynchronizowanego przez iCloud (bez laczenia z iPhonem)."""

from pathlib import Path

CANDIDATE_SOURCE_PATHS: list[Path] = [
    Path("~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings").expanduser(),
    Path("~/Library/Application Support/com.apple.voicememos/Recordings").expanduser(),
]


def find_voice_memos_source(candidates: list[Path] | None = None) -> Path | None:
    """Zwraca pierwszy istniejacy katalog Voice Memos, albo None jesli zaden nie istnieje.

    Sprawdza WYLACZNIE lokalne katalogi, do ktorych aplikacja Voice Memos na Macu juz
    zsynchronizowala nagrania przez iCloud - nie laczy sie z iPhonem.
    """
    for candidate in candidates if candidates is not None else CANDIDATE_SOURCE_PATHS:
        if candidate.is_dir():
            return candidate
    return None
