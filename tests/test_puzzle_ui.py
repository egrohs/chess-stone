import os
import tempfile
import unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import chess
import pygame

from crafting import CraftingInventory
from main import App, State
from chess_puzzles import Puzzle, PuzzleError


class PuzzleInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "decks.json"
        self.app = App(decks_path=self.path)
        self.addCleanup(pygame.quit)
        self.addCleanup(self.app.puzzle_view.close)
        self.view = self.app.puzzle_view
        self.future = Future()
        patcher = patch.object(self.view.executor, "submit", return_value=self.future)
        self.submit = patcher.start()
        self.addCleanup(patcher.stop)

    def open(self, card_id="ataque_duplo"):
        self.app.state = State.COLLECTION
        self.app.collection.selected = next(c for c in self.app.cards if c["id"] == card_id)
        self.app.click(self.app.collection.craft_button.center)

    def load(self, card_id="ataque_duplo", *, fen=chess.STARTING_FEN, solution=("e2e4", "e7e5", "g1f3")):
        self.open(card_id)
        from crafting import THEMES
        self.future.set_result(Puzzle("ui1", THEMES[card_id][0], 1500, fen, solution))
        self.app.update()
        self.assertIsNotNone(self.view.session)

    def move(self, uci):
        move = chess.Move.from_uci(uci)
        self.app.click(self.view.square_rect(move.from_square).center)
        self.app.click(self.view.square_rect(move.to_square).center)

    def test_async_load_board_solution_reward_deck_and_reload(self):
        self.open()
        self.assertEqual(self.app.state, State.PUZZLE)
        self.assertEqual(self.submit.call_args.args[1], "fork")
        self.app.draw()
        self.future.set_result(Puzzle("ui1", "fork", 1500, chess.STARTING_FEN, ("e2e4", "e7e5", "g1f3")))
        self.app.update()
        self.app.draw()
        self.move("e2e4")
        self.assertEqual(self.view.session.index, 2)
        self.move("g1f3")
        self.assertTrue(self.view.session.done)
        result = self.view.session.result
        self.assertIsNotNone(result)
        self.assertEqual(self.app.inventory.rewards, [])
        self.app.click(self.view.claim_button.center)
        self.assertTrue(self.view.saved)
        reward = self.app.inventory.rewards[0]
        self.assertEqual((reward["puzzle_id"], reward["errors"], reward["elapsed"], reward["moves"], reward["quality"]),
                         (result.puzzle_id, result.errors, result.elapsed, result.player_moves, result.quality))
        self.app.click(self.view.claim_button.center)
        self.assertEqual(len(self.app.inventory.rewards), 1)
        self.app.draw()
        self.app.click(self.view.back_button.center)
        self.assertEqual(self.app.state, State.COLLECTION)
        variant = "ataque_duplo__perfect"
        self.assertIn(variant, {c["id"] for c in self.app.cards})
        self.assertEqual(CraftingInventory(self.app.base_cards, self.path.with_name("collection.json")).count(variant), 1)
        self.app.open_builder()
        self.app.draft_name = "Craftado"
        self.app.draft[variant] = 1
        self.app.draft["peao"] = 10
        self.app.save_draft()
        self.assertEqual(self.app.active_deck, "Craftado")
        self.app.start_game()
        self.assertEqual(self.app.state, State.MATCH)
        player = self.app.game.players[0]
        self.assertIn(variant, player.deck + [c.definition["id"] for c in player.hand])
        self.app.draw()

    def test_error_and_retry_does_not_grant_card(self):
        self.open()
        self.future.set_exception(PuzzleError("offline"))
        self.app.update()
        self.assertIn("offline", self.view.message)
        self.assertIsNone(self.view.session)
        self.assertFalse(self.app.inventory.path.exists())
        self.app.draw()
        self.view.next_request = 0
        self.future = Future()
        self.submit.return_value = self.future
        self.app.click(self.view.retry_button.center)
        self.assertEqual(self.submit.call_count, 2)
        self.future.set_result(Puzzle("ui2", "fork", 1000, chess.STARTING_FEN, ("e2e4",)))
        self.app.update()
        self.assertEqual(self.view.session.puzzle.puzzle_id, "ui2")

    def test_rate_limit_and_pending_request_are_respected(self):
        self.open()
        self.view.request()
        self.assertEqual(self.submit.call_count, 1)
        self.future.set_exception(PuzzleError("Muitas requisicoes", retry_after=60))
        self.app.update()
        self.app.click(self.view.retry_button.center)
        self.assertIn("Aguarde", self.view.message)
        self.assertEqual(self.submit.call_count, 1)

    def test_retry_cannot_skip_unprocessed_rate_limit(self):
        self.open()
        self.future.set_exception(PuzzleError("Muitas requisicoes", retry_after=60))
        self.view.next_request = 0
        self.app.click(self.view.retry_button.center)
        self.assertIn("Aguarde", self.view.message)
        self.assertEqual(self.submit.call_count, 1)

    def test_abandon_during_download_does_not_update_collection(self):
        self.future.set_running_or_notify_cancel()
        self.open()
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertEqual(self.app.state, State.COLLECTION)
        self.future.set_result(Puzzle("ui1", "fork", 1000, chess.STARTING_FEN, ("e2e4",)))
        self.app.update()
        self.assertEqual(self.app.inventory.rewards, [])
        self.assertIsNone(self.view.session)

    def test_wrong_move_and_failed_save_are_visible_and_retryable(self):
        self.load()
        self.move("d2d4")
        self.assertEqual(self.view.session.errors, 1)
        self.assertIn("incorreto", self.view.message)
        self.move("e2e4")
        self.move("g1f3")
        with patch("crafting.write_json", side_effect=OSError("sem permissao")):
            self.app.click(self.view.claim_button.center)
        self.assertIn("sem permissao", self.view.message)
        self.assertFalse(self.view.saved)
        self.assertEqual(self.app.inventory.rewards, [])
        self.app.click(self.view.claim_button.center)
        self.assertTrue(self.view.saved)
        self.assertEqual(self.app.inventory.rewards[0]["quality"], "improved")

    def test_underpromotion_has_explicit_choice(self):
        self.load(fen="4k3/P7/8/8/8/8/8/4K3 w - - 0 1", solution=("a7a8n",))
        self.move("a7a8")
        self.assertEqual(len(self.view.promotions), 4)
        self.app.draw()
        move, rect = next((move, rect) for move, rect in self.view.promotion_buttons()
                          if move.promotion == chess.KNIGHT)
        self.app.click(rect.center)
        self.assertTrue(self.view.session.done)
        self.assertEqual(self.view.session.board.piece_at(chess.A8).piece_type, chess.KNIGHT)

    def test_black_orientation_and_castling(self):
        self.load(fen="4k2r/8/8/8/8/8/8/4K3 b k - 0 1", solution=("e8g8",))
        self.assertEqual(self.view.square_rect(chess.H8).topleft, (60, 720))
        self.move("e8g8")
        self.assertTrue(self.view.session.done)
        self.app.draw()

    def test_ownership_blocks_unearned_and_excess_copies(self):
        self.app.inventory.award("zugzwang", "ui1", 1, 10, 1)
        self.app.refresh_collection()
        self.app.open_builder()
        self.app.draft_name = "Invalido"
        self.app.draft["zugzwang"] = 1
        self.app.save_draft()
        self.assertIn("colecao possui 0", self.app.deck_message)
        self.assertFalse(self.path.exists())
        self.app.draft.clear()
        self.app.draft["zugzwang__improved"] = 2
        self.app.save_draft()
        self.assertIn("colecao possui 1", self.app.deck_message)
        self.app.saved_decks["Antigo"] = ["zugzwang"]
        self.app.active_deck = "Antigo"
        self.app.start_game()
        self.assertEqual(self.app.state, State.MENU)
        self.assertIn("colecao possui 0", self.app.deck_message)

    def test_duplicate_puzzle_cannot_be_farmed(self):
        self.app.inventory.award("peao", "ui1", 0, 10, 1)
        self.open()
        self.future.set_result(Puzzle("ui1", "fork", 1500, chess.STARTING_FEN, ("e2e4",)))
        self.app.update()
        self.assertIsNone(self.view.session)
        self.assertIn("ja recompensado", self.view.message)
        self.assertEqual(len(self.app.inventory.rewards), 1)

    def test_locked_card_cannot_be_added_and_starters_still_play(self):
        self.app.open_builder()
        self.app.catalog_page = 0
        _, _, plus = next(row for row in self.app.catalog_rows() if row[0]["id"] == "zugzwang")
        self.app.click(plus.center)
        self.assertEqual(self.app.draft["zugzwang"], 0)
        self.assertIn("Sem copias", self.app.deck_message)
        self.app.active_deck = None
        self.app.start_game()
        self.assertEqual(self.app.state, State.MATCH)
        self.assertTrue(all("piece_mode" in c.definition and "manouvre_mode" in c.definition
                            for c in self.app.game.players[0].hand))
        self.assertFalse(self.app.inventory.path.exists())


if __name__ == "__main__":
    unittest.main()
