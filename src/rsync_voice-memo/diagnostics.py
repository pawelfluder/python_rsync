"""Diagnostyka wykrytego katalogu Voice Memos - bez czytania baz SQLite Voice Memos."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class VoiceMemoDiagnostics:
    source: Path
    recordings: list[Path] = field(default_factory=list)
    sample: list[Path] = field(default_factory=list)
    latest_recording_date: str | None = None


def collect_m4a_recordings(source: Path) -> list[Path]:
    """Zbiera pliki .m4a rekurencyjnie z katalogu Voice Memos (bez czytania baz SQLite).

    Rekurencyjnie, bo dokladnie taki jest zasieg filtra rsync uzywanego przy
    kopiowaniu (--include='*/' --include='*.m4a' --exclude='*', patrz sync.py) -
    na tym Macu katalog Recordings zawiera obok plikow .m4a rowniez foldery
    "*.composition/fragments/" z wewnetrznymi fragmentami nagran w edycji;
    licznik ma pokazywac to samo, co faktycznie skopiuje rsync, wiec musi je
    widziec tak samo.
    """
    # rglob("*.m4a") sam jest case-sensitive niezaleznie od filesystemu, wiec
    # rozszerzenie porownujemy recznie (p.suffix.lower()), tak jak poprzednio.
    return sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() == ".m4a")


def list_selectable_recordings(source: Path) -> list[Path]:
    """Zwraca TYLKO nagrania na najwyzszym poziomie katalogu Voice Memos (bez rekursji).

    Uzywane przez numerowana selekcje (rsync_voice-memo_v2+): w przeciwienstwie do
    collect_m4a_recordings() (rekursywne, do liczenia/dry-run zgodnego z filtrem
    rsync), tutaj celowo NIE wchodzimy do "*.composition/fragments/" - to
    wewnetrzne fragmenty nagrania w edycji, nie odrebne nagrania do wyboru.
    """
    return sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() == ".m4a")


def build_diagnostics(source: Path, sample_limit: int = 5) -> VoiceMemoDiagnostics:
    """Buduje diagnostyke: liczba .m4a, do 5 przykladowych plikow, data najnowszego nagrania."""
    recordings = collect_m4a_recordings(source)
    sample = recordings[:sample_limit]

    latest_recording_date = None
    if recordings:
        latest = max(recordings, key=lambda p: p.stat().st_mtime)
        latest_recording_date = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

    return VoiceMemoDiagnostics(
        source=source,
        recordings=recordings,
        sample=sample,
        latest_recording_date=latest_recording_date,
    )


def print_diagnostics(diagnostics: VoiceMemoDiagnostics) -> None:
    print(f"📁 Znaleziony katalog Voice Memos: {diagnostics.source}", flush=True)
    print(f"🎙️ Liczba nagran .m4a: {len(diagnostics.recordings)}", flush=True)
    if diagnostics.sample:
        print("   Przykladowe pliki:", flush=True)
        for item in diagnostics.sample:
            print(f"   - {item.name}", flush=True)
    if diagnostics.latest_recording_date:
        print(f"🕐 Data najnowszego nagrania: {diagnostics.latest_recording_date}", flush=True)
    else:
        print("🕐 Brak nagran do wyznaczenia daty najnowszego pliku", flush=True)


def print_source_not_found(candidates: list[Path]) -> None:
    print("❌ Nie znaleziono katalogu Voice Memos zsynchronizowanego przez iCloud.", flush=True)
    print("   Sprawdzone sciezki:", flush=True)
    for candidate in candidates:
        print(f"   - {candidate}", flush=True)
    print("   Uruchom aplikacje Voice Memos na Macu i wlacz synchronizacje iCloud,", flush=True)
    print("   a nastepnie sprobuj ponownie.", flush=True)
