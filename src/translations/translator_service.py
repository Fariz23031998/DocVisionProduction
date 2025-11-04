from pathlib import Path
import json
from typing import Dict


class Translator:
    _cache: Dict[str, dict] = {}  # Class-level cache
    _locales_dir = Path(__file__).parent / ''

    def __init__(self, default_lang='en'):
        self.default_lang = default_lang
        # Load default language at startup
        self._load_language(default_lang)

    def _load_language(self, lang: str):
        """Load language file into memory (only once)"""
        if lang not in self._cache:
            file_path = self._locales_dir / f'{lang}.json'
            with open(file_path, 'r', encoding='utf-8') as f:
                self._cache[lang] = json.load(f)

    def get_language_translations(self, lang: str) -> Dict[str, str]:
        if lang not in self._cache:
            self._load_language(lang)
            return self._cache[lang]

        return self._cache[lang]

    def get_language_version(self, lang: str) -> str:
        if lang not in self._cache:
            self._load_language(lang)
            return self._cache[lang]['version']

        return self._cache[lang]['version']

    def get(self, key: str, lang: str = None) -> str:
        lang = lang or self.default_lang
        self._load_language(lang)  # No-op if already loaded
        return self._cache[lang].get(key, key)

    @classmethod
    def clear_cache(cls):
        """Useful for hot-reloading in development"""
        cls._cache.clear()


# Usage
t = Translator()
test = t.get_language_version("uz")  # Fast: reads from memory
print(test)
