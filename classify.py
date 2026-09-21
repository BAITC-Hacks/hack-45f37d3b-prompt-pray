#!/usr/bin/env python3
"""Классификация обращений и подготовка черновиков ответов без внешних сервисов."""

import re
import sys
from pathlib import Path
from typing import Tuple


CERTIFICATE_WORDS = ("справк", "выписк", "документ об уч", "подтверждение обучен")
COMPLAINT_WORDS = (
    "жалоб", "претензи", "не выдают", "не работает", "не ловит",
    "пропал", "сломал", "очеред", "холодн", "грязн", "плох", "ужасн", "сбой",
)
FOOD_WORDS = ("столов", "питан", "блюд")
NETWORK_WORDS = ("wi-fi", "wifi", "вайфай", "интернет", "сеть")


def clean_text(text: str) -> str:
    """Убирает нумерацию и приводит пробелы и варианты дефиса к одному виду."""
    text = re.sub(r"^\d+[\).]\s*", "", text.strip())
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip()


def classify_and_respond(message: str) -> Tuple[str, str]:
    """Возвращает категорию и черновик ответа для одного обращения."""
    lower = clean_text(message).lower()
    if not lower:
        raise ValueError("Текст обращения пуст.")

    is_complaint = any(word in lower for word in COMPLAINT_WORDS)
    is_certificate = any(word in lower for word in CERTIFICATE_WORDS)

    # Явная жалоба имеет приоритет, даже если в ней упоминается справка.
    if is_complaint:
        category = "жалоба"
        if any(word in lower for word in FOOD_WORDS) or re.search(r"\b(еда|кафе)\b", lower):
            draft = (
                "Здравствуйте! Спасибо, что сообщили о ситуации в столовой. "
                "Укажите, пожалуйста, дату и время посещения, а также блюдо или кассу. "
                "Эти сведения помогут ответственным сотрудникам проверить обращение."
            )
        elif any(word in lower for word in NETWORK_WORDS):
            draft = (
                "Здравствуйте! Спасибо за сообщение о проблеме с Wi-Fi. "
                "Укажите корпус, место и примерное время сбоя, а также устройство, "
                "на котором пропала связь. Это поможет проверить соединение."
            )
        else:
            draft = (
                "Здравствуйте! Спасибо, что сообщили о проблеме. "
                "Уточните, пожалуйста, где и когда она возникла, и опишите подробности. "
                "Эти сведения помогут разобраться в ситуации."
            )
    elif is_certificate:
        category = "справка"
        if any(word in lower for word in ("месте уч", "обучен", "студент")):
            draft = (
                "Здравствуйте! Для получения справки о месте учёбы уточните "
                "в учебной части вашего учреждения порядок оформления и срок выдачи. "
                "Сообщите, пожалуйста, для какой организации нужна справка."
            )
        else:
            draft = (
                "Здравствуйте! Уточните, пожалуйста, какой вид справки вам нужен "
                "и куда вы планируете её предоставить. После этого можно подсказать "
                "порядок оформления в вашем учреждении."
            )
    else:
        category = "другое"
        if "консультаци" in lower or "записаться" in lower:
            draft = (
                "Здравствуйте! Уточните, пожалуйста, к какому преподавателю "
                "или специалисту вы хотите записаться и какое время вам удобно. "
                "Это поможет подсказать порядок записи на консультацию."
            )
        elif "парковк" in lower or "автомобил" in lower:
            draft = (
                "Здравствуйте! Уточните, пожалуйста, в какой корпус вы направляетесь "
                "и когда планируете приехать. Это поможет сообщить актуальные "
                "условия въезда и расположение гостевой парковки."
            )
        else:
            draft = (
                "Здравствуйте! Спасибо за обращение. Уточните, пожалуйста, "
                "ваш вопрос и необходимые детали, чтобы можно было подготовить ответ."
            )

    return category, draft


def load_env_file():
    """Считывает локальный файл .env (если он существует), не требуя python-dotenv."""
    import os
    from pathlib import Path
    env_path = Path(__file__).resolve().with_name(".env")
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


_MODEL_CACHE = {"models": [], "ts": 0}


