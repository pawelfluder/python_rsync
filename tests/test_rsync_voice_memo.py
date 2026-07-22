"""
Mockowane testy dla src/rsync_voice-memo/ (unittest ze stdlib, bez pytest - nie ma go
w .venv tego repo, a testy nie powinny wymagac instalowania nowych zaleznosci).

Zadna z tych testow nie laczy sie z prawdziwym iCloud/Voice Memos ani z prawdziwym QNAP:
- katalogi Voice Memos sa tworzone jako tymczasowe foldery (tempfile),
- ensure_nas() / ensure_nas_available() jest mockowane,
- rsync jest mockowany na poziomie subprocess.run / run_rsync_with_live_output.

Uruchomienie: python3 -m unittest tests.test_rsync_voice_memo -v
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
VOICE_MEMO_DIR = SRC_ROOT / "rsync_voice-memo"

sys.path.insert(0, str(SRC_ROOT))
sys.path.insert(0, str(VOICE_MEMO_DIR))

import config  # noqa: E402
import diagnostics  # noqa: E402
import discovery  # noqa: E402
import sync  # noqa: E402
from rsync_core import nas as rsync_core_nas  # noqa: E402


def _touch(path: Path, mtime: float | None = None) -> None:
    path.write_bytes(b"fake-m4a-bytes")
    if mtime is not None:
        import os

        os.utime(path, (mtime, mtime))


class FindVoiceMemosSourceTests(unittest.TestCase):
    """1) aktualna lokalizacja, 2) starsza lokalizacja, 3) brak obu."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.current = Path(self.tmp.name) / "group.com.apple.VoiceMemos.shared" / "Recordings"
        self.legacy = Path(self.tmp.name) / "com.apple.voicememos" / "Recordings"
        self.missing_current = Path(self.tmp.name) / "does-not-exist-current"
        self.missing_legacy = Path(self.tmp.name) / "does-not-exist-legacy"

    def test_current_location_found(self):
        self.current.mkdir(parents=True)
        self.legacy.mkdir(parents=True)
        found = discovery.find_voice_memos_source([self.current, self.legacy])
        self.assertEqual(found, self.current)

    def test_legacy_location_fallback(self):
        self.legacy.mkdir(parents=True)
        found = discovery.find_voice_memos_source([self.missing_current, self.legacy])
        self.assertEqual(found, self.legacy)

    def test_neither_location_exists(self):
        found = discovery.find_voice_memos_source([self.missing_current, self.missing_legacy])
        self.assertIsNone(found)


