#!/usr/bin/env python3
"""Тесты для классификатора обращений."""

import unittest
from classify import classify_and_respond


class TestClassifier(unittest.TestCase):
    def test_sample_messages(self):
        cases = [
            ("Как получить справку о месте учёбы?", "справка"),
            ("В столовой очередь, еда холодная.", "жалоба"),
            ("Хочу записаться на консультацию завтра.", "другое"),
            ("Пропал Wi‑Fi в корпусе B.", "жалоба"),
            ("Где парковка для гостей?", "другое"),
        ]
        for message, expected_cat in cases:
            category, draft = classify_and_respond(message)
            self.assertEqual(category, expected_cat, f"Неверная категория для: {message}")
            self.assertTrue(len(draft) > 10, f"Черновик ответа слишком короткий для: {message}")
            self.assertTrue(draft.startswith("Здравствуйте!"))


if __name__ == "__main__":
    unittest.main()
