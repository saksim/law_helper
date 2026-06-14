from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any

from .models import seed_data


class Store:
    def __init__(self, path: str | Path | None = None, data: dict[str, list[dict[str, Any]]] | None = None):
        self.path = Path(path) if path else None
        self._lock = RLock()
        if data is not None:
            self.data = deepcopy(data)
        elif self.path and self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = seed_data()
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        for key, value in seed_data().items():
            self.data.setdefault(key, deepcopy(value))

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self, collection: str) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self.data.setdefault(collection, []))

    def get(self, collection: str, item_id: str) -> dict[str, Any] | None:
        with self._lock:
            for item in self.data.setdefault(collection, []):
                if item.get("id") == item_id:
                    return deepcopy(item)
        return None

    def find_one(self, collection: str, **criteria: Any) -> dict[str, Any] | None:
        with self._lock:
            for item in self.data.setdefault(collection, []):
                if all(item.get(key) == value for key, value in criteria.items()):
                    return deepcopy(item)
        return None

    def insert(self, collection: str, item: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.data.setdefault(collection, []).append(deepcopy(item))
            self.save()
            return deepcopy(item)

    def update(self, collection: str, item_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            for index, item in enumerate(self.data.setdefault(collection, [])):
                if item.get("id") == item_id:
                    item.update(deepcopy(updates))
                    self.data[collection][index] = item
                    self.save()
                    return deepcopy(item)
        raise KeyError(f"{collection}:{item_id}")

    def replace_collection(self, collection: str, rows: list[dict[str, Any]]) -> None:
        with self._lock:
            self.data[collection] = deepcopy(rows)
            self.save()


def create_memory_store() -> Store:
    return Store(data=seed_data())
