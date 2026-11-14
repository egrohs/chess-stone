"""Chess puzzle sessions and their independent performance results."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import chess

from .lichess import Puzzle, PuzzleError


def grade(errors: int, elapsed: float, moves: int) -> str:
    if errors == 0 and elapsed <= moves * 60:
        return "perfect"
    if errors <= 1 and elapsed <= moves * 120:
        return "improved"
    return "basic"


@dataclass(frozen=True)
class PuzzleResult:
    puzzle_id: str
    theme: str
    rating: int
    errors: int
    elapsed: float
    player_moves: int
    quality: str


class PuzzleSession:
    def __init__(
        self, puzzle: Puzzle, *, grader: Callable[[int, float, int], str] = grade,
    ):
        self.puzzle = puzzle
        self.board = chess.Board(puzzle.fen)
        self.player_color = self.board.turn
        self.index = 0
        self.errors = 0
        self.started_at = time.monotonic()
        self.finished_elapsed: float | None = None
        self._grader = grader
        self._result: PuzzleResult | None = None

    @property
    def done(self) -> bool:
        return self.index == len(self.puzzle.solution)

    @property
    def elapsed(self) -> float:
        return self.finished_elapsed if self.finished_elapsed is not None else time.monotonic() - self.started_at

    @property
    def player_moves(self) -> int:
        return (len(self.puzzle.solution) + 1) // 2

    @property
    def quality(self) -> str:
        if self._result is not None:
            return self._result.quality
        return self._grader(self.errors, self.elapsed, self.player_moves)

    @property
    def result(self) -> PuzzleResult | None:
        return self._result

    def play(self, move: chess.Move) -> bool:
        if self.done:
            raise PuzzleError("Puzzle ja concluido.")
        if move not in self.board.legal_moves or move.uci() != self.puzzle.solution[self.index]:
            self.errors += 1
            return False
        self.board.push(move)
        self.index += 1
        if not self.done:
            self.board.push_uci(self.puzzle.solution[self.index])
            self.index += 1
        if self.done:
            self.finished_elapsed = time.monotonic() - self.started_at
            self._result = PuzzleResult(
                self.puzzle.puzzle_id, self.puzzle.theme, self.puzzle.rating,
                self.errors, self.finished_elapsed, self.player_moves,
                self._grader(self.errors, self.finished_elapsed, self.player_moves),
            )
        return True
