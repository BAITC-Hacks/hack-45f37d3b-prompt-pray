#!/usr/bin/env python3
"""
Автономный веб-сервер для демонстрации классификатора.
Скрывает API-ключ на стороне сервера: клиентский браузер обращается к /api/classify,
а сервер производит вызовы Gemini API с использованием ключа из локального файла .env.
"""

import os
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from classify import classify_and_respond, classify_with_gemini, load_env_file

ROOT_DIR = Path(__file__).resolve().parent
load_env_file()


class ClassifierHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT_DIR), **kwargs)

    def do_POST(self):
        if self.path == "/api/classify":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                message = data.get("message", "").strip()
                engine = data.get("engine", "ai")

                if not message:
                    self._send_json({"error": "Пустой текст обращения"}, status=400)
                    return

                if engine == "ai":
                    # Использует ключ из .env сервера, не передавая его клиенту
                    category, draft = classify_with_gemini(message)
                    source_engine = "ai" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else "rules"
                else:
                    category, draft = classify_and_respond(message)
                    source_engine = "rules"

                self._send_json({
                    "category": category,
                    "draft": draft,
                    "text": message,
                    "engine": source_engine
                })
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
        else:
            self.send_error(404, "Not Found")

    def _send_json(self, response_data, status=200):
        body_bytes = json.dumps(response_data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)


def main():
    ports = [8088, 8080, 8000, 8090]
    httpd = None
    selected_port = 8088
    for p in ports:
        try:
            httpd = HTTPServer(("", p), ClassifierHandler)
            selected_port = p
            break
        except OSError:
            continue

    if not httpd:
        print("Ошибка: не удалось найти свободный порт.", file=sys.stderr)
        return

    print("=" * 70)
    print(f"🚀 Защищённый веб-сервер запущен: http://localhost:{selected_port}")
    print("  - API-ключ Gemini безопасно используется из вашего файла .env")
    print("  - Пользователям в браузере ничего вводить не нужно")
    print("=" * 70)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")


if __name__ == "__main__":
    main()
