"""Validated local deck persistence, independent of pygame."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Collection


DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "decks.json"


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=path.name + ".", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def validate_deck(cards: object, catalog: Collection[str]) -> list[str]:
    if not isinstance(cards, list) or not cards:
        raise ValueError("O deck deve conter pelo menos uma carta.")
    if any(not isinstance(card, str) or card not in catalog for card in cards):
        raise ValueError("O deck contem IDs de cartas desconhecidos.")
    return list(cards)


class DeckStore:
    def __init__(self, catalog: Collection[str], path: Path = DEFAULT_PATH):
        self.catalog = set(catalog)
        self.path = path

    def validate(self, decks: object) -> dict[str, list[str]]:
        if not isinstance(decks, dict):
            raise ValueError("A biblioteca de decks deve ser um objeto JSON.")
        result = {}
        for name, cards in decks.items():
            if not isinstance(name, str) or not name.strip() or len(name) > 40 or name != name.strip():
                raise ValueError("Nomes de decks devem ter entre 1 e 40 caracteres, sem espacos nas pontas.")
            if any(not character.isprintable() for character in name):
                raise ValueError("O nome do deck contem caracteres de controle.")
            result[name] = validate_deck(cards, self.catalog)
        return result

    def load(self) -> dict[str, list[str]]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        return self.validate(json.loads(text))

    def save(self, decks: dict[str, list[str]]) -> None:
        validated = self.validate(decks)
        write_json(self.path, validated)
