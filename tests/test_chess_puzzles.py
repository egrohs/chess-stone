import dataclasses
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chess

from chess_puzzles import Puzzle, PuzzleError, PuzzleSession, download_puzzle


class ReusablePuzzleTests(unittest.TestCase):
    def test_result_is_only_available_after_completion_and_is_frozen(self):
        puzzle = Puzzle("result1", "fork", 1500, chess.STARTING_FEN, ("e2e4", "e7e5", "g1f3"))
        with patch("chess_puzzles.session.time.monotonic", return_value=100):
            session = PuzzleSession(puzzle)
        self.assertIsNone(session.result)
        with patch("chess_puzzles.session.time.monotonic", return_value=150):
            self.assertFalse(session.play(chess.Move.from_uci("d2d4")))
            self.assertTrue(session.play(chess.Move.from_uci("e2e4")))
            self.assertIsNone(session.result)
            self.assertTrue(session.play(chess.Move.from_uci("g1f3")))
        result = session.result
        self.assertEqual(
            (result.puzzle_id, result.theme, result.rating, result.errors,
             result.elapsed, result.player_moves, result.quality),
            ("result1", "fork", 1500, 1, 50, 2, "improved"),
        )
        with patch("chess_puzzles.session.time.monotonic", return_value=9999):
            self.assertIs(session.result, result)
            self.assertEqual(session.elapsed, 50)
            self.assertEqual(session.quality, "improved")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.errors = 0
        with self.assertRaises(PuzzleError):
            session.play(chess.Move.from_uci("b1c3"))

    def test_custom_grade_policy_does_not_change_metrics(self):
        puzzle = Puzzle("custom1", "anyTheme", 1200, chess.STARTING_FEN, ("e2e4",))
        with patch("chess_puzzles.session.time.monotonic", return_value=10):
            session = PuzzleSession(puzzle, grader=lambda errors, elapsed, moves: "gold" if errors == 0 else "silver")
        with patch("chess_puzzles.session.time.monotonic", return_value=25):
            self.assertTrue(session.play(chess.Move.from_uci("e2e4")))
        self.assertEqual(session.result.quality, "gold")
        self.assertEqual((session.result.errors, session.result.elapsed, session.result.player_moves), (0, 15, 1))

    def test_download_accepts_themes_outside_the_game_and_enforces_response_limit(self):
        payload = json.dumps({"puzzle": {
            "id": "test1", "rating": 1200, "themes": ["discoveredAttack"],
            "fen": chess.STARTING_FEN, "solution": ["e2e4"],
        }}).encode()
        with patch("chess_puzzles.lichess.urlopen") as mock:
            response = mock.return_value.__enter__.return_value
            response.read.return_value = payload
            puzzle = download_puzzle("discoveredAttack", user_agent="OtherGame/1.0")
            self.assertEqual(puzzle.theme, "discoveredAttack")
            self.assertEqual(mock.call_args.args[0].get_header("User-agent"), "OtherGame/1.0")
            response.read.return_value = b"x" * 1_000_001
            with self.assertRaisesRegex(PuzzleError, "excedeu"):
                download_puzzle("discoveredAttack")
        for theme in ("", "bad-theme", "../fork", "123", "á"):
            with self.subTest(theme=theme), self.assertRaises(PuzzleError):
                download_puzzle(theme)

    def test_package_works_without_game_files(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(__file__).resolve().parents[1] / "chess_puzzles"
            shutil.copytree(package, Path(directory) / "chess_puzzles", ignore=shutil.ignore_patterns("__pycache__"))
            script = (
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "import chess; from chess_puzzles import Puzzle, PuzzleSession; "
                "s = PuzzleSession(Puzzle('test1', 'fork', 1200, chess.STARTING_FEN, ('e2e4',))); "
                "assert s.play(chess.Move.from_uci('e2e4')); "
                "assert s.result.quality == 'perfect'"
            )
            subprocess.run([sys.executable, "-I", "-c", script, directory], check=True, cwd=directory)


if __name__ == "__main__":
    unittest.main()
