import json
from pathlib import Path


_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config' / 'settings.json'


def load_settings():
    with _DEFAULT_CONFIG_PATH.open('r', encoding='utf-8') as fp:
        return json.load(fp)