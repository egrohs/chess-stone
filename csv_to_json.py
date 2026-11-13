"""Convert spreadsheet-friendly card definitions into validated engine data."""

from __future__ import annotations

import argparse
import csv
import json
import unicodedata
from pathlib import Path
from mate_rules import PATTERNS


ROOT = Path(__file__).resolve().parent
COLUMNS = {
    "id", "name", "category", "card_type", "cost", "attack", "health",
    "keywords", "trigger", "effect_code", "description",
}
KEYWORDS = {"taunt", "charge", "rush", "divine_shield", "windfury", "elusive"}
KEYWORD_ALIASES = {
    "provocar": "taunt", "investida": "charge", "rapidez": "rush",
    "escudo_divino": "divine_shield", "furia_dos_ventos": "windfury",
    "elusivo": "elusive",
}
TRIGGERS = {"on_play", "on_death", "on_turn_start", "on_turn_end"}
ACTIONS = {
    "damage", "heal", "buff", "draw", "summon", "freeze",
    "grant_keyword", "activate_king", "destroy", "win_pattern",
}
TARGETS = {
    "self", "own_hero", "enemy_hero", "target_enemy", "target_enemy_minion",
    "target_ally", "target_ally_minion", "all_enemies", "all_enemy_minions",
    "all_allies", "all_allied_minions", "adjacent_allies", "random_enemy",
    "random_enemy_minion",
}
TARGET_ALIASES = {
    "target_2_enemies": ("random_enemy_minion", 2),
}


def normalize(text: str) -> str:
    plain = "".join(
        char for char in unicodedata.normalize("NFD", text.lower().strip())
        if unicodedata.category(char) != "Mn"
    )
    return plain.replace(" ", "_")


def integer(value: object, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label}: esperado inteiro >= {minimum}, recebido {value!r}")
    return value


def validate_effect(effect: object, label: str, nested: bool = False) -> None:
    if not isinstance(effect, dict):
        raise ValueError(f"{label}: efeito deve ser um objeto")
    allowed = {
        "trigger", "action", "amount", "target", "count", "on_kill",
        "attack", "health", "duration", "keyword", "card_id", "condition", "pattern",
    }
    if set(effect) - allowed:
        raise ValueError(f"{label}: campos desconhecidos {sorted(set(effect) - allowed)}")
    action = effect.get("action")
    if not isinstance(action, str) or action not in ACTIONS:
        raise ValueError(f"{label}: acao desconhecida {action!r}")
    if (not nested or "trigger" in effect) and (
        not isinstance(effect.get("trigger"), str) or effect["trigger"] not in TRIGGERS
    ):
        raise ValueError(f"{label}: gatilho desconhecido")
    if "target" in effect and (
        not isinstance(effect["target"], str) or effect["target"] not in TARGETS
    ):
        raise ValueError(f"{label}: alvo desconhecido {effect['target']!r}")
    if (
        str(effect.get("target", "")).startswith("target_")
        and not nested and effect["trigger"] != "on_play"
    ):
        raise ValueError(f"{label}: apenas on_play pode solicitar alvo manual")
    if action == "win_pattern" and (
        not isinstance(effect.get("pattern"), str) or effect["pattern"] not in PATTERNS
        or nested or effect.get("trigger") != "on_play"
    ):
        raise ValueError(f"{label}: padrao de mate invalido (exige on_play)")
    if action not in {"draw", "summon", "activate_king", "win_pattern"} and "target" not in effect:
        raise ValueError(f"{label}: acao {action} exige target")
    if action in {"damage", "heal", "draw"}:
        integer(effect.get("amount"), f"{label}.amount", 1)
    if "amount" in effect:
        integer(effect["amount"], f"{label}.amount", 1)
    if "count" in effect:
        integer(effect["count"], f"{label}.count", 1)
    if action == "buff":
        if "attack" not in effect and "health" not in effect:
            raise ValueError(f"{label}: buff exige attack ou health")
        for field in ("attack", "health"):
            if field in effect:
                integer(effect[field], f"{label}.{field}")
        if effect.get("duration", "permanent") not in {"permanent", "until_end_of_turn"}:
            raise ValueError(f"{label}: duracao desconhecida")
        if effect.get("duration") == "until_end_of_turn" and effect.get("health", 0):
            raise ValueError(f"{label}: apenas ataque pode ser temporario")
    if action == "grant_keyword" and (
        not isinstance(effect.get("keyword"), str) or effect["keyword"] not in KEYWORDS
    ):
        raise ValueError(f"{label}: palavra-chave desconhecida")
    if action == "summon" and not isinstance(effect.get("card_id"), str):
        raise ValueError(f"{label}: summon exige card_id")
    if "card_id" in effect and not isinstance(effect["card_id"], str):
        raise ValueError(f"{label}: card_id deve ser texto")
    if "condition" in effect:
        condition = effect["condition"]
        if (
            not isinstance(condition, dict)
            or set(condition) != {"type", "card_id", "at_least"}
            or condition.get("type") != "friendly_count"
            or not isinstance(condition.get("card_id"), str)
        ):
            raise ValueError(f"{label}: condicao invalida")
        integer(condition["at_least"], f"{label}.condition.at_least", 1)
    if "on_kill" in effect:
        if action not in {"damage", "destroy"}:
            raise ValueError(f"{label}: on_kill exige damage ou destroy")
        validate_effect(effect["on_kill"], f"{label}.on_kill", nested=True)
        if str(effect["on_kill"].get("target", "")).startswith("target_"):
            raise ValueError(f"{label}: on_kill nao pode pedir um novo alvo manual")


