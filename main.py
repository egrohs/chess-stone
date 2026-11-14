"""Minimal pygame-ce client. All decisions are checked by game_engine."""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from enum import Enum, auto
from pathlib import Path

import pygame

from game_engine import BOARD_LIMIT, CENTER_SLOTS, KEYWORD_LABELS, Card, Entity, Game, RuleError, Unit, load_cards
from deck_store import DEFAULT_PATH, DeckStore, validate_legendary
from collection_view import CollectionView
from ui_theme import BG, PANEL, WHITE, MUTED, GREEN, GOLD, RED, BLUE
from crafting import CraftingInventory, STARTER_IDS
from puzzle_view import PuzzleView
from audio import ImpactAudio
from mate_rules import LABELS as MATE_LABELS


WIDTH, HEIGHT = 1440, 940
SLOT_WIDTH, SLOT_HEIGHT, SLOT_STEP = 118, 150, 130
SIDEBAR = 1100


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
        if self.audio.error:
            print(self.audio.error, file=sys.stderr)
        pygame.display.set_caption("Chess Stone - prototipo")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui", 18)
        self.small = pygame.font.SysFont("segoeui", 15)
        self.large = pygame.font.SysFont("segoeui", 30, bold=True)
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
        self.game: Game | None = None
        self.selected_card: Card | None = None
        self.selected_unit: Unit | None = None
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
            )
        except ValueError as error:
            self.deck_message = f"Erro ao iniciar partida: {error}"
            self.state = State.MENU
            return
        self.state = State.MATCH
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
        self.deck_message = ""

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
            self.inventory.validate_owned(cards)
            validate_legendary(
                cards, {c["id"]: c for c in self.inventory.catalog(all_variants=True)},
            )
            self.deck_store.save(candidate)
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
            slots = self.slots(owner)
            result.extend((unit, slots[unit.slot]) for unit in player.board)
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
        slots = self.slots(0)
        return [(slot, slots[slot]) for slot in self.game.players[0].free_slots()]

    def commit_card(self, target: Entity | None = None) -> None:
        if self.game and self.selected_card:
            self.game.play_card(0, self.selected_card, target, self.position)
            self.clear_selection()

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
                            game.log(game.mate_unavailable_reason(0, card) or
                                     "Carta indisponivel: verifique mana, espacos e alvos.")
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
        prepared = bool(game and any(
            unit.uid in threat.units for threat in game.mates.threats[unit.owner]
        ))
        pygame.draw.rect(self.screen, border, rect, 3, border_radius=5)
        if prepared:
            pygame.draw.rect(self.screen, GOLD, rect.inflate(-8, -8), 1, border_radius=4)
        self.paragraph(unit.name, pygame.Rect(rect.x + 7, rect.y + 7, rect.width - 14, 43), font=self.font)
        labels = [KEYWORD_LABELS[k] for k in sorted(unit.keywords)]
        if game and game.players[unit.owner].turns_started <= unit.frozen_through:
            labels.append("Congelado")
        self.paragraph(" / ".join(labels), pygame.Rect(rect.x + 7, rect.y + 54, rect.width - 14, 42), GOLD, font=self.small)
        if game:
            self.text(
                "Apoiada -1" if game.supported(unit) else "Pendurada +1",
                (rect.x + 7, rect.bottom - 53),
                GREEN if game.supported(unit) else RED, self.small,
            )
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
                pygame.draw.rect(self.screen, BLUE if index in CENTER_SLOTS else MUTED, rect, 1, border_radius=5)
                self.text(
                    f"{index + 1} {'Centro' if index in CENTER_SLOTS else 'Ala'}",
                    (rect.x + 8, rect.y + 7), MUTED, self.small,
                )
                unit = player.unit_at(index)
                if unit:
                    self.draw_unit(unit, rect, targets)
                    self.text(str(index + 1), (rect.right - 15, rect.y + 3), MUTED, self.small)
            self.text(
                "Alas: 1-2 / 7-8 | Centro: 3-6"
                f" | Controle: {game.center_control(owner)}"
                + (" | +1 mana no proximo turno" if player.center_bonus_pending else ""),
                (24, 568 if owner == 0 else 330), BLUE, self.small,
            )
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
            self.text(
                f"Mana: {player.mana}/{player.max_mana}"
                + (f" (+{player.temporary_mana} temporaria)" if player.temporary_mana else ""),
                (24, y), BLUE,
            )
            self.text(
                f"Deck: {len(player.deck)} | Mao: {len(player.hand)}/10 | Mesa: {len(player.board)}/8",
                (24, y + 28), MUTED, self.small,
            )
            if player.armor:
                self.text(f"Armadura do Rei: {player.armor}", (750, y + 10), BLUE)
            patterns = sorted({threat.pattern for threat in game.mates.threats[owner]})
            if patterns:
                self.paragraph(
                    "AMEACAS: " + " | ".join(MATE_LABELS[pattern] for pattern in patterns),
                    pygame.Rect(24, 647 if owner == 0 else 150, 1040, 23), GOLD,
                )
        for _, rect in self.placement_rects():
            pygame.draw.rect(self.screen, GREEN, rect, 2)
        hint = "Selecione carta ou unidade. Verde = alvo/espaco valido; azul = pronto; vermelho = Provocar."
        if self.selected_card:
            hint = (
                "Escolha um slot verde livre. Pecas nao mudam de slot quando outras morrem."
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
        if not self.audio.error:
            self.text(f"Feiticos neste turno: {game.players[game.current].spells_played}", (1120, 70), MUTED, self.small)
        if self.audio.error:
            self.text("Audio indisponivel (veja o console)", (1120, 70), RED, self.small)
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
            automatic_targets = [
                entity.name + (f" (slot {entity.slot + 1})" if isinstance(entity, Unit) else "")
                for effect in self.selected_card.definition["effects"]
                if effect.get("target", "").startswith("lowest_health_")
                for entity in game.parser.resolve_targets(effect, 0, preview=True)
            ]
            self.paragraph(
                ("Alvos agora: " + ", ".join(automatic_targets) + ". " if automatic_targets else "")
                + f"{self.selected_card.name}: {self.selected_card.definition['description']}",
                pygame.Rect(1120, 298, 296, 128),
            )
        elif self.selected_unit:
            unit = self.selected_unit
            description = self.game.catalog.get(unit.definition_id or unit.card_id, {}).get(
                "description", "A vida do Rei e a vida do heroi.",
            )
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
        minions = sum(self.draft[c["id"]] for c in self.cards if c["type"] == "minion")
        self.text(f"{total} cartas | {minions} lacaios | {total - minions} feiticos", (910, 235), GOLD)
        average = sum(c["cost"] * self.draft[c["id"]] for c in self.cards) / total if total else 0
        self.text(f"Custo medio: {average:.1f} mana", (910, 270), BLUE)
        self.paragraph(
            "Clique em um deck salvo para carregar e selecionar."
            " Alteracoes so entram na partida depois de salvar.",
            pygame.Rect(910, 310, 490, 65), MUTED,
        )
        self.text("CARTAS: custo / nome / atributos / efeito", (30, 153), MUTED, self.small)
        for card, minus, plus in self.catalog_rows():
            y = minus.y
            pygame.draw.rect(self.screen, PANEL, (30, y, 820, 55), border_radius=5)
            stats = f" {card['attack']}/{card['health']}" if card["type"] == "minion" else " Feitico"
            self.text(f"{card['cost']} - {card['name']}{stats}", (40, y + 3), WHITE)
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
            self.text(f"IA: {self.deck_size} cartas | 8 unidades por lado | 30 de vida", (493, 336), MUTED)
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
            if self.audio.error:
                self.text("Audio indisponivel (detalhes no console).", (30, 910), RED, self.small)
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
        if self.state == State.PUZZLE:
            self.puzzle_view.update()
            return
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
            self.puzzle_view.close()
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
            pygame.quit()
    else:
        app.run()


if __name__ == "__main__":
    main()
