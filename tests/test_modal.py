import copy
import unittest

from crafting import make_variant
from game_engine import BOARD_LIMIT, Card, Game, RuleError, load_cards


class ModalRulesTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(load_cards(), deck_size=100, seed=3, opening_hand=0)
        self.player, self.enemy = self.game.players
        self.player.hand.clear()
        self.player.mana = self.player.max_mana = 10

    def card(self, card_id):
        card = Card(self.game.uid(), self.game.catalog[card_id])
        self.player.hand.append(card)
        return card

    def test_every_card_has_two_valid_modes_at_the_same_cost(self):
        for definition in self.game.catalog.values():
            with self.subTest(card=definition["id"]):
                card = Card(self.game.uid(), definition)
                self.assertEqual(card.mode("piece")["cost"], card.mode("manobra")["cost"])
                self.assertGreater(card.mode("piece")["health"], 0)
                self.assertTrue(card.mode("manobra")["effects"])
                self.assertNotIn("type", definition)

    def test_same_card_is_a_piece_or_maneuver_never_both(self):
        piece, maneuver = self.card("peao"), self.card("peao")
        self.game.play_card(0, piece, position=5, mode="piece")
        self.assertEqual(self.player.unit_at(5).piece_type, "peao")
        self.assertEqual(self.player.discard, [])
        before = len(self.player.deck)
        self.game.play_card(0, maneuver, mode="manobra")
        self.assertEqual(len(self.player.board), 1)
        self.assertEqual(self.player.discard, [maneuver])
        self.assertEqual(len(self.player.deck), before - 1)
        self.assertEqual(self.player.mana, 8)
        self.assertEqual(self.player.maneuvers_played, 1)
        self.assertNotIn(piece, self.player.hand)
        self.assertNotIn(maneuver, self.player.hand)

    def test_former_maneuver_can_develop_without_executing_its_maneuver(self):
        card = self.card("roque")
        self.player.health = 20
        self.game.play_card(0, card, position=4, mode="piece")
        self.assertEqual(self.player.health, 20)
        self.assertEqual(len(self.player.board), 1)
        unit = self.player.unit_at(4)
        self.assertEqual((unit.card_id, unit.piece_type, unit.attack, unit.health), ("roque", "torre", 3, 5))
        self.assertEqual(self.player.maneuvers_played, 0)
        self.assertEqual(self.player.discard, [])

    def test_maneuver_still_works_on_full_board(self):
        for position in range(BOARD_LIMIT):
            self.game.summon(0, "peao", position)
        card = self.card("peao")
        self.assertFalse(self.game.playable(0, card, "piece"))
        self.assertTrue(self.game.playable(0, card, "manobra"))
        self.assertTrue(self.game.playable(0, card))
        before = self.player.mana
        with self.assertRaises(RuleError):
            self.game.play_card(0, card, mode="piece")
        self.assertEqual(self.player.mana, before)
        self.assertIn(card, self.player.hand)
        self.game.play_card(0, card, mode="manobra")
        self.assertEqual(len(self.player.board), 6)
        self.assertEqual(self.player.discard, [card])

    def test_bad_mode_position_turn_cost_and_target_are_atomic(self):
        card = self.card("cavalo")
        enemy = self.game.summon(1, "peao")
        cases = [
            {"mode": "invalid"}, {"mode": "manobra", "position": 0},
            {"mode": "piece", "position": 6}, {"mode": "piece", "position": -1},
            {"mode": "piece", "target": enemy}, {"mode": "manobra"},
            {"mode": "manobra", "target": self.enemy},
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments), self.assertRaises(RuleError):
                self.game.play_card(0, card, **arguments)
            self.assertEqual(self.player.mana, 10)
            self.assertIn(card, self.player.hand)
            self.assertEqual(self.player.discard, [])
            self.assertEqual(self.player.board, [])
            self.assertEqual(self.player.maneuvers_played, 0)
        with self.assertRaises(RuleError):
            self.game.play_card(1, card, mode="manobra")
        self.player.mana = 0
        for mode in ("piece", "manobra"):
            self.assertFalse(self.game.playable(0, card, mode))
            with self.assertRaisesRegex(RuleError, "Tempo"):
                self.game.play_card(0, card, target=enemy if mode == "manobra" else None, mode=mode)
        self.assertIn(card, self.player.hand)

    def test_targets_and_elusive_are_specific_to_the_mode(self):
        card = self.card("cavalo")
        bishop = self.game.summon(1, "bispo")
        self.assertEqual(self.game.manual_effects(card, "piece"), [])
        self.assertEqual(self.game.valid_card_targets(0, card, "piece"), [])
        self.assertFalse(self.game.playable(0, card, "manobra"))
        self.assertNotIn(bishop, self.game.valid_card_targets(0, card, "manobra"))
        pawn = self.game.summon(1, "peao")
        pawn.effects = []
        self.assertEqual(self.game.valid_card_targets(0, card, "manobra"), [pawn])
        self.game.play_card(0, card, pawn, mode="manobra")
        self.assertNotIn(pawn, self.enemy.board)
        self.assertEqual(self.player.board, [])
        self.assertEqual(self.player.discard, [card])

    def test_piece_death_discards_the_original_card_once(self):
        card = self.card("peao")
        self.game.play_card(0, card, mode="piece")
        unit = self.player.board[0]
        self.game.damage(unit, 99)
        self.game.cleanup()
        self.game.cleanup()
        self.assertEqual(self.player.discard, [card])
        self.assertEqual(self.player.discard[0].uid, card.uid)

    def test_self_destroying_piece_keeps_source_card_and_runs_death_effect(self):
        card = self.card("peao")
        card.definition = copy.deepcopy(card.definition)
        card.definition["piece_mode"]["effects"] = [{
            "trigger": "on_play", "action": "destroy", "target": "self",
        }, *card.definition["piece_mode"]["effects"]]
        self.game.catalog["peao"] = card.definition
        before = len(self.player.deck)
        self.game.play_card(0, card, mode="piece")
        self.assertEqual(self.player.board, [])
        self.assertEqual(self.player.discard, [card])
        self.assertEqual(len(self.player.deck), before - 1)

    def test_burned_draw_and_generated_variant_keep_definition_in_discard(self):
        definition = make_variant(self.game.catalog["torre"], "perfect")
        self.game.catalog[definition["id"]] = definition
        self.player.deck.append(definition["id"])
        for _ in range(10):
            self.card("peao")
        self.game.draw_card(0)
        self.assertEqual(len(self.player.hand), 10)
        self.assertIs(self.player.discard[0].definition, definition)
        unit = self.game.summon(0, definition["id"])
        unit.keywords.clear()
        self.game.damage(unit, 99)
        self.game.cleanup()
        self.assertEqual(len(self.player.discard), 2)
        self.assertIs(self.player.discard[1].definition, definition)

    def test_mate_requirements_only_apply_to_maneuver(self):
        card = self.card("mate_boden")
        self.assertFalse(self.game.playable(0, card, "manobra"))
        self.assertTrue(self.game.playable(0, card, "piece"))
        with self.assertRaises(RuleError):
            self.game.play_card(0, card, mode="manobra")
        self.game.play_card(0, card, position=5, mode="piece")
        self.assertFalse(self.game.over)
        self.assertEqual(self.player.unit_at(5).piece_type, "bispo")

    def test_modal_archetypes_participate_in_formations_and_conditions(self):
        for card_id, slot in (("mate_boden", 0), ("peao", 1), ("peao", 2), ("par_de_bispos", 5)):
            self.game.summon(0, card_id, slot)
        self.assertEqual(len(self.game.mates.formations(0, "boden")), 1)
        card = self.card("par_de_bispos")
        bishop = self.player.unit_at(5)
        before = bishop.attack
        self.game.play_card(0, card, mode="manobra")
        self.assertEqual(bishop.attack, before + 1)

    def test_variants_upgrade_both_modes_without_mutating_base(self):
        base = self.game.catalog["torre"]
        original = copy.deepcopy(base)
        variant = make_variant(base, "perfect")
        self.assertEqual(base, original)
        self.assertEqual(variant["piece_mode"]["attack"], base["piece_mode"]["attack"] + 2)
        self.assertEqual(variant["piece_mode"]["effects"][-1]["action"], "draw")
        self.assertEqual(variant["manouvre_mode"]["effects"][-2]["action"], "heal")
        self.assertEqual(variant["manouvre_mode"]["effects"][-1]["action"], "draw")
        self.assertEqual(variant["piece_mode"]["cost"], variant["manouvre_mode"]["cost"])

    def test_ai_can_play_maneuver_when_no_piece_fits(self):
        self.game.end_turn(0)
        for _ in range(BOARD_LIMIT):
            self.game.summon(1, "peao")
        card = Card(self.game.uid(), self.game.catalog["peao"])
        self.enemy.hand = [card]
        self.enemy.mana = 10
        self.game.ai_step()
        self.assertEqual(self.enemy.discard, [card])
        self.assertEqual(self.enemy.maneuvers_played, 1)
        self.assertEqual(len(self.enemy.board), 6)


if __name__ == "__main__":
    unittest.main()
