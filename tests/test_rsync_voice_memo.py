"""
Mockowane testy dla src/rsync_voice-memo/ (unittest ze stdlib, bez pytest - nie ma go
w .venv tego repo, a testy nie powinny wymagac instalowania nowych zaleznosci).

Zadna z tych testow nie laczy sie z prawdziwym iCloud/Voice Memos ani z prawdziwym QNAP:
- katalogi Voice Memos sa tworzone jako tymczasowe foldery (tempfile),
- ensure_nas() / ensure_nas_available() jest mockowane,
- rsync jest mockowany na poziomie subprocess.run / run_rsync_with_live_output.

Uruchomienie: python3 -m unittest tests.test_rsync_voice_memo -v
"""

import io
import importlib.util
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
VOICE_MEMO_DIR = SRC_ROOT / "rsync_voice-memo"
PYTHON_MODULES_ROOT = REPO_ROOT.parent / "python_modules"

sys.path.insert(0, str(SRC_ROOT))
sys.path.insert(0, str(VOICE_MEMO_DIR))
sys.path.insert(0, str(PYTHON_MODULES_ROOT))

import config  # noqa: E402
import diagnostics  # noqa: E402
import discovery  # noqa: E402
import sync  # noqa: E402
from rsync_core import nas as rsync_core_nas  # noqa: E402
from modules.files_selection.files_selection_v4 import (  # noqa: E402
    display_files_with_numbers,
    parse_selection,
)


def _load_voice_memo_version(filename: str, module_name: str):
    """<filename> ma myslnik w nazwie - wczytanie przez importlib, nie 'import'."""
    path = VOICE_MEMO_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


voice_memo_v2 = _load_voice_memo_version("rsync_voice-memo_v2.py", "rsync_voice_memo_v2_under_test")
voice_memo_v3 = _load_voice_memo_version("rsync_voice-memo_v3.py", "rsync_voice_memo_v3_under_test")


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


class FilesSelectionV4DisplayOrderTests(unittest.TestCase):
    """v4: numery przypisywane jak w v3 (chronologicznie), ale wypisywane od najwyzszego."""

    def test_display_order_is_reversed_but_numbering_stays_stable(self):
        recordings = [Path(f"/rec/2025010{i}.m4a") for i in range(1, 6)]
        collections = {"voice-memos": recordings}

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            display_files_with_numbers(collections, None, None, show_durations=False)
        output_lines = [line for line in buffer.getvalue().splitlines() if line.strip().startswith("(")]

        # (5) najnowszy na gorze ... (1) najstarszy na dole.
        self.assertEqual(
            output_lines,
            [
                "    (5) 20250105.m4a",
                "    (4) 20250104.m4a",
                "    (3) 20250103.m4a",
                "    (2) 20250102.m4a",
                "    (1) 20250101.m4a",
            ],
        )

        # Numeracja uzywana przez parse_selection() jest niezalezna od kolejnosci
        # wypisywania - (1) zawsze wskazuje najstarszy plik.
        self.assertEqual(
            [p.name for p in parse_selection("1-3", collections)["voice-memos"]],
            ["20250101.m4a", "20250102.m4a", "20250103.m4a"],
        )
        self.assertEqual(
            [p.name for p in parse_selection("all", collections)["voice-memos"]],
            [r.name for r in recordings],
        )


