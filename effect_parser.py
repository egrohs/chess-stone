"""Data-driven target resolution and ordered effect execution; no UI dependency."""

from __future__ import annotations

from typing import TYPE_CHECKING

from board_rules import BOARD_LIMIT

if TYPE_CHECKING:
    from game_engine import Entity, Game, Unit


MANUAL_TARGETS = {"target_enemy", "target_enemy_piece", "target_ally", "target_ally_piece"}


class EffectParser:
    def __init__(self, game: Game):
        self.game = game

    def resolve_targets(
        self, effect: dict, owner: int, source: Unit | None = None,
        target: Entity | None = None, *, preview: bool = False,
        allow_elusive: bool = False,
    ) -> list[Entity]:
        game = self.game
        allies = game.players[owner]
        enemies = game.players[1 - owner]
        code = effect.get("target", "self")
        own_hero = game.hero_target(owner)
        enemy_hero = game.hero_target(1 - owner)
        ally_units = list(allies.board)
        enemy_units = list(enemies.board)
        all_allies = ally_units + ([] if allies.king else [own_hero])
        all_enemies = enemy_units + ([] if enemies.king else [enemy_hero])
        groups = {
            "self": [source or own_hero],
            "own_hero": [own_hero], "enemy_hero": [enemy_hero],
            "target_enemy": all_enemies, "target_enemy_piece": enemy_units,
            "target_ally": all_allies, "target_ally_piece": ally_units,
            "all_enemies": all_enemies, "all_enemy_pieces": enemy_units,
            "all_allies": all_allies, "all_allied_pieces": ally_units,
            "lowest_health_enemy": all_enemies, "lowest_health_enemy_piece": enemy_units,
        }
        if code == "adjacent_allies":
            if source not in allies.board:
                return []
            candidates = [unit for unit in allies.board if abs(unit.slot - source.slot) == 1]
        else:
            candidates = groups[code]
        candidates = [
            entity for entity in candidates
            if entity.health > 0
            and (
                not effect.get("card_id")
                or getattr(entity, "card_id", None) == effect["card_id"]
                or getattr(entity, "piece_type", None) == effect["card_id"]
            )
        ]
        if code in MANUAL_TARGETS:
            # Elusive prevents manual maneuver targeting, not battlecries or area effects.
            if source is None and not allow_elusive:
                candidates = [e for e in candidates if "elusive" not in getattr(e, "keywords", set())]
            return candidates if preview else [e for e in candidates if e is target]
        if code.startswith("lowest_health_"):
            return sorted(candidates, key=lambda entity: (
                entity.health, getattr(entity, "slot", BOARD_LIMIT),
            ))[:effect.get("count", 1)]
        return candidates

    def execute(
        self, effects: list[dict], trigger: str, owner: int,
        source: Unit | None = None, target: Entity | None = None,
    ) -> None:
        for effect in effects:
            if self.game.over:
                break
            if effect.get("trigger", "on_play") == trigger:
                self.execute_action(effect, owner, source, target)

    def execute_action(
        self, effect: dict, owner: int, source: Unit | None = None,
        target: Entity | None = None,
    ) -> None:
        game = self.game
        condition = effect.get("condition")
        if condition:
            count = sum(
                u.card_id == condition["card_id"] or u.piece_type == condition["card_id"]
                for u in game.players[owner].board
            )
            if count < condition["at_least"]:
                game.log("Condicao do efeito nao atendida.")
                return
        action = effect["action"]
        if action == "win_pattern":
            game.mates.execute(owner, effect["pattern"])
            return
        if action == "draw":
            for _ in range(effect["amount"]):
                if not game.over:
                    game.draw_card(owner)
            return
        if action == "summon":
            for _ in range(effect.get("count", 1)):
                game.summon(owner, effect["card_id"])
            return
        if action == "activate_king":
            game.players[owner].endgame_ready = True
            game.activate_king(owner)
            return
        targets = self.resolve_targets(effect, owner, source, target)
        killed = []
        freeze_played = False
        for entity in targets:
            if action == "damage":
                game.damage(entity, effect["amount"])
            elif action == "heal":
                game.heal(entity, effect["amount"])
            elif action == "destroy":
                entity.health = 0
                game.log(f"{entity.name} foi sacrificado.")
            elif action == "buff":
                if not hasattr(entity, "attack"):
                    game.log(f"{entity.name}: bonus de atributos exige peça no tabuleiro.")
                    continue
                attack = effect.get("attack", 0)
                health = effect.get("health", 0)
                entity.attack += attack
                entity.health += health
                entity.max_health += health
                if effect.get("duration") == "until_end_of_turn":
                    entity.temporary_attack += attack
                game.log(f"{entity.name} recebe +{attack}/+{health}.")
            elif action == "freeze":
                if hasattr(entity, "frozen_through"):
                    entity.frozen_through = game.players[entity.owner].turns_started + 1
                    game.log(f"{entity.name} congelado ate o fim do proximo turno dele.")
                    if not freeze_played:
                        game.emit_event("freeze")
                        freeze_played = True
                else:
                    game.log(f"{entity.name}: congelamento exige peça no tabuleiro.")
            elif action == "grant_keyword":
                if hasattr(entity, "keywords"):
                    entity.keywords.add(effect["keyword"])
                    game.log(f"{entity.name} ganha {effect['keyword']}.")
                else:
                    game.log(f"{entity.name}: palavra-chave exige peça no tabuleiro.")
            if entity.health <= 0:
                killed.append(entity)
        # Resolve the entire area action before removing casualties (simultaneous damage).
        game.cleanup()
        if "on_kill" in effect:
            for _ in killed:
                if not game.over:
                    self.execute_action(effect["on_kill"], owner, source, target)
