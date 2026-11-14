import os
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

    def test_targeted_spell_click(self):
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
        enemy = self.game.summon(1, "peao", 7)
        removed.effects = []
        removed.health = 0
        self.game.cleanup()
        self.add_card("cravada_absoluta")
        self.select_first_card()
        rectangles = dict(self.app.entity_rects())
        self.assertEqual(rectangles[enemy], self.app.slots(1)[7])
        self.app.draw()
        self.app.click(self.app.slots(1)[7].center)
        self.assertGreater(enemy.frozen_through, 0)
        self.assertEqual(enemy.slot, 7)

    def test_placement_highlights_only_vacant_physical_slots(self):
        self.game.summon(0, "peao", 2)
        self.game.summon(0, "peao", 7)
        self.add_card("dama")
        self.select_first_card()
        self.assertEqual([slot for slot, _ in self.app.placement_rects()], [0, 1, 3, 4, 5, 6])
        self.app.click(self.app.slots(0)[5].center)
        self.assertEqual(self.player.unit_at(5).card_id, "dama")
        self.app.draw()

    def test_deterministic_spell_preview_and_center_bonus_render(self):
        self.game.summon(0, "peao", 3)
        self.game.summon(1, "bispo", 6)
        self.game.summon(1, "peao", 7)
        self.game.end_turn(0)
        self.app.draw()
        self.game.end_turn(1)
        self.player.hand.clear()
        self.add_card("ataque_duplo")
        self.select_first_card()
        self.app.draw()
        self.assertEqual(self.player.temporary_mana, 1)
        self.app.click(self.app.play_button.center)
        self.assertEqual(self.game.players[1].unit_at(6).health, 2)
        self.assertIsNone(self.game.players[1].unit_at(7))

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

    def test_announced_mate_renders_and_wins_through_clicks(self):
        for card_id, slot in (("bispo", 0), ("peao", 1), ("peao", 2), ("bispo", 7)):
            self.game.summon(0, card_id, slot)
        self.game.end_turn(0)
        self.game.end_turn(1)
        self.player.mana = 10
        self.player.spells_played = 2
        self.player.hand.clear()
        self.add_card("mate_boden")
        self.app.draw()
        self.select_first_card()
        self.app.click(self.app.play_button.center)
        self.assertTrue(self.game.over)
        self.assertEqual(self.game.winner, 0)
        self.assertEqual(self.game.players[1].health, 30)
        self.app.update()
        self.assertEqual(self.app.state, State.GAME_OVER)
        self.app.draw()

    def test_single_piece_threats_render_and_back_rank_wins_by_click(self):
        rook = self.game.summon(0, "torre")
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
        self.assertEqual(self.app.catalog_rows()[0][0]["id"], "roque")
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
        self.search("provocar")
        self.assertIn("torre", [c["id"] for c in self.collection.filtered_cards()])
        self.click(self.collection.type_button)
        self.assertEqual([c["id"] for c in self.collection.filtered_cards()], ["torre"])
        self.collection.card_type = None
        self.collection.query = ""
        self.collection.refresh()
        self.click(self.collection.next)
        self.click(self.collection.type_button)
        self.assertEqual(self.collection.page, 0)
        self.assertTrue(all(c["type"] == "minion" for c in self.collection.filtered_cards()))
        self.click(self.collection.type_button)
        self.assertTrue(all(c["type"] == "spell" for c in self.collection.filtered_cards()))
        self.click(self.collection.type_button)
        self.assertEqual(len(self.collection.filtered_cards()), len(self.app.cards))
        self.click(self.collection.sort_button)
        self.assertTrue(self.collection.sort_by_name)
        self.assertEqual(self.collection.filtered_cards()[0]["id"], "ataque_duplo")
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
