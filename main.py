"""Minimal pygame-ce client. All decisions are checked by game_engine."""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from enum import Enum, auto
from pathlib import Path

import pygame

from game_engine import BOARD_LIMIT, CASTLE_ARMOR, CENTER_SLOTS, KEYWORD_LABELS, STARTING_HEALTH, Card, Entity, Game, PlayMode, RuleError, Unit, load_cards
from deck_store import DEFAULT_PATH, DeckStore, validate_deck, validate_legendary
from collection_view import CollectionView
from ui_theme import BG, PANEL, WHITE, MUTED, GREEN, GOLD, RED, BLUE
from crafting import CraftingInventory, STARTER_IDS
from puzzle_view import PuzzleView
from audio import BackgroundMusic, ImpactAudio
from mate_rules import LABELS as MATE_LABELS
from board_rules import CORNER_SLOTS
from hand_view import CARD_SIZE, CardMotion, HandView


WIDTH, HEIGHT = 1440, 940
SIDEBAR = 1100
DRAG_THRESHOLD = 6
BOARD_PATH = Path(__file__).resolve().parent / "assets" / "board.jpg"
CARD_ART_DIR = Path(__file__).resolve().parent / "assets" / "cards"
CARD_ART_FILES = {
    "peao": "white_pawn.png",
    "cavalo": "white_knight.png",
    "bispo": "white_bishop.png",
    "torre": "white_rook.png",
    "dama": "white_queen.png",
}
CARD_ART_RECT = pygame.Rect(180, 90, 225, 265)
BOARD_SOURCE_SIZE = (2626, 1600)
BOARD_X_EDGES = (446, 722, 1022, 1320, 1622, 1922, 2219)
BOARD_Y_EDGES = (460, 742, 1050)
BOARD_TOP = 105
HERO_PORTRAITS = ((1205, 1060, 250, 310), (1205, 130, 250, 300))
HERO_HEALTH_CENTERS = ((1430, 1330), (1430, 385))


class State(Enum):
    MENU = auto()
    DECK_BUILDER = auto()
    COLLECTION = auto()
    PUZZLE = auto()
    MATCH = auto()
    GAME_OVER = auto()


