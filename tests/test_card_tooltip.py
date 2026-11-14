import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from card_tooltip import CardTooltip, HOVER_DELAY_MS, card_details
from crafting import make_variant
from game_engine import Card, KEYWORD_LABELS
from main import App, State


class CardTooltipTests(unittest.TestCase):
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
        self.player = self.game.players[0]
        self.player.hand.clear()

    def add_card(self, card_id):
        card = Card(self.game.uid(), self.game.catalog[card_id])
        self.player.hand.append(card)
        return card

    def hover(self, point, now):
        with patch("pygame.mouse.get_pos", return_value=point), patch("pygame.time.get_ticks", return_value=now):
            self.app.update(0.1)

    def test_hover_delay_switch_leave_and_removed_card(self):
        first = self.add_card("dama")
        second = self.add_card("peao")
        point1 = self.app.hand_rects()[0][1].center
        point2 = self.app.hand_rects()[1][1].center
        self.hover(point1, 1000)
        self.assertIs(self.app.card_tooltip.card, first.definition)
        self.assertFalse(self.app.card_tooltip.visible)
        self.hover(point1, 1000 + HOVER_DELAY_MS - 1)
        self.assertFalse(self.app.card_tooltip.visible)
        self.hover(point1, 1000 + HOVER_DELAY_MS)
        self.assertTrue(self.app.card_tooltip.visible)
        self.hover(point2, 2000)
        self.assertIs(self.app.card_tooltip.card, second.definition)
        self.assertFalse(self.app.card_tooltip.visible)
        self.hover(point2, 2000 + HOVER_DELAY_MS)
        self.assertTrue(self.app.card_tooltip.visible)
        self.player.hand.remove(second)
        self.hover((0, 0), 3000)
        self.assertIsNone(self.app.card_tooltip.card)
        self.assertFalse(self.app.card_tooltip.visible)

    def test_collection_builder_and_both_board_sides(self):
        for owner in (0, 1):
            unit = self.game.summon(owner, "cavalo", 0)
            point = self.app.slots(owner)[unit.slot].center
            self.hover(point, 1000 + owner * 1000)
            self.hover(point, 1000 + owner * 1000 + HOVER_DELAY_MS)
            self.assertTrue(self.app.card_tooltip.visible)
            self.assertEqual(self.app.card_tooltip.card["id"], "cavalo")
        self.app.state = State.COLLECTION
        definition, rect = self.app.collection.rows()[0]
        self.hover(rect.center, 4000)
        self.hover(rect.center, 4000 + HOVER_DELAY_MS)
        self.assertTrue(self.app.card_tooltip.visible)
        self.assertEqual(self.app.card_tooltip.card["id"], definition["id"])
        self.app.state = State.DECK_BUILDER
        definition, minus, _ = self.app.catalog_rows()[0]
        self.hover((50, minus.centery), 5000)
        self.hover((50, minus.centery), 5000 + HOVER_DELAY_MS)
        self.assertTrue(self.app.card_tooltip.visible)
        self.assertEqual(self.app.card_tooltip.card["id"], definition["id"])
        self.hover(minus.center, 6000)
        self.assertFalse(self.app.card_tooltip.visible)

    def test_drag_focus_and_window_leave_dismiss_tooltip(self):
        self.add_card("dama")
        point = self.app.hand_rects()[0][1].center
        self.hover(point, 1000)
        self.hover(point, 1000 + HOVER_DELAY_MS)
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
        self.assertFalse(self.app.card_tooltip.visible)
        self.hover(point, 3000)
        self.assertIsNone(self.app.card_tooltip.card)
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=point))
        self.hover(point, 4000)
        self.hover(point, 4000 + HOVER_DELAY_MS)
        self.app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.assertFalse(self.app.card_tooltip.visible)
        self.hover(point, 6000)
        self.assertIsNone(self.app.card_tooltip.card)
        self.app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
        self.hover(point, 7000)
        self.assertFalse(self.app.card_tooltip.visible)

    def test_keywords_and_actual_generated_effects(self):
        catalog = self.game.catalog
        self.assertEqual(card_details(catalog["dama"], catalog)[0], ["charge", "windfury"])
        self.assertEqual(card_details(catalog["coluna_aberta"], catalog)[0], ["rush"])
        self.assertEqual(
            card_details(make_variant(catalog["dama"], "perfect"), catalog)[0],
            ["charge", "windfury", "on_play"],
        )
        self.assertIn("freeze", card_details(catalog["zugzwang"], catalog)[0])
        self.assertIn("on_death", card_details(catalog["peao"], catalog)[0])
        self.assertIn("on_kill", card_details(catalog["ataque_duplo"], catalog)[0])
        self.assertEqual(card_details(catalog["sacrificio_da_dama"], catalog)[1], [])
        card = copy.deepcopy(catalog["peao"])
        card["piece_mode"]["effects"] = [
            {"trigger": "on_death", "action": "summon", "card_id": "cavalo"},
            {"trigger": "on_death", "action": "summon", "card_id": "cavalo"},
        ]
        card["manouvre_mode"]["effects"] = [{
            "action": "damage", "on_kill": {"action": "summon", "card_id": "torre"},
        }]
        mechanics, generated = card_details(card, catalog)
        self.assertIn("on_kill", mechanics)
        self.assertEqual([c["id"] for c in generated], ["cavalo", "torre"])

    def test_complete_text_keyword_panels_and_scroll(self):
        card = copy.deepcopy(self.game.catalog["mate_anastasia"])
        card["piece_mode"]["keywords"] = list(KEYWORD_LABELS)
        card["piece_mode"]["effects"] = [
            {"trigger": trigger, "action": "summon", "card_id": card_id}
            for trigger, card_id in zip(
                ("on_play", "on_death", "on_turn_start", "on_turn_end"),
                ("peao", "cavalo", "bispo", "torre"),
            )
        ]
        tooltip = CardTooltip()
        tooltip.update("test", card, pygame.Rect(1300, 850, 100, 80), 0)
        tooltip.update("test", card, pygame.Rect(1300, 850, 100, 80), HOVER_DELAY_MS)
        with patch.object(self.app, "text", wraps=self.app.text) as text:
            tooltip.draw(self.app)
        lines = [call.args[0] for call in text.call_args_list]
        self.assertTrue(all(line in lines for line in self.app.wrap(card["description"], 286, self.app.font)))
        self.assertTrue(all(label in lines for label in KEYWORD_LABELS.values()))
        self.assertIn("Cavalo", lines)
        self.assertGreater(tooltip.max_scroll, 0)
        self.assertTrue(tooltip.wheel(-1))
        self.assertEqual(tooltip.scroll, 60)
        self.app.card_tooltip = tooltip
        self.app.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=-1, x=0))
        self.assertEqual(tooltip.scroll, 120)
        tooltip.update("next", card, pygame.Rect(0, 0, 10, 10), 2000)
        self.assertEqual(tooltip.scroll, 0)
        self.assertFalse(tooltip.visible)

    def test_every_catalog_description_is_rendered_in_full(self):
        for index, card in enumerate(self.app.cards):
            with self.subTest(card=card["id"]):
                tooltip = CardTooltip()
                rect = pygame.Rect(10 if index % 2 else 1350, 10 if index % 3 else 850, 80, 80)
                tooltip.update(card["id"], card, rect, 0)
                tooltip.update(card["id"], card, rect, HOVER_DELAY_MS)
                with patch.object(self.app, "text", wraps=self.app.text) as text:
                    tooltip.draw(self.app)
                rendered = [call.args[0] for call in text.call_args_list]
                self.assertTrue(all(line in rendered for line in self.app.wrap(card["description"], 286, self.app.font)))


if __name__ == "__main__":
    unittest.main()
