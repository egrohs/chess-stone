"""Mouse-operated chess board and non-blocking Lichess crafting screen."""

from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING

import chess
import pygame

from chess_puzzles import Puzzle, PuzzleError, PuzzleSession, download_puzzle
from crafting import QUALITY_LABELS, THEMES, CraftingInventory
from ui_theme import BLUE, GOLD, GREEN, MUTED, PANEL, RED, WHITE

if TYPE_CHECKING:
    from main import App


class PuzzleView:
    def __init__(self, inventory: CraftingInventory):
        self.inventory = inventory
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lichess")
        self.pending: Future[Puzzle] | None = None
        self.base_id = ""
        self.session: PuzzleSession | None = None
        self.message = ""
        self.saved = False
        self.selected_square: chess.Square | None = None
        self.promotions: list[chess.Move] = []
        self.next_request = 0.0
        self.active = False
        self.board_rect = pygame.Rect(60, 160, 640, 640)
        self.back_button = pygame.Rect(900, 805, 450, 55)
        self.retry_button = pygame.Rect(900, 730, 450, 55)
        self.claim_button = pygame.Rect(900, 655, 450, 55)
        self.piece_font = pygame.font.SysFont("segoeuisymbol,dejavusans", 60)

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    def open(self, base_id: str) -> None:
        self.active = True
        self.update()
        self.base_id = base_id
        self.session = None
        self.saved = False
        self.selected_square = None
        self.promotions = []
        self.request()

    def leave(self) -> None:
        self.active = False
        if self.pending is not None:
            self.pending.cancel()

    def request(self) -> None:
        if self.pending is not None and self.pending.done():
            self.update()
            if self.session is not None:
                return
        if self.pending is not None and not self.pending.done():
            self.message = "Aguarde a requisicao anterior terminar e tente novamente."
            return
        if self.inventory.error:
            self.message = self.inventory.error
            return
        if self.base_id not in THEMES:
            self.message = "Carta sem tema de crafting configurado."
            return
        remaining = self.next_request - time.monotonic()
        if remaining > 0:
            self.message = f"Aguarde {int(remaining) + 1}s antes de baixar outro puzzle."
            return
        self.message = "Baixando puzzle do Lichess..."
        self.next_request = time.monotonic() + 3
        self.pending = self.executor.submit(
            download_puzzle, THEMES[self.base_id][0], user_agent="ChessStonePrototype/1.0",
        )

    def update(self) -> None:
        if self.pending is None or not self.pending.done() or not self.active:
            return
        future, self.pending = self.pending, None
        if future.cancelled():
            return
        try:
            puzzle = future.result()
        except PuzzleError as error:
            self.message = str(error)
            if error.retry_after:
                self.next_request = time.monotonic() + error.retry_after
            return
        if puzzle.theme != THEMES[self.base_id][0]:
            self.message = "Requisicao anterior concluida. Clique em Tentar novamente para o tema atual."
            return
        if puzzle.puzzle_id in self.inventory.completed:
            self.message = "Puzzle ja recompensado. Aguarde e tente baixar outro."
            return
        self.session = PuzzleSession(puzzle)
        self.message = "Encontre a sequencia correta. Clique na peca e depois no destino."

    def square_rect(self, square: chess.Square) -> pygame.Rect:
        white = self.session is None or self.session.player_color == chess.WHITE
        file, rank = chess.square_file(square), chess.square_rank(square)
        column, row = (file, 7 - rank) if white else (7 - file, rank)
        return pygame.Rect(self.board_rect.x + column * 80, self.board_rect.y + row * 80, 80, 80)

    def promotion_buttons(self) -> list[tuple[chess.Move, pygame.Rect]]:
        return [(move, pygame.Rect(800 + i * 140, 540, 125, 50)) for i, move in enumerate(self.promotions)]

    def play(self, move: chess.Move) -> None:
        if self.session is None:
            return
        correct = self.session.play(move)
        self.selected_square = None
        self.promotions = []
        self.message = (
            "Puzzle concluido! Clique em Receber carta para salvar."
            if self.session.done else "Correto. O adversario respondeu; encontre seu proximo lance."
            if correct else "Lance incorreto (+1 erro). A posicao foi mantida; tente novamente."
        )

    def click(self, point: tuple[int, int]) -> bool:
        if self.back_button.collidepoint(point):
            self.leave()
            return True
        if self.session is None:
            if self.retry_button.collidepoint(point):
                self.request()
            return False
        session = self.session
        if self.claim_button.collidepoint(point) and session.done and not self.saved:
            result = session.result
            if result is None:
                raise RuntimeError("Puzzle concluido sem resultado.")
            try:
                card = self.inventory.award(
                    self.base_id, result.puzzle_id, result.errors,
                    result.elapsed, result.player_moves,
                )
            except (OSError, ValueError) as error:
                self.message = f"Erro ao salvar recompensa: {error}. Tente receber novamente."
                return False
            self.saved = True
            self.message = f"Recebida: {card['name']}! A carta ja pode ser usada nos decks."
            return False
        if session.done:
            return False
        if self.promotions:
            for move, rect in self.promotion_buttons():
                if rect.collidepoint(point):
                    self.play(move)
            return False
        for square in chess.SQUARES:
            if not self.square_rect(square).collidepoint(point):
                continue
            piece = session.board.piece_at(square)
            if piece and piece.color == session.player_color:
                self.selected_square = None if self.selected_square == square else square
                return False
            if self.selected_square is not None:
                candidates = [
                    move for move in session.board.legal_moves
                    if move.from_square == self.selected_square and move.to_square == square
                ]
                if len(candidates) > 1:
                    self.promotions = candidates
                else:
                    self.play(candidates[0] if candidates else chess.Move(self.selected_square, square))
            return False
        return False

    def draw(self, app: App) -> None:
        app.text("CRAFTING - PUZZLE DE XADREZ", (60, 35), GOLD, app.large)
        card = self.inventory.base_catalog[self.base_id]
        app.text(card["name"], (800, 115), GOLD, app.large)
        app.paragraph(f"Tema: {THEMES[self.base_id][1]}", pygame.Rect(800, 165, 550, 70), font=app.font)
        session = self.session
        if session:
            legal_squares = {
                move.to_square for move in session.board.legal_moves
                if move.from_square == self.selected_square
            } if self.selected_square is not None else set()
            for square in chess.SQUARES:
                rect = self.square_rect(square)
                light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
                pygame.draw.rect(app.screen, (224, 212, 184) if light else (104, 132, 105), rect)
                if square == self.selected_square:
                    pygame.draw.rect(app.screen, GOLD, rect, 5)
                elif square in legal_squares:
                    pygame.draw.circle(app.screen, (50, 95, 78), rect.center, 10)
                piece = session.board.piece_at(square)
                if piece:
                    # Outline white pieces so they remain legible on light squares.
                    symbol = piece.unicode_symbol(invert_color=piece.color == chess.WHITE)
                    if piece.color == chess.WHITE:
                        outline = self.piece_font.render(symbol, True, (35, 40, 35))
                        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            app.screen.blit(outline, outline.get_rect(center=(rect.centerx + dx, rect.centery + dy)))
                    glyph = self.piece_font.render(
                        symbol, True, WHITE if piece.color else (20, 24, 29),
                    )
                    app.screen.blit(glyph, glyph.get_rect(center=rect.center))
                app.text(chess.square_name(square), (rect.x + 3, rect.y + 2), (35, 40, 35), app.small)
            side = "brancas" if session.player_color else "pretas"
            app.text(f"Voce joga com as {side}", (60, 825), WHITE, app.large)
            app.text(f"lichess.org/training/{session.puzzle.puzzle_id}", (60, 880), BLUE)
            app.text(f"Rating: {session.puzzle.rating} | Erros: {session.errors}", (800, 250))
            app.text(f"Tempo: {int(session.elapsed)}s | Qualidade: {QUALITY_LABELS[session.quality]}", (800, 290), GREEN)
            if session.board.is_check() and not session.done:
                app.text("Seu Rei esta em xeque.", (800, 330), RED)
            app.button(self.claim_button, "Receber carta" if not self.saved else "Carta salva", session.done and not self.saved)
        else:
            pygame.draw.rect(app.screen, PANEL, self.board_rect)
            app.paragraph("O tabuleiro aparece quando o download terminar.", pygame.Rect(110, 420, 540, 80), MUTED, font=app.font)
            app.button(self.retry_button, "Tentar novamente", self.pending is None or self.pending.done())
        app.paragraph(self.message, pygame.Rect(800, 370, 550, 135), GREEN if self.saved else WHITE, font=app.font)
        if self.promotions:
            app.text("Escolha a promocao:", (800, 510), GOLD)
            labels = {chess.QUEEN: "Dama", chess.ROOK: "Torre", chess.BISHOP: "Bispo", chess.KNIGHT: "Cavalo"}
            for move, rect in self.promotion_buttons():
                app.button(rect, labels[move.promotion])
        app.paragraph(
            "Perfeita: sem erros e ate 60s por lance seu. Aprimorada: ate 1 erro e"
            " 120s por lance seu. Demais: basica. Sem prazo para terminar."
            " Abandonar nao concede carta. Cada puzzle recompensa uma unica vez.",
            pygame.Rect(800, 870, 580, 65), MUTED,
        )
        app.button(self.back_button, "Voltar a colecao")
