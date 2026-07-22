import os
from pathlib import Path
import yaml


def resolve_yaml_path(raw_path: str) -> Path:
    """Rozwiązuje ścieżkę z YAML do lokalnej ścieżki systemowej."""
    path_obj = Path(raw_path).expanduser()
    if path_obj.is_absolute():
        return path_obj.resolve()

    # Skrót projektu: qnap/... -> /Volumes/qnap/...
    if raw_path.startswith("qnap/"):
        return (Path("/Volumes") / raw_path).resolve()

    return path_obj.resolve()

def collect_files_from_folder(folder_path: Path) -> list[Path]:
    """Zbiera wszystkie pliki audio/video z folderu rekurencyjnie"""
    files = []
    if folder_path.is_dir():
        for file_path in sorted(folder_path.iterdir()):
            if file_path.is_file():
                files.append(file_path)
            elif file_path.is_dir():
                files.extend(collect_files_from_folder(file_path))
    return files

def load_file_collections_from_yaml(yaml_path: str) -> dict:
    """Wczytuje kolekcje plików z pliku YAML"""
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"YAML file {yaml_path} does not exist.")

    with open(yaml_path, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)

    collections = {}

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                # Przypadek 1: Nazwana kolekcja z listą ścieżek do plików
                for collection_name, paths in item.items():
                    print(f"🔍 Processing collection: {collection_name}")
                    if isinstance(paths, list):
                        files = []
                        for path in paths:
                            resolved_path = resolve_yaml_path(path)
                            print(f"  🔍 Checking path: {resolved_path}")
                            if resolved_path.is_file() or resolved_path.is_dir():
                                files.append(resolved_path)
                            else:
                                print(f"⚠️ Path {resolved_path} does not exist or is not valid.")
                        collections[collection_name] = files
                    else:
                        print(f"⚠️ Unsupported structure for collection {collection_name}: {paths}")
            elif isinstance(item, str):
                # Przypadek 2: Ścieżka do folderu
                folder_path = resolve_yaml_path(item)
                print(f"🔍 Checking folder path: {folder_path}")
                if folder_path.is_dir():
                    collection_name = folder_path.name
                    collections[collection_name] = collect_files_from_folder(folder_path)
                else:
                    print(f"⚠️ Path {folder_path} is not a valid directory. Ensure the path exists and is accessible.")
            else:
                print(f"⚠️ Unsupported YAML structure: {item}")
    else:
        print(f"⚠️ Unsupported YAML structure: {data}")

    print(f"✅ Loaded collections: {collections.keys()}")
    return collections