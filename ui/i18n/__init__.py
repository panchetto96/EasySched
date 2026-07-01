import json
from pathlib import Path

_lang = "it"
_strings: dict[str, dict[str, str]] = {}

def _load_all() -> None:
    here = Path(__file__).parent
    for lang in ("it", "en"):
        path = here / f"{lang}.json"
        if path.exists():
            _strings[lang] = json.loads(path.read_text(encoding="utf-8"))

_load_all()


def tr(key: str) -> str:
    return _strings.get(_lang, {}).get(key) or _strings.get("it", {}).get(key) or key


def set_language(lang: str) -> None:
    global _lang
    if lang in ("it", "en"):
        _lang = lang


def get_language() -> str:
    return _lang
