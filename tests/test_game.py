from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from csv_to_json import ROOT, convert_csv, parse_effect_code, validate_cards
from game_engine import BOARD_LIMIT, Card, Game, RuleError, load_cards


class CatalogTests(unittest.TestCase):
    def test_csv_and_json_are_equivalent(self):
        with tempfile.TemporaryDirectory() as directory:
            cards = convert_csv(ROOT / "data" / "cards.csv", Path(directory) / "cards.json")
        self.assertEqual(cards, load_cards())
        self.assertGreaterEqual(len(cards), 12)

    def test_short_code_and_on_kill(self):
        self.assertEqual(
            parse_effect_code("DAMAGE:2:TARGET_2_ENEMIES|DRAW:1:IF_KILLED"),
            [{
                "trigger": "on_play", "action": "damage", "amount": 2,
                "target": "random_enemy_minion", "count": 2,
                "on_kill": {"action": "draw", "amount": 1},
            }],
        )

    def test_structured_triggers_are_preserved(self):
        effects = parse_effect_code(
            '[{"action":"draw","amount":1},'
            '{"trigger":"on_death","action":"draw","amount":2}]'
        )
        self.assertEqual([e["trigger"] for e in effects], ["on_play", "on_death"])

    def test_invalid_short_codes(self):
        for code in (
            "DRAW:1:IF_KILLED", "TYPO:2:SELF", "DAMAGE:2", "DAMAGE:x:SELF", "DRAW:1:TYPO",
        ):
            with self.subTest(code=code), self.assertRaises(ValueError):
                parse_effect_code(code)

    def test_invalid_catalogs(self):
        original = load_cards()
        mutations = [
            lambda c: c.append(copy.deepcopy(c[0])),
            lambda c: c[0].update(cost=11),
            lambda c: c[0].update(health=0),
            lambda c: c[0].update(keywords=["flight"]),
            lambda c: c[0].update(keywords=[{}]),
            lambda c: c[0].update(effects=[{"trigger": "on_play", "action": "typo"}]),
            lambda c: c[0].update(effects=[{"trigger": "on_play", "action": "draw", "amount": True}]),
            lambda c: c[0].update(effects=[{
                "trigger": "on_play", "action": "summon", "card_id": "missing",
            }]),
            lambda c: c[0].update(effects=[{
                "trigger": "on_play", "action": "summon", "card_id": "roque",
            }]),
            lambda c: c[0].update(effects=[{
                "trigger": "on_play", "action": "damage", "amount": 1, "target": "wrong",
            }]),
            lambda c: c[0].update(effects=[{
                "trigger": "on_death", "action": "damage", "amount": 1, "target": "target_enemy",
            }]),
            lambda c: c[-1].update(effects=[{
                "trigger": "on_turn_end", "action": "draw", "amount": 1,
            }]),
        ]
        for mutate in mutations:
            cards = copy.deepcopy(original)
            mutate(cards)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                validate_cards(cards)

    def test_bad_csv_does_not_overwrite_existing_json(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "bad.csv"
            destination = Path(directory) / "cards.json"
            source.write_text("id,name\nx,Teste\n", encoding="utf-8")
            destination.write_text("preservado", encoding="utf-8")
            with self.assertRaises(ValueError):
                convert_csv(source, destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), "preservado")


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(load_cards(), deck_size=100, seed=7, opening_hand=0)
        self.p0, self.p1 = self.game.players
        self.p0.hand.clear()
        self.p0.mana = self.p0.max_mana = 10

    def card(self, card_id, owner=0):
        card = Card(self.game.uid(), self.game.catalog[card_id])
        self.game.players[owner].hand.append(card)
        return card

    def unit(self, card_id="peao", owner=0, ready=False):
        unit = self.game.summon(owner, card_id)
        self.assertIsNotNone(unit)
        if ready:
            unit.summoned_turn -= 1
        return unit

    def test_initial_state(self):
        game = Game(load_cards(), seed=3)
        p0, p1 = game.players
        self.assertEqual((p0.health, p1.health), (30, 30))
        self.assertEqual((len(p0.hand), len(p1.hand)), (4, 3))
        self.assertEqual((len(p0.deck), len(p1.deck)), (26, 27))
        self.assertEqual((p0.mana, p1.mana), (1, 0))
        self.assertEqual((len(p0.board), len(p1.board)), (0, 0))

    def test_mana_refill_and_cap(self):
        for _ in range(25):
            self.game.end_turn(self.game.current)
        self.assertEqual(self.p0.max_mana, 10)
        self.assertEqual(self.p1.max_mana, 10)
        self.assertEqual(self.game.players[self.game.current].mana, 10)

    def test_mana_and_wrong_turn_rejections_are_atomic(self):
        card = self.card("dama")
        self.p0.mana = 1
        with self.assertRaises(RuleError):
            self.game.play_card(0, card)
        with self.assertRaises(RuleError):
            self.game.end_turn(1)
        self.assertIn(card, self.p0.hand)
        self.assertEqual(self.p0.mana, 1)

    def test_hand_limit_burns_but_removes_deck_card(self):
        for _ in range(10):
            self.card("peao")
        remaining = len(self.p0.deck)
        self.game.draw_card(0)
        self.assertEqual(len(self.p0.hand), 10)
        self.assertEqual(len(self.p0.deck), remaining - 1)
        self.assertIn("mao cheia", self.game.messages[-1])

    def test_board_limit_and_no_mana_spent(self):
        for _ in range(BOARD_LIMIT):
            self.unit()
        card = self.card("peao")
        with self.assertRaises(RuleError):
            self.game.play_card(0, card)
        self.assertEqual(self.p0.mana, 10)
        self.assertIn(card, self.p0.hand)
        self.assertEqual(len(self.p0.board), 8)

    def test_insertion_and_adjacent_battlecry(self):
        left, right, far = self.unit(), self.unit(), self.unit()
        self.game.play_card(0, self.card("cavalo"), position=1)
        self.assertEqual([u.card_id for u in self.p0.board], ["peao", "cavalo", "peao", "peao"])
        self.assertEqual((left.attack, right.attack, far.attack), (2, 2, 1))

    def test_invalid_position_does_not_consume_card_or_mana(self):
        card = self.card("peao")
        for position in (-1, 1, 0.5, True):
            with self.subTest(position=position), self.assertRaises(RuleError):
                self.game.play_card(0, card, position=position)
            self.assertIn(card, self.p0.hand)
            self.assertEqual(self.p0.mana, 10)

    def test_summoning_sickness_and_readiness(self):
        unit = self.unit()
        self.assertEqual(self.game.attack_targets(unit), [])
        self.game.end_turn(0)
        self.game.end_turn(1)
        self.assertIn(self.p1, self.game.attack_targets(unit))

    def test_rush_cannot_attack_hero_even_activated_king(self):
        knight = self.unit("cavalo")
        victim = self.unit("torre", 1)
        self.assertEqual(self.game.attack_targets(knight), [victim])
        self.p1.endgame_ready = True
        self.game.activate_king(1)
        self.assertNotIn(self.p1.king, self.game.attack_targets(knight))
        victim.keywords.clear()
        self.assertIn(victim, self.game.attack_targets(knight))
        self.assertNotIn(self.p1.king, self.game.attack_targets(knight))

    def test_charge_windfury_and_attack_limit(self):
        queen = self.unit("dama")
        self.game.attack(0, queen, self.p1)
        self.game.attack(0, queen, self.p1)
        self.assertEqual(self.p1.health, 20)
        with self.assertRaises(RuleError):
            self.game.attack(0, queen, self.p1)

    def test_taunt_and_divine_shield(self):
        queen = self.unit("dama")
        rook = self.unit("torre", 1)
        with self.assertRaises(RuleError):
            self.game.attack(0, queen, self.p1)
        self.game.attack(0, queen, rook)
        self.assertEqual(rook.health, 5)
        self.assertEqual(queen.health, 2)
        self.assertNotIn("divine_shield", rook.keywords)
        self.game.attack(0, queen, rook)
        self.assertNotIn(rook, self.p1.board)
        self.assertNotIn(queen, self.p0.board)

    def test_deathrattle_draws(self):
        pawn = self.unit()
        self.game.damage(pawn, 99)
        self.game.cleanup()
        self.assertNotIn(pawn, self.p0.board)
        self.assertEqual(len(self.p0.hand), 1)

    def test_fatigue_lethal_during_deathrattle_stops_the_chain(self):
        pawn = self.unit()
        pawn.effects = [
            {"trigger": "on_death", "action": "draw", "amount": 1},
            {"trigger": "on_death", "action": "damage", "amount": 30, "target": "enemy_hero"},
        ]
        self.p0.health = 1
        self.p0.deck.clear()
        self.game.damage(pawn, 10)
        self.game.cleanup()
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 1)
        self.assertEqual(self.p1.health, 30)

    def test_manual_spell_targets_and_elusive(self):
        bishop = self.unit("bispo", 1)
        pawn = self.unit(owner=1)
        card = self.card("cravada_absoluta")
        self.assertEqual(self.game.valid_card_targets(0, card), [pawn])
        with self.assertRaises(RuleError):
            self.game.play_card(0, card, bishop)
        self.assertEqual(self.p0.mana, 10)
        self.assertIn(card, self.p0.hand)
        self.game.play_card(0, card, pawn)
        self.assertGreater(pawn.frozen_through, self.p1.turns_started)

    def test_elusive_allows_battlecry_targeting(self):
        bishop = self.unit("bispo", 1)
        definition = copy.deepcopy(self.game.catalog["peao"])
        definition["effects"] = [{
            "trigger": "on_play", "action": "damage", "amount": 1, "target": "target_enemy",
        }]
        card = Card(self.game.uid(), definition)
        self.p0.hand.append(card)
        self.assertIn(bishop, self.game.valid_card_targets(0, card))
        self.game.play_card(0, card, bishop)
        self.assertEqual(bishop.health, 3)

    def test_freeze_expires_after_next_owner_turn(self):
        knight = self.unit("cavalo", 1, ready=True)
        self.game.play_card(0, self.card("cravada_absoluta"), knight)
        self.game.end_turn(0)
        self.assertEqual(self.game.attack_targets(knight), [])
        self.game.end_turn(1)
        self.game.end_turn(0)
        self.assertIn(self.p0, self.game.attack_targets(knight))

    def test_random_distinct_targets_and_draw_per_kill(self):
        victims = [self.unit(owner=1) for _ in range(3)]
        for unit in victims:
            unit.effects = []
        self.game.play_card(0, self.card("ataque_duplo"))
        self.assertEqual(len(self.p1.board), 1)
        self.assertEqual(len(self.p0.hand), 2)
        self.assertEqual(sum(u.health <= 0 for u in victims), 2)

    def test_area_effect_ignores_elusive_and_taunt(self):
        bishop = self.unit("bispo", 1)
        rook = self.unit("torre", 1)
        self.game.play_card(0, self.card("zugzwang"))
        self.assertEqual(bishop.frozen_through, 1)
        self.assertEqual(rook.frozen_through, 1)

    def test_conditional_pair_of_bishops(self):
        one = self.unit("bispo")
        self.game.play_card(0, self.card("par_de_bispos"))
        self.assertEqual((one.attack, one.health), (2, 4))
        two = self.unit("bispo")
        self.game.play_card(0, self.card("par_de_bispos"))
        self.assertEqual((one.attack, one.health, two.attack, two.health), (3, 5, 3, 5))

    def test_temporary_attack_and_permanent_keyword(self):
        pawn = self.unit()
        self.game.play_card(0, self.card("coluna_aberta"), pawn)
        self.assertEqual(pawn.attack, 3)
        self.assertIn("rush", pawn.keywords)
        self.game.end_turn(0)
        self.assertEqual(pawn.attack, 1)
        self.assertIn("rush", pawn.keywords)

    def test_castle_heals_and_summons_without_battlecry(self):
        self.p0.health = 27
        self.game.play_card(0, self.card("roque"))
        self.assertEqual(self.p0.health, 30)
        self.assertEqual(self.p0.board[0].card_id, "torre")

    def test_sacrifice_queen_is_playable_and_chains_actions(self):
        queen = self.unit("dama")
        pawn = self.unit(owner=1)
        pawn.effects = []
        card = self.card("sacrificio_da_dama")
        self.assertEqual(self.game.valid_card_targets(0, card), [queen])
        self.game.play_card(0, card, queen)
        self.assertNotIn(queen, self.p0.board)
        self.assertEqual(self.p1.board, [])
        self.assertEqual(self.p1.health, 25)
        self.assertEqual(len(self.p0.hand), 2)

    def test_bishop_end_turn_heal(self):
        self.unit("bispo")
        self.p0.health = 29
        self.game.end_turn(0)
        self.assertEqual(self.p0.health, 30)

    def test_last_draw_activates_shared_health_king(self):
        self.p0.health = 17
        self.p0.deck = ["peao"]
        self.game.draw_card(0)
        king = self.p0.king
        self.assertIsNotNone(king)
        self.assertEqual((king.attack, king.health), (2, 17))
        self.assertIn(king, self.p0.board)
        self.assertNotIn(self.p0, self.game.parser.resolve_targets(
            {"target": "all_enemies"}, 1,
        ))
        self.game.damage(king, 3)
        self.assertEqual(self.p0.health, 14)
        self.game.heal(self.game.hero_target(0), 2)
        self.assertEqual(king.health, 16)
        self.assertFalse(self.game.activate_king(0))

    def test_fatigue_increases(self):
        self.p0.deck.clear()
        for _ in range(3):
            self.game.draw_card(0)
        self.assertEqual(self.p0.health, 24)
        self.assertEqual(self.p0.fatigue, 3)
        self.assertEqual(len(self.p0.board), 1)

    def test_area_effect_hits_activated_king_only_once(self):
        self.p1.endgame_ready = True
        self.game.activate_king(1)
        self.game.parser.execute(
            [{"trigger": "on_play", "action": "damage", "amount": 3, "target": "all_enemies"}],
            "on_play", 0,
        )
        self.assertEqual(self.p1.health, 27)

    def test_full_board_defers_king_until_a_slot_is_free(self):
        units = [self.unit() for _ in range(8)]
        self.p0.deck = ["peao"]
        self.game.draw_card(0)
        self.assertIsNone(self.p0.king)
        self.assertTrue(self.p0.endgame_ready)
        units[0].effects = []
        self.game.damage(units[0], 10)
        self.game.cleanup()
        self.assertIsNotNone(self.p0.king)
        self.assertEqual(len(self.p0.board), 8)

    def test_endgame_after_eight_complete_rounds(self):
        self.game.turn_number = 15
        self.game.end_turn(0)
        self.assertFalse(self.p0.endgame_ready)
        self.game.end_turn(1)
        self.assertTrue(self.p0.endgame_ready)
        self.assertTrue(self.p1.endgame_ready)
        self.assertIsNone(self.p0.king)
        self.game.activate_king(0, manual=True)
        self.assertEqual(len(self.p0.board), 1)
        self.assertEqual(self.game.attack_targets(self.p0.king), [])

    def test_endgame_low_board_threshold_is_total_not_per_side(self):
        for owner in (0, 1):
            for _ in range(2):
                self.unit(owner=owner)
        self.game.turn_number = 16
        self.game.end_turn(0)
        self.assertFalse(self.p0.endgame_ready)
        self.assertFalse(self.p1.endgame_ready)

    def test_data_driven_king_trigger(self):
        self.game.parser.execute(
            [{"trigger": "on_play", "action": "activate_king"}], "on_play", 0,
        )
        self.assertIsNotNone(self.p0.king)

    def test_king_death_ends_game(self):
        self.p1.endgame_ready = True
        self.game.activate_king(1)
        self.game.damage(self.p1.king, 30)
        self.game.cleanup()
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 0)
        with self.assertRaises(RuleError):
            self.game.end_turn(0)

    def test_simultaneous_lethal_combat_is_a_draw(self):
        for player in self.game.players:
            player.health = 2
            player.endgame_ready = True
            self.game.activate_king(player.owner)
        self.p0.king.summoned_turn -= 1
        self.game.attack(0, self.p0.king, self.p1.king)
        self.assertTrue(self.game.over)
        self.assertIsNone(self.game.winner)

    def test_ai_full_games_finish_and_preserve_limits(self):
        for seed in range(15):
            game = Game(load_cards(), deck_size=30, seed=seed)
            for step in range(2000):
                if game.over:
                    break
                owner = game.current
                player = game.players[owner]
                if owner == 1:
                    game.ai_step()
                elif game.can_activate_king(owner):
                    game.activate_king(owner, manual=True)
                else:
                    options = [c for c in player.hand if game.playable(owner, c)]
                    attackers = [(u, game.attack_targets(u)) for u in player.board if game.attack_targets(u)]
                    if options:
                        card = max(options, key=lambda c: c.definition["cost"])
                        targets = game.valid_card_targets(owner, card)
                        game.play_card(owner, card, game.rng.choice(targets) if targets else None)
                    elif attackers:
                        unit, targets = attackers[0]
                        game.attack(owner, unit, game.rng.choice(targets))
                    else:
                        game.end_turn(owner)
                for p in game.players:
                    self.assertLessEqual(len(p.board), 8)
                    self.assertLessEqual(len(p.hand), 10)
                    self.assertTrue(0 <= p.mana <= p.max_mana <= 10)
            self.assertTrue(game.over, f"Partida seed={seed} nao terminou em {step + 1} acoes")


if __name__ == "__main__":
    unittest.main()
