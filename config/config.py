import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / 'settings.json'

settings_cache: Dict[str, Any] | None = None


def load_settings(force_reload: bool = False) -> Dict[str, Any]:
    global settings_cache

    if force_reload or settings_cache is None:
        with DEFAULT_CONFIG_PATH.open('r', encoding='utf-8') as fp:
            settings_cache = json.load(fp)
    return settings_cache


def get_app_config() -> Dict[str, Any]:
    return load_settings()['app']


def get_llm_config() -> Dict[str, Any]:
    return load_settings()['llm']


def get_llm_prompt_config() -> Dict[str, Any]:
    return get_llm_config()['prompt']


def get_ocr_config() -> Dict[str, Any]:
    return load_settings()['ocr']
