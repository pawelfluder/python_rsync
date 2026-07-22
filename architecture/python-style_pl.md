# Python Style Guide (PL)

## 1. Skrypty Powłoki w `03_scripts`

W folderze `03_scripts` znajdują się skrypty `.sh` do zarządzania środowiskiem wirtualnym Pythona:

- **`01_create_venv.sh`** - tworzy środowisko wirtualne `.venv`
- **`02_activate_venv.sh`** - aktywuje środowisko `.venv`
- **`03_requirements.sh`** - instaluje zależności z pliku `requirements.txt` do środowiska `.venv`
- **`04_vscode_setup_venv.sh`** - ustawia interpreter Pythona na `.venv` w VSCode dla tego workspace'u/folderu

Przykładowa struktura:
```
03_scripts/
├── 01_create_venv.sh
├── 02_activate_venv.sh
├── 03_requirements.sh
└── 04_vscode_setup_venv.sh
```

## 2. Ścieżka Repozytorium i Struktura Importów

Zawsze szukaj głównej ścieżki repozytorium i odnos się do niej w całym workspace'ie. Podejście to zapewnia spójność i umożliwia działanie skryptów niezależnie od tego, z którego miejsca w strukturze projektu są uruchamiane.

### 2.1 Wyszukiwanie Głównej Ścieżki Repozytorium

W każdym skrypcie ustawiaj ścieżkę do głównego folderu repozytorium:

```python
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]  # Dostosuj liczbę parents[] do głębokości zagnieżdżenia
```

### 2.2 Dodawanie do sys.path i Importy

Dodaj główną ścieżkę repozytorium do `sys.path`, aby umożliwić importy z folderu `modules` i innych lokalizacji w workspace'ie:

```python
import sys
sys.path.append(str(REPO_ROOT))

# Przykład importu z modules
from modules.ServerBySsh.server_by_ssh_v2 import run_remote_command
```

### 2.3 Odwoływanie się do Ścieżek w Workspace'ie

Używaj `REPO_ROOT` do budowania ścieżek do innych folderów w projekcie:

```python
# Przykłady odwołań do różnych folderów
input_folder = REPO_ROOT / "AA_Input"
output_folder = REPO_ROOT / "AA_Output"
temp_folder = REPO_ROOT / "AA_Temp"
scripts_folder = REPO_ROOT / "03_scripts"
```

To podejście zapewnia, że skrypty działają poprawnie niezależnie od tego, czy są uruchamiane z VSCode, terminala, czy jako moduły importowane w innych skryptach.

## 3. Struktura Folderów: `src` i `modules`

Projekt używa dwóch głównych folderów dla kodu Python:

### 3.1 `src/` - Główne Skrypty Projektu

W folderze `src` umieszczaj **główne skrypty wejściowe projektu** (1-2 pliki), które są uruchamiane bezpośrednio przez użytkownika. To są skrypty, które inicjują cały proces i są "wejściem" do projektu.

Przykładowa struktura:
```
src/
└── RsyncSync/
    ├── rsync_sync_v1.py      # Główny skrypt do uruchomienia
    └── rsync_sync_v1.txt     # Dokumentacja zmian
```

### 3.2 `modules/` - Moduły Wielokrotnego Użycia

W folderze `modules` umieszczaj **moduły/skrypty Python które się powtarzają między projektami**. Są to biblioteki funkcji, które mogą być importowane i używane w różnych projektach.

- **Nazwy folderów**: Używaj PascalCase (wielkie litery na początku każdego słowa) dla nazw kategorii/modułów, np. `ServerBySsh`, `RetryNetworkDrive`, `YamlParsing`.
- **Wersjonowanie plików**: Wewnątrz folderu nazywaj pliki używając snake_case z sufiksem wersji, np. `server_by_ssh_v1.py`, `server_by_ssh_v2.py`.

Przykładowa struktura:
```
modules/
├── ServerBySsh/
│   ├── server_by_ssh_v1.py
│   ├── server_by_ssh_v1.txt
│   ├── server_by_ssh_v2.py
│   └── server_by_ssh_v2.txt
├── RetryNetworkDrive/
│   ├── retry_network_drive_v1.py
│   └── retry_network_drive_v2.py
├── YamlParsing/
│   ├── files_collections_from_yaml_v1.py
│   ├── files_collections_yaml_parsing_v1.py
│   └── files_collections_yaml_parsing_v1.txt
└── RsyncSync/
    ├── rsync_sync_v1.py
    └── rsync_sync_v1.txt
```

