"""Validated local deck persistence, independent of pygame."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Collection
from collections import Counter


DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "decks.json"
RETIRED_ROQUE_IDS = {"roque", "roque__improved", "roque__perfect"}


def validate_legendary(deck: list[str], catalog: dict[str, dict]) -> None:
    counts = Counter(
        catalog[card_id].get("base_id", card_id)
        for card_id in deck if catalog[card_id].get("rarity") == "legendary"
    )
    if any(count > 1 for count in counts.values()):
        raise ValueError("Apenas uma copia de cada carta lendaria por deck, somando qualidades.")


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
        self.migrated = False

    def validate(self, decks: object, *, allow_empty: bool = False, legacy: bool = False) -> dict[str, list[str]]:
        if not isinstance(decks, dict):
            raise ValueError("A biblioteca de decks deve ser um objeto JSON.")
        result = {}
        for name, cards in decks.items():
            if not isinstance(name, str) or not name.strip() or len(name) > 40 or name != name.strip():
                raise ValueError("Nomes de decks devem ter entre 1 e 40 caracteres, sem espacos nas pontas.")
            if any(not character.isprintable() for character in name):
                raise ValueError("O nome do deck contem caracteres de controle.")
            if allow_empty and cards == []:
                result[name] = []
            else:
                catalog = self.catalog | RETIRED_ROQUE_IDS if legacy else self.catalog
                result[name] = validate_deck(cards, catalog)
        return result

    def load(self) -> dict[str, list[str]]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        decks = self.validate(json.loads(text), allow_empty=True, legacy=True)
        migrated = {
            name: [card for card in cards if card not in RETIRED_ROQUE_IDS]
            for name, cards in decks.items()
        }
        validated = self.validate(migrated, allow_empty=True)
        if migrated != decks:
            write_json(self.path, validated)
            self.migrated = True
        return validated

    def save(self, decks: dict[str, list[str]], *, allow_empty: bool = False) -> None:
        validated = self.validate(decks, allow_empty=allow_empty)
        write_json(self.path, validated)
