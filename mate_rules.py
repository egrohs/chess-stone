"""Telegraphed alternate victories on eight fixed board slots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game_engine import Game, Unit


PATTERNS = {"anastasia", "boden", "smothered", "back_rank", "opera", "opposition"}
LABELS = {
    "anastasia": "Mate de Anastasia", "boden": "Mate de Boden",
    "smothered": "Mate Abafado", "back_rank": "Mate de Gaveta",
    "opera": "Mate da Opera", "opposition": "Endgame Puro",
}


@dataclass(frozen=True)
class MateThreat:
    pattern: str
    units: tuple[int, ...]
    announced_turn: int


class MateRules:
    def __init__(self, game: Game):
        self.game = game
        self.threats: dict[int, list[MateThreat]] = {0: [], 1: []}

    def formations(self, owner: int, pattern: str) -> list[tuple[Unit, ...]]:
        board = self.game.players[owner].board
        pairs = []
        if pattern == "anastasia" and len(board) >= 3:
            player = self.game.players[owner]
            for rook_slot, knight_slot in ((0, 1), (7, 6)):
                rook, knight = player.unit_at(rook_slot), player.unit_at(knight_slot)
                if rook and knight and rook.card_id == "torre" and knight.card_id == "cavalo":
                    pairs.append((rook, knight))
        elif pattern == "boden" and len(board) >= 4:
            player = self.game.players[owner]
            left, right = player.unit_at(0), player.unit_at(7)
            if (
                left and right and left.card_id == right.card_id == "bispo"
                and sum(not unit.is_king and 0 < unit.slot < 7 for unit in board) >= 2
            ):
                pairs.append((left, right))
        elif pattern == "smothered":
            pairs.extend((unit,) for unit in board if unit.card_id == "cavalo")
        elif pattern == "back_rank":
            pairs.extend((unit,) for unit in board if unit.card_id == "torre")
        elif pattern == "opera":
            rooks = [unit for unit in board if unit.card_id == "torre"]
            bishops = [unit for unit in board if unit.card_id == "bispo"]
            if len(rooks) == len(bishops) == 1:
                rook, bishop = rooks[0], bishops[0]
                if abs(rook.slot - bishop.slot) == 1:
                    pairs.append((rook, bishop))
        elif pattern == "opposition":
            player = self.game.players[owner]
            enemy = self.game.players[1 - owner]
            if (
                player.king is not None and enemy.king is not None
                and player.board == [player.king] and enemy.board == [enemy.king]
            ):
                pairs.append((player.king,))
        return [
            pair for pair in pairs
            if all(
                unit.health > 0 and unit.attack > 0
                and unit.frozen_through < self.game.players[owner].turns_started
                for unit in pair
            )
        ]

    def invalidate(self) -> None:
        for owner in (0, 1):
            remaining = []
            for threat in self.threats[owner]:
                formations = self.formations(owner, threat.pattern)
                if any(tuple(u.uid for u in pair) == threat.units for pair in formations):
                    remaining.append(threat)
                else:
                    self.game.log(f"{LABELS[threat.pattern]} de {self.game.players[owner].name}: preparacao desfeita.")
            self.threats[owner] = remaining

    def announce(self, owner: int) -> None:
        self.threats[owner] = []
        for pattern in sorted(PATTERNS):
            for pair in self.formations(owner, pattern):
                self.threats[owner].append(MateThreat(
                    pattern, tuple(u.uid for u in pair), self.game.turn_number,
                ))
                self.game.log(
                    f"AMEACA: {self.game.players[owner].name} prepara {LABELS[pattern]}"
                    " com " + " e ".join(f"{unit.name} #{unit.uid}" for unit in pair) + "."
                )

    def ready_pair(self, owner: int, pattern: str) -> tuple[Unit, ...] | None:
        self.invalidate()
        for threat in self.threats[owner]:
            if threat.pattern != pattern or self.game.turn_number < threat.announced_turn + 2:
                continue
            for pair in self.formations(owner, pattern):
                attack_requirement = (
                    all(u.attacks_used > 0 for u in pair) if pattern == "back_rank"
                    else all(u.attacks_used == 0 for u in pair)
                )
                if tuple(u.uid for u in pair) == threat.units and attack_requirement:
                    return pair
        return None

    def unavailable_reason(self, owner: int, pattern: str) -> str:
        if self.ready_pair(owner, pattern) is None:
            attacks = "Torre que atacou neste turno" if pattern == "back_rank" else "sem ataques neste turno"
            return f"Exige formacao anunciada no turno anterior, intacta, descongelada e {attacks}."
        player = self.game.players[owner]
        enemy = self.game.players[1 - owner]
        if pattern == "anastasia":
            if enemy.health > 15:
                return "Anastasia exige inimigo com ate 15 de vida."
            if sum(not u.is_king for u in enemy.board) < 2:
                return "Anastasia exige ao menos dois lacaios inimigos."
            if any("taunt" in u.keywords for u in enemy.board):
                return "Anastasia e bloqueado por qualquer Provocar inimigo."
        elif pattern == "boden" and self.game.players[owner].spells_played < 2:
            return "Boden exige dois outros feiticos jogados neste turno."
        elif pattern == "smothered":
            if len(enemy.board) != 8 or any(unit.is_king for unit in enemy.board):
                return "Mate Abafado exige oito lacaios inimigos (Rei nao conta)."
            if any("taunt" in unit.keywords for unit in enemy.board):
                return "Mate Abafado e bloqueado por qualquer Provocar inimigo."
        elif pattern == "back_rank":
            blockers = sum(
                not unit.is_king and (unit.card_id in {"peao", "peao_passado"} or "taunt" in unit.keywords)
                for unit in enemy.board
            )
            if blockers < 3:
                return "Mate de Gaveta exige tres lacaios inimigos que sejam Peoes ou tenham Provocar."
            if enemy.armor != 0:
                return "Mate de Gaveta exige zero de Armadura inimiga."
        elif pattern == "opera":
            pair = self.ready_pair(owner, pattern)
            if pair is None or not all(unit.has_attacked for unit in pair):
                return "Mate da Opera exige que a Torre e o Bispo tenham atacado nesta partida."
            if enemy.health > 15 or sum(not unit.is_king for unit in enemy.board) != 1:
                return "Mate da Opera exige inimigo com ate 15 de vida e exatamente um lacaio."
        elif pattern == "opposition":
            if not any(
                card.definition.get("base_id", card.definition["id"]) == "peao_passado"
                for card in player.hand
            ):
                return "Endgame Puro exige um Peao Passado na mao."
            if player.health <= enemy.health:
                return "Endgame Puro exige mais vida no seu Rei que no Rei inimigo."
        return ""

    def execute(self, owner: int, pattern: str) -> None:
        reason = self.unavailable_reason(owner, pattern)
        if reason:
            self.game.log(f"{LABELS[pattern]} falhou: {reason}")
            return
        pair = self.ready_pair(owner, pattern)
        if pair is None:
            raise RuntimeError("Formacao de mate mudou durante a resolucao.")
        for unit in pair:
            unit.attacks_used = 2 if "windfury" in unit.keywords else 1
        self.game.over = True
        self.game.winner = owner
        self.game.log(f"{self.game.players[owner].name} venceu por {LABELS[pattern]}!")
