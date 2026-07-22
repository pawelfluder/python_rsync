# Feature Documentation - rsync sync

## 📋 Overview
This document describes the features implemented in the rsync sync scripts.

---

## ✅ Feature 1: Smart Confirmation

### Description
The `confirm_pair()` function asks for user confirmation **only when necessary**:
- **Target doesn't exist**: Auto-continue (safe - new folder)
- **Target exists but is empty**: Auto-continue (safe - empty folder)
- **Target exists and has data**: Ask for confirmation (protection against overwriting)

### Files
- `src/Rsync/rsync_v5.py` (line ~131-157)

### Bug Fixed
Previously (v3), the script always asked for confirmation even when target didn't exist, which was unnecessary and annoying for first-time syncs.

### Code Example
```python
def confirm_pair(source_path: Path, target_path: Path) -> bool:
    target_resolved = target_path.resolve()
    
    # Check if target exists and has data
    target_has_data = False
    if target_resolved.exists():
        try:
            has_entries = next(target_resolved.iterdir(), None) is not None
            target_has_data = has_entries
        except (PermissionError, OSError):
            target_has_data = True
    
    if not target_has_data:
        # Auto-continue for new or empty target
        return True
    
    # Ask for confirmation when target has data
    return ask_yes_no_default_no("   Kontynuowac te synchronizacje? (t/n, domyslnie n): ")
```

---

## ✅ Feature 2: Infinite Retry on Network Errors

### Description
The `run_rsync_with_live_output()` function automatically retries rsync operations when network/IO errors occur:
- Retries indefinitely until success
- Checks NAS availability before retry
- Waits 10 seconds between attempts
- Only retries specific error codes (11, 12, 23, 24, 30)

### Files
- `src/Rsync/rsync_v3.py` (line ~199-255)
- `src/Rsync/rsync_v5.py` (line ~213-269)

### Error Codes That Trigger Retry
| Code | Meaning | Cause |
|------|---------|-------|
| 11 | error in file IO | Files disappear during transfer |
| 12 | error in rsync protocol data stream | Connection interrupted |
| 23 | partial transfer | Some files not transferred |
| 24 | vanished source files | Files vanished during transfer |
| 30 | timeout in data transfer | Transfer timeout |

### Code Example
```python
def run_rsync_with_live_output(cmd: list[str], retry: bool = True, retry_delay: int = 10) -> bool:
    attempt = 1
    while True:
        completed = subprocess.run(cmd, check=False, stdout=None, stderr=None)
        if completed.returncode == 0:
            return True
        
        retryable_codes = [11, 12, 23, 24, 30]
        if retry and completed.returncode in retryable_codes:
            # Check NAS availability and retry
            if not Path("/Volumes/qnap").exists():
                ensure_nas_available(Path("/Volumes/qnap"))
            else:
                time.sleep(retry_delay)
            attempt += 1
            continue
        
        return False
```

---

## ✅ Feature 3: Live Progress Output

### Description
rsync output is displayed in real-time with detailed progress information:
- Uses `--progress` flag for file-level progress
- Uses `--info=progress2` for overall transfer progress (%)
- Uses `--info=name0` for file names during transfer
- All print statements use `flush=True` for immediate output

### Files
- `src/Rsync/rsync_v2.py` and later

### Code Example
```python
def build_rsync_progress_flags() -> list[str]:
    if rsync_supports_info_flags():
        return ["--progress", "--info=progress2", "--info=name0"]
    return ["--progress"]
```

---

## ✅ Feature 4: Safe Delete Operations

### Description
Delete operations are performed safely:
- Never uses `--delete` during main sync
- Scans for extra files in destination AFTER sync completes
- Shows list of files to be deleted
- Asks for user confirmation before deletion
- Uses dry-run to preview deletions

### Files
- `src/Rsync/rsync_v3.py` (line ~370-432)
- `src/Rsync/rsync_v5.py` (line ~384-446)

---

## ✅ Feature 5: Double Confirmation for Source Deletion

### Description
Source files are deleted only after double confirmation:
- First confirmation: "Delete sources?"
- Second confirmation: "Confirm again - delete sources?"
- Both must be "yes" for deletion to proceed
- Protects against accidental data loss

### Files
- `src/Rsync/rsync_v3.py` (line ~455-471)
- `src/Rsync/rsync_v5.py` (line ~469-485)