def get_available_gemini_models(api_key: str) -> list:
    """Динамически запрашивает у Google API список доступных моделей для данного ключа."""
    import time
    import json
    import urllib.request
    now = time.time()
    if _MODEL_CACHE["models"] and (now - _MODEL_CACHE["ts"]) < 600:
        return _MODEL_CACHE["models"]

    default_models = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Classifier/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            found = []
            for m in data.get("models", []):
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods and "flash" in name and "image" not in name and "tts" not in name:
                    found.append(name)
            if found:
                # На первые места ставим наиболее легковесные модели с максимальным RPM лимитом
                found.sort(key=lambda x: (0 if "lite" in x else 1, 0 if "3.5" in x else (1 if "3.1" in x else 2)))
                _MODEL_CACHE["models"] = found
                _MODEL_CACHE["ts"] = now
                return found
    except Exception:
        pass

    return default_models


def classify_with_gemini(message: str, api_key: str = None, return_meta: bool = False) -> Tuple:
    """
    Классифицирует обращение с помощью Google Gemini API с автовыбором доступной модели.
    При отсутствии ключа или сетевой ошибке безопасно возвращает результат локальных правил.
    """
    import os
    import json
    import urllib.request
    import urllib.error

    load_env_file()
    key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        print("[Инфо] GEMINI_API_KEY не задан. Используются локальные правила.", file=sys.stderr)
        cat, draft = classify_and_respond(message)
        return (cat, draft, "rules", "GEMINI_API_KEY не задан") if return_meta else (cat, draft)

    models = get_available_gemini_models(key)
    prompt = (
        "Ты — лаконичный специалист службы поддержки.\n"
        f"Проанализируй обращение: \"{message}\"\n\n"
        "1. Определи категорию строго из: 'справка', 'жалоба', 'другое'.\n"
        "2. Напиши краткий, точный и человечный черновик ответа (1-3 предложения, начинай со 'Здравствуйте!'). Без лишней воды.\n\n"
        "Формат JSON:\n"
        '{"category": "справка"|"жалоба"|"другое", "draft": "текст ответа"}'
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.5,
            "maxOutputTokens": 200
        }
    }

    last_error = None
    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                raw_json = res_data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_json)
                cat = str(parsed.get("category", "другое")).strip().lower()
                if cat not in ("справка", "жалоба", "другое"):
                    cat = "другое"
                draft = str(parsed.get("draft", "")).strip()
                if not draft:
                    draft = classify_and_respond(message)[1]
                return (cat, draft, "ai", None) if return_meta else (cat, draft)
        except urllib.error.HTTPError as err:
            last_error = f"HTTP {err.code}"
            if err.code in (429, 503, 404):
                continue
            error_body = err.read().decode("utf-8", errors="replace")
            print(f"[Предупреждение] Gemini API HTTP {err.code}: {error_body}", file=sys.stderr)
            cat, draft = classify_and_respond(message)
            return (cat, draft, "rules", f"Gemini API вернул ошибку {err.code}") if return_meta else (cat, draft)
        except Exception as exc:
            err_str = str(exc)
            if "nodename nor servname" in err_str or "Errno 8" in err_str or "Name or service not known" in err_str or "temporary failure" in err_str.lower():
                last_error = "Отсутствует подключение к интернету"
            else:
                last_error = err_str
            continue

    cat, draft = classify_and_respond(message)
    return (cat, draft, "rules", last_error or "Ошибка соединения с Gemini API") if return_meta else (cat, draft)


def main(argv=None) -> int:
    """Обрабатывает файл из аргумента или комплектный messages.txt."""
    # На Windows кодировка консоли может быть cp1251 и не поддерживать Wi‑Fi.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    raw_args = sys.argv[1:] if argv is None else argv
    use_llm = "--llm" in raw_args
    positional = [arg for arg in raw_args if not arg.startswith("--")]

    if len(positional) > 1:
        print("Использование: python classify.py [--llm] [путь-к-файлу]", file=sys.stderr)
        return 2

    file_path = Path(positional[0]) if positional else Path(__file__).resolve().with_name("messages.txt")
    try:
        lines = [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeError) as exc:
        print(f"Ошибка чтения файла '{file_path}': {exc}", file=sys.stderr)
        return 1

    if not lines:
        print(f"Ошибка: файл '{file_path}' не содержит обращений.", file=sys.stderr)
        return 1

    for number, line in enumerate(lines, 1):
        if use_llm:
            category, draft = classify_with_gemini(line)
        else:
            category, draft = classify_and_respond(line)

        print(f"Обращение #{number}: {line}")
        print(f"Категория: {category}")
        print(f"Черновик: {draft}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
