"""Compatibility imports; new integrations should import from chess_puzzles."""

from chess_puzzles import Puzzle, PuzzleError, PuzzleResult, PuzzleSession, download_puzzle, grade

__all__ = ["Puzzle", "PuzzleError", "PuzzleResult", "PuzzleSession", "download_puzzle", "grade"]
