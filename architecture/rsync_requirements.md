# Wymagania dla rsync sync - Retry Mechanism

## 🔁 Automatic Retry on Network/IO Errors

### Problem
Podczas synchronizacji dużych folderów przez sieć, połączenie może zostać przerwane z różnych przyczyn:
- Dysk sieciowy (QNAP) rozłącza się
- Pliki znikają podczas transferu (np. node_modules, cache)
- Timeout w transferze danych
- Błędy I/O na sieciowym dysku

### Rozwiązanie
rsync_v3.py implementuje **nieskończony retry** przy błędach związanych z połączeniem/siecią.

### Kody błędów które triggerują retry:
| Kod | Znaczenie | Przyczyna |
|-----|-----------|-----------|
| 11 | error in file IO | Pliki znikają podczas transferu |
| 12 | error in rsync protocol data stream | Połączenie przerwane |
| 23 | partial transfer | Niektóre pliki nie zostały przeniesione |
| 24 | vanished source files | Pliki zniknęły podczas transferu |
| 30 | timeout in data transfer | Timeout w transferze |

### Jak to działa:
1. rsync kończy się z jednym z powyższych kodów
2. Skrypt sprawdza dostępność QNAP (`/Volumes/qnap`)
3. Jeśli QNAP niedostępny → próbuje podłączyć (ensure_nas_available)
4. Jeśli QNAP dostępny → czeka 10 sekund i próbuje ponownie
5. Powtarza w nieskończoność aż do sukcesu

### Przykładowy output:
```
  ▶ rsync -av --progress /source/ /dest/ (prob 1)
  ❌ rsync zakonczyl sie kodem: 12
  ⚠️ rsync zakonczyl sie kodem 12 - prawdopodobnie problem z polaczeniem
  🔄 Sprawdzam dostepnosc QNAP i probuje ponownie za 10s...
  ℹ️ QNAP dostepny, czekam 10s i probuje ponownie...
  ▶ rsync -av --progress /source/ /dest/ (prob 2)
  ✅ rsync zakonczyl pomyslnie
```

### Konfiguracja:
- `retry: bool = True` (domyślnie włączone)
- `retry_delay: int = 10` (sekund między próbami)

### Uwagi:
- Retry dotyczy tylko błędów sieciowych/IO
- Inne błędy (np. brak uprawnień, brak miejsca) NIE są retry'owane
- rsync jest idempotentny - kolejne próby kontynuują od miejsca błędu