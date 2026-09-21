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


def classify_with_gemini(message: str, api_key: str = None) -> Tuple[str, str]:
    """
    Классифицирует обращение с помощью Google Gemini API (бесплатный уровень).
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
        return classify_and_respond(message)

    models = ["gemini-flash-latest", "gemini-3.5-flash-lite"]
    prompt = (
        "Ты — помощник службы поддержки. Классифицируй входящее обращение строго по одной из трёх категорий: "
        "'справка', 'жалоба', 'другое'.\n"
        "Сформируй вежливый черновик ответа на русском языке (начинается с 'Здравствуйте!').\n"
        f"Обращение: \"{message}\"\n\n"
        "Верни результат СТРОГО в формате JSON:\n"
        '{"category": "справка"|"жалоба"|"другое", "draft": "текст ответа"}'
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }

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
                return cat, draft
        except urllib.error.HTTPError as err:
            if err.code == 503:
                continue
            error_body = err.read().decode("utf-8", errors="replace")
            print(f"[Предупреждение] Gemini API HTTP {err.code}: {error_body}", file=sys.stderr)
            return classify_and_respond(message)
        except Exception:
            continue

    return classify_and_respond(message)


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
