# Architektura Projektu: Rsync Sync do QNAP

## 1. Opis Projektu

Projekt ma na celu synchronizację plików z komputera Mac do folderu na QNAP (/Volumes/qnap/01_todo_a) przy użyciu komendy `rsync`. Skrypt wykorzystuje konfigurację YAML do określania źródeł plików i automatycznie obsługuje sytuacje, gdy QNAP staje się niedostępny.

## 2. Struktura Folderów

```
python_rsync/
├── architecture/
│   ├── python-style.md
│   ├── python-style_pl.md
│   └── rsync_sync_architecture.md    # Ten plik
├── 03_scripts/
│   ├── 01_create_venv.sh
│   ├── 02_activate_venv.sh
│   ├── 03_requirements.sh
│   └── 04_vscode_setup_venv.sh
├── modules/                          # Główne moduły projektu
│   ├── RetryNetworkDrive/
│   │   ├── retry_network_drive_v1.py
│   │   └── retry_network_drive_v2.py
│   ├── ServerBySsh/
│   │   ├── server_by_ssh_v1.py
│   │   ├── server_by_ssh_v1.txt
│   │   ├── server_by_ssh_v2.py
│   │   └── server_by_ssh_v2.txt
│   ├── YamlParsing/
│   │   ├── files_collections_from_yaml_v1.py
│   │   ├── files_collections_yaml_parsing_v1.py
│   │   └── files_collections_yaml_parsing_v1.txt
│   └── RsyncSync/
│       ├── rsync_sync_v1.py          # Główny skrypt
│       └── rsync_sync_v1.txt         # Dokumentacja zmian
├── AA_Input/
│   └── input.yaml                    # Konfiguracja synchronizacji
└── requirements.txt
```

**Uwaga:** Zgodnie z konwencjami projektu (python-style.md), moduły są organizowane w folderze `modules/` z użyciem PascalCase dla nazw folderów.

## 3. Zasady Konfiguracji YAML (AA_Input/input.yaml)

Skrypt wykorzystuje zasady zdefiniowane w `files_collections_yaml_parsing_v1.py` do parsowania pliku YAML. Obsługiwane są dwa warianty:

### Wariant 1: Nazwana kolekcja z listą ścieżek do plików

```yaml
- moja_kolekcja:
    - /Users/pawelfluder/Documents/file1.txt
    - /Users/pawelfluder/Music/song.mp3
    - qnap/02_reference/szkolenie.mp3
```

### Wariant 2: Ścieżka do folderu (wszystkie pliki z folderu)

```yaml
- /Users/pawelfluder/Downloads/music_folder
- qnap/04_procedury
```

### Przykład kompletnego pliku input.yaml:

```yaml
# Synchronizacja wybranych plików
- do_sync_pliki:
    - /Users/pawelfluder/Documents/wazny_dokument.pdf
    - /Users/pawelfluder/Desktop/prezentacja.key

# Synchronizacja całego folderu
- /Users/pawelfluder/Music/do_zgrania

# Kolejna kolekcja plików
- do_sync_projekty:
    - /Users/pawelfluder/Projects/projekt1
    - /Users/pawelfluder/Projects/projekt2
```

## 4. Działanie Skryptu

### 4.1 Uruchomienie

```bash
python modules/RsyncSync/rsync_sync_v1.py
```

### 4.2 Przepływ Działania

1. **Wczytanie konfiguracji**: Skrypt odczytuje `AA_Input/input.yaml`
2. **Pytanie o folder docelowy**: Konsola pyta o ścieżkę docelową na QNAP (domyślnie: `/Volumes/qnap/01_todo_a`)
3. **Sprawdzenie dostępności QNAP**: Wykorzystuje `ensure_nas_available()` z `retry_network_drive_v2.py`
4. **Parsowanie źródeł**: Wczytuje kolekcje plików zgodnie z zasadami z `files_collections_yaml_parsing_v1.py`
5. **Synchronizacja**: Dla każdej kolekcji uruchamia `rsync` z odpowiednimi parametrami
6. **Obsługa błędów**: Jeśli QNAP stanie się niedostępny podczas synchronizacji, skrypt próbuje go ponownie podłączyć

### 4.3 Parametry rsync