class DiagnosticsTests(unittest.TestCase):
    """4) katalog bez .m4a, 5) filtrowanie tylko nagran (+ przyklady i data najnowszego)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)

    def test_directory_without_m4a_files(self):
        _touch(self.source / "notes.txt")
        _touch(self.source / "readme.md")

        diag = diagnostics.build_diagnostics(self.source)

        self.assertEqual(diag.recordings, [])
        self.assertEqual(diag.sample, [])
        self.assertIsNone(diag.latest_recording_date)

    def test_filters_only_m4a_recordings(self):
        _touch(self.source / "note.txt")
        _touch(self.source / "memo1.m4a", mtime=1_700_000_000)
        _touch(self.source / "memo2.M4A", mtime=1_700_000_100)  # rozszerzenie case-insensitive
        _touch(self.source / "ignore.wav")

        recordings = diagnostics.collect_m4a_recordings(self.source)

        self.assertEqual(
            sorted(p.name for p in recordings),
            ["memo1.m4a", "memo2.M4A"],
        )

    def test_counts_m4a_inside_nested_composition_fragments(self):
        # Realny przypadek z tego Maca: Recordings/ zawiera obok plikow .m4a takze
        # foldery "*.composition/fragments/*.m4a" - ten sam zasieg co filtr rsync
        # (--include='*/' --include='*.m4a'), wiec diagnostyka musi je widziec tak samo.
        _touch(self.source / "memo1.m4a")
        fragments_dir = self.source / "20260722 141900.composition" / "fragments"
        fragments_dir.mkdir(parents=True)
        _touch(fragments_dir / "AAAA-fragment.m4a")

        recordings = diagnostics.collect_m4a_recordings(self.source)

        self.assertEqual(
            sorted(p.name for p in recordings),
            ["AAAA-fragment.m4a", "memo1.m4a"],
        )

    def test_sample_limited_to_five_and_latest_date_detected(self):
        latest_mtime = 1_700_000_000 + 6 * 60
        for i in range(7):
            _touch(self.source / f"memo{i}.m4a", mtime=1_700_000_000 + i * 60)

        diag = diagnostics.build_diagnostics(self.source, sample_limit=5)

        self.assertEqual(len(diag.recordings), 7)
        self.assertEqual(len(diag.sample), 5)
        # Nie zakladamy konkretnej strefy czasowej maszyny testowej - liczymy
        # oczekiwana wartosc tym samym sposobem co diagnostics.build_diagnostics().
        from datetime import datetime

        expected = datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(diag.latest_recording_date, expected)


class VoiceMemoRsyncCommandTests(unittest.TestCase):
    """5) filtrowanie tylko nagran w komendzie rsync, 6) brak kasowania zrodel, 8) dry-run."""

    def test_command_uses_only_m4a_include_exclude_filters(self):
        cmd = sync.build_voice_memo_rsync_cmd(Path("/src"), Path("/dst"))

        self.assertIn("--include=*/", cmd)
        self.assertIn("--include=*.m4a", cmd)
        self.assertIn("--exclude=*", cmd)

    def test_command_never_includes_delete(self):
        cmd_normal = sync.build_voice_memo_rsync_cmd(Path("/src"), Path("/dst"), dry_run=False)
        cmd_dry = sync.build_voice_memo_rsync_cmd(Path("/src"), Path("/dst"), dry_run=True)

        self.assertNotIn("--delete", cmd_normal)
        self.assertNotIn("--delete", cmd_dry)

    def test_dry_run_uses_dry_run_flag_and_skips_progress_flags(self):
        cmd = sync.build_voice_memo_rsync_cmd(Path("/src"), Path("/dst"), dry_run=True)

        self.assertIn("-avn", cmd)
        self.assertNotIn("--progress", cmd)

    def test_run_voice_memo_dry_run_calls_subprocess_without_delete(self):
        fake_result = mock.Mock(stdout=">f+++++++++ memo1.m4a\n", returncode=0)
        with mock.patch("sync.subprocess.run", return_value=fake_result) as mocked_run:
            output = sync.run_voice_memo_dry_run(Path("/src"), Path("/dst"))

        self.assertEqual(output, ">f+++++++++ memo1.m4a\n")
        called_cmd = mocked_run.call_args.args[0]
        self.assertIn("-avn", called_cmd)
        self.assertNotIn("--delete", called_cmd)


class SyncVoiceMemosTests(unittest.TestCase):
    """6) brak kasowania zrodel, 7) uzycie ensure_nas_available() (przez rsync_core.nas)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.destination = Path(self.tmp.name) / "qnap-target"

    def test_sync_voice_memos_never_calls_delete_and_creates_destination(self):
        with mock.patch("sync.run_rsync_with_live_output", return_value=True) as mocked_run:
            ok = sync.sync_voice_memos(Path("/src"), self.destination)

        self.assertTrue(ok)
        self.assertTrue(self.destination.is_dir())
        called_cmd = mocked_run.call_args.args[0]
        self.assertNotIn("--delete", called_cmd)

    def test_ensure_nas_delegates_to_shared_ensure_nas_available(self):
        with mock.patch.object(rsync_core_nas, "ensure_nas_available") as mocked_ensure:
            mocked_ensure.return_value = Path("/Volumes/qnap")
            result = rsync_core_nas.ensure_nas()

        mocked_ensure.assert_called_once_with(nas_path=None)
        self.assertEqual(result, Path("/Volumes/qnap"))


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_load_target_from_yaml(self):
        yaml_path = Path(self.tmp.name) / "input_voice-memo.yaml"
        yaml_path.write_text("target: /Volumes/qnap/custom-voice-memos\n", encoding="utf-8")

        target = config.load_voice_memo_target(yaml_path)

        self.assertEqual(target, Path("/Volumes/qnap/custom-voice-memos"))

    def test_missing_yaml_falls_back_to_default(self):
        missing = Path(self.tmp.name) / "does-not-exist.yaml"

        target = config.load_voice_memo_target(missing)

        self.assertEqual(target, config.DEFAULT_TARGET)


if __name__ == "__main__":
    unittest.main()
