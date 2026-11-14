"""Pure-Python game rules, shared by the human UI and the simple AI."""

from __future__ import annotations

import json
import random
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from csv_to_json import validate_cards
from deck_store import validate_deck, validate_legendary
from effect_parser import EffectParser, MANUAL_TARGETS
from mate_rules import MateRules
from board_rules import BOARD_LIMIT, CENTER_SLOTS, CORNER_SLOTS


MOVE_COST = 1
CASTLE_COST = 2
CASTLE_ARMOR = 6
HAND_LIMIT = 10
PlayMode = Literal["piece", "manobra"]
KEYWORD_LABELS = {
    "charge": "Iniciativa", "rush": "Desenvolvimento",
    "divine_shield": "Proteção", "windfury": "Ataque duplo", "elusive": "Elusivo",
}


class RuleError(ValueError):
    """A rejected player action; the caller must display its message."""


@dataclass(eq=False)
class Card:
    uid: int
    definition: dict

    @property
    def name(self) -> str:
        return self.definition["name"]

    def mode(self, mode: PlayMode) -> dict:
        if mode not in ("piece", "manobra"):
            raise RuleError("Modo invalido: escolha piece ou manobra.")
        return self.definition["piece_mode" if mode == "piece" else "manouvre_mode"]


@dataclass(eq=False)
class Unit:
    uid: int
    owner: int
    card_id: str
    name: str
    attack: int
    health: int
    max_health: int
    keywords: set[str]
    effects: list[dict]
    summoned_turn: int
    slot: int
    attacks_used: int = 0
    frozen_through: int = -1
    temporary_attack: int = 0
    is_king: bool = False
    definition_id: str = ""
    has_attacked: bool = False
    piece_type: str = ""
    source_card: Card | None = None


@dataclass(eq=False)
class Player:
    owner: int
    name: str
    deck: list[str]
    hand: list[Card] = field(default_factory=list)
    discard: list[Card] = field(default_factory=list)
    board: list[Unit] = field(default_factory=list)
    _health: int = 30
    max_health: int = 30
    max_mana: int = 0
    mana: int = 0
    fatigue: int = 0
    turns_started: int = 0
    endgame_ready: bool = False
    king: Unit | None = None
    maneuvers_played: int = 0
    armor: int = 0
    castled: bool = False
    center_bonus_pending: bool = False
    temporary_mana: int = 0

    def unit_at(self, slot: int) -> Unit | None:
        return next((unit for unit in self.board if unit.slot == slot), None)

    def free_slots(self) -> list[int]:
        occupied = {unit.slot for unit in self.board}
        return [slot for slot in range(BOARD_LIMIT) if slot not in occupied]

    @property
    def health(self) -> int:
        return self.king.health if self.king else self._health

    @health.setter
    def health(self, value: int) -> None:
        if self.king:
            self.king.health = value
        else:
            self._health = value


Entity = Player | Unit


def load_cards(path: Path | None = None) -> list[dict]:
    path = path or Path(__file__).resolve().parent / "data" / "cards.json"
    return validate_cards(json.loads(path.read_text(encoding="utf-8")))