class ListSelectableRecordingsTests(unittest.TestCase):
    """list_selectable_recordings(): tylko top-level, bez wewnetrznych fragmentow .composition."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)

    def test_excludes_nested_composition_fragments(self):
        _touch(self.source / "20250101 100000.m4a")
        _touch(self.source / "20250102 110000.m4a")
        fragments_dir = self.source / "20260722 141900.composition" / "fragments"
        fragments_dir.mkdir(parents=True)
        _touch(fragments_dir / "AAAA-fragment.m4a")

        selectable = diagnostics.list_selectable_recordings(self.source)
        recursive = diagnostics.collect_m4a_recordings(self.source)

        self.assertEqual(
            sorted(p.name for p in selectable),
            ["20250101 100000.m4a", "20250102 110000.m4a"],
        )
        # collect_m4a_recordings() (uzywane przez v1/diagnostyke) widzi rowniez fragment.
        self.assertEqual(len(recursive), 3)


class AskSelectionIntegrationTests(unittest.TestCase):
    """ask_selection(): te same opcje co files_selection - all / zakres / lista - i domyslne 'all'."""

    def setUp(self) -> None:
        self.recordings = [Path(f"/rec/2025010{i}.m4a") for i in range(1, 6)]

    def test_all_option(self):
        with mock.patch("builtins.input", return_value="all"), redirect_stdout(io.StringIO()):
            selected = voice_memo_v2.ask_selection(self.recordings)
        self.assertEqual([p.name for p in selected], [r.name for r in self.recordings])

    def test_range_option(self):
        with mock.patch("builtins.input", return_value="1-3"), redirect_stdout(io.StringIO()):
            selected = voice_memo_v2.ask_selection(self.recordings)
        self.assertEqual([p.name for p in selected], ["20250101.m4a", "20250102.m4a", "20250103.m4a"])

    def test_explicit_list_option(self):
        with mock.patch("builtins.input", return_value="1,3,4"), redirect_stdout(io.StringIO()):
            selected = voice_memo_v2.ask_selection(self.recordings)
        self.assertEqual(
            [p.name for p in selected],
            ["20250101.m4a", "20250103.m4a", "20250104.m4a"],
        )

    def test_empty_input_defaults_to_all(self):
        with mock.patch("builtins.input", return_value=""), redirect_stdout(io.StringIO()):
            selected = voice_memo_v2.ask_selection(self.recordings)
        self.assertEqual([p.name for p in selected], [r.name for r in self.recordings])


class DefaultDestinationForTodayTests(unittest.TestCase):
    def test_matches_rr_mm_dd_voice_memo_pattern(self):
        base_target = Path("/Volumes/qnap/01_todo_a/voice-memos")

        result = voice_memo_v2.default_destination_for_today(base_target)

        self.assertEqual(result.parent, base_target)
        self.assertRegex(result.name, r"^\d{2}-\d{2}-\d{2}_voice_memo$")


class SelectedFilesCopyTests(unittest.TestCase):
    """copy_selected_files() / run_dry_run_for_selected_files(): tylko wybrane pliki, nigdy --delete."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.destination = Path(self.tmp.name) / "target"
        self.selected = [Path("/rec/20250101 100000.m4a"), Path("/rec/20250102 110000.m4a")]

    def test_build_cmd_uses_files_from_and_never_delete(self):
        files_from = Path("/tmp/fake-list.txt")
        cmd = sync.build_selected_files_rsync_cmd(Path("/rec"), self.destination, files_from, dry_run=False)

        self.assertIn(f"--files-from={files_from}", cmd)
        self.assertNotIn("--delete", cmd)

    def test_copy_selected_files_writes_only_selected_names_and_cleans_up_tmp_file(self):
        captured_cmd = {}

        def fake_run_rsync(cmd, *args, **kwargs):
            captured_cmd["cmd"] = cmd
            files_from_arg = next(part for part in cmd if part.startswith("--files-from="))
            files_from_path = Path(files_from_arg.split("=", 1)[1])
            captured_cmd["files_from_content"] = files_from_path.read_text(encoding="utf-8")
            captured_cmd["files_from_path"] = files_from_path
            return True

        with mock.patch("sync.run_rsync_with_live_output", side_effect=fake_run_rsync):
            ok = sync.copy_selected_files(Path("/rec"), self.destination, self.selected)

        self.assertTrue(ok)
        self.assertTrue(self.destination.is_dir())
        self.assertNotIn("--delete", captured_cmd["cmd"])
        self.assertEqual(
            captured_cmd["files_from_content"].splitlines(),
            ["20250101 100000.m4a", "20250102 110000.m4a"],
        )
        # Plik tymczasowy z lista jest usuwany po uzyciu.
        self.assertFalse(captured_cmd["files_from_path"].exists())

    def test_dry_run_for_selected_files_never_deletes(self):
        fake_result = mock.Mock(stdout="20250101 100000.m4a\n20250102 110000.m4a\n", returncode=0)
        with mock.patch("sync.subprocess.run", return_value=fake_result) as mocked_run:
            output = sync.run_dry_run_for_selected_files(Path("/rec"), self.destination, self.selected)

        self.assertEqual(output, "20250101 100000.m4a\n20250102 110000.m4a\n")
        called_cmd = mocked_run.call_args.args[0]
        self.assertIn("-avn", called_cmd)
        self.assertNotIn("--delete", called_cmd)