class App:
    def __init__(
        self, *, deck_size: int = 30, seed: int | None = None,
        decks_path: Path = DEFAULT_PATH,
    ):
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=256)
        pygame.init()
        self.audio = ImpactAudio()
        self.music = BackgroundMusic()
        if self.audio.error:
            print(self.audio.error, file=sys.stderr)
        pygame.display.set_caption("Chess Stone - prototipo")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        board = pygame.image.load(str(BOARD_PATH)).convert()
        if board.get_size() != BOARD_SOURCE_SIZE:
            raise ValueError(f"Imagem do tabuleiro deve ter dimensoes {BOARD_SOURCE_SIZE}.")
        board_height = round(BOARD_SOURCE_SIZE[1] * SIDEBAR / BOARD_SOURCE_SIZE[0])
        self.board_image = pygame.transform.smoothscale(board, (SIDEBAR, board_height))
        self.board_rect = self.board_image.get_rect(topleft=(0, BOARD_TOP))
        self.card_art_images: dict[str, pygame.Surface] = {}
        for card_id, filename in CARD_ART_FILES.items():
            path = CARD_ART_DIR / filename
            image = pygame.image.load(str(path)).convert_alpha()
            if not image.get_rect().contains(CARD_ART_RECT):
                raise ValueError(f"Imagem da carta muito pequena: {path}")
            self.card_art_images[card_id] = image.subsurface(CARD_ART_RECT).copy()
        self.card_art_sizes: dict[tuple[str, tuple[int, int]], pygame.Surface] = {}
        self.clock = pygame.time.Clock()
        self.hand_view = HandView()
        self.font = pygame.font.SysFont("segoeui", 18)
        self.small = pygame.font.SysFont("segoeui", 15)
        self.large = pygame.font.SysFont("segoeui", 30, bold=True)
        self.health_font = pygame.font.SysFont("segoeui", 18, bold=True)
        self.base_cards = load_cards()
        self.inventory = CraftingInventory(self.base_cards, decks_path.with_name("collection.json"))
        self.cards = self.inventory.catalog()
        self.collection = CollectionView(self.cards)
        self.puzzle_view = PuzzleView(self.inventory)
        self.deck_size = deck_size
        self.seed = seed
        self.deck_store = DeckStore(
            [card["id"] for card in self.inventory.catalog(all_variants=True)], decks_path,
        )
        self.saved_decks: dict[str, list[str]] = {}
        self.active_deck: str | None = None
        self.library_error = False
        self.deck_message = ""
        self.draft_name = ""
        self.draft: Counter[str] = Counter()
        self.name_focused = False
        self.catalog_page = 0
        self.saved_page = 0
        self.reload_decks()
        self.state = State.MENU
        self.music.update(False)
        self.game: Game | None = None
        self.selected_card: Card | None = None
        self.selected_unit: Unit | None = None
        self.selected_mode: PlayMode | None = None
        self.drag_unit: Unit | None = None
        self.end_button_pressed = False
        self.drag_card: Card | None = None
        self.card_drag_start: tuple[int, int] | None = None
        self.card_drag_point: tuple[int, int] | None = None
        self.card_drag_center: tuple[int, int] | None = None
        self.card_dragging = False
        self.position: int | None = None
        self.running = True
        self.ai_at = 0
        self.start_button = pygame.Rect(540, 440, 360, 65)
        self.quit_button = pygame.Rect(540, 750, 360, 60)
        self.collection_button = pygame.Rect(540, 675, 360, 60)
        self.builder_button = pygame.Rect(540, 520, 360, 60)
        self.deck_select_button = pygame.Rect(440, 600, 560, 60)
        self.name_rect = pygame.Rect(30, 95, 820, 48)
        self.save_deck_button = pygame.Rect(910, 95, 490, 48)
        self.new_deck_button = pygame.Rect(910, 160, 235, 48)
        self.back_deck_button = pygame.Rect(1165, 160, 235, 48)
        self.catalog_prev = pygame.Rect(30, 830, 180, 45)
        self.catalog_next = pygame.Rect(670, 830, 180, 45)
        self.saved_prev = pygame.Rect(910, 745, 180, 45)
        self.saved_next = pygame.Rect(1220, 745, 180, 45)
        self.end_button = pygame.Rect(1120, 100, 296, 52)
        self.king_button = pygame.Rect(1120, 164, 296, 52)
        self.play_button = pygame.Rect(1120, 228, 296, 52)
        self.castle_button = pygame.Rect(1120, 292, 296, 52)
        self.menu_button = pygame.Rect(1120, 868, 296, 48)

    def start_game(self) -> None:
        starter_ids = [card["id"] for card in self.base_cards if card["id"] in STARTER_IDS]
        deck = (
            self.saved_decks[self.active_deck] if self.active_deck
            else [starter_ids[i % len(starter_ids)] for i in range(self.deck_size)]
        )
        try:
            self.inventory.validate_owned(deck)
            self.game = Game(
                self.cards, deck_size=self.deck_size, seed=self.seed, player_deck=deck,
                on_damage=self.audio.play_damage,
                on_event=self.audio.play_event,
            )
        except ValueError as error:
            self.deck_message = f"Erro ao iniciar partida: {error}"
            self.state = State.MENU
            return
        self.state = State.MATCH
        self.music.update(True)
        self.hand_view = HandView()
        if self.audio.error:
            self.game.log(self.audio.error)
        self.clear_selection()
        self.ai_at = pygame.time.get_ticks() + 450

    def refresh_collection(self) -> None:
        self.cards = self.inventory.catalog()
        self.collection.cards = self.cards
        self.collection.refresh()

    def open_puzzle(self) -> None:
        if self.collection.selected is None:
            return
        card = self.collection.selected
        self.puzzle_view.open(card.get("base_id", card["id"]))
        self.state = State.PUZZLE

    def reload_decks(self) -> None:
        try:
            decks = self.deck_store.load()
        except (OSError, ValueError) as error:
            self.library_error = True
            self.deck_message = f"Erro ao ler decks: {error}. Corrija o arquivo e reabra o editor."
            return
        self.saved_decks = decks
        self.saved_page = min(self.saved_page, max(0, (len(decks) - 1) // 6))
        if self.active_deck not in decks:
            self.active_deck = None
        self.library_error = False
        self.deck_message = (
            "Carta Roque removida; decks vazios precisam ser editados."
            if self.deck_store.migrated or self.inventory.migrated else ""
        )

    def open_builder(self) -> None:
        self.reload_decks()
        self.state = State.DECK_BUILDER
        self.name_focused = False
        if self.active_deck:
            self.draft_name = self.active_deck
            self.draft = Counter(self.saved_decks[self.active_deck])
        else:
            self.draft_name = ""
            self.draft = Counter()

    def catalog_rows(self) -> list[tuple[dict, pygame.Rect, pygame.Rect]]:
        return [
            (card, pygame.Rect(660, 180 + i * 63, 54, 45),
             pygame.Rect(783, 180 + i * 63, 54, 45))
            for i, card in enumerate(self.cards[self.catalog_page * 10:(self.catalog_page + 1) * 10])
        ]

    def saved_rows(self) -> list[tuple[str, pygame.Rect]]:
        names = sorted(self.saved_decks, key=str.casefold)
        return [
            (name, pygame.Rect(910, 390 + i * 55, 490, 45))
            for i, name in enumerate(names[self.saved_page * 6:(self.saved_page + 1) * 6])
        ]

    def save_draft(self) -> None:
        if self.library_error:
            return
        cards = list(self.draft.elements())
        name = self.draft_name.strip()
        candidate = {**self.saved_decks, name: cards}
        try:
            validate_deck(cards, self.deck_store.catalog)
            self.inventory.validate_owned(cards)
            validate_legendary(
                cards, {c["id"]: c for c in self.inventory.catalog(all_variants=True)},
            )
            self.deck_store.save(candidate, allow_empty=True)
        except (OSError, ValueError) as error:
            self.deck_message = f"Erro ao salvar: {error}"
            return
        self.saved_decks = candidate
        self.active_deck = name
        self.draft_name = name
        self.deck_message = f"Deck '{name}' salvo e selecionado ({len(cards)} cartas)."

    def click_builder(self, point: tuple[int, int]) -> None:
        self.name_focused = self.name_rect.collidepoint(point)
        if self.name_focused:
            pygame.key.start_text_input()
            return
        pygame.key.stop_text_input()
        if self.back_deck_button.collidepoint(point):
            self.state = State.MENU
        elif self.save_deck_button.collidepoint(point):
            self.save_draft()
        elif self.new_deck_button.collidepoint(point):
            self.draft_name = ""
            self.draft = Counter()
            if not self.library_error:
                self.deck_message = "Novo deck. Informe um nome e adicione cartas."
        elif self.catalog_prev.collidepoint(point):
            self.catalog_page = max(0, self.catalog_page - 1)
        elif self.catalog_next.collidepoint(point):
            self.catalog_page = min((len(self.cards) - 1) // 10, self.catalog_page + 1)
        elif self.saved_prev.collidepoint(point):
            self.saved_page = max(0, self.saved_page - 1)
        elif self.saved_next.collidepoint(point):
            self.saved_page = min(max(0, (len(self.saved_decks) - 1) // 6), self.saved_page + 1)
        else:
            for card, minus, plus in self.catalog_rows():
                if plus.collidepoint(point):
                    available = self.inventory.count(card["id"])
                    if available is not None and self.draft[card["id"]] >= available:
                        self.deck_message = "Sem copias disponiveis. Resolva puzzles na colecao para criar esta carta."
                        return
                    self.draft[card["id"]] += 1
                    return
                if minus.collidepoint(point):
                    self.draft[card["id"]] = max(0, self.draft[card["id"]] - 1)
                    return
            for name, rect in self.saved_rows():
                if rect.collidepoint(point):
                    self.draft_name = name
                    self.draft = Counter(self.saved_decks[name])
                    self.active_deck = name
                    if not self.library_error:
                        self.deck_message = f"Deck '{name}' carregado e selecionado."
                    return

    def clear_selection(self) -> None:
        self.selected_card = None
        self.selected_unit = None
        self.selected_mode = None
        self.position = None
        self.cancel_card_drag()

    def cancel_card_drag(self) -> None:
        self.drag_card = None
        self.card_drag_start = None
        self.card_drag_point = None
        self.card_drag_center = None
        self.card_dragging = False

    def slots(self, owner: int) -> list[pygame.Rect]:
        x_edges = [round(x * self.board_rect.width / BOARD_SOURCE_SIZE[0]) for x in BOARD_X_EDGES]
        y_edges = [
            self.board_rect.top + round(y * self.board_rect.height / BOARD_SOURCE_SIZE[1])
            for y in BOARD_Y_EDGES
        ]
        top, bottom = (y_edges[1], y_edges[2]) if owner == 0 else (y_edges[0], y_edges[1])
        return [
            pygame.Rect(x_edges[i], top, x_edges[i + 1] - x_edges[i], bottom - top)
            for i in range(BOARD_LIMIT)
        ]

    def hero_rect(self, owner: int) -> pygame.Rect:
        x, y, width, height = HERO_PORTRAITS[owner]
        left = self.board_rect.left + round(x * self.board_rect.width / BOARD_SOURCE_SIZE[0])
        top = self.board_rect.top + round(y * self.board_rect.height / BOARD_SOURCE_SIZE[1])
        right = self.board_rect.left + round((x + width) * self.board_rect.width / BOARD_SOURCE_SIZE[0])
        bottom = self.board_rect.top + round((y + height) * self.board_rect.height / BOARD_SOURCE_SIZE[1])
        return pygame.Rect(left, top, right - left, bottom - top)

    def hero_health_rect(self, owner: int) -> pygame.Rect:
        x, y = HERO_HEALTH_CENTERS[owner]
        center = (
            self.board_rect.left + round(x * self.board_rect.width / BOARD_SOURCE_SIZE[0]),
            self.board_rect.top + round(y * self.board_rect.height / BOARD_SOURCE_SIZE[1]),
        )
        return pygame.Rect(0, 0, 29, 26).move(center[0] - 14, center[1] - 13)

    def draw_hero_health(self, owner: int, health_value: int) -> None:
        rect = self.hero_health_rect(owner)
        pygame.draw.ellipse(self.screen, (48, 12, 12), rect)
        pygame.draw.ellipse(self.screen, (135, 23, 24), rect.inflate(-3, -3))
        label = self.health_font.render(str(health_value), True, WHITE)
        self.screen.blit(label, label.get_rect(center=rect.center))

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
            slots = self.slots(owner)
            result.extend((unit, slots[unit.slot]) for unit in player.board)
            if not player.king:
                result.append((player, self.hero_rect(owner)))
        return result

    def valid_targets(self) -> list[Entity]:
        if not self.game or self.game.current != 0 or self.game.over:
            return []
        if self.selected_card:
            mode = self.selected_mode or "manobra"
            if self.game.playable(0, self.selected_card, mode):
                return self.game.valid_card_targets(0, self.selected_card, mode)
            return []
        if self.selected_unit:
            return self.game.attack_targets(self.selected_unit)
        return []

    def choosing_position(self) -> bool:
        return bool(
            self.game and self.selected_card
            and self.selected_mode is None
            and self.game.playable(0, self.selected_card, "piece")
        )

    def placement_rects(self) -> list[tuple[int, pygame.Rect]]:
        if not self.game or not self.choosing_position():
            return []
        slots = self.slots(0)
        return [(slot, slots[slot]) for slot in self.game.players[0].free_slots()]

    def commit_card(self, target: Entity | None = None) -> None:
        if self.game and self.selected_card:
            if self.selected_mode is None:
                raise RuleError("Escolha Peça ou Manobra.")
            self.game.play_card(0, self.selected_card, target, self.position, mode=self.selected_mode)
            self.clear_selection()

    def choose_maneuver(self, point: tuple[int, int]) -> None:
        if not self.game or not self.selected_card:
            return
        self.selected_mode = "manobra"
        self.position = None
        if not self.game.manual_effects(self.selected_card, "manobra"):
            self.commit_card()
            return
        for entity, rect in self.entity_rects():
            if rect.collidepoint(point):
                if entity not in self.valid_targets():
                    raise RuleError("Alvo invalido para a Manobra. Use os destaques verdes.")
                self.commit_card(entity)
                return
        self.game.log("Manobra selecionada: escolha um alvo verde (Esc cancela).")

    def begin_drag(self, point: tuple[int, int]) -> None:
        self.drag_unit = None
        game = self.game
        if self.state != State.MATCH or not game or game.current != 0 or game.over or self.selected_card:
            return
        for unit in game.players[0].board:
            if not unit.is_king and self.slots(0)[unit.slot].collidepoint(point):
                self.drag_unit = unit

    def drop_rects(self) -> list[tuple[int, pygame.Rect]]:
        if not self.game or not self.drag_unit:
            return []
        slots = self.slots(0)
        return [(slot, slots[slot]) for slot in self.game.players[0].free_slots()]

    def end_drag(self, point: tuple[int, int]) -> None:
        unit, self.drag_unit = self.drag_unit, None
        game = self.game
        if not unit or not game or self.state != State.MATCH:
            return
        for slot, rect in [(s, self.slots(0)[s]) for s in game.players[0].free_slots()]:
            if rect.collidepoint(point):
                try:
                    game.move_unit(0, unit, slot)
                    self.clear_selection()
                except RuleError as error:
                    game.log(str(error))
                return

    def begin_card_drag(self, point: tuple[int, int]) -> bool:
        game = self.game
        if self.state != State.MATCH or not game or game.current != 0 or game.over:
            return False
        card = self.hand_view.card_at(self.hand_rects(), point, self.selected_card)
        if not card:
            return False
        motion = self.hand_view.motions[card.uid]
        self.drag_card = card
        self.card_drag_start = point
        self.card_drag_point = point
        self.card_drag_center = (round(motion.x), round(motion.y))
        self.card_dragging = False
        return True

    def move_card_drag(self, point: tuple[int, int]) -> None:
        if not self.drag_card or self.card_drag_start is None:
            return
        self.card_drag_point = point
        dx = point[0] - self.card_drag_start[0]
        dy = point[1] - self.card_drag_start[1]
        if not self.card_dragging and dx * dx + dy * dy >= DRAG_THRESHOLD ** 2:
            card = self.drag_card
            self.selected_card = card
            self.selected_unit = None
            self.selected_mode = None
            self.position = None
            self.card_dragging = True

    def end_card_drag(self, point: tuple[int, int]) -> None:
        if not self.drag_card:
            return
        self.move_card_drag(point)
        card = self.drag_card
        dragging = self.card_dragging
        start = self.card_drag_start
        self.cancel_card_drag()
        game = self.game
        if self.state != State.MATCH or not game or game.current != 0 or game.over or card not in game.players[0].hand:
            self.clear_selection()
            return
        if not dragging:
            if start is not None:
                self.click(start)
            return
        try:
            # A valid friendly maneuver target takes precedence over its occupied slot.
            if any(
                entity in self.valid_targets() and rect.collidepoint(point)
                for entity, rect in self.entity_rects()
            ):
                self.choose_maneuver(point)
            elif any(rect.collidepoint(point) for rect in self.slots(0)):
                self.click(point)
            elif (
                self.play_button.collidepoint(point)
                or any(rect.collidepoint(point) for rect in self.slots(1))
                or self.hero_rect(1).collidepoint(point)
            ):
                self.choose_maneuver(point)
            else:
                self.clear_selection()
        except RuleError as error:
            game.log(str(error))

    def click(self, point: tuple[int, int]) -> None:
        if self.state == State.MENU:
            if self.start_button.collidepoint(point):
                self.start_game()
            elif self.builder_button.collidepoint(point):
                self.open_builder()
            elif self.collection_button.collidepoint(point):
                self.state = State.COLLECTION
            elif self.deck_select_button.collidepoint(point):
                options = [None, *sorted(self.saved_decks, key=str.casefold)]
                self.active_deck = options[(options.index(self.active_deck) + 1) % len(options)]
            elif self.quit_button.collidepoint(point):
                self.running = False
            return
        if self.state == State.DECK_BUILDER:
            self.click_builder(point)
            return
        if self.state == State.COLLECTION:
            if self.collection.craft_button.collidepoint(point):
                self.open_puzzle()
                return
            if self.collection.click(point):
                self.state = State.MENU
            return
        if self.state == State.PUZZLE:
            if self.puzzle_view.click(point):
                self.refresh_collection()
                self.state = State.COLLECTION
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
            if self.castle_button.collidepoint(point):
                game.castle(0)
                self.clear_selection()
                return
            if self.play_button.collidepoint(point) and self.selected_card:
                self.choose_maneuver(point)
                return
            card = self.hand_view.card_at(self.hand_rects(), point, self.selected_card)
            if card:
                if card is self.selected_card:
                    self.clear_selection()
                else:
                    self.clear_selection()
                    self.selected_card = card
                    if not game.playable(0, card):
                        game.log("Carta indisponivel nos dois modos: verifique tempo, casas e alvos.")
                return
            if self.selected_card:
                if self.selected_mode is None:
                    for position, rect in enumerate(self.slots(0)):
                        if rect.collidepoint(point):
                            game.require_free_slot(0, position)
                            self.position = position
                            self.selected_mode = "piece"
                            if not game.manual_effects(self.selected_card, "piece"):
                                self.commit_card()
                            return
                    self.choose_maneuver(point)
                elif self.selected_mode == "manobra":
                    self.choose_maneuver(point)
                else:
                    for entity, rect in self.entity_rects():
                        if rect.collidepoint(point):
                            self.commit_card(entity)
                            return
                    raise RuleError("Escolha um alvo verde para o efeito de entrada da Peça.")
                return
            for entity, rect in self.entity_rects():
                if not rect.collidepoint(point):
                    continue
                if entity in self.valid_targets():
                    if self.selected_unit:
                        game.attack(0, self.selected_unit, entity)
                        self.clear_selection()
                    return
                if isinstance(entity, Unit) and entity.owner == 0:
                    self.clear_selection()
                    if not game.attack_targets(entity):
                        raise RuleError("Peça nao pode atacar agora.")
                    self.selected_unit = entity
                    return
            self.clear_selection()
        except RuleError as error:
            game.log(str(error))

    def text(
        self, text: str, position: tuple[int, int], color: tuple = WHITE,
        font: pygame.font.Font | None = None, *, surface: pygame.Surface | None = None,
    ) -> None:
        (surface if surface is not None else self.screen).blit(
            (font or self.font).render(text, True, color), position,
        )

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
        surface: pygame.Surface | None = None,
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
            self.text(line, (rect.x, rect.y + index * font.get_linesize()), color, font, surface=surface)

    def button(self, rect: pygame.Rect, label: str, enabled: bool = True) -> None:
        pygame.draw.rect(self.screen, (48, 77, 84) if enabled else PANEL, rect, border_radius=6)
        pygame.draw.rect(self.screen, GREEN if enabled else MUTED, rect, 2, border_radius=6)
        image = self.font.render(label, True, WHITE if enabled else MUTED)
        self.screen.blit(image, image.get_rect(center=rect.center))

    def card_art(self, card: dict, size: tuple[int, int]) -> pygame.Surface | None:
        card_id = card.get("base_id", card["id"])
        if card_id not in self.card_art_images:
            return None
        key = (card_id, size)
        if key not in self.card_art_sizes:
            self.card_art_sizes[key] = pygame.transform.smoothscale(self.card_art_images[card_id], size)
        return self.card_art_sizes[key]

    def draw_unit(self, unit: Unit, rect: pygame.Rect, targets: list[Entity]) -> None:
        game = self.game
        color = (42, 67, 83) if unit.owner == 0 else (79, 48, 58)
        if unit.is_king:
            color = (88, 75, 38)
        pygame.draw.rect(self.screen, color, rect, border_radius=5)
        definition = game.catalog.get(unit.definition_id or unit.card_id) if game else None
        art = self.card_art(definition, (38, 45)) if definition else None
        if art:
            self.screen.blit(art, (rect.right - 43, rect.y + 5))
        border = MUTED
        if game and game.attack_targets(unit):
            border = BLUE
        if unit in targets:
            border = GREEN
        if unit is self.selected_unit:
            border = GOLD
        prepared = bool(game and any(
            unit.uid in threat.units for threat in game.mates.threats[unit.owner]
        ))
        pygame.draw.rect(self.screen, border, rect, 3, border_radius=5)
        if prepared:
            pygame.draw.rect(self.screen, GOLD, rect.inflate(-8, -8), 1, border_radius=4)
        name_width = rect.width - (50 if art else 14)
        self.paragraph(unit.name, pygame.Rect(rect.x + 7, rect.y + 7, name_width, self.font.get_linesize()), font=self.font)
        labels = [unit.piece_type.capitalize(), *[KEYWORD_LABELS[k] for k in sorted(unit.keywords)]]
        if game and game.players[unit.owner].turns_started <= unit.frozen_through:
            labels.append("Congelado")
        self.paragraph(
            " / ".join(labels),
            pygame.Rect(rect.x + 7, rect.y + (52 if art else 33), rect.width - 14, 24 if art else 38),
            GOLD, font=self.small,
        )
        if game:
            self.text(
                "Apoiada -1" if game.supported(unit) else "Pendurada +1",
                (rect.x + 7, rect.bottom - 43),
                GREEN if game.supported(unit) else RED, self.small,
            )
        self.text(f"{unit.attack} / {unit.health}", (rect.x + 9, rect.bottom - 23), WHITE, self.font)

    def draw_match(self) -> None:
        game = self.game
        if game is None:
            return
        self.screen.blit(self.board_image, self.board_rect)
        for rect in (
            pygame.Rect(15, 85, 360, 65), pygame.Rect(15, 230, 430, 67),
            pygame.Rect(15, 555, 420, 22), pygame.Rect(15, 595, 360, 65),
            pygame.Rect(15, 669, 780, 48),
        ):
            pygame.draw.rect(self.screen, PANEL, rect, border_radius=4)
        targets = self.valid_targets()
        self.text("CHESS STONE", (24, 18), GOLD, self.large)
        self.text(
            f"Rodada {(game.turn_number + 1) // 2} | Turno {game.turn_number}"
            f" | {'Sua vez' if game.current == 0 else 'IA jogando...'}",
            (24, 235), WHITE, self.large,
        )
        for owner, player in enumerate(game.players):
            for index, rect in enumerate(self.slots(owner)):
                unit = player.unit_at(index)
                if unit:
                    self.draw_unit(unit, rect.inflate(-4, -4), targets)
                    self.text(str(index + 1), (rect.right - 15, rect.y + 3), MUTED, self.small)
                else:
                    label = f"{index + 1} {'Centro' if index in CENTER_SLOTS else 'Canto' if index in CORNER_SLOTS else 'Borda'}"
                    label_rect = pygame.Rect(rect.x + 4, rect.y + 4, self.small.size(label)[0] + 8, self.small.get_linesize())
                    pygame.draw.rect(self.screen, PANEL, label_rect, border_radius=3)
                    self.text(label, (label_rect.x + 4, label_rect.y), WHITE, self.small)
            self.text(
                "Cantos: 1 e 6 | Bordas: 2 e 5 | Centro: 3 e 4"
                f" | Controle: {game.center_control(owner)}"
                + (" | +1 tempo no proximo turno" if player.center_bonus_pending else ""),
                (24, 560 if owner == 0 else 275), BLUE, self.small,
            )
            hero = self.hero_rect(owner)
            if not player.king and player in targets:
                pygame.draw.rect(self.screen, GREEN, hero, 3, border_radius=6)
            y = 90 if owner == 1 else 603
            self.text(
                f"Tempo: {player.mana}/{player.max_mana}"
                + (f" (+{player.temporary_mana} temporario)" if player.temporary_mana else ""),
                (24, y), BLUE,
            )
            self.text(
                f"Deck: {len(player.deck)} | Mao: {len(player.hand)}/10 | Tabuleiro: {len(player.board)}/{BOARD_LIMIT}"
                f" | Descarte: {len(player.discard)}",
                (24, y + 28), MUTED, self.small,
            )
            if player.armor:
                pygame.draw.rect(self.screen, PANEL, (742, y + 6, 210, 26), border_radius=4)
                self.text(f"Armadura do Rei: {player.armor}", (750, y + 10), BLUE)
            patterns = sorted({threat.pattern for threat in game.mates.threats[owner]})
            if patterns:
                threat_y = 577 if owner == 0 else 63
                pygame.draw.rect(self.screen, PANEL, (15, threat_y, 1040, 18), border_radius=4)
                self.paragraph(
                    "AMEACAS: " + " | ".join(MATE_LABELS[pattern] for pattern in patterns),
                    pygame.Rect(24, threat_y, 1020, 18), GOLD,
                )
        for _, rect in self.placement_rects():
            pygame.draw.rect(self.screen, GREEN, rect, 2)
        for _, rect in self.drop_rects():
            pygame.draw.rect(self.screen, BLUE, rect, 2)
        if self.drag_unit:
            ghost = self.slots(0)[0].copy()
            ghost.center = pygame.mouse.get_pos()
            pygame.draw.rect(self.screen, GOLD, ghost, 2, border_radius=5)
            self.text(self.drag_unit.name, (ghost.x + 8, ghost.y + 8), GOLD, self.small)
        hint = "Selecione carta ou peça. Verde = alvo/espaco valido; azul = pronto."
        if self.card_dragging:
            hint = "Arraste ate uma casa vazia, alvo verde, campo inimigo ou botao de Manobra."
        elif self.selected_card:
            hint = (
                "Casa vazia = Peca; fora das casas = Manobra. Mesmo custo nos dois modos."
                if self.selected_mode is None
                else f"Modo {'Peca' if self.selected_mode == 'piece' else 'Manobra'}: escolha um alvo verde. Esc cancela."
            )
        elif self.selected_unit:
            hint = "Escolha um inimigo verde para atacar."
        self.text(hint, (24, 674), GREEN if self.selected_card or self.selected_unit else MUTED, self.small)
        self.text("Clique direito / ESC: cancelar selecao", (24, 696), MUTED, self.small)
        for card, motion in self.hand_view.layers(self.hand_rects(), self.selected_card):
            if self.card_dragging and card is self.drag_card:
                continue
            self.draw_hand_card(card, motion)
        for owner, player in enumerate(game.players):
            self.draw_hero_health(owner, player.health)
        self.draw_sidebar()
        if self.card_dragging and self.drag_card and self.card_drag_start and self.card_drag_point and self.card_drag_center:
            motion = self.hand_view.motions[self.drag_card.uid]
            center = (
                self.card_drag_center[0] + self.card_drag_point[0] - self.card_drag_start[0],
                self.card_drag_center[1] + self.card_drag_point[1] - self.card_drag_start[1],
            )
            self.draw_hand_card(self.drag_card, motion, center)

    def draw_hand_card(self, card: Card, motion: CardMotion, center: tuple[int, int] | None = None) -> None:
        image = self.hand_card_image(card)
        image = pygame.transform.rotozoom(image, motion.angle, motion.scale)
        rect = image.get_rect(center=center or (round(motion.x), round(motion.y)))
        shadow = pygame.Surface(image.get_size(), pygame.SRCALPHA)
        shadow.blit(image, (0, 0))
        shadow.fill((0, 0, 0, 110), special_flags=pygame.BLEND_RGBA_MULT)
        self.screen.blit(shadow, rect.move(4, 6 + round(8 * motion.focus)))
        self.screen.blit(image, rect)

    def hand_card_image(self, card: Card) -> pygame.Surface:
        image = pygame.Surface(CARD_SIZE, pygame.SRCALPHA)
        rect = image.get_rect()
        game = self.game
        if game:
            definition = card.definition["piece_mode"]
            playable = game.playable(0, card)
            pygame.draw.rect(
                image, (43, 61, 77),
                rect, border_radius=5,
            )
            border = GOLD if card is self.selected_card else GREEN if playable else MUTED
            focused = card is self.selected_card or card is self.hand_view.hovered
            pygame.draw.rect(image, border, rect, 3 if focused else 1, border_radius=5)
            self.text(str(definition["cost"]), (8, 5), BLUE, self.large, surface=image)
            art = self.card_art(card.definition, (51, 60))
            if art:
                image.blit(art, (43, 7))
            self.paragraph(card.name, pygame.Rect(7, 69 if art else 46, 85, 26 if art else 49), surface=image)
            self.paragraph(
                card.definition["description"], pygame.Rect(7, 98, 85, 62),
                WHITE if playable else MUTED, surface=image,
            )
            self.text(
                f"{definition['attack']}/{definition['health']} ou M",
                (8, rect.bottom - 28), WHITE, self.small, surface=image,
            )
        return image

    def draw_sidebar(self) -> None:
        game = self.game
        if game is None:
            return
        pygame.draw.rect(self.screen, PANEL, (SIDEBAR, 0, WIDTH - SIDEBAR, HEIGHT))
        self.text("COMANDOS", (1120, 28), GOLD, self.large)
        if not self.audio.error and not self.music.error:
            self.text(f"Manobras neste turno: {game.players[game.current].maneuvers_played}", (1120, 70), MUTED, self.small)
        if self.audio.error or self.music.error:
            self.text("Erro de audio (veja o console)", (1120, 70), RED, self.small)
        human_turn = game.current == 0 and not game.over
        self.button(self.end_button, "Passar Turno", human_turn)
        self.button(self.king_button, "Ativar Rei (Final de jogo)", human_turn and game.can_activate_king(0))
        can_play = bool(human_turn and self.selected_card and game.playable(0, self.selected_card, "manobra"))
        self.button(self.play_button, "Jogar como Manobra", can_play)
        self.button(self.castle_button, f"Roque: +{CASTLE_ARMOR} Armadura (2 tempo)", game.can_castle(0))
        if self.selected_card:
            automatic_targets = [
                game.entity_name(entity) + (f" (casa {entity.slot + 1})" if isinstance(entity, Unit) else "")
                for effect in self.selected_card.mode(self.selected_mode or "manobra")["effects"]
                if effect.get("target", "").startswith("lowest_health_")
                for entity in game.parser.resolve_targets(effect, 0, preview=True)
            ]
            self.paragraph(
                ("Alvos agora: " + ", ".join(automatic_targets) + ". " if automatic_targets else "")
                + f"{self.selected_card.name}: {self.selected_card.definition['description']}",
                pygame.Rect(1120, 360, 296, 128),
            )
        elif self.selected_unit:
            unit = self.selected_unit
            description = self.game.catalog.get(unit.definition_id or unit.card_id, {}).get(
                "description", "O Rei no tabuleiro compartilha a vida indicada no retrato.",
            )
            self.paragraph(f"{unit.name}: {description}", pygame.Rect(1120, 360, 296, 128))
        else:
            self.paragraph(
                "Roque: Torre no canto e Rei fora do tabuleiro. Uma vez por partida."
                " Final de jogo: Rei ativa com deck esgotado ou apos 8 rodadas com ate 3 peças.",
                pygame.Rect(1120, 360, 296, 128), MUTED,
            )
        self.text("ULTIMAS JOGADAS", (1120, 505), GOLD)
        lines = [line for message in game.messages for line in self.wrap(message, 296)]
        height = self.small.get_linesize()
        capacity = (843 - 542) // height
        for index, line in enumerate(lines[-capacity:]):
            self.text(line, (1120, 542 + height * index), WHITE, self.small)
        self.button(self.menu_button, "Voltar ao Menu")

    def draw_builder(self) -> None:
        self.text("MONTAR DECK", (30, 25), GOLD, self.large)
        self.text("Pecas basicas livres; demais copias exigem crafting | Mesmo nome substitui o deck.", (350, 38), MUTED)
        pygame.draw.rect(self.screen, PANEL, self.name_rect, border_radius=5)
        pygame.draw.rect(self.screen, GOLD if self.name_focused else MUTED, self.name_rect, 2)
        self.paragraph(
            self.draft_name + ("|" if self.name_focused else "") if self.draft_name or self.name_focused
            else "Clique para informar o nome do deck",
            self.name_rect.inflate(-20, -14), WHITE if self.draft_name else MUTED, font=self.font,
        )
        self.button(self.save_deck_button, "Salvar / substituir e selecionar", not self.library_error)
        self.button(self.new_deck_button, "Novo (descartar rascunho)")
        self.button(self.back_deck_button, "Voltar (descartar)")
        total = sum(self.draft.values())
        self.text(f"{total} cartas modais | Peca ou Manobra", (910, 235), GOLD)
        average = sum(c["piece_mode"]["cost"] * self.draft[c["id"]] for c in self.cards) / total if total else 0
        self.text(f"Custo medio: {average:.1f} tempo", (910, 270), BLUE)
        self.paragraph(
            "Clique em um deck salvo para carregar e selecionar."
            " Alteracoes so entram na partida depois de salvar.",
            pygame.Rect(910, 310, 490, 65), MUTED,
        )
        self.text("CARTAS: custo / nome / atributos / efeito", (30, 153), MUTED, self.small)
        for card, minus, plus in self.catalog_rows():
            y = minus.y
            pygame.draw.rect(self.screen, PANEL, (30, y, 820, 55), border_radius=5)
            piece = card["piece_mode"]
            stats = f" {piece['attack']}/{piece['health']} ou Manobra"
            self.text(f"{piece['cost']} - {card['name']}{stats}", (40, y + 3), WHITE)
            self.paragraph(card["description"], pygame.Rect(40, y + 29, 605, 22), MUTED)
            self.button(minus, "-", self.draft[card["id"]] > 0)
            self.paragraph(
                str(self.draft[card["id"]]), pygame.Rect(722, y + 12, 55, 24), GOLD,
            )
            available = self.inventory.count(card["id"])
            self.button(plus, "+", available is None or self.draft[card["id"]] < available)
        for name, rect in self.saved_rows():
            pygame.draw.rect(self.screen, PANEL, rect, border_radius=5)
            pygame.draw.rect(self.screen, GOLD if name == self.active_deck else MUTED, rect, 2)
            self.paragraph(
                f"{name} ({len(self.saved_decks[name])} cartas)", rect.inflate(-18, -12),
                font=self.font,
            )
        if not self.saved_decks:
            self.text("Nenhum deck salvo.", (910, 400), MUTED)
        self.button(self.catalog_prev, "Cartas anteriores", self.catalog_page > 0)
        self.button(self.catalog_next, "Proximas cartas", (self.catalog_page + 1) * 10 < len(self.cards))
        self.text(f"Pagina {self.catalog_page + 1}", (350, 842), MUTED)
        self.button(self.saved_prev, "Decks anteriores", self.saved_page > 0)
        self.button(self.saved_next, "Proximos decks", (self.saved_page + 1) * 6 < len(self.saved_decks))
        self.paragraph(
            self.deck_message, pygame.Rect(30, 888, 1370, 45),
            RED if self.library_error or self.deck_message.startswith("Erro") else GREEN,
        )

    def draw(self) -> None:
        self.screen.fill(BG)
        if self.state == State.MATCH:
            self.draw_match()
        elif self.state == State.DECK_BUILDER:
            self.draw_builder()
        elif self.state == State.COLLECTION:
            self.collection.draw(self)
        elif self.state == State.PUZZLE:
            self.puzzle_view.draw(self)
        elif self.state == State.MENU:
            self.text("CHESS STONE", (600, 220), GOLD, self.large)
            self.text("Card game de xadrez | Jogador x IA", (548, 292))
            self.text(f"IA: {self.deck_size} cartas | {BOARD_LIMIT} peças por lado | {STARTING_HEALTH} de vida", (493, 336), MUTED)
            self.button(self.start_button, "Iniciar partida")
            self.button(self.builder_button, "Montar / editar decks")
            self.button(self.collection_button, "Colecao de cartas")
            self.button(self.deck_select_button, "")
            self.paragraph(
                f"Deck: {self.active_deck} (clique para trocar)" if self.active_deck
                else f"Deck automatico: {self.deck_size} cartas (clique para trocar)",
                self.deck_select_button.inflate(-20, -14), font=self.font,
            )
            self.button(self.quit_button, "Sair")
            self.paragraph(
                self.inventory.error or self.deck_message, pygame.Rect(360, 830, 720, 100),
                RED if self.library_error or self.inventory.error or self.deck_message.startswith("Erro") else GREEN,
            )
            if self.audio.error or self.music.error:
                self.text("Erro de audio (detalhes no console).", (30, 910), RED, self.small)
        else:
            game = self.game
            title = "Empate!" if game is None or game.winner is None else (
                "Voce venceu!" if game.winner == 0 else "A IA venceu!"
            )
            self.text(title, (610, 290), GOLD, self.large)
            self.button(self.start_button, "Jogar novamente")
            self.button(self.quit_button, "Voltar ao Menu")
        pygame.display.flip()

    def update(self, dt: float = 0.0) -> None:
        self.music.update(self.state == State.MATCH)
        if self.state == State.PUZZLE:
            self.puzzle_view.update()
            return
        game = self.game
        if self.state != State.MATCH or game is None:
            return
        if game.over:
            self.finish_match()
            return
        if self.selected_card and self.selected_card not in game.players[0].hand:
            self.clear_selection()
        if self.drag_card and (game.current != 0 or self.drag_card not in game.players[0].hand):
            self.clear_selection()
        if self.selected_unit and self.selected_unit not in game.players[0].board:
            self.clear_selection()
        point = (-1000, -1000) if self.card_dragging else pygame.mouse.get_pos()
        self.hand_view.update(self.hand_rects(), point, dt, self.selected_card)
        now = pygame.time.get_ticks()
        if game.current == 1 and now >= self.ai_at:
            game.ai_step()
            self.ai_at = now + 450
            if game.over:
                self.finish_match()

    def finish_match(self) -> None:
        if self.game and self.game.winner == 0:
            self.audio.play_event("victory")
        self.state = State.GAME_OVER
        self.music.update(False)
        self.clear_selection()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif self.state == State.PUZZLE:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.puzzle_view.leave()
                self.refresh_collection()
                self.state = State.COLLECTION
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.click(event.pos)
        elif self.state == State.COLLECTION:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.click(event.pos)
            elif self.collection.handle_event(event):
                self.state = State.MENU
        elif self.state == State.DECK_BUILDER and event.type == pygame.TEXTINPUT and self.name_focused:
            self.draft_name = (self.draft_name + "".join(c for c in event.text if c.isprintable()))[:40]
        elif self.state == State.DECK_BUILDER and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.name_focused = False
                pygame.key.stop_text_input()
                self.state = State.MENU
            elif self.name_focused and event.key == pygame.K_BACKSPACE:
                self.draft_name = self.draft_name[:-1]
            elif event.key == pygame.K_RETURN:
                self.name_focused = False
                pygame.key.stop_text_input()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.drag_unit = None
            self.clear_selection()
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.drag_unit = None
            self.end_button_pressed = False
            self.clear_selection()
        elif event.type == pygame.MOUSEMOTION and self.drag_card:
            self.move_card_drag(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if (
                    self.state == State.MATCH and self.game and self.game.current == 0
                    and not self.game.over and self.end_button.collidepoint(event.pos)
                ):
                    self.end_button_pressed = True
                    self.audio.play_event("end_turn_down")
                if not self.begin_card_drag(event.pos):
                    self.begin_drag(event.pos)
                    self.click(event.pos)
            elif event.button == 3:
                self.drag_unit = None
                self.clear_selection()
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.end_button_pressed:
                self.end_button_pressed = False
                self.audio.play_event("end_turn_up")
            if self.drag_card:
                self.end_card_drag(event.pos)
            else:
                self.end_drag(event.pos)

    def run(self) -> None:
        try:
            while self.running:
                for event in pygame.event.get():
                    self.handle_event(event)
                self.update(self.clock.get_time() / 1000.0)
                self.draw()
                self.clock.tick(60)
        finally:
            self.puzzle_view.close()
            self.music.stop()
            pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck-size", type=int, default=30, help="Quantidade de cartas por deck (>= 1)")
    parser.add_argument("--seed", type=int, help="Semente para partidas reproduziveis")
    parser.add_argument("--smoke-test", action="store_true", help="Renderiza todos os estados sem janela")
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
            from chess_puzzles import Puzzle, PuzzleSession

            app.draw()
            app.click(app.collection_button.center)
            app.draw()
            app.click(app.collection.next.center)
            app.draw()
            app.puzzle_view.base_id = "peao"
            app.puzzle_view.session = PuzzleSession(Puzzle(
                "smoke", "pawnEndgame", 1500,
                "4k3/P7/8/8/8/8/8/4K3 w - - 0 1", ("a7a8q",),
            ))
            app.state = State.PUZZLE
            app.draw()
            app.click(app.puzzle_view.back_button.center)
            app.click(app.collection.back_button.center)
            app.click(app.builder_button.center)
            app.draw()
            app.click(app.back_deck_button.center)
            app.click(app.start_button.center)
            app.draw()
            app.game.damage(app.game.hero_target(1), 99)
            app.game.cleanup()
            app.update()
            app.draw()
            if app.state != State.GAME_OVER:
                raise RuntimeError("Transicao para fim de jogo falhou")
        finally:
            app.puzzle_view.close()
            app.music.stop()
            pygame.quit()
    else:
        app.run()


if __name__ == "__main__":
    main()
