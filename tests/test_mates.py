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
            knight = self.unit("cavalo", position=4)
            rook = self.unit("torre", position=5)
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
        right = self.unit("bispo", position=5)
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
        self.assertTrue(self.game.playable(0, card, mode="manobra"))
        self.game.play_card(0, card, mode="manobra")
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 0)
        self.assertEqual(self.p1.health, 15)
        self.assertEqual(self.p0.mana, 1)
        self.assertTrue(all(u.attacks_used == 1 for u in pair))
        self.assertIn("venceu por Mate de Anastasia", self.game.messages[-1])

    def test_right_edge_anastasia(self):
        self.anastasia(right=True)
        self.cycle()
        self.game.play_card(0, self.card("mate_anastasia"), mode="manobra")
        self.assertTrue(self.game.over)

    def test_no_instant_victory_and_no_resources_spent_on_failure(self):
        self.anastasia()
        card = self.card("mate_anastasia")
        self.assertFalse(self.game.playable(0, card, mode="manobra"))
        with self.assertRaises(RuleError):
            self.game.play_card(0, card, mode="manobra")
        self.assertEqual(self.p0.mana, 10)
        self.assertIn(card, self.p0.hand)
        self.assertFalse(self.game.over)

    def test_two_unit_formation_does_not_prepare(self):
        self.unit("torre")
        self.unit("cavalo")
        self.game.end_turn(0)
        self.assertNotIn("anastasia", {t.pattern for t in self.game.mates.threats[0]})

    def test_unrelated_mana_maneuver_does_not_count_as_prior_boden_maneuver(self):
        self.boden()
        self.cycle()
        self.p0.maneuvers_played = 1
        card = self.card("mate_boden")
        with self.assertRaisesRegex(RuleError, "duas outras"):
            self.game.play_card(0, card, mode="manobra")
        self.assertEqual(self.p0.maneuvers_played, 1)
        self.assertEqual(self.p0.mana, 10)

    def test_boden_real_two_maneuver_sequence_and_counter_reset(self):
        self.boden()
        self.cycle()
        # Two copies of Coluna Aberta on interior pawns cost 4; mate costs 5.
        pawn = self.p0.board[1]
        for _ in range(2):
            self.game.play_card(0, self.card("coluna_aberta"), pawn, mode="manobra")
        self.assertEqual(self.p0.maneuvers_played, 2)
        self.game.play_card(0, self.card("mate_boden"), mode="manobra")
        self.assertEqual(self.p0.maneuvers_played, 3)
        self.assertEqual(self.p0.mana, 1)
        self.assertTrue(self.game.over)
        self.assertEqual(self.p1.health, 30)

    def test_boden_needs_two_interior_pieces_not_only_kings(self):
        self.unit("bispo")
        self.p0.endgame_ready = True
        self.game.activate_king(0)
        self.unit("peao")
        self.unit("bispo", position=5)
        self.game.end_turn(0)
        self.assertEqual(self.game.mates.threats[0], [])

    def test_bishops_alone_do_not_prepare(self):
        self.unit("bispo")
        self.unit("bispo", position=5)
        self.game.end_turn(0)
        self.assertEqual(self.game.mates.threats[0], [])

    def test_queue_extremes_are_not_physical_edges(self):
        self.unit("peao", position=2)
        self.unit("cavalo", position=3)
        self.unit("torre", position=4)
        self.assertEqual(self.game.mates.formations(0, "anastasia"), [])
        self.p0.board.clear()
        for card_id, slot in (("bispo", 1), ("peao", 2), ("peao", 3), ("bispo", 4)):
            self.unit(card_id, position=slot)
        self.assertEqual(self.game.mates.formations(0, "boden"), [])

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
        self.p0.maneuvers_played = 2
        self.assertFalse(self.game.playable(0, self.card("mate_boden"), mode="manobra"))

    def test_frozen_then_thawed_formation_stays_cancelled(self):
        rook, knight = self.anastasia()
        self.game.end_turn(0)
        self.game.parser.execute(
            [{"trigger": "on_play", "action": "freeze", "target": "all_enemy_pieces"}],
            "on_play", 1,
        )
        self.assertEqual(self.game.mates.threats[0], [])
        rook.frozen_through = knight.frozen_through = -1
        self.game.end_turn(1)
        self.assertFalse(self.game.playable(0, self.card("mate_anastasia"), mode="manobra"))

    def test_replacing_same_piece_type_does_not_preserve_preparation(self):
        rook, _ = self.anastasia()
        self.game.end_turn(0)
        rook.health = 0
        self.game.cleanup()
        self.unit("torre", position=0)
        self.game.end_turn(1)
        self.assertFalse(self.game.playable(0, self.card("mate_anastasia"), mode="manobra"))

    def test_attack_uses_up_execution_opportunity(self):
        rook, _ = self.anastasia()
        self.cycle()
        self.game.attack(0, rook, self.p1.board[0])
        self.assertFalse(self.game.playable(0, self.card("mate_anastasia"), mode="manobra"))

    def test_enemy_can_counter_with_health_or_board_clearance(self):
        self.anastasia()
        self.cycle()
        card = self.card("mate_anastasia")
        self.p1.health = 16
        self.assertIn("15", self.game.mate_unavailable_reason(0, card))
        self.p1.health = 15
        self.assertEqual(self.game.mate_unavailable_reason(0, card), "")
        pawn = self.p1.board[0]
        pawn.effects = []
        pawn.health = 0
        self.game.cleanup()
        self.assertIn("duas peças", self.game.mate_unavailable_reason(0, card))

    def test_activated_enemy_king_is_not_second_piece(self):
        self.anastasia()
        self.p1.board.pop()
        self.p1.endgame_ready = True
        self.game.activate_king(1)
        self.cycle()
        self.assertIn("duas peças", self.game.mate_unavailable_reason(0, self.card("mate_anastasia")))

    def test_new_unit_in_free_slot_preserves_fixed_edge_preparation(self):
        self.anastasia(right=True)
        self.game.end_turn(0)
        self.unit("peao")
        self.assertIn("anastasia", {t.pattern for t in self.game.mates.threats[0]})
        self.game.end_turn(1)
        self.p0.mana = 10
        self.assertTrue(self.game.playable(0, self.card("mate_anastasia"), mode="manobra"))

    def test_boden_intermediate_death_with_two_survivors_keeps_threat(self):
        self.unit("bispo")
        for _ in range(3):
            self.unit("peao")
        self.unit("bispo", position=5)
        self.game.end_turn(0)
        pawn = self.p0.board[2]
        pawn.effects = []
        pawn.health = 0
        self.game.cleanup()
        self.assertEqual(len(self.game.mates.threats[0]), 1)
        self.game.end_turn(1)
        self.p0.mana = 10
        self.p0.maneuvers_played = 2
        self.game.play_card(0, self.card("mate_boden"), mode="manobra")
        self.assertTrue(self.game.over)

    def test_direct_effect_cannot_bypass_conditions(self):
        self.game.parser.execute(self.game.catalog["mate_boden"]["manouvre_mode"]["effects"], "on_play", 0)
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
            self.assertEqual(variant["piece_mode"]["cost"], 5)
            self.assertEqual(variant["manouvre_mode"]["effects"][0], base["manouvre_mode"]["effects"][0])
            self.assertEqual(variant["rarity"], "legendary")
        self.assertEqual(THEMES["mate_boden"][0], "bodenMate")
        self.assertEqual(THEMES["mate_anastasia"][0], "anastasiaMate")

    def test_schema_rejects_bad_pattern_or_nonlegendary(self):
        for mutation in ("pattern", "rarity", "trigger", "type"):
            cards = copy.deepcopy(load_cards())
            mate = next(c for c in cards if c["id"] == "mate_boden")
            if mutation == "pattern":
                mate["manouvre_mode"]["effects"][0]["pattern"] = "unknown"
            elif mutation == "rarity":
                del mate["rarity"]
            elif mutation == "trigger":
                mate["manouvre_mode"]["effects"][0]["trigger"] = "on_turn_end"
            else:
                mate["piece_mode"]["effects"] = mate["manouvre_mode"]["effects"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_cards(cards)

    def test_maneuver_counter_resets_on_own_next_turn(self):
        self.game.play_card(0, self.card("roque"), mode="manobra")
        self.assertEqual(self.p0.maneuvers_played, 1)
        self.game.end_turn(0)
        self.game.end_turn(1)
        self.assertEqual(self.p0.maneuvers_played, 0)

    def test_ai_executes_legal_alternate_victory(self):
        self.game.end_turn(0)
        for card_id, slot in (("bispo", 0), ("peao", 1), ("peao", 2), ("bispo", 5)):
            self.unit(card_id, 1, slot)
        self.game.end_turn(1)
        self.game.end_turn(0)
        self.p1.hand = [Card(self.game.uid(), self.game.catalog["mate_boden"])]
        self.p1.mana = 10
        self.p1.maneuvers_played = 2
        self.game.ai_step()
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 1)

    def smothered(self):
        knight = self.unit("cavalo")
        for _ in range(6):
            unit = self.unit("peao", 1)
            unit.effects = []
        return knight

    def back_rank(self):
        rook = self.unit("torre", position=5)
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

    def test_smothered_wins_with_six_pieces_and_surviving_knight(self):
        self.smothered()
        self.cycle()
        self.game.play_card(0, self.card("mate_abafado"), mode="manobra")
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 0)
        self.assertEqual(self.p1.health, 30)
        self.assertEqual(self.p0.mana, 4)

    def test_smothered_allows_frozen_enemy_pieces(self):
        self.smothered()
        self.cycle()
        self.p1.board[0].frozen_through = 100
        self.game.play_card(0, self.card("mate_abafado"), mode="manobra")
        self.assertTrue(self.game.over)

    def test_smothered_fails_if_enemy_opens_a_slot_or_has_a_king(self):
        self.smothered()
        self.cycle()
        card = self.card("mate_abafado")
        self.p1.board[0].health = 0
        self.game.cleanup()
        self.assertFalse(self.game.playable(0, card, mode="manobra"))
        self.p1.endgame_ready = True
        self.game.activate_king(1)
        self.assertEqual(len(self.p1.board), 6)
        self.assertFalse(self.game.playable(0, card, mode="manobra"))

    def test_smothered_knight_must_not_attack_in_execution_turn(self):
        knight = self.smothered()
        self.cycle()
        self.game.attack(0, knight, self.p1.board[0])
        self.assertFalse(self.game.playable(0, self.card("mate_abafado"), mode="manobra"))

    def test_back_rank_requires_actual_attack_this_turn_and_survival(self):
        rook = self.back_rank()
        self.cycle()
        card = self.card("mate_gaveta")
        self.assertFalse(self.game.playable(0, card, mode="manobra"))
        self.game.attack(0, rook, self.p1)
        self.game.play_card(0, card, mode="manobra")
        self.assertTrue(self.game.over)
        self.assertEqual(self.p1.health, 27)
        self.assertEqual(self.p0.mana, 2)

    def test_back_rank_counts_only_pawns_and_excludes_king(self):
        rook = self.back_rank()
        self.cycle()
        self.game.attack(0, rook, self.p1)
        card = self.card("mate_gaveta")
        removed = self.p1.board[-1]
        removed.health = 0
        self.game.cleanup()
        self.assertFalse(self.game.playable(0, card, mode="manobra"))
        self.p1.endgame_ready = True
        self.game.activate_king(1)
        self.assertFalse(self.game.playable(0, card, mode="manobra"))
        self.unit("torre", 1)
        self.assertFalse(self.game.playable(0, card, mode="manobra"))
        self.unit("peao_passado", 1)
        self.assertTrue(self.game.playable(0, card, mode="manobra"))

    def test_back_rank_zero_armor_requirement(self):
        rook = self.back_rank()
        self.cycle()
        self.game.attack(0, rook, self.p1)
        self.p1.armor = 1
        card = self.card("mate_gaveta")
        with self.assertRaisesRegex(RuleError, "Armadura"):
            self.game.play_card(0, card, mode="manobra")
        self.assertEqual(self.p0.mana, 10)
        self.assertIn(card, self.p0.hand)
        self.game.damage(self.p1, 1)
        self.assertEqual(self.p1.armor, 0)
        self.assertEqual(self.p1.health, 27)
        self.game.play_card(0, card, mode="manobra")
        self.assertTrue(self.game.over)

    def test_back_rank_dead_attacker_cannot_execute(self):
        rook = self.back_rank()
        self.cycle()
        self.p1.board[0].attack = 10
        self.game.move_unit(0, rook, 0)
        self.game.attack(0, rook, self.p1.board[0])  # Shield absorbs retaliation.
        self.game.damage(rook, 99)
        self.game.cleanup()
        self.assertFalse(self.game.playable(0, self.card("mate_gaveta"), mode="manobra"))

    def test_opera_victory_uses_history_of_same_units(self):
        pair = self.opera()
        self.cycle()
        self.assertTrue(all(u.has_attacked and u.attacks_used == 0 for u in pair))
        self.game.play_card(0, self.card("mate_opera"), mode="manobra")
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
        self.game.attack(0, rook, self.p1.board[0])
        self.assertFalse(self.game.playable(0, card, mode="manobra"))

    def test_opera_enemy_health_and_exactly_one_piece(self):
        self.opera()
        self.cycle()
        card = self.card("mate_opera")
        self.p1.health = 16
        self.assertFalse(self.game.playable(0, card, mode="manobra"))
        self.p1.health = 15
        self.unit("peao", 1)
        self.assertFalse(self.game.playable(0, card, mode="manobra"))

    def test_opera_requires_exactly_one_rook_bishop_and_adjacency(self):
        self.unit("torre")
        self.unit("peao")
        self.unit("bispo")
        self.assertEqual(self.game.mates.formations(0, "opera"), [])
        self.p0.board.pop(1)
        self.assertEqual(self.game.mates.formations(0, "opera"), [])
        # A new bishop in the vacant neighboring slot gives physical adjacency.
        self.p0.board.pop()
        self.unit("bispo", position=1)
        self.assertEqual(len(self.game.mates.formations(0, "opera")), 1)
        self.unit("bispo")
        self.assertEqual(self.game.mates.formations(0, "opera"), [])

    def test_opposition_victory_with_passed_pawn_in_hand(self):
        self.opposition()
        self.cycle()
        self.game.play_card(0, self.card("endgame_puro"), mode="manobra")
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
        self.assertFalse(self.game.playable(0, card, mode="manobra"))
        self.p0.health = self.p1.health - 1
        self.assertFalse(self.game.playable(0, card, mode="manobra"))

    def test_opposition_any_other_piece_cancels_preparation_permanently(self):
        self.opposition()
        self.game.end_turn(0)
        pawn = self.unit("peao", 1)
        self.assertNotIn("opposition", {t.pattern for t in self.game.mates.threats[0]})
        pawn.effects = []
        pawn.health = 0
        self.game.cleanup()
        self.game.end_turn(1)
        self.assertFalse(self.game.playable(0, self.card("endgame_puro"), mode="manobra"))

    def test_opposition_king_attack_blocks_execution(self):
        king = self.opposition()
        self.cycle()
        self.game.attack(0, king, self.p1.king)
        self.assertFalse(self.game.playable(0, self.card("endgame_puro"), mode="manobra"))

    def test_new_patterns_require_prior_announcement(self):
        for pattern, card_id in (
            ("smothered", "mate_abafado"), ("back_rank", "mate_gaveta"),
            ("opera", "mate_opera"), ("opposition", "endgame_puro"),
        ):
            self.assertFalse(self.game.playable(0, self.card(card_id), mode="manobra"))
            self.game.mates.execute(0, pattern)
            self.assertFalse(self.game.over)

    def test_all_six_quality_variants_preserve_requirements_and_cost(self):
        from mate_rules import PATTERNS

        mates = [c for c in self.game.catalog.values()
                 if any(e["action"] == "win_pattern" for e in c["manouvre_mode"]["effects"])]
        self.assertEqual(len(mates), 6)
        self.assertEqual({c["manouvre_mode"]["effects"][0]["pattern"] for c in mates}, PATTERNS)
        for base in mates:
            for quality in ("improved", "perfect"):
                variant = make_variant(base, quality)
                self.assertEqual(variant["manouvre_mode"]["effects"][0], base["manouvre_mode"]["effects"][0])
                self.assertEqual(variant["piece_mode"]["cost"], base["piece_mode"]["cost"])
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