class FindRelatedSourceItemsTests(unittest.TestCase):
    """v3: usuwanie oryginalu musi zabrac CALY zestaw (.m4a + .composition + .waveform), nie tylko .m4a."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)

    def test_finds_composition_folder_and_waveform_for_same_stem(self):
        recording = self.source / "20250107 110307.m4a"
        _touch(recording)
        composition_dir = self.source / "20250107 110307.composition" / "fragments"
        composition_dir.mkdir(parents=True)
        _touch(composition_dir / "inner-fragment.m4a")
        _touch(self.source / "20250107 110307.waveform")
        # Inne nagranie w tym samym folderze - nie powinno zostac dopasowane.
        _touch(self.source / "20250108 090000.m4a")

        related = voice_memo_v3.find_related_source_items(self.source, recording)

        self.assertEqual(
            sorted(p.name for p in related),
            ["20250107 110307.composition", "20250107 110307.m4a", "20250107 110307.waveform"],
        )

    def test_collect_related_source_items_dedupes_across_selection(self):
        recording_a = self.source / "20250107 110307.m4a"
        recording_b = self.source / "20250108 090000.m4a"
        _touch(recording_a)
        _touch(recording_b)
        (self.source / "20250107 110307.composition").mkdir()
        (self.source / "20250108 090000.waveform").touch()

        related = voice_memo_v3.collect_related_source_items(self.source, [recording_a, recording_b])

        self.assertEqual(
            sorted(p.name for p in related),
            [
                "20250107 110307.composition",
                "20250107 110307.m4a",
                "20250108 090000.m4a",
                "20250108 090000.waveform",
            ],
        )
        self.assertEqual(len(related), len(set(related)))  # bez duplikatow


class DeleteRelatedSourceItemsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)

    def test_removes_files_and_rmtrees_directories(self):
        m4a = self.source / "20250107 110307.m4a"
        _touch(m4a)
        composition_dir = self.source / "20250107 110307.composition" / "fragments"
        composition_dir.mkdir(parents=True)
        _touch(composition_dir / "inner-fragment.m4a")
        waveform = self.source / "20250107 110307.waveform"
        _touch(waveform)

        ok = voice_memo_v3.delete_related_source_items(
            [m4a, self.source / "20250107 110307.composition", waveform]
        )

        self.assertTrue(ok)
        self.assertFalse(m4a.exists())
        self.assertFalse((self.source / "20250107 110307.composition").exists())
        self.assertFalse(waveform.exists())


class DeleteConfirmationGateTests(unittest.TestCase):
    """v3: kasowanie oryginalow wymaga podwojnego 't' - domyslnie (Enter) NIC nie usuwa."""

    def test_no_on_first_question_skips_deletion(self):
        with mock.patch("builtins.input", return_value=""):
            confirmed = voice_memo_v3.ask_delete_originals_double_confirm([Path("/rec/x.m4a")])
        self.assertFalse(confirmed)

    def test_yes_then_no_skips_deletion(self):
        with mock.patch("builtins.input", side_effect=["t", ""]):
            confirmed = voice_memo_v3.ask_delete_originals_double_confirm([Path("/rec/x.m4a")])
        self.assertFalse(confirmed)

    def test_yes_twice_confirms_deletion(self):
        with mock.patch("builtins.input", side_effect=["t", "t"]):
            confirmed = voice_memo_v3.ask_delete_originals_double_confirm([Path("/rec/x.m4a")])
        self.assertTrue(confirmed)


class CopyStartsWithoutConfirmationTests(unittest.TestCase):
    """v3: po dry-run kopiowanie startuje od razu - nie ma juz pytania 'Skopiowac? (t/n)'."""

    def test_main_source_has_no_copy_confirmation_prompt(self):
        source_code = (VOICE_MEMO_DIR / "rsync_voice-memo_v3.py").read_text(encoding="utf-8")
        self.assertNotIn("Skopiowac wybrane nagrania na QNAP", source_code)


class VerifySelectedFilesCopiedTests(unittest.TestCase):
    """v3: usuwanie oryginalow jest oferowane TYLKO gdy weryfikacja rozmiaru sie zgadza."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source"
        self.destination = Path(self.tmp.name) / "destination"
        self.source.mkdir()
        self.destination.mkdir()

    def test_matching_sizes_report_no_mismatch(self):
        recording = self.source / "20250107 110307.m4a"
        recording.write_bytes(b"same-bytes")
        (self.destination / recording.name).write_bytes(b"same-bytes")

        mismatched = voice_memo_v3.verify_selected_files_copied(self.destination, [recording])

        self.assertEqual(mismatched, [])

    def test_size_mismatch_is_reported(self):
        recording = self.source / "20250107 110307.m4a"
        recording.write_bytes(b"twelve-bytes")
        (self.destination / recording.name).write_bytes(b"short")

        mismatched = voice_memo_v3.verify_selected_files_copied(self.destination, [recording])

        self.assertEqual(mismatched, [recording])


if __name__ == "__main__":
    unittest.main()