Skrypt używa następujących flag rsync:
- `-av` - archive mode (zachowuje uprawnienia, czasy, itp.) + verbose
- `--progress` - pokazuje postęp transferu
- `--ignore-existing` - pomija pliki, które już istnieją w destynacji (opcjonalne)

## 5. Integracja z retry_network_drive_v2.py

Skrypt importuje funkcje z `retry_network_drive_v2.py`:

```python
from modules.RetryNetworkDrive.retry_network_drive_v2 import ensure_nas_available, ensure_nas_readable
```

### Kluczowe funkcje:
- `ensure_nas_available()` - blokuje do czasu uzyskania dostępu do NAS
- `ensure_nas_readable(file_path)` - blokuje do czasu, aż plik na NAS będzie dostępny

### Konfiguracja NAS (do dostosowania):
```python
NAS_PATH = Path("/Volumes/qnap")
NAS_MOUNT_PATH = "//pawelfluder@100.117.139.83/qnap"
NAS_RETRY_DELAY = 10  # sekund
```

## 6. Przykładowe Uruchomienie

```
$ python modules/RsyncSync/rsync_sync_v1.py

🔍 Wczytywanie konfiguracji z AA_Input/input.yaml...
🔍 Processing collection: do_sync_pliki
  🔍 Checking file path: /Users/pawelfluder/Documents/wazny_dokument.pdf
  🔍 Checking file path: /Users/pawelfluder/Desktop/prezentacja.key
🔍 Checking folder path: /Users/pawelfluder/Music/do_zgrania
✅ Loaded collections: dict_keys(['do_sync_pliki', 'do_zgrania'])

📁 Podaj ścieżkę docelową na QNAP (domyślnie: /Volumes/qnap/01_todo_a): 

✓ NAS dostępny: /Volumes/qnap

🚀 Rozpoczynanie synchronizacji...

📂 Synchronizacja kolekcji: do_sync_pliki
  📄 /Users/pawelfluder/Documents/wazny_dokument.pdf -> /Volumes/qnap/01_todo_a/do_sync_pliki/
  📄 /Users/pawelfluder/Desktop/prezentacja.key -> /Volumes/qnap/01_todo_a/do_sync_pliki/

📂 Synchronizacja kolekcji: do_zgrania
  📁 /Users/pawelfluder/Music/do_zgrania/ -> /Volumes/qnap/01_todo_a/do_zgrania/

✅ Synchronizacja zakończona pomyślnie!
```

## 7. Obsługa Błędów

### 7.1 QNAP niedostępny
- Skrypt wykrywa brak dostępu do `/Volumes/qnap`
- Automatycznie próbuje zamontować ponownie (co 10 sekund)
- Kontynuuje synchronizację po przywróceniu połączenia

### 7.2 Brakujące pliki źródłowe
- Skrypt ostrzega o brakujących plikach (zgodnie z `files_collections_yaml_parsing_v1.py`)
- Kontynuuje synchronizację pozostałych plików

### 7.3 Błąd rsync
- Skrypt przechwytuje błędy rsync
- Loguje szczegóły błędu
- Kontynuuje z następną kolekcją

## 8. Wymagania

### 8.1 Zależności Python
```
pyyaml>=6.0
```

### 8.2 Wymagania systemowe
- macOS (dla komendy `open` w retry_network_drive)
- rsync (wbudowany w macOS)
- Dostęp do QNAP przez SMB

## 9. Konfiguracja dla Innych Użytkowników

Użytkownik powinien dostosować następujące wartości w skrypcie:

```python
# W retry_network_drive_v2.py (lub jako parametry)
NAS_PATH = Path("/Volumes/qnap")  # ścieżka montowania
NAS_MOUNT_PATH = "//username@IP_ADDRESS/share_name"  # adres SMB
```

Lub przekazać jako argumenty wiersza poleceń (w przyszłych wersjach).

## 10. Przyszłe Rozszerzenia

### 10.1 Możliwe ulepszenia:
- Dodanie argumentów wiersza poleceń (--target, --config)
- Tryb dry-run (symulacja bez kopiowania)
- Filtrowanie plików po rozszerzeniu
- Równoległa synchronizacja wielu kolekcji
- Logowanie do pliku
- Powiadomienia po zakończeniu