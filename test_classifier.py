"""Проверки комплектного сценария, правил и ошибок запуска."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from classify import classify_and_respond, clean_text


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "classify.py"
SAMPLES = [
    ("Как получить справку о месте учёбы?", "справка", "справки о месте учёбы"),
    ("В столовой очередь, еда холодная.", "жалоба", "ситуации в столовой"),
    ("Хочу записаться на консультацию завтра.", "другое", "записаться"),
    ("Пропал Wi‑Fi в корпусе B.", "жалоба", "проблеме с Wi-Fi"),
    ("Где парковка для гостей?", "другое", "гостевой парковки"),
]


def run_cli(*args, cwd=None, encoding="utf-8"):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = encoding
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *map(str, args)],
        cwd=cwd or ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class TestClassifier(unittest.TestCase):
    def test_exact_task_messages_and_drafts(self):
        lines = (ROOT / "messages.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, [message for message, _, _ in SAMPLES])
        for message, expected_category, expected_topic in SAMPLES:
            with self.subTest(message=message):
                category, draft = classify_and_respond(message)
                self.assertEqual(category, expected_category)
                self.assertIn(expected_topic, draft)
                self.assertTrue(draft.startswith("Здравствуйте!"))
                self.assertNotIn("зарегистрирована", draft)
                self.assertNotIn("передана", draft)

    def test_rules_on_new_wordings_and_empty_input(self):
        self.assertEqual(clean_text("  4) Пропал Wi‑Fi  "), "Пропал Wi-Fi")
        self.assertEqual(classify_and_respond("Жалоба: не выдают справку")[0], "жалоба")
        category, draft = classify_and_respond("Не работает медпункт")
        self.assertEqual(category, "жалоба")
        self.assertNotIn("столовой", draft)
        self.assertNotIn("столовой", classify_and_respond("Не работает кафедра")[1])
        with self.assertRaises(ValueError):
            classify_and_respond(" \n ")

    def test_cli_runs_from_another_directory_with_legacy_console_encoding(self):
        with tempfile.TemporaryDirectory() as other_directory:
            result = run_cli(cwd=other_directory, encoding="cp1251")
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        output = result.stdout.decode("utf-8")
        self.assertEqual(output.count("Категория:"), 5)
        self.assertEqual(output.count("Черновик:"), 5)
        self.assertIn("Пропал Wi‑Fi в корпусе B.", output)
        self.assertEqual(result.stderr, b"")

    def test_invalid_files_report_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            empty = root / "empty.txt"
            empty.write_text("\n", encoding="utf-8")
            invalid = root / "invalid.txt"
            invalid.write_bytes(b"\xff\xfe")
            for path in (root / "missing.txt", empty, invalid, root):
                with self.subTest(path=path):
                    result = run_cli(path, encoding="cp1251")
                    self.assertEqual(result.returncode, 1)
                    error = result.stderr.decode("utf-8", errors="replace")
                    self.assertIn("Ошибка", error)
                    self.assertNotIn("Traceback", error)

    def test_custom_file_is_processed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "one-message.txt"
            path.write_text("Где парковка для гостей?\n", encoding="utf-8")
            result = run_cli(path)
        self.assertEqual(result.returncode, 0)
        output = result.stdout.decode("utf-8")
        self.assertEqual(output.count("Категория:"), 1)
        self.assertIn("Категория: другое", output)
        self.assertIn("Черновик:", output)

    def test_extra_arguments_are_rejected(self):
        result = run_cli("first.txt", "second.txt")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Использование", result.stderr.decode("utf-8", errors="replace"))


if __name__ == "__main__":
    unittest.main()
