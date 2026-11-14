import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from card_tooltip import HOVER_DELAY_MS
from game_engine import Card
from main import App, State
from ui_theme import GOLD


class ResourceUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.app = App(seed=3, decks_path=Path(cls.temporary.name) / "decks.json")

    @classmethod
    def tearDownClass(cls):
        pygame.quit()
        cls.temporary.cleanup()

    def setUp(self):
        self.app.pointer_in_window = True
        self.app.start_game()
        self.game = self.app.game

    def hover(self, point, now):
        with patch("pygame.mouse.get_pos", return_value=point), patch("pygame.time.get_ticks", return_value=now):
            self.app.update(0.1)

    def test_zone_tooltips_for_both_sides_and_live_counts(self):
        for owner in (0, 1):
            player = self.game.players[owner]
            for index, (zone, rect) in enumerate(self.app.zone_rects(owner).items()):
                point = rect.center
                now = 10000 + owner * 10000 + index * 1000
                with self.subTest(owner=owner, zone=zone):
                    self.hover(point, now)
                    self.assertFalse(self.app.info_tooltip.visible)
                    self.hover(point, now + HOVER_DELAY_MS)
                    self.assertTrue(self.app.info_tooltip.visible)
                    self.assertEqual(self.app.info_tooltip.key, (owner, zone))
                    value = {
                        "hand": len(player.hand), "deck": len(player.deck),
                        "discard": len(player.discard), "tempo": player.mana,
                    }[zone]
                    self.assertIn(str(value), self.app.info_tooltip.text)
        player = self.game.players[1]
        point = self.app.zone_rects(1)["deck"].center
        self.hover(point, 40000)
        self.hover(point, 40000 + HOVER_DELAY_MS)
        player.deck.pop()
        self.hover(point, 41000)
        self.assertIn(str(len(player.deck)), self.app.info_tooltip.text)
        self.hover((0, 0), 42000)
        self.assertFalse(self.app.info_tooltip.visible)

    def test_card_hover_has_priority_and_focus_loss_hides_info(self):
        player = self.game.players[0]
        player.hand = [Card(self.game.uid(), self.game.catalog["dama"])]
        point = self.app.hand_rects()[0][1].center
        self.hover(point, 1000)
        self.hover(point, 1000 + HOVER_DELAY_MS)
        self.assertTrue(self.app.card_tooltip.visible)
        self.assertFalse(self.app.info_tooltip.visible)
        point = self.app.zone_rects(0)["hand"].center
        self.hover(point, 2000)
        self.hover(point, 2000 + HOVER_DELAY_MS)
        self.assertTrue(self.app.info_tooltip.visible)
        self.app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.assertFalse(self.app.info_tooltip.visible)
        self.app.state = State.MENU
        self.hover(point, 4000)
        self.assertFalse(self.app.info_tooltip.visible)

    def test_tempo_balls_show_unlocked_spent_and_temporary_resources(self):
        player = self.game.players[0]
        player.max_mana, player.temporary_mana, player.mana = 3, 1, 2
        with patch("pygame.draw.circle") as circle:
            self.app.draw_tempo(0)
        calls = circle.call_args_list
        fills = [call.args[1] for call in calls[::2]]
        borders = [call.args[1] for call in calls[1::2]]
        self.assertEqual(len(fills), 10)
        self.assertEqual(fills[:2], [(72, 179, 250)] * 2)
        self.assertEqual(fills[2:4], [(34, 69, 96)] * 2)
        self.assertEqual(fills[4:], [(44, 49, 56)] * 6)
        self.assertEqual([i for i, border in enumerate(borders) if border == GOLD], [3])
        player.max_mana, player.temporary_mana, player.mana = 10, 1, 11
        with patch("pygame.draw.circle") as circle:
            self.app.draw_tempo(0)
        self.assertEqual(len(circle.call_args_list), 22)
        self.assertEqual(circle.call_args_list[-1].args[1], GOLD)
        player.mana = 0
        with patch("pygame.draw.circle") as circle:
            self.app.draw_tempo(0)
        self.assertTrue(all(call.args[1] == (34, 69, 96) for call in circle.call_args_list[::2]))

    def test_resource_zones_take_priority_over_raised_hand_and_do_not_play_cards(self):
        player = self.game.players[0]
        player.hand = [Card(self.game.uid(), self.game.catalog["dama"]) for _ in range(10)]
        player.mana = player.max_mana = 10
        point = self.app.hand_rects()[7][1].center
        self.hover(point, 1000)
        zone = self.app.zone_rects(0)["tempo"].center
        self.hover(zone, 2000)
        self.hover(zone, 2000 + HOVER_DELAY_MS)
        self.assertTrue(self.app.info_tooltip.visible)
        self.assertEqual(self.app.info_tooltip.key, (0, "tempo"))
        self.assertFalse(self.app.card_tooltip.visible)
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=zone))
        self.assertIsNone(self.app.drag_card)
        self.assertIsNone(self.app.selected_card)
        self.assertEqual(len(player.hand), 10)
        card = player.hand[0]
        self.app.selected_card = card
        for owner in (0, 1):
            for rect in self.app.zone_rects(owner).values():
                self.app.click(rect.center)
                self.assertIs(self.app.selected_card, card)
                self.assertIn(card, player.hand)


if __name__ == "__main__":
    unittest.main()
