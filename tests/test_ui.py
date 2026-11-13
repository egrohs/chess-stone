import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from game_engine import Card
from main import App, State


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App(deck_size=100, seed=3)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app.start_game()
        self.game = self.app.game
        self.player = self.game.players[0]
        self.player.hand.clear()
        self.player.mana = self.player.max_mana = 10

    def add_card(self, card_id):
        card = Card(self.game.uid(), self.game.catalog[card_id])
        self.player.hand.append(card)
        return card

    def select_first_card(self):
        self.app.click(self.app.hand_rects()[0][1].center)

    def test_select_and_place_minion(self):
        card = self.add_card("peao")
        self.select_first_card()
        self.assertIs(self.app.selected_card, card)
        self.assertTrue(self.app.choosing_position())
        self.assertEqual(len([r for _, r in self.app.placement_rects() if r.width > 8]), 8)
        self.app.draw()
        self.app.click(self.app.slots(0)[0].center)
        self.assertEqual(self.player.board[0].card_id, "peao")
        self.assertIsNone(self.app.selected_card)

    def test_insertion_bar_click(self):
        left = self.game.summon(0, "peao")
        right = self.game.summon(0, "peao")
        self.add_card("cavalo")
        self.select_first_card()
        position, rect = self.app.placement_rects()[1]
        self.assertEqual(position, 1)
        self.app.click(rect.center)
        self.assertEqual(self.player.board[1].card_id, "cavalo")
        self.assertEqual((left.attack, right.attack), (2, 2))

    def test_targeted_spell_click(self):
        enemy = self.game.summon(1, "peao")
        self.add_card("cravada_absoluta")
        self.select_first_card()
        self.assertIn(enemy, self.app.valid_targets())
        self.app.draw()
        self.app.click(self.app.slots(1)[0].center)
        self.assertGreater(enemy.frozen_through, 0)
        self.assertIsNone(self.app.selected_card)

    def test_minion_with_target_uses_two_click_stages(self):
        enemy = self.game.summon(1, "peao")
        card = self.add_card("peao")
        card.definition = dict(card.definition, effects=[{
            "trigger": "on_play", "action": "damage", "amount": 1, "target": "target_enemy",
        }])
        self.select_first_card()
        self.assertEqual(self.app.valid_targets(), [])
        self.app.click(self.app.slots(0)[0].center)
        self.assertIn(enemy, self.app.valid_targets())
        self.assertEqual(len(self.player.board), 0)
        self.app.click(self.app.slots(1)[0].center)
        self.assertEqual(enemy.health, 1)
        self.assertEqual(len(self.player.board), 1)

    def test_no_target_spell_uses_button(self):
        card = self.add_card("roque")
        self.select_first_card()
        self.assertIn(card, self.player.hand)
        self.app.click(self.app.play_button.center)
        self.assertNotIn(card, self.player.hand)
        self.assertEqual(self.player.board[0].card_id, "torre")

    def test_attack_hero_click(self):
        self.game.summon(0, "dama")
        self.app.click(self.app.slots(0)[0].center)
        self.assertIsNotNone(self.app.selected_unit)
        self.app.click(self.app.hero_rect(1).center)
        self.assertEqual(self.game.players[1].health, 25)

    def test_invalid_card_shows_reason(self):
        self.player.mana = 0
        self.add_card("roque")
        self.select_first_card()
        self.app.click(self.app.play_button.center)
        self.assertIn("Mana insuficiente", self.game.messages[-1])

    def test_cancel_selection_and_king_button(self):
        self.add_card("peao")
        self.select_first_card()
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(0, 0)))
        self.assertIsNone(self.app.selected_card)
        self.player.endgame_ready = True
        self.app.click(self.app.king_button.center)
        self.assertIsNotNone(self.player.king)
        self.app.draw()

    def test_end_turn_and_nonblocking_ai_update(self):
        self.app.click(self.app.end_button.center)
        self.assertEqual(self.game.current, 1)
        self.app.ai_at = 0
        self.app.update()
        self.assertGreater(self.app.ai_at, 0)
        self.app.draw()

    def test_three_states_and_restart(self):
        self.app.state = State.MENU
        self.app.draw()
        self.app.click(self.app.start_button.center)
        self.assertEqual(self.app.state, State.MATCH)
        self.game = self.app.game
        self.game.damage(self.game.hero_target(1), 99)
        self.game.cleanup()
        self.app.update()
        self.assertEqual(self.app.state, State.GAME_OVER)
        self.app.draw()
        self.app.click(self.app.start_button.center)
        self.assertEqual(self.app.state, State.MATCH)
        self.assertFalse(self.app.game.over)


if __name__ == "__main__":
    unittest.main()
