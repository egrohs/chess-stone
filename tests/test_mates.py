import copy
import unittest

from crafting import make_variant, THEMES
from csv_to_json import validate_cards
from deck_store import validate_legendary
from game_engine import Card, Game, RuleError, load_cards


class MateTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(load_cards(), deck_size=100, opening_hand=0, seed=3)
        self.p0, self.p1 = self.game.players
        self.p0.hand.clear()
        self.p0.mana = self.p0.max_mana = 10

    def card(self, card_id):
        card = Card(self.game.uid(), self.game.catalog[card_id])
        self.p0.hand.append(card)
        return card

    def unit(self, card_id, owner=0, position=None):
        return self.game.summon(owner, card_id, position)

    def anastasia(self, right=False):
        if right:
            self.unit("peao")
            knight = self.unit("cavalo")
            rook = self.unit("torre")
        else:
            rook = self.unit("torre")
            knight = self.unit("cavalo")
            self.unit("peao")
        self.unit("peao", 1)
        self.unit("peao", 1)
        self.p1.health = 15
        return rook, knight

    def boden(self):
        left = self.unit("bispo")
        self.unit("peao")
        self.unit("peao")
        right = self.unit("bispo")
        return left, right

    def cycle(self):
        self.game.end_turn(0)
        self.assertTrue(self.game.mates.threats[0])
        self.game.end_turn(1)
        self.p0.mana = 10

    def test_anastasia_victory_preserves_enemy_health(self):
        pair = self.anastasia()
        card = self.card("mate_anastasia")
        self.cycle()
        self.assertTrue(self.game.playable(0, card))
        self.game.play_card(0, card)
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 0)
        self.assertEqual(self.p1.health, 15)
        self.assertEqual(self.p0.mana, 1)
        self.assertTrue(all(u.attacks_used == 1 for u in pair))
        self.assertIn("venceu por Mate de Anastasia", self.game.messages[-1])

    def test_right_edge_anastasia(self):
        self.anastasia(right=True)
        self.cycle()
        self.game.play_card(0, self.card("mate_anastasia"))
        self.assertTrue(self.game.over)

    def test_no_instant_victory_and_no_resources_spent_on_failure(self):
        self.anastasia()
        card = self.card("mate_anastasia")
        self.assertFalse(self.game.playable(0, card))
        with self.assertRaises(RuleError):
            self.game.play_card(0, card)
        self.assertEqual(self.p0.mana, 10)
        self.assertIn(card, self.p0.hand)
        self.assertFalse(self.game.over)

    def test_two_unit_formation_does_not_prepare(self):
        self.unit("torre")
        self.unit("cavalo")
        self.game.end_turn(0)
        self.assertNotIn("anastasia", {t.pattern for t in self.game.mates.threats[0]})

    def test_unrelated_mana_spell_does_not_count_as_prior_boden_spell(self):
        self.boden()
        self.cycle()
        self.p0.spells_played = 1
        card = self.card("mate_boden")
        with self.assertRaisesRegex(RuleError, "dois outros"):
            self.game.play_card(0, card)
        self.assertEqual(self.p0.spells_played, 1)
        self.assertEqual(self.p0.mana, 10)

    def test_boden_real_two_spell_sequence_and_counter_reset(self):
        self.boden()
        self.cycle()
        # Two copies of Coluna Aberta on interior pawns cost 4; mate costs 5.
        pawn = self.p0.board[1]
        for _ in range(2):
            self.game.play_card(0, self.card("coluna_aberta"), pawn)
        self.assertEqual(self.p0.spells_played, 2)
        self.game.play_card(0, self.card("mate_boden"))
        self.assertEqual(self.p0.spells_played, 3)
        self.assertEqual(self.p0.mana, 1)
        self.assertTrue(self.game.over)
        self.assertEqual(self.p1.health, 30)

    def test_boden_needs_two_interior_minions_not_only_kings(self):
        self.unit("bispo")
        self.p0.endgame_ready = True
        self.game.activate_king(0)
        self.unit("peao")
        self.unit("bispo")
        self.game.end_turn(0)
        self.assertEqual(self.game.mates.threats[0], [])

    def test_bishops_alone_do_not_prepare(self):
        self.unit("bispo")
        self.unit("bispo")
        self.game.end_turn(0)
        self.assertEqual(self.game.mates.threats[0], [])

    def test_formation_broken_then_restored_does_not_rearm(self):
        self.boden()
        self.game.end_turn(0)
        pawn = self.p0.board[1]
        pawn.effects = []
        self.game.damage(pawn, 99)
        self.game.cleanup()
        self.assertEqual(self.game.mates.threats[0], [])
        self.unit("peao", position=1)
        self.game.end_turn(1)
        self.p0.spells_played = 2
        self.assertFalse(self.game.playable(0, self.card("mate_boden")))

    def test_frozen_then_thawed_formation_stays_cancelled(self):
        rook, knight = self.anastasia()
        self.game.end_turn(0)
        self.game.parser.execute(
            [{"trigger": "on_play", "action": "freeze", "target": "all_enemy_minions"}],
            "on_play", 1,
        )
        self.assertEqual(self.game.mates.threats[0], [])
        rook.frozen_through = knight.frozen_through = -1
        self.game.end_turn(1)
        self.assertFalse(self.game.playable(0, self.card("mate_anastasia")))

    def test_replacing_same_piece_type_does_not_preserve_preparation(self):
        rook, _ = self.anastasia()
        self.game.end_turn(0)
        rook.health = 0
        self.game.cleanup()
        self.unit("torre", position=0)
        self.game.end_turn(1)
        self.assertFalse(self.game.playable(0, self.card("mate_anastasia")))

    def test_attack_uses_up_execution_opportunity(self):
        rook, _ = self.anastasia()
        self.cycle()
        self.game.attack(0, rook, self.p1)
        self.assertFalse(self.game.playable(0, self.card("mate_anastasia")))

    def test_enemy_can_counter_with_health_taunt_or_board_clearance(self):
        self.anastasia()
        self.cycle()
        card = self.card("mate_anastasia")
        self.p1.health = 16
        self.assertIn("15", self.game.mate_unavailable_reason(0, card))
        self.p1.health = 15
        self.p1.board[0].keywords.add("taunt")
        self.assertIn("Provocar", self.game.mate_unavailable_reason(0, card))
        self.p1.board[0].keywords.clear()
        pawn = self.p1.board[0]
        pawn.effects = []
        pawn.health = 0
        self.game.cleanup()
        self.assertIn("dois lacaios", self.game.mate_unavailable_reason(0, card))

    def test_activated_enemy_king_is_not_second_minion(self):
        self.anastasia()
        self.p1.board.pop()
        self.p1.endgame_ready = True
        self.game.activate_king(1)
        self.cycle()
        self.assertIn("dois lacaios", self.game.mate_unavailable_reason(0, self.card("mate_anastasia")))

    def test_new_end_unit_breaks_edge_preparation(self):
        self.anastasia(right=True)
        self.game.end_turn(0)
        self.unit("peao")
        self.assertNotIn("anastasia", {t.pattern for t in self.game.mates.threats[0]})

    def test_boden_intermediate_death_with_two_survivors_keeps_threat(self):
        self.unit("bispo")
        for _ in range(3):
            self.unit("peao")
        self.unit("bispo")
        self.game.end_turn(0)
        pawn = self.p0.board[2]
        pawn.effects = []
        pawn.health = 0
        self.game.cleanup()
        self.assertEqual(len(self.game.mates.threats[0]), 1)
        self.game.end_turn(1)
        self.p0.mana = 10
        self.p0.spells_played = 2
        self.game.play_card(0, self.card("mate_boden"))
        self.assertTrue(self.game.over)

    def test_direct_effect_cannot_bypass_conditions(self):
        self.game.parser.execute(self.game.catalog["mate_boden"]["effects"], "on_play", 0)
        self.assertFalse(self.game.over)
        self.assertIn("falhou", self.game.messages[-1])

    def test_legendary_limit_includes_quality_variants(self):
        cards = load_cards()
        base = next(c for c in cards if c["id"] == "mate_boden")
        cards.append(make_variant(base, "perfect"))
        catalog = {c["id"]: c for c in cards}
        with self.assertRaises(ValueError):
            validate_legendary(["mate_boden", "mate_boden__perfect"], catalog)
        with self.assertRaises(ValueError):
            Game(cards, player_deck=["mate_boden"] * 2)
        validate_legendary(["mate_boden", "mate_anastasia"], catalog)

    def test_quality_keeps_cost_and_mate_requirements(self):
        base = self.game.catalog["mate_boden"]
        for quality in ("improved", "perfect"):
            variant = make_variant(base, quality)
            self.assertEqual(variant["cost"], 5)
            self.assertEqual(variant["effects"][0], base["effects"][0])
            self.assertEqual(variant["rarity"], "legendary")
        self.assertEqual(THEMES["mate_boden"][0], "bodenMate")
        self.assertEqual(THEMES["mate_anastasia"][0], "anastasiaMate")

    def test_schema_rejects_bad_pattern_or_nonlegendary(self):
        for mutation in ("pattern", "rarity", "trigger", "type"):
            cards = copy.deepcopy(load_cards())
            mate = next(c for c in cards if c["id"] == "mate_boden")
            if mutation == "pattern":
                mate["effects"][0]["pattern"] = "unknown"
            elif mutation == "rarity":
                del mate["rarity"]
            elif mutation == "trigger":
                mate["effects"][0]["trigger"] = "on_turn_end"
            else:
                mate.update(type="minion", attack=1, health=1)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_cards(cards)

    def test_spell_counter_resets_on_own_next_turn(self):
        self.game.play_card(0, self.card("roque"))
        self.assertEqual(self.p0.spells_played, 1)
        self.game.end_turn(0)
        self.game.end_turn(1)
        self.assertEqual(self.p0.spells_played, 0)

    def test_ai_executes_legal_alternate_victory(self):
        self.game.end_turn(0)
        for card_id in ("bispo", "peao", "peao", "bispo"):
            self.unit(card_id, 1)
        self.game.end_turn(1)
        self.game.end_turn(0)
        self.p1.hand = [Card(self.game.uid(), self.game.catalog["mate_boden"])]
        self.p1.mana = 10
        self.p1.spells_played = 2
        self.game.ai_step()
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 1)

    def smothered(self):
        knight = self.unit("cavalo")
        for _ in range(8):
            unit = self.unit("peao", 1)
            unit.effects = []
        return knight

    def back_rank(self):
        rook = self.unit("torre")
        for _ in range(3):
            unit = self.unit("peao", 1)
            unit.effects = []
        return rook

    def opera(self):
        rook, bishop = self.unit("torre"), self.unit("bispo")
        enemy = self.unit("torre", 1)
        enemy.keywords.clear()
        enemy.attack = 0
        enemy.health = enemy.max_health = 30
        rook.summoned_turn -= 1
        bishop.summoned_turn -= 1
        self.game.attack(0, rook, enemy)
        self.game.attack(0, bishop, enemy)
        self.p1.health = 15
        return rook, bishop

    def opposition(self):
        for player in self.game.players:
            player.endgame_ready = True
            self.game.activate_king(player.owner)
        self.p0.health = 20
        self.p1.health = 15
        self.card("peao_passado")
        return self.p0.king

    def test_smothered_wins_with_eight_minions_and_surviving_knight(self):
        self.smothered()
        self.cycle()
        self.game.play_card(0, self.card("mate_abafado"))
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 0)
        self.assertEqual(self.p1.health, 30)
        self.assertEqual(self.p0.mana, 4)

    def test_smothered_is_stopped_by_taunt_even_when_frozen(self):
        self.smothered()
        self.cycle()
        self.p1.board[0].keywords.add("taunt")
        self.p1.board[0].frozen_through = 100
        self.assertIn("Provocar", self.game.mate_unavailable_reason(0, self.card("mate_abafado")))
        self.assertFalse(self.game.over)

    def test_smothered_fails_if_enemy_opens_a_slot_or_has_a_king(self):
        self.smothered()
        self.cycle()
        card = self.card("mate_abafado")
        self.p1.board[0].health = 0
        self.game.cleanup()
        self.assertFalse(self.game.playable(0, card))
        self.p1.endgame_ready = True
        self.game.activate_king(1)
        self.assertEqual(len(self.p1.board), 8)
        self.assertFalse(self.game.playable(0, card))

    def test_smothered_knight_must_not_attack_in_execution_turn(self):
        knight = self.smothered()
        self.cycle()
        self.game.attack(0, knight, self.p1)
        self.assertFalse(self.game.playable(0, self.card("mate_abafado")))

    def test_back_rank_requires_actual_attack_this_turn_and_survival(self):
        rook = self.back_rank()
        self.cycle()
        card = self.card("mate_gaveta")
        self.assertFalse(self.game.playable(0, card))
        self.game.attack(0, rook, self.p1)
        self.game.play_card(0, card)
        self.assertTrue(self.game.over)
        self.assertEqual(self.p1.health, 27)
        self.assertEqual(self.p0.mana, 2)

    def test_back_rank_counts_pawns_or_taunts_once_and_excludes_king(self):
        rook = self.back_rank()
        self.cycle()
        self.game.attack(0, rook, self.p1)
        card = self.card("mate_gaveta")
        self.p1.board[0].keywords.add("taunt")
        removed = self.p1.board[-1]
        removed.health = 0
        self.game.cleanup()
        self.assertFalse(self.game.playable(0, card))
        self.p1.endgame_ready = True
        self.game.activate_king(1)
        self.assertFalse(self.game.playable(0, card))
        self.unit("torre", 1)
        self.assertTrue(self.game.playable(0, card))

    def test_back_rank_zero_armor_requirement(self):
        rook = self.back_rank()
        self.cycle()
        self.game.attack(0, rook, self.p1)
        self.p1.armor = 1
        card = self.card("mate_gaveta")
        with self.assertRaisesRegex(RuleError, "Armadura"):
            self.game.play_card(0, card)
        self.assertEqual(self.p0.mana, 10)
        self.assertIn(card, self.p0.hand)
        self.game.damage(self.p1, 1)
        self.assertEqual(self.p1.armor, 0)
        self.assertEqual(self.p1.health, 27)
        self.game.play_card(0, card)
        self.assertTrue(self.game.over)

    def test_back_rank_dead_attacker_cannot_execute(self):
        rook = self.back_rank()
        self.cycle()
        self.p1.board[0].attack = 10
        self.game.attack(0, rook, self.p1.board[0])  # Shield absorbs retaliation.
        self.game.damage(rook, 99)
        self.game.cleanup()
        self.assertFalse(self.game.playable(0, self.card("mate_gaveta")))

    def test_opera_victory_uses_history_of_same_units(self):
        pair = self.opera()
        self.cycle()
        self.assertTrue(all(u.has_attacked and u.attacks_used == 0 for u in pair))
        self.game.play_card(0, self.card("mate_opera"))
        self.assertTrue(self.game.over)
        self.assertEqual(self.p1.health, 15)
        self.assertEqual(self.p0.mana, 3)

    def test_opera_requires_both_attack_histories(self):
        rook, bishop = self.opera()
        self.cycle()
        bishop.has_attacked = False
        card = self.card("mate_opera")
        self.assertIn("nesta partida", self.game.mate_unavailable_reason(0, card))
        bishop.has_attacked = True
        self.game.attack(0, rook, self.p1)
        self.assertFalse(self.game.playable(0, card))

    def test_opera_enemy_health_and_exactly_one_minion(self):
        self.opera()
        self.cycle()
        card = self.card("mate_opera")
        self.p1.health = 16
        self.assertFalse(self.game.playable(0, card))
        self.p1.health = 15
        self.unit("peao", 1)
        self.assertFalse(self.game.playable(0, card))

    def test_opera_requires_exactly_one_rook_bishop_and_adjacency(self):
        self.unit("torre")
        self.unit("peao")
        self.unit("bispo")
        self.assertEqual(self.game.mates.formations(0, "opera"), [])
        self.p0.board.pop(1)
        self.assertEqual(len(self.game.mates.formations(0, "opera")), 1)
        self.unit("bispo")
        self.assertEqual(self.game.mates.formations(0, "opera"), [])

    def test_opposition_victory_with_passed_pawn_in_hand(self):
        self.opposition()
        self.cycle()
        self.game.play_card(0, self.card("endgame_puro"))
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 0)
        self.assertEqual(self.p0.mana, 0)
        self.assertEqual(self.p1.health, 15)
        self.assertTrue(any(c.definition["id"] == "peao_passado" for c in self.p0.hand))

    def test_opposition_requires_pawn_and_strictly_more_health(self):
        self.opposition()
        self.cycle()
        card = self.card("endgame_puro")
        self.p0.hand = [c for c in self.p0.hand if c.definition["id"] != "peao_passado"]
        self.assertIn("Peao Passado", self.game.mate_unavailable_reason(0, card))
        self.card("peao_passado")
        self.p0.health = self.p1.health
        self.assertFalse(self.game.playable(0, card))
        self.p0.health = self.p1.health - 1
        self.assertFalse(self.game.playable(0, card))

    def test_opposition_any_other_minion_cancels_preparation_permanently(self):
        self.opposition()
        self.game.end_turn(0)
        pawn = self.unit("peao", 1)
        self.assertNotIn("opposition", {t.pattern for t in self.game.mates.threats[0]})
        pawn.effects = []
        pawn.health = 0
        self.game.cleanup()
        self.game.end_turn(1)
        self.assertFalse(self.game.playable(0, self.card("endgame_puro")))

    def test_opposition_king_attack_blocks_execution(self):
        king = self.opposition()
        self.cycle()
        self.game.attack(0, king, self.p1.king)
        self.assertFalse(self.game.playable(0, self.card("endgame_puro")))

    def test_new_patterns_require_prior_announcement(self):
        for pattern, card_id in (
            ("smothered", "mate_abafado"), ("back_rank", "mate_gaveta"),
            ("opera", "mate_opera"), ("opposition", "endgame_puro"),
        ):
            self.assertFalse(self.game.playable(0, self.card(card_id)))
            self.game.mates.execute(0, pattern)
            self.assertFalse(self.game.over)

    def test_all_six_quality_variants_preserve_requirements_and_cost(self):
        from mate_rules import PATTERNS

        mates = [c for c in self.game.catalog.values()
                 if any(e["action"] == "win_pattern" for e in c["effects"])]
        self.assertEqual(len(mates), 6)
        self.assertEqual({c["effects"][0]["pattern"] for c in mates}, PATTERNS)
        for base in mates:
            for quality in ("improved", "perfect"):
                variant = make_variant(base, quality)
                self.assertEqual(variant["effects"][0], base["effects"][0])
                self.assertEqual(variant["cost"], base["cost"])
                self.assertEqual(variant["rarity"], "legendary")
                with self.assertRaises(ValueError):
                    validate_legendary([base["id"], variant["id"]],
                                       {base["id"]: base, variant["id"]: variant})

    def test_armor_absorbs_hero_damage_before_and_after_activation(self):
        self.p1.armor = 5
        self.game.damage(self.p1, 3)
        self.assertEqual((self.p1.armor, self.p1.health), (2, 30))
        self.p1.endgame_ready = True
        self.game.activate_king(1)
        self.game.damage(self.p1.king, 5)
        self.assertEqual((self.p1.armor, self.p1.health), (0, 27))
        self.game.heal(self.p1.king, 2)
        self.assertEqual((self.p1.armor, self.p1.health), (0, 29))


if __name__ == "__main__":
    unittest.main()