## 4. Struktura Folderów Danych: AA_Input, AA_Output, AA_Temp

Pliki danych są organizowane w trzech głównych folderach:

- **`AA_Input`** - folder z plikami wejściowymi (np. pliki YAML, pliki MP3 do przetworzenia)
- **`AA_Output`** - folder z plikami wyjściowymi (wyniki działania skryptów)
- **`AA_Temp`** - folder z plikami tymczasowymi

### 4.1 Pliki YAML w AA_Input

W `AA_Input` mogą znajdować się pliki konfiguracyjne YAML (np. `input.yaml`), które zawierają ścieżki do plików wejściowych. Skrypty odczytują te pliki YAML i przetwarzają listy plików zgodnie z zasadami zdefiniowanymi w:

```
modules/YamlParsing/files_collections_yaml_parsing_v[n].py
```

### 4.2 Bezpośrednie Pliki w AA_Input

W `AA_Input` mogą również znajdować się bezpośrednio pliki do przetworzenia (np. pliki MP3 do transkrypcji Whisperem). **Uwaga:** Skrypty odczytują wyłącznie pliki znajdujące się bezpośrednio w folderze `AA_Input`. Pliki umieszczone w podfolderach wewnątrz `AA_Input` nie zostaną odczytane jako input.

Przykład struktury:
```
AA_Input/
├── input.yaml                    # Konfiguracja z listami plików
├── MusicStation_Pawel_F.yaml     # Przykładowy plik YAML
├── song1.mp3                     # Bezpośredni plik do przetworzenia
└── song2.mp3                     # Bezpośredni plik do przetworzenia
```

## 5. Dokumentacja Zmian w Plikach .txt

Przy każdej nowej wersji skryptu, twórz plik dokumentacyjny z rozszerzeniem `.txt` o tej samej nazwie co plik Pythona. Plik ten powinien zawierać:

- **Opis zmian** - co zostało zmienione w porównaniu do poprzedniej wersji
- **Nowe funkcje** - jakie nowe funkcjonalności zostały dodane
- **Informacje dla AI** - szczegółowe wyjaśnienie zmian, aby kolejne AI dopisujące kod mogło zrozumieć kontekst i kontynuować rozwój

Przykład:
```
modules/YamlToServerPlaylist/
├── yaml_to_playlist_v5.py
├── yaml_to_playlist_v5.txt     # Dokumentacja zmian v5
├── yaml_to_playlist_v6.py
└── yaml_to_playlist_v6.txt     # Dokumentacja zmian v6
```

Pliki `.txt` służą jako historia zmian i przewodnik dla AI, aby każda kolejna iteracja kodu była spójna i dobrze udokumentowana.

## 6. Samodzielne Uruchamianie i Możliwość Importu Skryptów

Każdy plik skryptu z wersją (np. `v1`, `v[n].py`) powinien być zaprojektowany zgodnie z następującymi zasadami:

### 6.1 Samodzielne Uruchamianie

Skrypty muszą być uruchamialne bezpośrednio przez kliknięcie "Run Python File" w VSCode (lub inne IDE). Nie wymagają zewnętrznych runnerów ani skomplikowanej konfiguracji.

### 6.2 Możliwość Importu

Pliki wersji (np. `server_by_ssh_v1.py`, `yaml_to_playlist_v6.py`) są również przygotowane do importowania w innych skryptach. Powinny być napisane tak, aby mogły działać zarówno jako samodzielne skrypty, jak i jako moduły do includowania.

Przykład struktury pliku:
```python
# Na początku pliku - konfiguracja ścieżek (umożliwia importy)
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.append(str(REPO_ROOT))

# Główna logika w funkcji
def main():
    # kod skryptu
    pass

# Uruchomienie przy bezpośrednim wykonaniu
if __name__ == "__main__":
    main()
```

Dzięki tej strukturze:
- Można kliknąć "Run Python File" i skrypt uruchomi się samodzielnie
- Można zaimportować funkcje z tego pliku w innym skrypcie (np. `from modules.ServerBySsh.server_by_ssh_v2 import run_remote_command`)