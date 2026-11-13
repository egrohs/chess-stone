import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import chess

from crafting import CraftingInventory, STARTER_IDS, THEMES, grade, make_variant
from game_engine import Game, load_cards
from puzzles import Puzzle, PuzzleError, PuzzleSession, download_puzzle


def puzzle_response(theme="fork"):
    return {
        "puzzle": {
            "id": "test1", "rating": 1500, "themes": [theme],
            "fen": chess.STARTING_FEN, "solution": ["e2e4", "e7e5", "g1f3"],
        },
    }


class CraftingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "collection.json"
        self.cards = load_cards()
        self.inventory = CraftingInventory(self.cards, self.path)

    def test_quality_exact_thresholds(self):
        for errors, elapsed, moves, expected in (
            (0, 60, 1, "perfect"), (0, 60.01, 1, "improved"),
            (0, 120, 2, "perfect"), (1, 120, 1, "improved"),
            (1, 120.01, 1, "basic"), (2, 0, 1, "basic"),
            (0, 9999, 1, "basic"),
        ):
            with self.subTest(errors=errors, elapsed=elapsed, moves=moves):
                self.assertEqual(grade(errors, elapsed, moves), expected)

    def test_starters_free_tactics_locked_and_themes_complete(self):
        self.assertFalse(self.inventory.error)
        for card in self.cards:
            self.assertIn(card["id"], THEMES)
            self.assertEqual(self.inventory.count(card["id"]), None if card["id"] in STARTER_IDS else 0)
        self.inventory.validate_owned(["peao"] * 100)
        with self.assertRaises(ValueError):
            self.inventory.validate_owned(["roque"])

    def test_award_persist_and_duplicate_prevention(self):
        card = self.inventory.award("torre", "test1", 0, 25.0, 1)
        self.assertEqual(card["id"], "torre__perfect")
        self.assertEqual((card["attack"], card["health"]), (5, 7))
        self.assertEqual(card["effects"][-1]["action"], "draw")
        self.assertEqual(self.inventory.count(card["id"]), 1)
        self.inventory.validate_owned([card["id"], "peao"] * 1)
        with self.assertRaises(ValueError):
            self.inventory.validate_owned([card["id"]] * 2)
        reloaded = CraftingInventory(self.cards, self.path)
        self.assertEqual(reloaded.rewards, self.inventory.rewards)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.inventory.award("dama", "test1", 0, 1, 1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_basic_and_improved_rewards_have_separate_counts(self):
        self.inventory.award("roque", "one", 2, 5, 1)
        self.inventory.award("roque", "two", 1, 5, 1)
        self.inventory.award("roque", "three", 0, 5, 1)
        self.assertEqual(self.inventory.count("roque"), 1)
        self.assertEqual(self.inventory.count("roque__improved"), 1)
        self.assertEqual(self.inventory.count("roque__perfect"), 1)
        self.assertEqual(len(self.inventory.catalog()), len(self.cards) + 2)

    def test_all_variants_valid_and_originals_unchanged(self):
        originals = copy.deepcopy(self.cards)
        catalog = self.inventory.catalog(all_variants=True)
        self.assertEqual(len(catalog), 36)
        game = Game(catalog, deck_size=30, seed=3)
        self.assertTrue(all("__" not in card_id for player in game.players for card_id in player.deck))
        self.assertEqual(self.cards, originals)

    def test_variant_identity_preserves_filters_and_condition(self):
        self.inventory.award("dama", "queen", 0, 5, 1)
        self.inventory.award("bispo", "bishop", 1, 5, 1)
        game = Game(self.inventory.catalog(), seed=3)
        queen = game.summon(0, "dama__perfect")
        bishop = game.summon(0, "bispo__improved")
        game.summon(0, "bispo")
        self.assertEqual(queen.card_id, "dama")
        self.assertEqual(queen.definition_id, "dama__perfect")
        self.assertEqual(game.parser.resolve_targets(
            {"target": "target_ally_minion", "card_id": "dama"}, 0, preview=True,
        ), [queen])
        before = bishop.attack
        game.parser.execute(game.catalog["par_de_bispos"]["effects"], "on_play", 0)
        self.assertEqual(bishop.attack, before + 1)

    def test_improved_spell_extra_healing_and_perfect_draw(self):
        base = next(c for c in self.cards if c["id"] == "roque")
        self.assertEqual(make_variant(base, "improved")["effects"][-1]["amount"], 1)
        perfect = make_variant(base, "perfect")
        self.assertEqual(perfect["effects"][-2]["amount"], 2)
        self.assertEqual(perfect["effects"][-1]["action"], "draw")

    def test_corrupt_inventory_cannot_be_overwritten(self):
        self.path.write_text("{", encoding="utf-8")
        inventory = CraftingInventory(self.cards, self.path)
        self.assertIn("Erro ao ler colecao", inventory.error)
        with self.assertRaises(ValueError):
            inventory.award("roque", "test1", 0, 0, 1)
        self.assertEqual(self.path.read_text(), "{")

    def test_failed_write_does_not_grant_reward(self):
        with patch("crafting.write_json", side_effect=OSError("sem permissao")):
            with self.assertRaises(OSError):
                self.inventory.award("roque", "test1", 0, 0, 1)
        self.assertEqual(self.inventory.rewards, [])

    def test_invalid_records_are_rejected(self):
        self.inventory.award("roque", "good", 0, 1, 1)
        original = json.loads(self.path.read_text())
        for field, value in (("elapsed", float("nan")), ("elapsed", -1), ("errors", True),
                             ("base_id", "missing"), ("quality", "basic"), ("moves", 0)):
            data = copy.deepcopy(original)
            data["rewards"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.inventory.validate(data)


class PuzzleTests(unittest.TestCase):
    def test_fen_and_solution_validation(self):
        puzzle = Puzzle.from_response(puzzle_response(), "fork")
        self.assertEqual(puzzle.fen, chess.STARTING_FEN)
        self.assertEqual(len(puzzle.solution), 3)
        for field, value in (("themes", None), ("themes", ["pin"]), ("id", "../bad"),
                             ("solution", []), ("solution", ["e2e5"]),
                             ("solution", ["0000"]), ("fen", "bad"), ("rating", "x"),
                             ("solution", ["e2e4", "e7e5"])):
            response = puzzle_response()
            response["puzzle"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(PuzzleError):
                Puzzle.from_response(response, "fork")

    def test_pgn_fallback_applies_initial_opponent_move(self):
        response = puzzle_response()
        del response["puzzle"]["fen"]
        response["game"] = {"pgn": "1. e4 e5 2. Nf3 Nc6"}
        response["puzzle"].update(initialPly=1, solution=["g1f3", "b8c6", "f1b5"])
        puzzle = Puzzle.from_response(response, "fork")
        expected = chess.Board()
        expected.push_uci("e2e4")
        expected.push_uci("e7e5")
        self.assertEqual(puzzle.fen, expected.fen())
        response["puzzle"]["initialPly"] = 100
        with self.assertRaises(PuzzleError):
            Puzzle.from_response(response, "fork")

    def test_wrong_move_does_not_change_position_and_clock_freezes(self):
        puzzle = Puzzle.from_response(puzzle_response(), "fork")
        with patch("puzzles.time.monotonic", return_value=100):
            session = PuzzleSession(puzzle)
        with patch("puzzles.time.monotonic", return_value=150):
            self.assertFalse(session.play(chess.Move.from_uci("d2d4")))
            self.assertEqual(session.board.fen(), chess.STARTING_FEN)
            self.assertEqual(session.errors, 1)
            self.assertTrue(session.play(chess.Move.from_uci("e2e4")))
            self.assertEqual(session.index, 2)
            self.assertEqual(session.board.piece_at(chess.E5), chess.Piece(chess.PAWN, chess.BLACK))
            self.assertTrue(session.play(chess.Move.from_uci("g1f3")))
            self.assertTrue(session.done)
            self.assertEqual(session.quality, "improved")
        with patch("puzzles.time.monotonic", return_value=9999):
            self.assertEqual(session.elapsed, 50)
        with self.assertRaises(PuzzleError):
            session.play(chess.Move.from_uci("b1c3"))

    def test_real_lichess_fen_and_solution(self):
        response = {"puzzle": {
            "id": "9R7si", "rating": 1312, "themes": ["fork"],
            "fen": "1n2n1k1/pp3r1p/1qp2Pp1/3p2P1/1P4B1/P1N5/2P2P1P/4R1K1 w - - 0 1",
            "solution": ["e1e8", "f7f8", "g4e6", "g8h8", "e8f8"],
        }}
        session = PuzzleSession(Puzzle.from_response(response, "fork"))
        for move in ("e1e8", "g4e6", "e8f8"):
            self.assertTrue(session.play(chess.Move.from_uci(move)))
        self.assertTrue(session.done)
        self.assertTrue(session.board.is_checkmate())

    def test_castling_en_passant_and_promotion(self):
        for fen, solution in (
            ("4k3/8/8/8/8/8/8/4K2R w K - 0 1", ["e1g1"]),
            ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", ["e5d6"]),
            ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", ["a7a8n"]),
        ):
            response = puzzle_response()
            response["puzzle"].update(fen=fen, solution=solution)
            session = PuzzleSession(Puzzle.from_response(response, "fork"))
            self.assertTrue(session.play(chess.Move.from_uci(solution[0])))
            self.assertTrue(session.done)

    def test_download_request_and_errors(self):
        payload = json.dumps(puzzle_response()).encode()
        with patch("puzzles.urlopen") as mock:
            mock.return_value.__enter__.return_value.read.return_value = payload
            puzzle = download_puzzle("fork")
            self.assertEqual(puzzle.theme, "fork")
            request = mock.call_args.args[0]
            self.assertIn("angle=fork", request.full_url)
            self.assertEqual(mock.call_args.kwargs["timeout"], 15)
        for error in (
            HTTPError("https://lichess.org", 429, "rate", {}, None),
            HTTPError("https://lichess.org", 503, "down", {}, None),
            URLError("offline"), TimeoutError(),
        ):
            with patch("puzzles.urlopen", side_effect=error), self.assertRaises(PuzzleError):
                download_puzzle("fork")
        with patch("puzzles.urlopen") as mock:
            mock.return_value.__enter__.return_value.read.return_value = b"bad"
            with self.assertRaises(PuzzleError):
                download_puzzle("fork")
        with self.assertRaises(PuzzleError):
            download_puzzle("not-a-theme")


if __name__ == "__main__":
    unittest.main()
