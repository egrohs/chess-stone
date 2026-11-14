"""Download and validate puzzles from Lichess."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import chess
import chess.pgn

class PuzzleError(ValueError):
    def __init__(self, message: str, *, retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class Puzzle:
    puzzle_id: str
    theme: str
    rating: int
    fen: str
    solution: tuple[str, ...]

    @classmethod
    def from_response(cls, data: object, theme: str) -> Puzzle:
        if not isinstance(data, dict) or not isinstance(data.get("puzzle"), dict):
            raise PuzzleError("Resposta Lichess sem puzzle.")
        puzzle = data["puzzle"]
        if not isinstance(puzzle.get("themes"), list) or theme not in puzzle["themes"]:
            raise PuzzleError("O puzzle recebido nao corresponde ao tema solicitado.")
        puzzle_id = puzzle.get("id")
        solution = puzzle.get("solution")
        if (
            not isinstance(puzzle_id, str) or not puzzle_id.isalnum()
            or not isinstance(solution, list) or not solution
            or any(not isinstance(move, str) for move in solution)
            or type(puzzle.get("rating")) is not int
            or len(solution) % 2 == 0
        ):
            raise PuzzleError("Dados do puzzle invalidos.")
        try:
            fen = puzzle.get("fen")
            if fen is not None:
                if not isinstance(fen, str):
                    raise ValueError("FEN deve ser texto.")
                board = chess.Board(fen)
            else:
                game_data = data.get("game")
                if not isinstance(game_data, dict) or not isinstance(game_data.get("pgn"), str):
                    raise ValueError("PGN ausente.")
                game = chess.pgn.read_game(io.StringIO(game_data["pgn"]))
                ply = puzzle.get("initialPly")
                if game is None or game.errors or type(ply) is not int or ply < 0:
                    raise ValueError("PGN ou initialPly invalido.")
                board = game.board()
                moves = list(game.mainline_moves())
                # Lichess initialPly is the index of the last, opponent move.
                if ply >= len(moves):
                    raise ValueError("initialPly fora do PGN.")
                for move in moves[:ply + 1]:
                    board.push(move)
            if not board.is_valid():
                raise ValueError("Posicao de xadrez invalida.")
            initial_fen = board.fen()
            for uci in solution:
                move = chess.Move.from_uci(uci)
                if not move or move not in board.legal_moves:
                    raise ValueError(f"Lance ilegal na solucao: {uci}")
                board.push(move)
        except ValueError as error:
            raise PuzzleError(f"Puzzle Lichess invalido: {error}") from error
        return cls(puzzle_id, theme, puzzle["rating"], initial_fen, tuple(solution))


def download_puzzle(theme: str, *, user_agent: str = "ChessPuzzleTrainer/1.0") -> Puzzle:
    if (
        not isinstance(theme, str) or not theme or not theme.isascii()
        or not theme.isalnum() or not theme[0].isalpha()
    ):
        raise PuzzleError("Tema invalido.")
    url = "https://lichess.org/api/puzzle/next?" + urlencode({"angle": theme})
    request = Request(url, headers={"Accept": "application/json", "User-Agent": user_agent})
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read(1_000_001)
    except HTTPError as error:
        error.close()
        if error.code == 429:
            raise PuzzleError(
                "Limite Lichess atingido. Aguarde ao menos 60 segundos antes de tentar.",
                retry_after=60,
            ) from error
        raise PuzzleError(f"Lichess retornou HTTP {error.code}. Tente novamente mais tarde.") from error
    except (URLError, TimeoutError, OSError) as error:
        raise PuzzleError(f"Nao foi possivel acessar o Lichess: {error}") from error
    if len(raw) > 1_000_000:
        raise PuzzleError("Resposta Lichess excedeu o tamanho permitido.")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise PuzzleError("Lichess retornou JSON invalido.") from error
    return Puzzle.from_response(data, theme)