class Game:
    def __init__(
        self, cards: list[dict], deck_size: int = 30, seed: int | None = None,
        opening_hand: int = 3,
        player_deck: list[str] | None = None,
        on_damage: Callable[[int], None] | None = None,
    ):
        validate_cards(cards)
        if isinstance(deck_size, bool) or not isinstance(deck_size, int) or deck_size < 1:
            raise ValueError("deck_size deve ser inteiro positivo")
        if isinstance(opening_hand, bool) or not isinstance(opening_hand, int) or not 0 <= opening_hand <= HAND_LIMIT:
            raise ValueError("opening_hand deve estar entre 0 e 10")
        self.catalog = {card["id"]: card for card in cards}
        custom_deck = validate_deck(player_deck, self.catalog) if player_deck is not None else None
        if custom_deck is not None:
            validate_legendary(custom_deck, self.catalog)
        self.rng = random.Random(seed)
        self._next_uid = 1
        self.messages: deque[str] = deque(maxlen=150)
        self.current = 0
        self.turn_number = 1
        self.over = False
        self.winner: int | None = None
        self._cleaning = False
        self.on_damage = on_damage
        decks = [self._make_deck(deck_size) if custom_deck is None else custom_deck,
                 self._make_deck(deck_size)]
        if custom_deck is not None:
            self.rng.shuffle(decks[0])
        self.players = [
            Player(owner, name, decks[owner])
            for owner, name in enumerate(("Jogador", "Adversario"))
        ]
        self.parser = EffectParser(self)
        self.mates = MateRules(self)
        for owner in (0, 1):
            for _ in range(min(opening_hand, len(self.players[owner].deck))):
                self.draw_card(owner)
        self.start_turn()

    def _make_deck(self, size: int) -> list[str]:
        ids = [
            card_id for card_id, card in self.catalog.items()
            if "base_id" not in card and card.get("rarity") != "legendary"
        ]
        if not ids:
            raise ValueError("O catalogo exige ao menos uma carta nao lendaria para decks automaticos.")
        deck = [ids[index % len(ids)] for index in range(size)]
        self.rng.shuffle(deck)
        return deck

    def uid(self) -> int:
        result = self._next_uid
        self._next_uid += 1
        return result

    def log(self, text: str) -> None:
        self.messages.append(text)

    def hero_target(self, owner: int) -> Entity:
        return self.players[owner].king or self.players[owner]

    @staticmethod
    def entity_name(entity: Entity) -> str:
        return f"Rei ({entity.name})" if isinstance(entity, Player) else entity.name

    def require_turn(self, owner: int) -> None:
        if self.over:
            raise RuleError("A partida terminou.")
        if self.current != owner:
            raise RuleError("Aguarde seu turno.")

    def castle_unavailable_reason(self, owner: int) -> str:
        if self.over:
            return "A partida terminou."
        if self.current != owner:
            return "Aguarde seu turno."
        player = self.players[owner]
        if player.castled:
            return "Roque ja foi usado nesta partida."
        if player.king:
            return "Roque exige o Rei fora do tabuleiro."
        if not any(
            unit.health > 0 and not unit.is_king and unit.piece_type == "torre"
            and unit.slot in CORNER_SLOTS for unit in player.board
        ):
            return "Roque exige uma Torre aliada em um canto."
        if player.mana < CASTLE_COST:
            return "Tempo insuficiente para o Roque."
        return ""

    def can_castle(self, owner: int) -> bool:
        return not self.castle_unavailable_reason(owner)

    def castle(self, owner: int) -> None:
        reason = self.castle_unavailable_reason(owner)
        if reason:
            raise RuleError(reason)
        player = self.players[owner]
        player.mana -= CASTLE_COST
        player.armor += CASTLE_ARMOR
        player.castled = True
        self.log(f"{player.name} usa Roque: +{CASTLE_ARMOR} de Armadura (Seguranca do Rei).")

    def draw_card(self, owner: int) -> None:
        player = self.players[owner]
        if not player.deck:
            player.endgame_ready = True
            self.activate_king(owner)
            player.fatigue += 1
            self.log(f"{player.name}: fadiga {player.fatigue}.")
            self.damage(self.hero_target(owner), player.fatigue)
            self.cleanup()
            return
        card_id = player.deck.pop()
        if len(player.hand) >= HAND_LIMIT:
            player.discard.append(Card(self.uid(), self.catalog[card_id]))
            self.log(f"{player.name}: mao cheia, {self.catalog[card_id]['name']} descartada.")
        else:
            player.hand.append(Card(self.uid(), self.catalog[card_id]))
            self.log(f"{player.name} compra uma carta.")
        if not player.deck:
            player.endgame_ready = True
            self.activate_king(owner)

    def start_turn(self) -> None:
        player = self.players[self.current]
        player.turns_started += 1
        player.maneuvers_played = 0
        player.max_mana = min(10, player.max_mana + 1)
        player.temporary_mana = int(player.center_bonus_pending)
        player.center_bonus_pending = False
        player.mana = player.max_mana + player.temporary_mana
        if player.temporary_mana:
            self.log(f"{player.name}: dominio do Centro concede +1 tempo temporario.")
        for unit in player.board:
            unit.attacks_used = 0
        self.log(f"Turno {self.turn_number} - {player.name} ({player.mana} tempo).")
        self.draw_card(self.current)
        for unit in list(player.board):
            if not self.over and unit in player.board:
                self.parser.execute(unit.effects, "on_turn_start", self.current, unit)

    def end_turn(self, owner: int) -> None:
        self.require_turn(owner)
        for unit in list(self.players[owner].board):
            if not self.over and unit in self.players[owner].board:
                self.parser.execute(unit.effects, "on_turn_end", owner, unit)
        for player in self.players:
            for unit in player.board:
                unit.attack -= unit.temporary_attack
                unit.temporary_attack = 0
        if self.over:
            return
        self.mates.invalidate()
        self.mates.announce(owner)
        player = self.players[owner]
        player.center_bonus_pending = self.center_control(owner) > self.center_control(1 - owner)
        if player.center_bonus_pending:
            self.log(f"{player.name} domina o Centro: +1 tempo no proximo turno.")
        # Eight complete rounds = sixteen individual player turns.
        if self.turn_number >= 16 and sum(len(p.board) for p in self.players) <= 3:
            for player in self.players:
                if not player.endgame_ready:
                    self.log(f"{player.name}: Final de jogo disponivel por tabuleiro reduzido.")
                player.endgame_ready = True
        self.current = 1 - owner
        self.turn_number += 1
        self.start_turn()

    def can_activate_king(self, owner: int) -> bool:
        player = self.players[owner]
        return (
            not self.over and player.health > 0 and player.endgame_ready
            and player.king is None and len(player.board) < BOARD_LIMIT
        )

    def activate_king(self, owner: int, *, manual: bool = False) -> bool:
        if manual:
            self.require_turn(owner)
            if not self.can_activate_king(owner):
                raise RuleError("Rei indisponivel: exige Final de jogo e um espaco livre.")
        if not self.can_activate_king(owner):
            if not self.over and self.players[owner].endgame_ready and not self.players[owner].king:
                self.log(f"{self.players[owner].name}: Rei aguarda um espaco livre.")
            return False
        player = self.players[owner]
        king = Unit(
            self.uid(), owner, "rei", f"Rei ({player.name})", 2, player.health,
            player.max_health, set(), [], self.turn_number, is_king=True,
            slot=player.free_slots()[0], piece_type="rei",
        )
        player.king = king
        player.board.append(king)
        player.board.sort(key=lambda unit: unit.slot)
        self.mates.invalidate()
        self.log(f"{player.name} ativa o Rei: 2/{king.health}.")
        return True

    def summon(self, owner: int, card_id: str, position: int | None = None) -> Unit | None:
        player = self.players[owner]
        if len(player.board) >= BOARD_LIMIT:
            self.log(f"{player.name}: desenvolvimento de {self.catalog[card_id]['name']} falhou, tabuleiro cheio.")
            return None
        position = player.free_slots()[0] if position is None else position
        self.require_free_slot(owner, position)
        card = self.catalog[card_id]
        piece = card["piece_mode"]
        unit = Unit(
            self.uid(), owner, card.get("base_id", card_id), card["name"], piece["attack"], piece["health"],
            piece["health"], set(piece["keywords"]), piece["effects"], self.turn_number,
            definition_id=card_id, slot=position, piece_type=piece["piece_type"],
        )
        player.board.append(unit)
        player.board.sort(key=lambda unit: unit.slot)
        self.mates.invalidate()
        self.log(f"{player.name} desenvolve {unit.name} na casa {position + 1}.")
        return unit

    def move_unit(self, owner: int, unit: Unit, position: int) -> None:
        self.require_turn(owner)
        player = self.players[owner]
        if unit.owner != owner or unit not in player.board:
            raise RuleError("Escolha uma peça sua no tabuleiro.")
        if unit.is_king:
            raise RuleError("O Rei nao pode ser reposicionado.")
        self.require_free_slot(owner, position)
        if player.mana < MOVE_COST:
            raise RuleError(f"Tempo insuficiente para reposicionar ({MOVE_COST}).")
        origin = unit.slot
        player.mana -= MOVE_COST
        unit.slot = position
        player.board.sort(key=lambda item: item.slot)
        self.mates.invalidate()
        self.log(f"{player.name} move {unit.name}: casa {origin + 1} -> {position + 1} ({MOVE_COST} tempo).")

    def require_free_slot(self, owner: int, position: int) -> None:
        if (
            isinstance(position, bool) or not isinstance(position, int)
            or not 0 <= position < BOARD_LIMIT
        ):
            raise RuleError(f"Posicao de desenvolvimento invalida: escolha uma casa de 1 a {BOARD_LIMIT}.")
        if self.players[owner].unit_at(position) is not None:
            raise RuleError("Casa ocupada. Escolha um espaco livre.")

    def center_control(self, owner: int) -> int:
        return sum(unit.health > 0 and unit.slot in CENTER_SLOTS for unit in self.players[owner].board)

    def supported(self, unit: Unit) -> bool:
        return any(
            ally is not unit and ally.health > 0 and abs(ally.slot - unit.slot) == 1
            for ally in self.players[unit.owner].board
        )

    def combat_damage(self, target: Entity, amount: int) -> int:
        if amount <= 0 or not isinstance(target, Unit):
            return amount
        supported = self.supported(target)
        adjusted = max(0, amount - 1) if supported else amount + 1
        self.log(
            f"{target.name}: {'Apoiada (-1)' if supported else 'Pendurada (+1)'}"
            f", dano de combate {adjusted}."
        )
        return adjusted

    def manual_effects(self, card: Card, mode: PlayMode = "piece") -> list[dict]:
        return [
            effect for effect in card.mode(mode)["effects"]
            if effect["trigger"] == "on_play" and effect.get("target") in MANUAL_TARGETS
        ]

    def valid_card_targets(self, owner: int, card: Card, mode: PlayMode = "piece") -> list[Entity]:
        effects = self.manual_effects(card, mode)
        if not effects:
            return []
        # A piece's battlecry is not a maneuver and can select Elusive units.
        groups = [
            self.parser.resolve_targets(
                effect, owner, preview=True,
                allow_elusive=mode == "piece",
            )
            for effect in effects
        ]
        return [entity for entity in groups[0] if all(entity in group for group in groups[1:])]

    def playable(self, owner: int, card: Card, mode: PlayMode | None = None) -> bool:
        if mode is None:
            return any(self.playable(owner, card, candidate) for candidate in ("piece", "manobra"))
        definition = card.mode(mode)
        player = self.players[owner]
        return (
            not self.over and self.current == owner and card in player.hand
            and definition["cost"] <= player.mana
            and (mode != "piece" or len(player.board) < BOARD_LIMIT)
            and (not self.manual_effects(card, mode) or bool(self.valid_card_targets(owner, card, mode)))
            and not self.mate_unavailable_reason(owner, card, mode)
        )

    def mate_unavailable_reason(self, owner: int, card: Card, mode: PlayMode = "manobra") -> str:
        for effect in card.mode(mode)["effects"]:
            if effect["action"] == "win_pattern":
                reason = self.mates.unavailable_reason(owner, effect["pattern"])
                if reason:
                    return reason
        return ""

    def play_card(
        self, owner: int, card: Card, target: Entity | None = None,
        position: int | None = None, *, mode: PlayMode = "piece",
    ) -> None:
        self.require_turn(owner)
        player = self.players[owner]
        if card not in player.hand:
            raise RuleError("Carta nao esta na mao.")
        definition = card.mode(mode)
        if definition["cost"] > player.mana:
            raise RuleError("Tempo insuficiente.")
        if mode == "piece":
            if len(player.board) >= BOARD_LIMIT:
                raise RuleError(f"Seu tabuleiro ja tem {BOARD_LIMIT} peças.")
            if position is not None:
                self.require_free_slot(owner, position)
        elif position is not None:
            raise RuleError("Manobras nao ocupam casas do tabuleiro.")
        if self.manual_effects(card, mode) and target not in self.valid_card_targets(owner, card, mode):
            raise RuleError("Escolha um alvo valido para a carta.")
        if not self.manual_effects(card, mode) and target is not None:
            raise RuleError("Esta carta nao exige alvo.")
        reason = self.mate_unavailable_reason(owner, card, mode)
        if reason:
            raise RuleError(reason)
        player.mana -= definition["cost"]
        player.hand.remove(card)
        self.log(f"{player.name} joga {card.name} como {'Peça' if mode == 'piece' else 'Manobra'}.")
        source = None
        if mode == "piece":
            source = self.summon(owner, card.definition["id"], position)
            if source is not None:
                source.source_card = card
        self.parser.execute(definition["effects"], "on_play", owner, source, target)
        if mode == "manobra":
            player.discard.append(card)
            player.maneuvers_played += 1
        self.cleanup()

    def attack_targets(self, unit: Unit) -> list[Entity]:
        if (
            self.over or unit.owner != self.current
            or unit not in self.players[unit.owner].board or unit.health <= 0
            or unit.attack <= 0 or unit.attacks_used >= (2 if "windfury" in unit.keywords else 1)
            or self.players[unit.owner].turns_started <= unit.frozen_through
        ):
            return []
        just_summoned = unit.summoned_turn == self.turn_number
        if just_summoned and not ({"charge", "rush"} & unit.keywords):
            return []
        enemy = self.players[1 - unit.owner]
        targets: list[Entity]
        if unit.piece_type in {"torre", "bispo", "cavalo", "dama"}:
            if unit.piece_type == "torre":
                front = lambda slot: slot >= unit.slot if unit.owner == 0 else slot <= unit.slot
                targets = [entity for entity in enemy.board if front(entity.slot) and abs(entity.slot - unit.slot) <= 3]
            elif unit.piece_type == "bispo":
                targets = [entity for entity in enemy.board if abs(entity.slot - unit.slot) <= 2]
            elif unit.piece_type == "cavalo":
                targets = [entity for entity in enemy.board if abs(entity.slot - unit.slot) <= 2]
            else:
                front = lambda slot: slot >= unit.slot if unit.owner == 0 else slot <= unit.slot
                targets = [entity for entity in enemy.board if front(entity.slot) and abs(entity.slot - unit.slot) <= 3]
            if not targets:
                targets = [self.hero_target(enemy.owner)]
            if just_summoned and "charge" not in unit.keywords:
                targets = [entity for entity in targets if entity is not self.hero_target(enemy.owner)]
            return targets

        targets = list(enemy.board)
        if not enemy.king:
            targets.append(enemy)
        if just_summoned and "charge" not in unit.keywords:
            targets = [entity for entity in targets if entity is not self.hero_target(enemy.owner)]
        return targets

    def attack(self, owner: int, unit: Unit, target: Entity) -> None:
        self.require_turn(owner)
        if unit.owner != owner or target not in self.attack_targets(unit):
            raise RuleError("Ataque invalido: verifique prontidao, congelamento e alcance.")
        unit.attacks_used += 1
        unit.has_attacked = True
        retaliation = target.attack if isinstance(target, Unit) else 0
        self.log(f"{unit.name} ataca {self.entity_name(target)}.")
        dealt = self.combat_damage(target, unit.attack)
        received = self.combat_damage(unit, retaliation)
        self.damage(target, dealt)
        if retaliation:
            self.damage(unit, received)
        self.cleanup()

    def damage(self, target: Entity, amount: int) -> None:
        if amount <= 0:
            return
        if isinstance(target, Unit) and "divine_shield" in target.keywords:
            target.keywords.remove("divine_shield")
            self.log(f"{target.name}: Proteção absorve o dano.")
            return
        hero = target if isinstance(target, Player) else self.players[target.owner] if target.is_king else None
        absorbed = min(hero.armor, amount) if hero is not None else 0
        if hero is not None and absorbed:
            hero.armor -= absorbed
            self.log(f"{self.entity_name(self.hero_target(hero.owner))}: Armadura absorve {absorbed} de dano.")
        target.health -= amount - absorbed
        if self.on_damage is not None:
            self.on_damage(amount)
        self.log(f"{self.entity_name(target)} sofre {amount} de dano.")

    def heal(self, target: Entity, amount: int) -> None:
        healed = min(amount, max(0, target.max_health - target.health))
        target.health += healed
        self.log(f"{self.entity_name(target)} recupera {healed} de vida.")

    def cleanup(self) -> None:
        self.mates.invalidate()
        if self._cleaning:
            self.check_winner()
            return
        self._cleaning = True
        try:
            while True:
                dead = [unit for p in self.players for unit in p.board if unit.health <= 0]
                for unit in dead:
                    self.players[unit.owner].board.remove(unit)
                    if not unit.is_king:
                        self.players[unit.owner].discard.append(
                            unit.source_card or Card(unit.uid, self.catalog[unit.definition_id or unit.card_id])
                        )
                    self.log(f"{unit.name} saiu do tabuleiro.")
                self.mates.invalidate()
                self.check_winner()
                if self.over or not dead:
                    break
                for unit in dead:
                    self.parser.execute(unit.effects, "on_death", unit.owner, unit)
            if not self.over:
                for player in self.players:
                    # Exhausted decks activate automatically as soon as space is available.
                    if not player.deck and self.can_activate_king(player.owner):
                        self.activate_king(player.owner)
        finally:
            self._cleaning = False

    def check_winner(self) -> None:
        if self.over:
            return
        defeated = [p.owner for p in self.players if p.health <= 0]
        if defeated:
            self.over = True
            self.winner = 1 - defeated[0] if len(defeated) == 1 else None
            self.log("Empate!" if self.winner is None else f"{self.players[self.winner].name} venceu!")

    def ai_step(self) -> None:
        """Perform one legal action; the UI schedules steps without blocking events."""
        if self.over or self.current != 1:
            return
        if self.can_castle(1):
            self.castle(1)
            return
        if self.can_activate_king(1):
            self.activate_king(1, manual=True)
            return
        player = self.players[1]
        options = [
            (card, mode) for card in player.hand for mode in ("piece", "manobra")
            if self.playable(1, card, mode)
        ]
        if options:
            card, mode = max(options, key=lambda option: (
                any(e["action"] == "win_pattern" for e in option[0].mode(option[1])["effects"]),
                option[0].mode(option[1])["cost"],
                option[1] == "piece",
            ))
            targets = self.valid_card_targets(1, card, mode)
            target = self.rng.choice(targets) if targets else None
            position = None
            if mode == "piece":
                prefer_corner = (
                    card.mode("piece")["piece_type"] == "torre"
                    and not player.castled and not player.king
                )
                position = min(
                    player.free_slots(),
                    key=lambda slot: (slot not in (CORNER_SLOTS if prefer_corner else CENTER_SLOTS), slot),
                )
            self.play_card(1, card, target, position, mode=mode)
            return
        for unit in player.board:
            targets = self.attack_targets(unit)
            if targets:
                hero = self.hero_target(0)
                target = hero if hero in targets else min(targets, key=lambda e: e.health)
                self.attack(1, unit, target)
                return
        self.end_turn(1)
