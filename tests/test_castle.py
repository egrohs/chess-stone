import unittest

from game_engine import Card, Game, RuleError, load_cards


class CastleTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(load_cards(), deck_size=100, seed=3, opening_hand=0)
        self.player = self.game.players[0]
        self.player.mana = 10

    def test_requires_corner_rook_and_spends_two_for_four_armor_once(self):
        self.player.armor = 3
        self.assertFalse(self.game.can_castle(0))
        rook = self.game.summon(0, "coluna_aberta", 1)
        with self.assertRaisesRegex(RuleError, "canto"):
            self.game.castle(0)
        rook.slot = 5
        self.player.mana = 1
        with self.assertRaisesRegex(RuleError, "Tempo"):
            self.game.castle(0)
        self.assertEqual((self.player.mana, self.player.armor, self.player.castled), (1, 3, False))
        self.player.mana = 10
        self.game.castle(0)
        self.assertEqual((self.player.mana, self.player.armor, self.player.castled), (8, 7, True))
        self.assertEqual(self.player.board, [rook])
        self.assertEqual(self.player.health, 20)
        self.assertEqual(self.player.maneuvers_played, 0)
        self.game.damage(self.player, 4)
        self.assertEqual((self.player.armor, self.player.health), (3, 20))
        with self.assertRaisesRegex(RuleError, "ja foi usado"):
            self.game.castle(0)

    def test_king_on_board_turn_and_game_over_prevent_castle(self):
        self.game.summon(0, "torre", 0)
        with self.assertRaisesRegex(RuleError, "turno"):
            self.game.castle(1)
        self.player.endgame_ready = True
        self.game.activate_king(0)
        with self.assertRaisesRegex(RuleError, "Rei fora"):
            self.game.castle(0)
        self.game.over = True
        with self.assertRaisesRegex(RuleError, "terminou"):
            self.game.castle(0)
        self.assertEqual((self.player.mana, self.player.armor, self.player.castled), (10, 0, False))

    def test_ai_prepares_and_uses_castle(self):
        self.game.end_turn(0)
        enemy = self.game.players[1]
        enemy.mana = 10
        enemy.hand.clear()
        enemy.hand.append(Card(self.game.uid(), self.game.catalog["torre"]))
        self.game.ai_step()
        self.assertIn(enemy.board[0].slot, (0, 5))
        self.game.ai_step()
        self.assertTrue(enemy.castled)
        self.assertEqual((enemy.armor, enemy.mana), (4, 4))

    def test_removed_card_not_in_catalog_or_random_decks(self):
        self.assertNotIn("roque", self.game.catalog)
        for player in self.game.players:
            self.assertNotIn("roque", player.deck)


if __name__ == "__main__":
    unittest.main()
