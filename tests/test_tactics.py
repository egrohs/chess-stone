import unittest
from unittest.mock import patch

from game_engine import Card, Game, RuleError, load_cards


class TacticalRulesTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(load_cards(), deck_size=100, opening_hand=0, seed=7)
        self.p0, self.p1 = self.game.players
        self.p0.hand.clear()
        self.p0.mana = self.p0.max_mana = 10

    def unit(self, owner=0, slot=None, card_id="peao"):
        unit = self.game.summon(owner, card_id, slot)
        unit.effects = []
        return unit

    def test_move_unit_costs_mana_and_changes_slot(self):
        unit = self.unit(0, 0)
        before = self.p0.mana
        self.game.move_unit(0, unit, 4)
        self.assertEqual((unit.slot, self.p0.mana), (4, before - 1))
        self.assertIs(self.p0.unit_at(4), unit)
        self.assertIsNone(self.p0.unit_at(0))

    def test_move_unit_rejections_change_nothing(self):
        unit = self.unit(0, 0)
        other = self.unit(0, 1)
        before = self.p0.mana
        for owner, mover, slot in ((0, unit, 1), (0, unit, 8), (1, unit, 3), (0, self.unit(1, 0), 3)):
            with self.assertRaises(RuleError):
                self.game.move_unit(owner, mover, slot)
        self.p0.mana = 0
        with self.assertRaises(RuleError):
            self.game.move_unit(0, unit, 3)
        self.assertEqual((unit.slot, other.slot), (0, 1))
        self.p0.mana = before

    def test_move_unit_king_rejected(self):
        self.p0.endgame_ready = True
        self.game.activate_king(0)
        with self.assertRaises(RuleError):
            self.game.move_unit(0, self.p0.king, 7)

    def test_move_unit_changes_center_control(self):
        unit = self.unit(0, 0)
        self.assertEqual(self.game.center_control(0), 0)
        self.game.move_unit(0, unit, 3)
        self.assertEqual(self.game.center_control(0), 1)

    def card(self, card_id):
        card = Card(self.game.uid(), self.game.catalog[card_id])
        self.p0.hand.append(card)
        return card

    def cycle(self):
        self.game.end_turn(0)
        self.game.end_turn(1)

    def test_death_leaves_gap_and_default_summon_reuses_first_free_slot(self):
        left, middle, right = self.unit(slot=0), self.unit(slot=1), self.unit(slot=7)
        middle.health = 0
        self.game.cleanup()
        self.assertEqual([unit.slot for unit in self.p0.board], [0, 7])
        self.assertIsNone(self.p0.unit_at(1))
        self.assertEqual(self.p0.free_slots(), [1, 2, 3, 4, 5, 6])
        replacement = self.unit()
        self.assertEqual(replacement.slot, 1)
        self.assertEqual((left.slot, right.slot), (0, 7))

    def test_king_uses_first_free_slot_without_moving_survivors(self):
        left, right = self.unit(slot=0), self.unit(slot=7)
        self.p0.endgame_ready = True
        self.game.activate_king(0)
        self.assertEqual(self.p0.king.slot, 1)
        self.assertEqual((left.slot, right.slot), (0, 7))
        self.assertEqual([unit.slot for unit in self.p0.board], [0, 1, 7])

    def test_occupied_slot_rejection_is_atomic(self):
        occupant = self.unit(slot=5)
        card = self.card("cavalo")
        next_uid = self.game._next_uid
        with self.assertRaisesRegex(RuleError, "ocupado"):
            self.game.play_card(0, card, position=5)
        self.assertIn(card, self.p0.hand)
        self.assertEqual(self.p0.mana, 10)
        self.assertEqual(self.p0.board, [occupant])
        self.assertEqual(self.game._next_uid, next_uid)
        with self.assertRaisesRegex(RuleError, "ocupado"):
            self.game.summon(0, "peao", 5)

    def test_empty_slot_is_not_restricted_by_occupied_count(self):
        self.game.play_card(0, self.card("peao"), position=7)
        self.assertEqual(self.p0.board[0].slot, 7)
        self.assertEqual(len(self.p0.free_slots()), 7)

    def test_gap_blocks_battlecry_adjacency_and_support(self):
        left, far = self.unit(slot=0), self.unit(slot=3)
        self.game.play_card(0, self.card("cavalo"), position=1)
        self.assertEqual((left.attack, far.attack), (2, 1))
        self.assertTrue(self.game.supported(left))
        self.assertFalse(self.game.supported(far))

    def test_opposite_edges_are_not_adjacent(self):
        left, right = self.unit(slot=0), self.unit(slot=7)
        self.assertFalse(self.game.supported(left))
        self.assertFalse(self.game.supported(right))
        left.health = 0
        self.assertFalse(self.game.supported(right))

    def test_supported_combat_reduces_damage_for_both_participants(self):
        attacker = self.unit(slot=0, card_id="dama")
        self.unit(slot=1)
        defender = self.unit(1, 4)
        self.unit(1, 5)
        attacker.attack = 4
        defender.attack = 3
        attacker.health = defender.health = 10
        self.game.attack(0, attacker, defender)
        self.assertEqual((attacker.health, defender.health), (8, 7))
        self.assertEqual((attacker.attack, defender.attack), (4, 3))

    def test_hanging_combat_increases_damage_for_both_participants(self):
        attacker = self.unit(slot=0, card_id="dama")
        defender = self.unit(1, 4)
        attacker.attack = 4
        defender.attack = 3
        attacker.health = defender.health = 10
        self.game.attack(0, attacker, defender)
        self.assertEqual((attacker.health, defender.health), (6, 5))

    def test_removing_support_changes_next_attack_not_printed_stats(self):
        attacker = self.unit(card_id="dama")
        attacker.attack = 2
        defender = self.unit(1, 4)
        defender.health = 10
        defender.attack = 0
        support = self.unit(1, 5)
        self.game.attack(0, attacker, defender)
        self.assertEqual(defender.health, 9)
        support.health = 0
        self.game.cleanup()
        self.game.attack(0, attacker, defender)
        self.assertEqual(defender.health, 6)
        self.assertEqual(attacker.health, 5)

    def test_zero_damage_does_not_consume_shield_or_play_impact(self):
        attacker = self.unit(card_id="dama")
        attacker.attack = 1
        defender = self.unit(1, 2)
        defender.attack = 0
        defender.keywords.add("divine_shield")
        self.unit(1, 3)
        impacts = []
        self.game.on_damage = impacts.append
        self.game.attack(0, attacker, defender)
        self.assertEqual(defender.health, 2)
        self.assertIn("divine_shield", defender.keywords)
        self.assertEqual(impacts, [])

    def test_retaliation_keeps_support_snapshot_when_defender_dies(self):
        attacker = self.unit(card_id="dama")
        self.unit(slot=1)
        defender = self.unit(1)
        defender.attack = 4
        defender.health = 1
        self.game.attack(0, attacker, defender)
        self.assertEqual(attacker.health, 2)
        self.assertNotIn(defender, self.p1.board)

    def test_spells_ignore_support_and_hanging_modifiers(self):
        supported = self.unit(1, 0, "bispo")
        self.unit(1, 1)
        hanging = self.unit(1, 5, "bispo")
        self.game.parser.execute([{
            "trigger": "on_play", "action": "damage", "amount": 2,
            "target": "all_enemy_minions",
        }], "on_play", 0)
        self.assertEqual((supported.health, hanging.health), (2, 2))

    def test_king_on_board_participates_in_support_but_face_damage_is_unchanged(self):
        attacker = self.unit(card_id="dama")
        attacker.attack = 2
        self.game.attack(0, attacker, self.p1)
        self.assertEqual(self.p1.health, 28)
        self.p1.endgame_ready = True
        self.game.activate_king(1)
        support = self.unit(1, 1)
        self.assertTrue(self.game.supported(self.p1.king))
        self.p1.armor = 1
        self.game.attack(0, attacker, self.p1.king)
        self.assertEqual((self.p1.health, self.p1.armor), (28, 0))
        support.health = 0
        self.assertFalse(self.game.supported(self.p1.king))

    def test_center_excludes_wings_and_dead_units(self):
        for slot in (0, 1, 6, 7):
            self.unit(slot=slot)
        self.assertEqual(self.game.center_control(0), 0)
        center = self.unit(slot=2)
        self.assertEqual(self.game.center_control(0), 1)
        center.health = 0
        self.assertEqual(self.game.center_control(0), 0)

    def test_center_bonus_is_awarded_on_own_end_and_consumed_next_own_start(self):
        self.unit(slot=2)
        self.game.end_turn(0)
        self.assertTrue(self.p0.center_bonus_pending)
        self.assertEqual(self.p1.mana, self.p1.max_mana)
        self.game.end_turn(1)
        self.assertFalse(self.p0.center_bonus_pending)
        self.assertEqual(self.p0.temporary_mana, 1)
        self.assertEqual((self.p0.max_mana, self.p0.mana), (10, 11))

    def test_center_bonus_survives_opponent_removal_but_does_not_repeat(self):
        center = self.unit(slot=2)
        self.game.end_turn(0)
        center.health = 0
        self.game.cleanup()
        self.game.end_turn(1)
        self.assertEqual(self.p0.mana, 11)
        self.cycle()
        self.assertEqual(self.p0.temporary_mana, 0)
        self.assertEqual(self.p0.mana, 10)

    def test_center_ties_and_enemy_dominance_grant_no_bonus(self):
        self.unit(slot=2)
        self.unit(1, 3)
        self.cycle()
        self.assertEqual((self.p0.temporary_mana, self.p1.temporary_mana), (0, 0))
        self.unit(1, 4)
        self.cycle()
        self.assertEqual(self.p0.temporary_mana, 0)
        self.assertTrue(self.p1.center_bonus_pending)
        self.game.end_turn(0)
        self.assertEqual(self.p1.temporary_mana, 1)

    def test_center_bonus_does_not_stack_or_increase_max_crystals(self):
        self.unit(slot=5)
        for _ in range(3):
            self.cycle()
            self.assertEqual((self.p0.max_mana, self.p0.mana), (10, 11))
        self.game.play_card(0, self.card("dama"), position=7)
        self.assertEqual(self.p0.mana, 4)

    def test_center_uses_state_after_end_turn_effects(self):
        center = self.unit(slot=2)
        center.effects = [{
            "trigger": "on_turn_end", "action": "destroy", "target": "self",
        }]
        self.cycle()
        self.assertEqual(self.p0.temporary_mana, 0)
        self.assertEqual(self.game.center_control(0), 0)

    def test_activated_king_counts_toward_center(self):
        self.unit(slot=0)
        self.unit(slot=1)
        self.p0.endgame_ready = True
        self.game.activate_king(0)
        self.assertEqual(self.p0.king.slot, 2)
        self.assertEqual(self.game.center_control(0), 1)
        self.cycle()
        self.assertEqual(self.p0.temporary_mana, 1)

    def test_lowest_health_targets_are_deterministic_with_slot_tiebreaks(self):
        high = self.unit(1, 0, "bispo")
        later = self.unit(1, 7)
        earlier = self.unit(1, 3)
        effect = self.game.catalog["ataque_duplo"]["effects"][0]
        with patch.object(self.game.rng, "sample", side_effect=AssertionError("RNG")):
            self.assertEqual(self.game.parser.resolve_targets(effect, 0, preview=True), [earlier, later])
            self.game.play_card(0, self.card("ataque_duplo"))
        self.assertEqual(self.p1.board, [high])
        self.assertEqual(len(self.p0.hand), 2)
        self.assertEqual(self.p1.health, 30)

    def test_lowest_health_hero_tie_comes_after_slots_and_respects_count(self):
        piece = self.unit(1, 7)
        self.p1.health = piece.health
        effect = {"target": "lowest_health_enemy", "count": 2}
        self.assertEqual(self.game.parser.resolve_targets(effect, 0), [piece, self.p1])
        self.assertEqual(
            self.game.parser.resolve_targets({"target": "lowest_health_enemy"}, 0), [piece],
        )

    def test_lowest_health_filters_before_ordering_and_ignores_elusive(self):
        bishop = self.unit(1, 6, "bispo")
        bishop.health = 1
        self.unit(1, 0)
        effect = {"target": "lowest_health_enemy_minion", "card_id": "bispo", "count": 2}
        self.assertEqual(self.game.parser.resolve_targets(effect, 0), [bishop])

    def test_lowest_health_with_zero_or_one_target(self):
        effect = self.game.catalog["ataque_duplo"]["effects"][0]
        self.assertEqual(self.game.parser.resolve_targets(effect, 0), [])
        only = self.unit(1, 5)
        self.assertEqual(self.game.parser.resolve_targets(effect, 0), [only])

    def test_ai_places_minions_in_available_center_slots(self):
        self.game.end_turn(0)
        self.p1.hand = [Card(self.game.uid(), self.game.catalog["peao"])]
        self.game.ai_step()
        self.assertEqual(self.p1.board[0].slot, 2)


if __name__ == "__main__":
    unittest.main()
