import os
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from game_engine import Card
from main import App, State


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.app = App(deck_size=100, seed=3, decks_path=Path(cls.temporary.name) / "decks.json")

    @classmethod
    def tearDownClass(cls):
        pygame.quit()
        cls.temporary.cleanup()

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

    def card_mouse_down(self, card):
        rect = next(rect for candidate, rect in self.app.hand_rects() if candidate is card)
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
        return rect.center

    def card_mouse_up(self, point):
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=point))

    def test_drag_card_to_empty_slot_draws_and_plays_piece(self):
        card = self.add_card("peao")
        start = self.card_mouse_down(card)
        destination = self.app.slots(0)[2].center
        self.app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=destination, rel=(0, 0), buttons=(1, 0, 0)))
        self.assertIs(self.app.selected_card, card)
        self.assertEqual(len(self.app.placement_rects()), 6)
        with patch.object(self.app, "draw_hand_card", wraps=self.app.draw_hand_card) as draw:
            self.app.draw()
        self.assertEqual(draw.call_args.args[2], destination)
        self.card_mouse_up(destination)
        self.assertEqual(self.player.unit_at(2).card_id, "peao")
        self.assertEqual(self.player.mana, 9)
        self.assertNotIn(card, self.player.hand)
        self.assertIsNone(self.app.drag_card)
        self.assertNotEqual(start, destination)

    def test_card_click_and_selected_card_drag(self):
        card = self.add_card("peao")
        start = self.card_mouse_down(card)
        self.card_mouse_up(start)
        self.assertIs(self.app.selected_card, card)
        self.card_mouse_down(card)
        self.card_mouse_up(start)
        self.assertIsNone(self.app.selected_card)
        self.card_mouse_down(card)
        self.card_mouse_up(start)
        self.card_mouse_down(card)
        self.card_mouse_up(self.app.slots(0)[0].center)
        self.assertEqual(self.player.unit_at(0).card_id, "peao")

    def test_drag_maneuvers_to_button_and_valid_targets(self):
        card = self.add_card("peao")
        self.card_mouse_down(card)
        self.card_mouse_up(self.app.play_button.center)
        self.assertIn(card, self.player.discard)
        enemy = self.game.summon(1, "peao")
        card = self.add_card("cravada_absoluta")
        self.card_mouse_down(card)
        self.card_mouse_up(self.app.slots(1)[0].center)
        self.assertGreater(enemy.frozen_through, 0)
        self.assertIn(card, self.player.discard)
        ally = self.game.summon(0, "peao")
        card = self.add_card("torre")
        self.card_mouse_down(card)
        self.card_mouse_up(self.app.slots(0)[0].center)
        self.assertIn("divine_shield", ally.keywords)
        self.assertIn(card, self.player.discard)

    def test_drag_maneuver_to_enemy_field_or_choose_target_later(self):
        card = self.add_card("peao")
        self.card_mouse_down(card)
        self.card_mouse_up(self.app.slots(1)[2].center)
        self.assertIn(card, self.player.discard)
        ally = self.game.summon(0, "peao")
        card = self.add_card("torre")
        self.card_mouse_down(card)
        self.card_mouse_up(self.app.play_button.center)
        self.assertEqual(self.app.selected_mode, "manobra")
        self.assertIn(card, self.player.hand)
        self.app.click(self.app.slots(0)[0].center)
        self.assertIn("divine_shield", ally.keywords)
        self.assertIn(card, self.player.discard)

    def test_drag_targeted_piece_then_select_target(self):
        enemy = self.game.summon(1, "peao")
        card = self.add_card("peao")
        card.definition = copy.deepcopy(card.definition)
        card.definition["piece_mode"]["effects"] = [{
            "trigger": "on_play", "action": "damage", "amount": 1, "target": "target_enemy",
        }]
        self.card_mouse_down(card)
        self.card_mouse_up(self.app.slots(0)[0].center)
        self.assertEqual(self.app.selected_mode, "piece")
        self.assertIn(card, self.player.hand)
        self.app.click(self.app.slots(1)[0].center)
        self.assertEqual(enemy.health, 1)
        self.assertEqual(self.player.unit_at(0).card_id, "peao")

    def test_card_drag_invalid_drops_and_cancellation(self):
        self.game.summon(0, "peao", 0)
        card = self.add_card("peao")
        self.card_mouse_down(card)
        self.card_mouse_up(self.app.slots(0)[0].center)
        self.assertIn("Casa ocupada", self.game.messages[-1])
        self.assertIn(card, self.player.hand)
        self.card_mouse_down(card)
        self.card_mouse_up((50, 380))
        self.assertIsNone(self.app.selected_card)
        self.assertIn(card, self.player.hand)
        self.card_mouse_down(card)
        self.app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(500, 500), rel=(0, 0), buttons=(1, 0, 0)))
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.card_mouse_up(self.app.slots(0)[1].center)
        self.assertIsNone(self.player.unit_at(1))
        self.assertEqual(self.player.mana, 10)
        for cancel in (
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(500, 500)),
            pygame.event.Event(pygame.WINDOWFOCUSLOST),
        ):
            self.card_mouse_down(card)
            self.app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(500, 500), rel=(0, 0), buttons=(1, 0, 0)))
            self.app.handle_event(cancel)
            self.card_mouse_up(self.app.slots(0)[1].center)
            self.assertIsNone(self.player.unit_at(1))
            self.assertIn(card, self.player.hand)

    def test_card_drag_respects_turn_and_mana(self):
        card = self.add_card("peao")
        self.player.mana = 0
        self.card_mouse_down(card)
        self.card_mouse_up(self.app.slots(0)[0].center)
        self.assertIn("Tempo insuficiente", self.game.messages[-1])
        self.assertIn(card, self.player.hand)
        self.app.clear_selection()
        self.game.end_turn(0)
        self.card_mouse_down(card)
        self.card_mouse_up(self.app.slots(0)[0].center)
        self.assertIsNone(self.player.unit_at(0))
        self.assertIsNone(self.app.drag_card)

    def test_hover_update_and_click_on_raised_card_preserve_piece_play(self):
        card = self.add_card("peao")
        rect = self.app.hand_rects()[0][1]
        with patch("pygame.mouse.get_pos", return_value=rect.center):
            self.app.update(0.25)
        self.assertIs(self.app.hand_view.hovered, card)
        motion = self.app.hand_view.motions[card.uid]
        self.app.draw()
        self.app.click((rect.centerx, round(motion.y - 100)))
        self.assertIs(self.app.selected_card, card)
        self.app.click(self.app.slots(0)[0].center)
        self.assertEqual(self.player.board[0].card_id, "peao")
        self.assertNotIn(card, self.player.hand)
        self.app.update(1 / 60)
        self.assertNotIn(card.uid, self.app.hand_view.motions)

    def test_hover_during_enemy_turn_does_not_allow_play(self):
        card = self.add_card("peao")
        rect = self.app.hand_rects()[0][1]
        self.game.end_turn(0)
        self.app.ai_at = pygame.time.get_ticks() + 10000
        with patch("pygame.mouse.get_pos", return_value=rect.center):
            self.app.update(0.25)
        self.assertIs(self.app.hand_view.hovered, card)
        self.app.click(rect.center)
        self.assertIsNone(self.app.selected_card)
        self.assertIn(card, self.player.hand)

    def test_new_match_resets_hand_animation(self):
        self.add_card("peao")
        self.app.hand_view.update(self.app.hand_rects(), self.app.hand_rects()[0][1].center, 1, None)
        self.app.start_game()
        self.assertEqual(self.app.hand_view.motions, {})
        self.assertIsNone(self.app.hand_view.hovered)

    def test_outside_board_click_plays_piece_card_as_maneuver(self):
        card = self.add_card("peao")
        self.select_first_card()
        self.assertIn(card, self.player.hand)
        self.assertIsNone(self.app.selected_mode)
        self.app.click((50, 380))
        self.assertEqual(self.player.board, [])
        self.assertEqual(self.player.discard, [card])
        self.assertEqual(self.player.mana, 9)
        self.assertIsNone(self.app.selected_card)

    def test_board_click_plays_former_maneuver_as_piece(self):
        card = self.add_card("coluna_aberta")
        self.player.health = 20
        self.select_first_card()
        self.app.click(self.app.slots(0)[5].center)
        self.assertEqual(self.player.unit_at(5).piece_type, "torre")
        self.assertEqual(self.player.health, 20)
        self.assertEqual(self.player.mana, 8)
        self.assertEqual(self.player.discard, [])
        self.assertNotIn(card, self.player.hand)

    def test_outside_click_selects_targeted_maneuver_before_ally_target(self):
        ally = self.game.summon(0, "peao", 0)
        card = self.add_card("torre")
        self.select_first_card()
        self.app.click((50, 380))
        self.assertEqual(self.app.selected_mode, "manobra")
        self.assertIn(card, self.player.hand)
        self.assertEqual(self.player.mana, 10)
        self.assertIn(ally, self.app.valid_targets())
        self.app.draw()
        self.app.click(self.app.slots(0)[0].center)
        self.assertIn("divine_shield", ally.keywords)
        self.assertEqual(self.player.discard, [card])
        self.assertEqual(len(self.player.board), 1)

    def test_occupied_piece_destination_does_not_accidentally_play_maneuver(self):
        self.game.summon(0, "peao", 0)
        card = self.add_card("peao")
        self.select_first_card()
        self.app.click(self.app.slots(0)[0].center)
        self.assertIn("Casa ocupada", self.game.messages[-1])
        self.assertIn(card, self.player.hand)
        self.assertEqual(self.player.mana, 10)
        self.assertEqual(self.player.discard, [])

    def test_full_board_and_cancel_targeted_maneuver(self):
        for _ in range(6):
            self.game.summon(0, "peao")
        card = self.add_card("torre")
        self.select_first_card()
        self.assertEqual(self.app.placement_rects(), [])
        self.app.click((50, 380))
        self.assertEqual(self.app.selected_mode, "manobra")
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertIsNone(self.app.selected_mode)
        self.assertIsNone(self.app.selected_card)
        self.assertIn(card, self.player.hand)
        self.assertEqual(self.player.mana, 10)

    def test_slots_match_board_image_without_labels_for_both_players(self):
        labels = ["1 Canto", "2 Borda", "3 Centro", "4 Centro", "5 Borda", "6 Canto"]
        self.game.summon(0, "peao", 0)
        with patch.object(self.app, "text", wraps=self.app.text) as text:
            self.app.draw()
        rendered = [call.args[0] for call in text.call_args_list]
        for label in labels:
            self.assertNotIn(label, rendered)
        self.assertNotIn("1", rendered)
        round_call = next(call for call in text.call_args_list if call.args[0].startswith("Rodada "))
        self.assertLess(round_call.args[1][1] + self.app.large.get_linesize(), self.app.board_rect.top)
        x_edges = (187, 302, 428, 553, 679, 805, 930)
        for owner, top, bottom in ((1, 298, 416), (0, 416, 545)):
            slots = self.app.slots(owner)
            self.assertEqual(len(slots), 6)
            for index, rect in enumerate(slots):
                self.assertEqual((rect.left, rect.right, rect.top, rect.bottom),
                                 (x_edges[index], x_edges[index + 1], top, bottom))
                self.assertTrue(self.app.board_rect.contains(rect))
            self.assertTrue(all(left.right == right.left for left, right in zip(slots, slots[1:])))

    def test_board_cells_are_interactive_for_placement_and_targeting(self):
        for index in range(6):
            with self.subTest(slot=index):
                self.setUp()
                enemy = self.game.summon(1, "peao", index)
                self.add_card("cravada_absoluta")
                self.select_first_card()
                self.app.click(self.app.slots(1)[index].center)
                self.assertGreater(enemy.frozen_through, 0)
                self.add_card("peao")
                self.card_mouse_down(self.player.hand[0])
                self.card_mouse_up(self.app.slots(0)[index].center)
                self.assertEqual(self.player.unit_at(index).card_id, "peao")

    def test_unit_name_and_stats_render_in_board_cell(self):
        unit = self.game.summon(0, "torre", 0)
        with patch.object(self.app, "text", wraps=self.app.text) as text:
            self.app.draw()
        rendered = [call.args[0] for call in text.call_args_list]
        self.assertIn(unit.name, rendered)
        self.assertIn("3 / 5", rendered)

    def test_pawn_art_uses_catalog_identity_and_keeps_real_card_values(self):
        from crafting import make_variant

        pawn = self.add_card("peao")
        art = self.app.card_art(pawn.definition, (51, 60))
        self.assertIsNotNone(art)
        self.assertIs(art, self.app.card_art(pawn.definition, (51, 60)))
        self.assertIsNotNone(self.app.card_art(make_variant(pawn.definition, "perfect"), (51, 60)))
        self.assertIsNone(self.app.card_art(self.game.catalog["peao_passado"], (51, 60)))
        with patch.object(self.app, "text", wraps=self.app.text) as text:
            self.app.hand_card_image(pawn)
        rendered = [call.args[0] for call in text.call_args_list]
        self.assertIn("1", rendered)
        self.assertIn("1/2 ou M", rendered)

    def test_basic_card_art_and_variants_use_distinct_images(self):
        from crafting import make_variant

        images = []
        for card_id in ("peao", "cavalo", "bispo", "torre", "dama"):
            with self.subTest(card=card_id):
                definition = self.game.catalog[card_id]
                art = self.app.card_art(definition, (51, 60))
                self.assertIsNotNone(art)
                self.assertIs(art, self.app.card_art(definition, (51, 60)))
                self.assertIs(art, self.app.card_art(make_variant(definition, "improved"), (51, 60)))
                images.append(pygame.image.tobytes(art, "RGBA"))
        self.assertEqual(len(set(images)), 5)
        self.assertIsNone(self.app.card_art(self.game.catalog["coluna_aberta"], (51, 60)))

    def test_basic_card_art_renders_on_hand_both_boards_and_collection(self):
        card_ids = ("peao", "cavalo", "bispo", "torre", "dama")
        for index, card_id in enumerate(card_ids):
            self.add_card(card_id)
            self.game.summon(0, card_id, index)
            self.game.summon(1, card_id, index)
        with patch.object(self.app, "card_art", wraps=self.app.card_art) as art:
            self.app.draw()
        calls = [(call.args[0]["id"], call.args[1]) for call in art.call_args_list]
        for card_id in card_ids:
            self.assertIn((card_id, (51, 60)), calls)
            self.assertEqual(calls.count((card_id, (38, 45))), 2)
        self.app.state = State.COLLECTION
        self.app.collection.query = ""
        self.app.collection.refresh()
        with patch.object(self.app, "card_art", wraps=self.app.card_art) as art:
            while True:
                self.app.draw()
                if (self.app.collection.page + 1) * 8 >= len(self.app.collection.filtered_cards()):
                    break
                self.app.collection.page += 1
        collection_calls = [(call.args[0]["id"], call.args[1]) for call in art.call_args_list]
        for card_id in card_ids:
            self.assertIn((card_id, (65, 77)), collection_calls)

    def test_pawn_art_renders_in_hand_board_and_collection(self):
        pawn = self.add_card("peao")
        self.game.summon(0, "peao", 0)
        self.game.summon(1, "peao", 0)
        with patch.object(self.app, "card_art", wraps=self.app.card_art) as art:
            self.app.draw()
        calls = [(call.args[0]["id"], call.args[1]) for call in art.call_args_list]
        self.assertIn(("peao", (51, 60)), calls)
        self.assertEqual(calls.count(("peao", (38, 45))), 2)
        self.app.state = State.COLLECTION
        self.app.collection.query = "peao"
        self.app.collection.refresh()
        with patch.object(self.app, "card_art", wraps=self.app.card_art) as art:
            self.app.draw()
        self.assertTrue(any(call.args[0]["id"] == pawn.definition["id"] and call.args[1] == (65, 77)
                            for call in art.call_args_list))

    def test_maneuver_button_switches_from_pending_piece_target(self):
        ally = self.game.summon(0, "peao", 0)
        card = self.add_card("torre")
        card.definition = copy.deepcopy(card.definition)
        card.definition["piece_mode"]["effects"] = [{
            "trigger": "on_play", "action": "heal", "amount": 1, "target": "target_ally_piece",
        }]
        self.select_first_card()
        self.app.click(self.app.slots(0)[5].center)
        self.assertEqual(self.app.selected_mode, "piece")
        self.app.click(self.app.play_button.center)
        self.assertEqual(self.app.selected_mode, "manobra")
        self.assertIsNone(self.app.position)
        self.app.click(self.app.slots(0)[0].center)
        self.assertIn("divine_shield", ally.keywords)
        self.assertEqual(self.player.discard, [card])
        self.assertIsNone(self.player.unit_at(5))

    def test_drag_from_last_corner_to_center(self):
        unit = self.game.summon(0, "peao", 5)
        slots = self.app.slots(0)
        event = pygame.event.Event
        self.app.handle_event(event(pygame.MOUSEBUTTONDOWN, button=1, pos=slots[5].center))
        self.app.handle_event(event(pygame.MOUSEBUTTONUP, button=1, pos=slots[2].center))
        self.assertEqual((unit.slot, self.player.mana), (2, 9))
        self.assertEqual(self.game.center_control(0), 1)

    def test_resource_labels_and_messages_use_tempo(self):
        self.player.temporary_mana = 1
        self.player.center_bonus_pending = True
        with patch.object(self.app, "text", wraps=self.app.text) as text:
            self.app.draw()
        rendered = [call.args[0] for call in text.call_args_list]
        self.assertFalse(any(label.startswith(("Tempo:", "Deck:", "Mao:", "Descarte:")) for label in rendered))
        with patch.object(self.app, "pointer_in_window", True):
            self.app.update_info_tooltip(self.app.zone_rects(0)["tempo"].center, 1000)
        self.assertIn("+1 tempo no proximo turno", self.app.info_tooltip.text)
        unit = self.game.summon(0, "peao", 0)
        self.game.move_unit(0, unit, 2)
        self.assertIn("(1 tempo)", self.game.messages[-1])

    def test_chess_terminology_renders_in_match(self):
        self.game.summon(0, "torre")
        self.game.summon(0, "dama")
        self.game.summon(0, "cavalo")
        with (
            patch.object(self.app, "text", wraps=self.app.text) as text,
            patch.object(self.app, "paragraph", wraps=self.app.paragraph) as paragraph,
            patch.object(self.app, "button", wraps=self.app.button) as button,
        ):
            self.app.draw()
        labels = [call.args[0] for call in text.call_args_list + paragraph.call_args_list]
        for keyword in ("Proteção", "Ataque duplo", "Iniciativa", "Desenvolvimento"):
            self.assertTrue(any(keyword in label for label in labels))
        self.assertFalse(any("Tabuleiro:" in label for label in labels))
        self.assertTrue(any(call.args[1] == "Ativar Rei (Final de jogo)" for call in button.call_args_list))
        for label in labels:
            self.assertNotRegex(
                label.casefold(),
                r"\b(?:provocar|investida|rapidez|heroi|herói|unidades?|slots?|mesa|endgame)\b",
            )

    def test_drag_unit_to_empty_slot(self):
        unit = self.game.summon(0, "peao", 0)
        before = self.player.mana
        slots = self.app.slots(0)
        event = pygame.event.Event
        self.app.handle_event(event(pygame.MOUSEBUTTONDOWN, button=1, pos=slots[0].center))
        self.assertIs(self.app.drag_unit, unit)
        self.app.draw()
        self.app.handle_event(event(pygame.MOUSEBUTTONUP, button=1, pos=slots[4].center))
        self.assertEqual((unit.slot, self.player.mana), (4, before - 1))
        self.assertIsNone(self.app.drag_unit)

    def test_drag_onto_occupied_slot_is_rejected(self):
        unit = self.game.summon(0, "peao", 0)
        self.game.summon(0, "peao", 1)
        before = self.player.mana
        slots = self.app.slots(0)
        event = pygame.event.Event
        self.app.handle_event(event(pygame.MOUSEBUTTONDOWN, button=1, pos=slots[0].center))
        self.app.handle_event(event(pygame.MOUSEBUTTONUP, button=1, pos=slots[1].center))
        self.assertEqual((unit.slot, self.player.mana), (0, before))

    def test_select_and_place_piece(self):
        card = self.add_card("peao")
        self.select_first_card()
        self.assertIs(self.app.selected_card, card)
        self.assertTrue(self.app.choosing_position())
        self.assertEqual(len([r for _, r in self.app.placement_rects() if r.width > 8]), 6)
        self.app.draw()
        self.app.click(self.app.slots(0)[0].center)
        self.assertEqual(self.player.board[0].card_id, "peao")
        self.assertIsNone(self.app.selected_card)

    def test_free_slot_click_between_allies(self):
        left = self.game.summon(0, "peao", 0)
        right = self.game.summon(0, "peao", 2)
        self.add_card("cavalo")
        self.select_first_card()
        position, rect = self.app.placement_rects()[0]
        self.assertEqual(position, 1)
        self.app.click(rect.center)
        self.assertEqual(self.player.board[1].card_id, "cavalo")
        self.assertEqual((left.attack, right.attack), (2, 2))

    def test_targeted_maneuver_click(self):
        enemy = self.game.summon(1, "peao")
        self.add_card("cravada_absoluta")
        self.select_first_card()
        self.assertIn(enemy, self.app.valid_targets())
        self.app.draw()
        self.app.click(self.app.slots(1)[0].center)
        self.assertGreater(enemy.frozen_through, 0)
        self.assertIsNone(self.app.selected_card)

    def test_fixed_slots_render_and_target_after_interior_death(self):
        removed = self.game.summon(1, "peao", 0)
        enemy = self.game.summon(1, "peao", 5)
        removed.effects = []
        removed.health = 0
        self.game.cleanup()
        self.add_card("cravada_absoluta")
        self.select_first_card()
        rectangles = dict(self.app.entity_rects())
        self.assertEqual(rectangles[enemy], self.app.slots(1)[5])
        self.app.draw()
        self.app.click(self.app.slots(1)[5].center)
        self.assertGreater(enemy.frozen_through, 0)
        self.assertEqual(enemy.slot, 5)

    def test_placement_highlights_only_vacant_physical_slots(self):
        self.game.summon(0, "peao", 2)
        self.game.summon(0, "peao", 5)
        self.add_card("dama")
        self.select_first_card()
        self.assertEqual([slot for slot, _ in self.app.placement_rects()], [0, 1, 3, 4])
        self.app.click(self.app.slots(0)[4].center)
        self.assertEqual(self.player.unit_at(4).card_id, "dama")
        self.app.draw()

    def test_deterministic_maneuver_preview_and_center_bonus_render(self):
        self.game.summon(0, "peao", 3)
        self.game.summon(1, "bispo", 4)
        self.game.summon(1, "peao", 5)
        self.game.end_turn(0)
        self.app.draw()
        self.game.end_turn(1)
        self.player.hand.clear()
        self.add_card("ataque_duplo")
        self.select_first_card()
        self.app.draw()
        self.assertEqual(self.player.temporary_mana, 1)
        self.app.click(self.app.play_button.center)
        self.assertEqual(self.game.players[1].unit_at(4).health, 2)
        self.assertIsNone(self.game.players[1].unit_at(5))

    def test_piece_with_target_uses_two_click_stages(self):
        enemy = self.game.summon(1, "peao")
        card = self.add_card("peao")
        card.definition = copy.deepcopy(card.definition)
        card.definition["piece_mode"]["effects"] = [{
            "trigger": "on_play", "action": "damage", "amount": 1, "target": "target_enemy",
        }]
        self.select_first_card()
        self.assertEqual(self.app.valid_targets(), [])
        self.app.click(self.app.slots(0)[0].center)
        self.assertIn(enemy, self.app.valid_targets())
        self.assertEqual(len(self.player.board), 0)
        self.app.click(self.app.slots(1)[0].center)
        self.assertEqual(enemy.health, 1)
        self.assertEqual(len(self.player.board), 1)

    def test_no_target_maneuver_uses_button(self):
        card = self.add_card("bispo")
        self.select_first_card()
        self.assertIn(card, self.player.hand)
        self.app.click(self.app.play_button.center)
        self.assertNotIn(card, self.player.hand)
        self.assertEqual(self.player.discard, [card])

    def test_attack_hero_click(self):
        self.game.summon(0, "dama")
        self.app.click(self.app.slots(0)[0].center)
        self.assertIsNotNone(self.app.selected_unit)
        self.app.click(self.app.hero_rect(1).center)
        self.assertEqual(self.game.players[1].health, 15)

    def test_hero_health_is_drawn_over_drops_and_tracks_activated_king(self):
        self.player.health = 17
        self.game.players[1].health = 9
        self.assertEqual(self.app.hero_health_rect(0).center, (599, 662))
        self.assertEqual(self.app.hero_health_rect(1).center, (599, 266))
        with patch.object(self.app, "draw_hero_health", wraps=self.app.draw_hero_health) as health:
            self.app.draw()
        self.assertEqual([call.args for call in health.call_args_list], [(0, 17), (1, 9)])
        self.player.endgame_ready = True
        self.game.activate_king(0)
        self.game.damage(self.player.king, 3)
        with patch.object(self.app, "draw_hero_health", wraps=self.app.draw_hero_health) as health:
            self.app.draw()
        self.assertEqual([call.args for call in health.call_args_list], [(0, 14), (1, 9)])
        self.assertNotIn(self.player, [entity for entity, _ in self.app.entity_rects()])

    def test_invalid_card_shows_reason(self):
        self.player.mana = 0
        self.add_card("bispo")
        self.select_first_card()
        self.app.click(self.app.play_button.center)
        self.assertIn("Tempo insuficiente", self.game.messages[-1])

    def test_castle_button_requires_corner_rook_and_is_once_per_game(self):
        self.app.click(self.app.castle_button.center)
        self.assertIn("Torre aliada em um canto", self.game.messages[-1])
        self.game.summon(0, "torre", 5)
        self.add_card("peao")
        self.select_first_card()
        with patch.object(self.app, "button", wraps=self.app.button) as button:
            self.app.draw()
        castle = next(call for call in button.call_args_list if call.args[0] == self.app.castle_button)
        self.assertTrue(castle.args[2])
        self.app.click(self.app.castle_button.center)
        self.assertEqual((self.player.mana, self.player.armor), (8, 4))
        self.assertIsNone(self.app.selected_card)
        self.app.click(self.app.castle_button.center)
        self.assertIn("ja foi usado", self.game.messages[-1])
        self.assertEqual((self.player.mana, self.player.armor), (8, 4))

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

    def test_announced_mate_renders_and_wins_through_clicks(self):
        for card_id, slot in (("bispo", 0), ("peao", 1), ("peao", 2), ("bispo", 5)):
            self.game.summon(0, card_id, slot)
        self.game.end_turn(0)
        self.game.end_turn(1)
        self.player.mana = 10
        self.player.maneuvers_played = 2
        self.game.players[1].health = 10
        self.player.hand.clear()
        self.add_card("mate_boden")
        self.app.draw()
        self.select_first_card()
        self.app.click(self.app.play_button.center)
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 0)
        self.assertEqual(self.game.players[1].health, 10)
        self.app.update()
        self.assertEqual(self.app.state, State.GAME_OVER)
        self.app.draw()

    def test_single_piece_threats_render_and_back_rank_wins_by_click(self):
        rook = self.game.summon(0, "torre", 5)
        for _ in range(3):
            self.game.summon(1, "peao")
        self.game.end_turn(0)
        self.game.end_turn(1)
        self.player.mana = 10
        self.game.players[1].armor = 1
        self.player.hand.clear()
        self.add_card("mate_gaveta")
        self.app.draw()
        self.game.players[1].armor = 0
        self.game.players[1].health = 10
        self.game.attack(0, rook, self.game.players[1])
        self.select_first_card()
        self.app.draw()
        self.app.click(self.app.play_button.center)
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 0)
        self.app.update()
        self.assertEqual(self.app.state, State.GAME_OVER)


class DeckBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "decks.json"
        self.app = App(seed=42, decks_path=self.path)
        self.addCleanup(pygame.quit)
        self.app.click(self.app.builder_button.center)

    def name_deck(self, name):
        self.app.click(self.app.name_rect.center)
        self.app.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=name))
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))

    def test_builder_uses_new_piece_and_resource_labels(self):
        with patch.object(self.app, "text", wraps=self.app.text) as text:
            self.app.draw()
        rendered = [call.args[0] for call in text.call_args_list]
        self.assertIn("0 cartas modais | Peca ou Manobra", rendered)
        self.assertIn("Custo medio: 0.0 tempo", rendered)

    def test_build_save_reload_select_and_play(self):
        self.assertEqual(self.app.state, State.DECK_BUILDER)
        self.name_deck("Peoes")
        _, minus, plus = self.app.catalog_rows()[0]
        self.app.click(minus.center)
        self.assertEqual(self.app.draft["peao"], 0)
        for _ in range(13):
            self.app.click(plus.center)
        self.app.click(minus.center)
        self.app.draw()
        self.app.click(self.app.save_deck_button.center)
        self.assertEqual(self.app.saved_decks, {"Peoes": ["peao"] * 12})
        self.assertTrue(self.path.is_file())
        self.app.click(self.app.back_deck_button.center)
        self.app.draw()
        self.app.click(self.app.start_button.center)
        player = self.app.game.players[0]
        self.assertEqual(len(player.deck) + len(player.hand), 12)
        self.assertTrue(all(c.definition["id"] == "peao" for c in player.hand))
        reloaded = App(decks_path=self.path)
        self.assertEqual(reloaded.saved_decks, {"Peoes": ["peao"] * 12})
        reloaded.click(reloaded.deck_select_button.center)
        self.assertEqual(reloaded.active_deck, "Peoes")
        reloaded.start_game()
        self.assertEqual(len(reloaded.game.players[0].deck), 8)

    def test_edit_existing_and_save_another_name(self):
        self.name_deck("Primeiro")
        self.app.click(self.app.catalog_rows()[0][2].center)
        self.app.save_draft()
        self.app.click(self.app.new_deck_button.center)
        self.assertEqual(sum(self.app.draft.values()), 0)
        self.app.click(self.app.saved_rows()[0][1].center)
        self.assertEqual(self.app.draft_name, "Primeiro")
        self.app.click(self.app.catalog_rows()[1][2].center)
        self.app.save_draft()
        self.assertEqual(self.app.saved_decks["Primeiro"], ["peao", "cavalo"])
        self.app.draft_name = "Segundo"
        self.app.save_draft()
        self.assertEqual(len(self.app.deck_store.load()), 2)

    def test_invalid_empty_deck_and_save_failure_reported(self):
        self.app.save_draft()
        self.assertIn("Erro ao salvar", self.app.deck_message)
        self.assertFalse(self.path.exists())
        self.name_deck("Teste")
        self.app.click(self.app.catalog_rows()[0][2].center)
        with patch.object(self.app.deck_store, "save", side_effect=OSError("sem permissao")):
            self.app.save_draft()
        self.assertIn("sem permissao", self.app.deck_message)
        self.assertEqual(self.app.saved_decks, {})
        self.assertIsNone(self.app.active_deck)

    def test_corrupt_file_is_not_overwritten_and_can_be_reloaded(self):
        self.path.write_text("{", encoding="utf-8")
        self.app.open_builder()
        self.assertTrue(self.app.library_error)
        self.name_deck("Teste")
        self.app.click(self.app.catalog_rows()[0][2].center)
        self.app.save_draft()
        self.assertEqual(self.path.read_text(), "{")
        self.assertIn("Erro ao ler", self.app.deck_message)
        self.app.draw()
        self.path.write_text('{"Recuperado": ["peao"]}', encoding="utf-8")
        self.app.click(self.app.back_deck_button.center)
        self.app.click(self.app.builder_button.center)
        self.assertFalse(self.app.library_error)
        self.assertIn("Recuperado", self.app.saved_decks)

    def test_pagination_name_backspace_and_discard(self):
        self.app.click(self.app.catalog_next.center)
        self.assertEqual(self.app.catalog_page, 1)
        self.assertEqual(self.app.catalog_rows()[0][0]["id"], "sacrificio_da_dama")
        self.app.click(self.app.catalog_rows()[0][2].center)
        self.app.draw()
        self.app.click(self.app.catalog_prev.center)
        self.name_deck("A" * 50)
        self.assertEqual(len(self.app.draft_name), 40)
        self.app.click(self.app.name_rect.center)
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE))
        self.assertEqual(len(self.app.draft_name), 39)
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertEqual(self.app.state, State.MENU)
        self.app.click(self.app.builder_button.center)
        self.assertEqual(sum(self.app.draft.values()), 0)
        self.assertFalse(self.path.exists())

    def test_saved_deck_pagination_and_automatic_selection(self):
        self.app.saved_decks = {f"Deck {i}": ["peao"] for i in range(8)}
        self.app.click(self.app.saved_next.center)
        self.assertEqual(len(self.app.saved_rows()), 2)
        name, rect = self.app.saved_rows()[0]
        self.app.click(rect.center)
        self.assertEqual(self.app.active_deck, name)
        self.app.draw()
        self.app.click(self.app.saved_prev.center)
        self.assertEqual(len(self.app.saved_rows()), 6)
        self.app.active_deck = None
        self.app.state = State.MENU
        for _ in range(9):
            self.app.click(self.app.deck_select_button.center)
        self.assertIsNone(self.app.active_deck)

    def test_builder_rejects_multiple_legendary_qualities(self):
        self.app.inventory.award("mate_boden", "mate1", 2, 1, 1)
        self.app.inventory.award("mate_boden", "mate2", 0, 1, 1)
        self.app.refresh_collection()
        self.app.draft_name = "Lendarias"
        self.app.draft["mate_boden"] = 1
        self.app.draft["mate_boden__perfect"] = 1
        self.app.save_draft()
        self.assertIn("Apenas uma copia", self.app.deck_message)
        self.assertFalse(self.path.exists())


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "decks.json"
        self.app = App(decks_path=self.path)
        self.addCleanup(pygame.quit)
        self.app.click(self.app.collection_button.center)
        self.collection = self.app.collection

    def click(self, rect):
        self.app.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center,
        ))

    def search(self, query):
        self.click(self.collection.search_rect)
        self.app.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=query))

    def test_paginated_catalog_and_detail_selection(self):
        self.assertEqual(self.app.state, State.COLLECTION)
        first = self.collection.rows()
        self.assertEqual(len(first), 8)
        self.app.draw()
        self.click(self.collection.next)
        second = self.collection.rows()
        self.assertEqual(len(second), min(8, len(self.app.cards) - len(first)))
        self.click(second[0][1])
        self.assertIs(self.collection.selected, second[0][0])
        self.app.draw()
        all_rows = first + second
        while (self.collection.page + 1) * 8 < len(self.app.cards):
            self.click(self.collection.next)
            all_rows += self.collection.rows()
            self.app.draw()
        self.assertEqual(len({c["id"] for c, _ in all_rows}), len(self.app.cards))
        last_page = self.collection.page
        self.click(self.collection.next)
        self.assertEqual(self.collection.page, last_page)
        while self.collection.page:
            self.click(self.collection.previous)
        self.click(self.collection.previous)
        self.assertEqual(self.collection.page, 0)
        self.assertFalse(self.path.exists())

    def test_collection_uses_new_piece_and_resource_labels(self):
        self.collection.card_type = "peao"
        self.collection.refresh()
        with (
            patch.object(self.app, "text", wraps=self.app.text) as text,
            patch.object(self.app, "button", wraps=self.app.button) as button,
        ):
            self.app.draw()
        self.assertTrue(any(call.args[1] == "Peao" for call in button.call_args_list))
        self.assertTrue(any(call.args[1] == "Ordem: custo de tempo" for call in button.call_args_list))
        self.assertTrue(any(call.args[0].endswith(" tempo") for call in text.call_args_list))
        self.assertTrue(any("Custo nos dois modos:" in call.args[0] for call in text.call_args_list))
        for card in self.app.cards:
            self.assertNotRegex(card["description"].casefold(), r"\b(?:mana|lacaios?)\b")

    def test_collection_uses_maneuver_labels(self):
        self.collection.card_type = None
        self.collection.refresh()
        with (
            patch.object(self.app, "text", wraps=self.app.text) as text,
            patch.object(self.app, "button", wraps=self.app.button) as button,
        ):
            self.app.draw()
        self.assertTrue(any(call.args[1] == "Todas as pecas" for call in button.call_args_list))
        self.assertTrue(any("ou Manobra" in call.args[0] for call in text.call_args_list))
        self.assertTrue(all("manouvre_mode" in card for card in self.collection.filtered_cards()))

    def test_accent_insensitive_search_and_empty_results(self):
        self.search("peao")
        self.assertIn("peao", [c["id"] for c in self.collection.filtered_cards()])
        self.assertIn("peao_passado", [c["id"] for c in self.collection.filtered_cards()])
        self.app.draw()
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE))
        self.assertEqual(self.collection.query, "pea")
        self.search("inexistente")
        self.assertEqual(self.collection.rows(), [])
        self.assertIsNone(self.collection.selected)
        self.app.draw()
        self.click(self.collection.next)
        self.assertEqual(self.collection.page, 0)

    def test_keywords_type_filter_sort_and_reset_page(self):
        self.search("protecao")
        self.assertIn("torre", [c["id"] for c in self.collection.filtered_cards()])
        self.collection.card_type = "torre"
        self.collection.refresh()
        self.assertEqual([c["id"] for c in self.collection.filtered_cards()], ["torre"])
        self.collection.card_type = None
        self.collection.query = ""
        self.collection.refresh()
        self.click(self.collection.next)
        self.click(self.collection.type_button)
        self.assertEqual(self.collection.page, 0)
        self.assertTrue(all(c["piece_mode"]["piece_type"] == "peao" for c in self.collection.filtered_cards()))
        self.click(self.collection.type_button)
        self.assertTrue(all(c["piece_mode"]["piece_type"] == "cavalo" for c in self.collection.filtered_cards()))
        for _ in range(4):
            self.click(self.collection.type_button)
        self.assertEqual(len(self.collection.filtered_cards()), len(self.app.cards))
        self.click(self.collection.sort_button)
        self.assertTrue(self.collection.sort_by_name)
        self.assertEqual(self.collection.filtered_cards()[0]["id"], "bispo")
        self.app.draw()

    def test_back_escape_and_unmodified_game_and_deck(self):
        self.app.saved_decks = {"Teste": ["peao"]}
        self.app.active_deck = "Teste"
        self.app.draft["dama"] = 2
        self.click(self.collection.back_button)
        self.assertEqual(self.app.state, State.MENU)
        self.app.click(self.app.collection_button.center)
        self.search("dama")
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertEqual(self.app.state, State.MENU)
        self.assertFalse(self.collection.search_focused)
        self.assertEqual(self.app.saved_decks, {"Teste": ["peao"]})
        self.assertEqual(self.app.active_deck, "Teste")
        self.assertEqual(self.app.draft["dama"], 2)
        self.assertIsNone(self.app.game)

    def test_long_details_scroll_and_clamp(self):
        original = self.collection.selected
        self.collection.selected = dict(original, description="Descricao longa. " * 500)
        self.collection.detail_scroll = 9999
        self.app.draw()
        self.assertGreater(self.collection.detail_scroll, 0)
        self.assertLess(self.collection.detail_scroll, 9999)
        with patch("pygame.mouse.get_pos", return_value=self.collection.detail_rect.center):
            self.app.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=9999))
        self.assertEqual(self.collection.detail_scroll, 0)
        self.collection.selected = original
        self.app.draw()


if __name__ == "__main__":
    unittest.main()
