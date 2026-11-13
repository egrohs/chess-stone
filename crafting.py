"""Persistent puzzle rewards and deterministic, engine-compatible card variants."""

from __future__ import annotations

import copy
import json
import math
from collections import Counter
from pathlib import Path

from csv_to_json import validate_cards
from deck_store import write_json


STARTER_IDS = {"peao", "cavalo", "bispo", "torre", "dama"}
QUALITY_LABELS = {"basic": "Basica", "improved": "Aprimorada", "perfect": "Perfeita"}
THEMES = {
    "peao": ("pawnEndgame", "Final de peoes"),
    "cavalo": ("knightEndgame", "Final de cavalos"),
    "bispo": ("bishopEndgame", "Final de bispos"),
    "torre": ("rookEndgame", "Final de torres"),
    "dama": ("queenEndgame", "Final de damas"),
    "cravada_absoluta": ("pin", "Cravada (inclui cravadas relativas)"),
    "ataque_duplo": ("fork", "Garfo / ataque duplo"),
    "par_de_bispos": ("doubleBishopMate", "Mate com dois bispos"),
    "coluna_aberta": ("clearance", "Desobstrucao (aproximacao de coluna aberta)"),
    "zugzwang": ("zugzwang", "Zugzwang"),
    "roque": ("castling", "Roque"),
    "sacrificio_da_dama": ("sacrifice", "Sacrificio (nao necessariamente da dama)"),
}
DEFAULT_INVENTORY = Path(__file__).resolve().parent / "data" / "collection.json"


def grade(errors: int, elapsed: float, moves: int) -> str:
    if errors == 0 and elapsed <= moves * 60:
        return "perfect"
    if errors <= 1 and elapsed <= moves * 120:
        return "improved"
    return "basic"


def variant_id(base_id: str, quality: str) -> str:
    return base_id if quality == "basic" else f"{base_id}__{quality}"


def make_variant(base: dict, quality: str) -> dict:
    card = copy.deepcopy(base)
    if quality == "basic":
        return card
    bonus = 1 if quality == "improved" else 2
    card["id"] = variant_id(base["id"], quality)
    card["base_id"] = base["id"]
    card["quality"] = quality
    card["name"] += f" ({QUALITY_LABELS[quality]})"
    if card["type"] == "minion":
        card["attack"] += bonus
        card["health"] += bonus
        extra = f"+{bonus}/+{bonus}."
        if quality == "perfect":
            # A separate triggered effect avoids duplicating an existing keyword.
            card["effects"].append({"trigger": "on_play", "action": "draw", "amount": 1})
            extra += " Ao jogar: compre 1 carta."
    else:
        card["effects"].append({
            "trigger": "on_play", "action": "heal", "amount": bonus, "target": "own_hero",
        })
        extra = f"Cure seu Rei em mais {bonus}."
        if quality == "perfect":
            card["effects"].append({"trigger": "on_play", "action": "draw", "amount": 1})
            extra += " Compre mais 1 carta."
    card["description"] += f" Crafting: {extra}"
    return card


class CraftingInventory:
    def __init__(self, base_cards: list[dict], path: Path = DEFAULT_INVENTORY):
        self.base_cards = base_cards
        self.base_catalog = {c["id"]: c for c in base_cards}
        self.path = path
        self.rewards: list[dict] = []
        self.error = ""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.rewards = self.validate(data)
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            self.error = f"Erro ao ler colecao: {error}. Corrija o arquivo e reinicie o jogo."

    def validate(self, data: object) -> list[dict]:
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("rewards"), list):
            raise ValueError("Formato de colecao invalido.")
        seen = set()
        for reward in data["rewards"]:
            if not isinstance(reward, dict) or set(reward) != {
                "puzzle_id", "base_id", "quality", "errors", "elapsed", "moves",
            }:
                raise ValueError("Recompensa invalida.")
            if (
                not isinstance(reward["puzzle_id"], str) or not reward["puzzle_id"].isalnum()
                or reward["puzzle_id"] in seen
                or not isinstance(reward["base_id"], str) or reward["base_id"] not in self.base_catalog
            ):
                raise ValueError("Puzzle repetido ou carta desconhecida na colecao.")
            for field, minimum in (("errors", 0), ("moves", 1)):
                if type(reward[field]) is not int or reward[field] < minimum:
                    raise ValueError(f"{field} invalido.")
            if (
                type(reward["elapsed"]) not in (int, float)
                or not math.isfinite(reward["elapsed"]) or reward["elapsed"] < 0
                or reward["quality"] != grade(reward["errors"], reward["elapsed"], reward["moves"])
            ):
                raise ValueError("Qualidade ou tempo invalido.")
            seen.add(reward["puzzle_id"])
        return copy.deepcopy(data["rewards"])

    @property
    def completed(self) -> set[str]:
        return {r["puzzle_id"] for r in self.rewards}

    def count(self, card_id: str) -> int | None:
        if card_id in STARTER_IDS:
            return None  # Starter pieces retain the prototype's unlimited-copy rule.
        return sum(variant_id(r["base_id"], r["quality"]) == card_id for r in self.rewards)

    def catalog(self, *, all_variants: bool = False) -> list[dict]:
        cards = copy.deepcopy(self.base_cards)
        for base in self.base_cards:
            for quality in ("improved", "perfect"):
                if all_variants or self.count(variant_id(base["id"], quality)):
                    cards.append(make_variant(base, quality))
        return validate_cards(cards)

    def validate_owned(self, deck: list[str]) -> None:
        for card_id, needed in Counter(deck).items():
            available = self.count(card_id)
            if available is not None and needed > available:
                raise ValueError(f"{card_id}: deck pede {needed}, colecao possui {available}.")

    def award(self, base_id: str, puzzle_id: str, errors: int, elapsed: float, moves: int) -> dict:
        if self.error:
            raise ValueError(self.error)
        quality = grade(errors, elapsed, moves)
        reward = dict(
            base_id=base_id, puzzle_id=puzzle_id, quality=quality,
            errors=errors, elapsed=elapsed, moves=moves,
        )
        data = {"version": 1, "rewards": [*self.rewards, reward]}
        validated = self.validate(data)
        write_json(self.path, data)
        self.rewards = validated
        return make_variant(self.base_catalog[base_id], quality)