def validate_cards(cards: object) -> list[dict]:
    if not isinstance(cards, list) or not cards:
        raise ValueError("O catalogo deve ser uma lista nao vazia")
    ids: set[str] = set()
    for index, card in enumerate(cards):
        label = f"carta {index + 1}"
        if not isinstance(card, dict):
            raise ValueError(f"{label}: esperado objeto")
        for field in ("id", "name", "category", "description"):
            if not isinstance(card.get(field), str) or not card[field].strip():
                raise ValueError(f"{label}: {field} deve ser texto nao vazio")
        if card["id"] in ids:
            raise ValueError(f"ID duplicado: {card['id']}")
        ids.add(card["id"])
        if not isinstance(card.get("type"), str) or card["type"] not in {"minion", "spell"}:
            raise ValueError(f"{label}: type deve ser minion ou spell")
        integer(card.get("cost"), f"{label}.cost")
        if card["cost"] > 10:
            raise ValueError(f"{label}: custo maximo e 10")
        if card["type"] == "minion":
            integer(card.get("attack"), f"{label}.attack")
            integer(card.get("health"), f"{label}.health", 1)
        keywords = card.get("keywords")
        if not isinstance(keywords, list) or any(
            not isinstance(k, str) or k not in KEYWORDS for k in keywords
        ):
            raise ValueError(f"{label}: keywords invalidas")
        if not isinstance(card.get("effects"), list):
            raise ValueError(f"{label}: effects deve ser uma lista")
        if "rarity" in card and card["rarity"] != "legendary":
            raise ValueError(f"{label}: raridade desconhecida")
        for effect in card["effects"]:
            validate_effect(effect, label)
            if effect["action"] == "win_pattern" and (
                card["type"] != "spell" or card.get("rarity") != "legendary"
            ):
                raise ValueError(f"{label}: mate exige feitico lendario")
            if card["type"] == "spell" and effect["trigger"] != "on_play":
                raise ValueError(f"{label}: feiticos nao persistem para gatilhos futuros")
    for card in cards:
        pending = list(card["effects"])
        while pending:
            effect = pending.pop()
            reference = effect.get("card_id")
            if reference is not None and reference not in ids:
                raise ValueError(f"{card['id']}: carta referenciada inexistente {reference}")
            if effect["action"] == "summon":
                referenced = next(c for c in cards if c["id"] == reference)
                if referenced["type"] != "minion":
                    raise ValueError(f"{card['id']}: summon exige um lacaio")
            condition = effect.get("condition")
            if condition and condition["card_id"] not in ids:
                raise ValueError(f"{card['id']}: condicao referencia carta inexistente")
            if "on_kill" in effect:
                pending.append(effect["on_kill"])
    return cards


