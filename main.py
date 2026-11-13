"""Minimal pygame-ce client. All decisions are checked by game_engine."""

from __future__ import annotations

import argparse
import os
from enum import Enum, auto

import pygame

from game_engine import BOARD_LIMIT, KEYWORD_LABELS, Card, Entity, Game, RuleError, Unit, load_cards


WIDTH, HEIGHT = 1440, 940
BG = (22, 27, 35)
PANEL = (34, 41, 52)
WHITE = (235, 239, 245)
MUTED = (165, 176, 191)
GREEN = (100, 220, 155)
GOLD = (249, 203, 90)
RED = (228, 107, 112)
BLUE = (107, 170, 239)
SLOT_WIDTH, SLOT_HEIGHT, SLOT_STEP = 118, 150, 130
SIDEBAR = 1100


class State(Enum):
    MENU = auto()
    MATCH = auto()
    GAME_OVER = auto()


class App:
    def __init__(self, *, deck_size: int = 30, seed: int | None = None):
        pygame.init()
        pygame.display.set_caption("Chess Stone - prototipo")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui", 18)
        self.small = pygame.font.SysFont("segoeui", 15)
        self.large = pygame.font.SysFont("segoeui", 30, bold=True)
        self.cards = load_cards()
        self.deck_size = deck_size
        self.seed = seed
        self.state = State.MENU
        self.game: Game | None = None
        self.selected_card: Card | None = None
        self.selected_unit: Unit | None = None
        self.position: int | None = None
        self.running = True
        self.ai_at = 0
        self.start_button = pygame.Rect(540, 440, 360, 65)
        self.quit_button = pygame.Rect(540, 530, 360, 60)
        self.end_button = pygame.Rect(1120, 100, 296, 52)
        self.king_button = pygame.Rect(1120, 164, 296, 52)
        self.play_button = pygame.Rect(1120, 228, 296, 52)
        self.menu_button = pygame.Rect(1120, 868, 296, 48)

    def start_game(self) -> None:
        self.game = Game(self.cards, deck_size=self.deck_size, seed=self.seed)
        self.state = State.MATCH
        self.clear_selection()
        self.ai_at = pygame.time.get_ticks() + 450

    def clear_selection(self) -> None:
        self.selected_card = None
        self.selected_unit = None
        self.position = None

    def slots(self, owner: int) -> list[pygame.Rect]:
        return [
            pygame.Rect(24 + i * SLOT_STEP, 405 if owner == 0 else 178, SLOT_WIDTH, SLOT_HEIGHT)
            for i in range(BOARD_LIMIT)
        ]

    def hero_rect(self, owner: int) -> pygame.Rect:
        return pygame.Rect(402, 590 if owner == 0 else 70, 300, 70)

    def hand_rects(self) -> list[tuple[Card, pygame.Rect]]:
        if not self.game:
            return []
        return [
            (card, pygame.Rect(24 + i * 105, 718, 99, 196))
            for i, card in enumerate(self.game.players[0].hand)
        ]

    def entity_rects(self) -> list[tuple[Entity, pygame.Rect]]:
        if not self.game:
            return []
        result: list[tuple[Entity, pygame.Rect]] = []
        for owner, player in enumerate(self.game.players):
            result.extend(zip(player.board, self.slots(owner)))
            if not player.king:
                result.append((player, self.hero_rect(owner)))
        return result

    def valid_targets(self) -> list[Entity]:
        if not self.game or self.game.current != 0 or self.game.over:
            return []
        if self.selected_card and self.game.playable(0, self.selected_card):
            if self.selected_card.definition["type"] == "minion" and self.position is None:
                return []
            return self.game.valid_card_targets(0, self.selected_card)
        if self.selected_unit:
            return self.game.attack_targets(self.selected_unit)
        return []

    def choosing_position(self) -> bool:
        return bool(
            self.game and self.selected_card
            and self.selected_card.definition["type"] == "minion"
            and self.position is None and self.game.playable(0, self.selected_card)
        )

    def placement_rects(self) -> list[tuple[int, pygame.Rect]]:
        if not self.game or not self.choosing_position():
            return []
        count = len(self.game.players[0].board)
        # Thin insertion bars support adjacency effects without moving occupied slots.
        bars = [
            (i, pygame.Rect(16 + i * SLOT_STEP, 399, 8, 162))
            for i in range(count + 1)
        ]
        empty = [(count, rect) for rect in self.slots(0)[count:]]
        return bars + empty

    def commit_card(self, target: Entity | None = None) -> None:
        if self.game and self.selected_card:
            self.game.play_card(0, self.selected_card, target, self.position)
            self.clear_selection()

    def click(self, point: tuple[int, int]) -> None:
        if self.state == State.MENU:
            if self.start_button.collidepoint(point):
                self.start_game()
            elif self.quit_button.collidepoint(point):
                self.running = False
            return
        if self.state == State.GAME_OVER:
            if self.start_button.collidepoint(point):
                self.start_game()
            elif self.quit_button.collidepoint(point):
                self.state = State.MENU
            return
        game = self.game
        if game is None:
            return
        if self.menu_button.collidepoint(point):
            self.state = State.MENU
            self.clear_selection()
            return
        if game.current != 0 or game.over:
            return
        try:
            if self.end_button.collidepoint(point):
                game.end_turn(0)
                self.clear_selection()
                self.ai_at = pygame.time.get_ticks() + 450
                return
            if self.king_button.collidepoint(point):
                game.activate_king(0, manual=True)
                self.clear_selection()
                return
            if self.play_button.collidepoint(point) and self.selected_card:
                if self.selected_card.definition["type"] == "minion" and self.position is None:
                    raise RuleError("Escolha um espaco verde na sua mesa.")
                self.commit_card()
                return
            for card, rect in self.hand_rects():
                if rect.collidepoint(point):
                    if card is self.selected_card:
                        self.clear_selection()
                    else:
                        self.clear_selection()
                        self.selected_card = card
                        if not game.playable(0, card):
                            game.log("Carta indisponivel: verifique mana, espacos e alvos.")
                    return
            for position, rect in self.placement_rects():
                if rect.collidepoint(point):
                    self.position = position
                    if self.selected_card and not game.manual_effects(self.selected_card):
                        self.commit_card()
                    return
            for entity, rect in self.entity_rects():
                if not rect.collidepoint(point):
                    continue
                if entity in self.valid_targets():
                    if self.selected_card:
                        self.commit_card(entity)
                    elif self.selected_unit:
                        game.attack(0, self.selected_unit, entity)
                        self.clear_selection()
                    return
                if self.selected_card:
                    raise RuleError("Alvo invalido. Use os destaques verdes.")
                if isinstance(entity, Unit) and entity.owner == 0:
                    self.clear_selection()
                    if not game.attack_targets(entity):
                        raise RuleError("Unidade nao pode atacar agora.")
                    self.selected_unit = entity
                    return
            self.clear_selection()
        except RuleError as error:
            game.log(str(error))

    def text(
        self, text: str, position: tuple[int, int], color: tuple = WHITE,
        font: pygame.font.Font | None = None,
    ) -> None:
        self.screen.blit((font or self.font).render(text, True, color), position)

    def wrap(self, text: str, width: int, font: pygame.font.Font | None = None) -> list[str]:
        font = font or self.small
        lines: list[str] = []
        line = ""
        for word in text.split():
            candidate = f"{line} {word}".strip()
            if line and font.size(candidate)[0] > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        return lines

    def paragraph(
        self, text: str, rect: pygame.Rect, color: tuple = WHITE,
        *, font: pygame.font.Font | None = None, limit: int | None = None,
    ) -> None:
        font = font or self.small
        lines = self.wrap(text, rect.width, font)
        capacity = max(0, rect.height // font.get_linesize())
        capacity = min(capacity, limit) if limit is not None else capacity
        for index, line in enumerate(lines[:capacity]):
            if index == capacity - 1 and len(lines) > capacity:
                while line and font.size(line + "...")[0] > rect.width:
                    line = line[:-1]
                line += "..."
            self.text(line, (rect.x, rect.y + index * font.get_linesize()), color, font)

    def button(self, rect: pygame.Rect, label: str, enabled: bool = True) -> None:
        pygame.draw.rect(self.screen, (48, 77, 84) if enabled else PANEL, rect, border_radius=6)
        pygame.draw.rect(self.screen, GREEN if enabled else MUTED, rect, 2, border_radius=6)
        image = self.font.render(label, True, WHITE if enabled else MUTED)
        self.screen.blit(image, image.get_rect(center=rect.center))

    def draw_unit(self, unit: Unit, rect: pygame.Rect, targets: list[Entity]) -> None:
        game = self.game
        color = (42, 67, 83) if unit.owner == 0 else (79, 48, 58)
        if unit.is_king:
            color = (88, 75, 38)
        pygame.draw.rect(self.screen, color, rect, border_radius=5)
        border = MUTED
        if game and game.attack_targets(unit):
            border = BLUE
        if "taunt" in unit.keywords:
            border = RED
        if unit in targets:
            border = GREEN
        if unit is self.selected_unit:
            border = GOLD
        pygame.draw.rect(self.screen, border, rect, 3, border_radius=5)
        self.paragraph(unit.name, pygame.Rect(rect.x + 7, rect.y + 7, rect.width - 14, 43), font=self.font)
        labels = [KEYWORD_LABELS[k] for k in sorted(unit.keywords)]
        if game and game.players[unit.owner].turns_started <= unit.frozen_through:
            labels.append("Congelado")
        self.paragraph(" / ".join(labels), pygame.Rect(rect.x + 7, rect.y + 54, rect.width - 14, 61), GOLD)
        self.text(f"{unit.attack} / {unit.health}", (rect.x + 9, rect.bottom - 34), WHITE, self.large)

    def draw_match(self) -> None:
        game = self.game
        if game is None:
            return
        targets = self.valid_targets()
        self.text("CHESS STONE", (24, 18), GOLD, self.large)
        self.text(
            f"Rodada {(game.turn_number + 1) // 2} | Turno {game.turn_number}"
            f" | {'Sua vez' if game.current == 0 else 'IA jogando...'}",
            (24, 349), WHITE, self.large,
        )
        for owner, player in enumerate(game.players):
            for index, rect in enumerate(self.slots(owner)):
                pygame.draw.rect(self.screen, PANEL, rect, border_radius=5)
                pygame.draw.rect(self.screen, (65, 73, 87), rect, 1, border_radius=5)
                self.text(str(index + 1), (rect.x + 8, rect.y + 7), MUTED, self.small)
                if index < len(player.board):
                    self.draw_unit(player.board[index], rect, targets)
            hero = self.hero_rect(owner)
            if player.king:
                self.text(
                    f"Rei na mesa | Vida compartilhada: {player.health}",
                    (hero.x, hero.y + 10), GOLD,
                )
            else:
                pygame.draw.rect(self.screen, PANEL, hero, border_radius=6)
                pygame.draw.rect(self.screen, GREEN if player in targets else MUTED, hero, 3, border_radius=6)
                self.text(f"Rei - {player.name}", (hero.x + 12, hero.y + 6))
                self.text(f"Vida: {player.health} / 30", (hero.x + 12, hero.y + 35), GOLD)
            y = 90 if owner == 1 else 603
            self.text(f"Mana: {player.mana}/{player.max_mana}", (24, y), BLUE)
            self.text(
                f"Deck: {len(player.deck)} | Mao: {len(player.hand)}/10 | Mesa: {len(player.board)}/8",
                (24, y + 28), MUTED, self.small,
            )
        for _, rect in self.placement_rects():
            pygame.draw.rect(self.screen, GREEN, rect, 2)
        hint = "Selecione carta ou unidade. Verde = alvo/espaco valido; azul = pronto; vermelho = Provocar."
        if self.selected_card:
            hint = (
                "Escolha um espaco verde (barras inserem entre aliados)."
                if self.choosing_position()
                else "Escolha um alvo verde ou use Jogar carta para efeitos sem alvo."
            )
        elif self.selected_unit:
            hint = "Escolha um inimigo verde para atacar."
        self.text(hint, (24, 674), GREEN if self.selected_card or self.selected_unit else MUTED, self.small)
        self.text("Clique direito / ESC: cancelar selecao", (24, 696), MUTED, self.small)
        for card, rect in self.hand_rects():
            definition = card.definition
            playable = game.playable(0, card)
            pygame.draw.rect(
                self.screen, (43, 61, 77) if definition["type"] == "minion" else (66, 49, 80),
                rect, border_radius=5,
            )
            border = GOLD if card is self.selected_card else GREEN if playable else MUTED
            pygame.draw.rect(self.screen, border, rect, 3 if card is self.selected_card else 1, border_radius=5)
            self.text(str(definition["cost"]), (rect.x + 8, rect.y + 5), BLUE, self.large)
            self.paragraph(card.name, pygame.Rect(rect.x + 7, rect.y + 46, 85, 49), font=self.small)
            self.paragraph(
                definition["description"], pygame.Rect(rect.x + 7, rect.y + 98, 85, 62),
                WHITE if playable else MUTED,
            )
            footer = (
                f"{definition['attack']} / {definition['health']}"
                if definition["type"] == "minion" else "FEITICO"
            )
            self.text(footer, (rect.x + 8, rect.bottom - 28), WHITE, self.small)
        self.draw_sidebar()

    def draw_sidebar(self) -> None:
        game = self.game
        if game is None:
            return
        pygame.draw.rect(self.screen, PANEL, (SIDEBAR, 0, WIDTH - SIDEBAR, HEIGHT))
        self.text("COMANDOS", (1120, 28), GOLD, self.large)
        human_turn = game.current == 0 and not game.over
        self.button(self.end_button, "Passar Turno", human_turn)
        self.button(self.king_button, "Ativar Rei (Endgame)", human_turn and game.can_activate_king(0))
        can_play = bool(
            human_turn and self.selected_card and game.playable(0, self.selected_card)
            and not game.manual_effects(self.selected_card)
            and (self.selected_card.definition["type"] == "spell" or self.position is not None)
        )
        self.button(self.play_button, "Jogar carta", can_play)
        if self.selected_card:
            self.paragraph(
                f"{self.selected_card.name}: {self.selected_card.definition['description']}",
                pygame.Rect(1120, 298, 296, 128),
            )
        elif self.selected_unit:
            unit = self.selected_unit
            description = self.game.catalog.get(unit.card_id, {}).get("description", "A vida do Rei e a vida do heroi.")
            self.paragraph(f"{unit.name}: {description}", pygame.Rect(1120, 298, 296, 128))
        else:
            self.paragraph(
                "Endgame: deck esgotado ativa automaticamente. Apos 8 rodadas, mesa total com ate 3"
                " unidades libera o botao. O Rei precisa de um espaco livre.",
                pygame.Rect(1120, 298, 296, 128), MUTED,
            )
        self.text("ULTIMAS JOGADAS", (1120, 443), GOLD)
        lines = [line for message in game.messages for line in self.wrap(message, 296)]
        height = self.small.get_linesize()
        capacity = (843 - 480) // height
        for index, line in enumerate(lines[-capacity:]):
            self.text(line, (1120, 480 + height * index), WHITE, self.small)
        self.button(self.menu_button, "Voltar ao Menu")

    def draw(self) -> None:
        self.screen.fill(BG)
        if self.state == State.MATCH:
            self.draw_match()
        elif self.state == State.MENU:
            self.text("CHESS STONE", (600, 220), GOLD, self.large)
            self.text("Card game de xadrez | Jogador x IA", (548, 292))
            self.text(f"Deck: {self.deck_size} cartas | 8 unidades por lado | 30 de vida", (493, 336), MUTED)
            self.button(self.start_button, "Iniciar partida")
            self.button(self.quit_button, "Sair")
        else:
            game = self.game
            title = "Empate!" if game is None or game.winner is None else (
                "Voce venceu!" if game.winner == 0 else "A IA venceu!"
            )
            self.text(title, (610, 290), GOLD, self.large)
            self.button(self.start_button, "Jogar novamente")
            self.button(self.quit_button, "Voltar ao Menu")
        pygame.display.flip()

    def update(self) -> None:
        game = self.game
        if self.state != State.MATCH or game is None:
            return
        if game.over:
            self.state = State.GAME_OVER
            self.clear_selection()
            return
        if self.selected_card and self.selected_card not in game.players[0].hand:
            self.clear_selection()
        if self.selected_unit and self.selected_unit not in game.players[0].board:
            self.clear_selection()
        now = pygame.time.get_ticks()
        if game.current == 1 and now >= self.ai_at:
            game.ai_step()
            self.ai_at = now + 450
            if game.over:
                self.state = State.GAME_OVER

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.clear_selection()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.click(event.pos)
            elif event.button == 3:
                self.clear_selection()

    def run(self) -> None:
        try:
            while self.running:
                for event in pygame.event.get():
                    self.handle_event(event)
                self.update()
                self.draw()
                self.clock.tick(60)
        finally:
            pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck-size", type=int, default=30, help="Quantidade de cartas por deck (>= 1)")
    parser.add_argument("--seed", type=int, help="Semente para partidas reproduziveis")
    parser.add_argument("--smoke-test", action="store_true", help="Renderiza os tres estados sem janela")
    args = parser.parse_args()
    if args.deck_size < 1:
        parser.error("--deck-size deve ser >= 1")
    if args.smoke_test:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    try:
        app = App(deck_size=args.deck_size, seed=args.seed)
    except (OSError, ValueError, pygame.error) as error:
        pygame.quit()
        parser.exit(1, f"Erro ao iniciar o jogo: {error}\n")
    if args.smoke_test:
        try:
            app.draw()
            app.click(app.start_button.center)
            app.draw()
            app.game.damage(app.game.hero_target(1), 99)
            app.game.cleanup()
            app.update()
            app.draw()
            if app.state != State.GAME_OVER:
                raise RuntimeError("Transicao para fim de jogo falhou")
        finally:
            pygame.quit()
    else:
        app.run()


if __name__ == "__main__":
    main()
