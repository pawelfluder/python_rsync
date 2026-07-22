"""Wczytuje cel na QNAP z AA_Input/input_voice-memo.yaml (ten sam prosty format YAML jak input.yaml)."""

from pathlib import Path

import yaml

DEFAULT_TARGET = Path("/Volumes/qnap/01_todo_a/voice-memos")


def load_voice_memo_target(yaml_path: Path) -> Path:
    """Wczytuje docelowa sciezke na QNAP z pliku YAML; jesli plik nie istnieje - uzywa domyslnej."""
    if not yaml_path.exists():
        return DEFAULT_TARGET

    with open(yaml_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    target = data.get("target") if isinstance(data, dict) else None
    return Path(target).expanduser() if target else DEFAULT_TARGET
