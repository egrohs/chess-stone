"""Persistent puzzle rewards and deterministic, engine-compatible card variants."""

from __future__ import annotations

import copy
import json
import math
from collections import Counter
from pathlib import Path

from chess_puzzles import grade
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
    "sacrificio_da_dama": ("sacrifice", "Sacrificio (nao necessariamente da dama)"),
    "mate_anastasia": ("anastasiaMate", "Mate de Anastasia"),
    "mate_boden": ("bodenMate", "Mate de Boden"),
    "mate_abafado": ("smotheredMate", "Mate abafado"),
    "mate_gaveta": ("backRankMate", "Mate de gaveta"),
    "mate_opera": ("operaMate", "Mate da Opera"),
    "endgame_puro": ("pawnEndgame", "Final de peoes (aproximacao de oposicao)"),
    "peao_passado": ("advancedPawn", "Peao avancado (aproximacao de peao passado)"),
}
DEFAULT_INVENTORY = Path(__file__).resolve().parent / "data" / "collection.json"


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
    piece = card["piece_mode"]
    maneuver = card["manouvre_mode"]
    piece["attack"] += bonus
    piece["health"] += bonus
    maneuver["effects"].append({
        "trigger": "on_play", "action": "heal", "amount": bonus, "target": "own_hero",
    })
    extra = f"Peca: +{bonus}/+{bonus}. Manobra: cure seu Rei em mais {bonus}."
    if quality == "perfect":
        for mode in (piece, maneuver):
            mode["effects"].append({"trigger": "on_play", "action": "draw", "amount": 1})
        extra += " Em qualquer modo: compre mais 1 carta ao jogar."
    card["description"] += f" Crafting: {extra}"
    return card


class CraftingInventory:
    def __init__(self, base_cards: list[dict], path: Path = DEFAULT_INVENTORY):
        self.base_cards = base_cards
        self.base_catalog = {c["id"]: c for c in base_cards}
        self.path = path
        self.rewards: list[dict] = []
        self.retired_puzzles: list[str] = []
        self.error = ""
        self.migrated = False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rewards = self.validate(data, allow_retired=True)
            retained = [reward for reward in rewards if reward["base_id"] != "roque"]
            retired = data.get("retired_puzzles", []) + [
                reward["puzzle_id"] for reward in rewards if reward["base_id"] == "roque"
            ]
            if retained != rewards:
                write_json(path, {"version": 1, "rewards": retained, "retired_puzzles": retired})
                self.migrated = True
            self.rewards = retained
            self.retired_puzzles = retired
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            self.error = f"Erro ao ler colecao: {error}. Corrija o arquivo e reinicie o jogo."

    def validate(self, data: object, *, allow_retired: bool = False) -> list[dict]:
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("rewards"), list):
            raise ValueError("Formato de colecao invalido.")
        retired = data.get("retired_puzzles", [])
        if not isinstance(retired, list) or any(
            not isinstance(puzzle, str) or not puzzle.isalnum() for puzzle in retired
        ) or len(set(retired)) != len(retired):
            raise ValueError("Historico de puzzles invalido.")
        seen = set(retired)
        for reward in data["rewards"]:
            if not isinstance(reward, dict) or set(reward) != {
                "puzzle_id", "base_id", "quality", "errors", "elapsed", "moves",
            }:
                raise ValueError("Recompensa invalida.")
            if (
                not isinstance(reward["puzzle_id"], str) or not reward["puzzle_id"].isalnum()
                or reward["puzzle_id"] in seen
                or not isinstance(reward["base_id"], str)
                or (reward["base_id"] not in self.base_catalog
                    and not (allow_retired and reward["base_id"] == "roque"))
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
        return {r["puzzle_id"] for r in self.rewards} | set(self.retired_puzzles)

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
        if self.retired_puzzles:
            data["retired_puzzles"] = self.retired_puzzles
        validated = self.validate(data)
        write_json(self.path, data)
        self.rewards = validated
        return make_variant(self.base_catalog[base_id], quality)