def parse_effect_code(code: str, trigger: str = "on_play") -> list[dict]:
    code = code.strip()
    if not code:
        return []
    if code.startswith(("[", "{")):
        decoded = json.loads(code)
        effects = decoded if isinstance(decoded, list) else [decoded]
        for effect in effects:
            if not isinstance(effect, dict):
                raise ValueError("Efeito estruturado deve ser um objeto")
            effect.setdefault("trigger", trigger or "on_play")
        return effects
    effects: list[dict] = []
    for segment in code.split("|"):
        parts = [part.strip() for part in segment.split(":")]
        action = normalize(parts[0])
        if len(parts) != 3 or action not in {"damage", "heal", "draw", "freeze"}:
            raise ValueError(f"Codigo invalido {segment!r}; use JSON para efeitos complexos")
        amount = int(parts[1])
        target_code = normalize(parts[2])
        effect: dict = {"action": action, "amount": amount}
        if target_code == "if_killed":
            if not effects or effects[-1]["action"] not in {"damage", "destroy"}:
                raise ValueError("IF_KILLED precisa seguir DAMAGE ou DESTROY")
            if "on_kill" in effects[-1]:
                raise ValueError("Apenas um on_kill por acao; use JSON para encadear")
            if action != "draw":
                raise ValueError("No formato curto, IF_KILLED aceita apenas DRAW")
            effects[-1]["on_kill"] = effect
            continue
        if action != "draw":
            target, count = TARGET_ALIASES.get(target_code, (target_code, 1))
            effect["target"] = target
            if count > 1:
                effect["count"] = count
        elif target_code not in TARGETS:
            raise ValueError(f"Alvo desconhecido {parts[2]!r}")
        effect["trigger"] = trigger or "on_play"
        effects.append(effect)
    return effects


def convert_csv(source: Path, destination: Path) -> list[dict]:
    cards = []
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or []) != COLUMNS:
            raise ValueError(f"Cabecalho deve conter exatamente: {', '.join(sorted(COLUMNS))}")
        for line, row in enumerate(reader, 2):
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("numero incorreto de colunas")
                keywords = [
                    KEYWORD_ALIASES.get(normalize(k), normalize(k))
                    for k in row["keywords"].replace(";", "|").split("|") if k.strip()
                ]
                card = {
                    "id": row["id"].strip(), "name": row["name"].strip(),
                    "category": row["category"].strip(),
                    "type": normalize(row["card_type"]), "cost": int(row["cost"]),
                    "keywords": keywords,
                    "effects": parse_effect_code(row["effect_code"], row["trigger"].strip()),
                    "description": row["description"].strip(),
                }
                if card["type"] == "minion":
                    card.update(attack=int(row["attack"]), health=int(row["health"]))
                if normalize(row["category"]) == "lendario":
                    card["rarity"] = "legendary"
                cards.append(card)
            except (ValueError, TypeError) as error:
                raise ValueError(f"Linha {line}: {error}") from error
    validate_cards(cards)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return cards


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=ROOT / "data" / "cards.csv")
    parser.add_argument("destination", nargs="?", type=Path, default=ROOT / "data" / "cards.json")
    args = parser.parse_args()
    try:
        cards = convert_csv(args.source, args.destination)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Erro na conversao: {error}\n")
    print(f"{len(cards)} cartas validadas: {args.destination}")


if __name__ == "__main__":
    main()
