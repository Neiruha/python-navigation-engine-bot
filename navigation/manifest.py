import json
from typing import Dict, Any

class ManifestLoader:
    def __init__(self, manifest_path: str = "menu-manifest.json"):
        self.manifest_path = manifest_path
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Манифест не найден: {self.manifest_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Невалидный JSON: {e}")
        if "screens" not in data:
            raise ValueError("Манифест должен содержать 'screens'")
        if "defaults" not in data:
            data["defaults"] = {}
        return data

    @property
    def screens(self) -> Dict[str, Any]:
        return self.data["screens"]

    @property
    def defaults(self) -> Dict[str, Any]:
        return self.data["defaults"]