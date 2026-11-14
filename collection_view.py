"""Paginated catalog browser and entry point for puzzle crafting."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from csv_to_json import normalize
from game_engine import KEYWORD_LABELS
from ui_theme import BLUE, GOLD, MUTED, PANEL
from crafting import THEMES, QUALITY_LABELS

if TYPE_CHECKING:
    from main import App


PAGE_SIZE = 8
TYPES = (None, "peao", "cavalo", "bispo", "torre", "dama")
TYPE_LABELS = {
    None: "Todas as pecas", "peao": "Peao", "cavalo": "Cavalo",
    "bispo": "Bispo", "torre": "Torre", "dama": "Dama",
}
TRIGGER_LABELS = {
    "on_play": "Ao jogar", "on_death": "Ao morrer",
    "on_turn_start": "Inicio do turno", "on_turn_end": "Fim do turno",
}


class CollectionView:
    def __init__(self, cards: list[dict]):
        self.cards = cards
        self.query = ""
        self.card_type: str | None = None
        self.sort_by_name = False
        self.page = 0
        self.selected: dict | None = None
        self.search_focused = False
        self.detail_scroll = 0
        self.search_rect = pygame.Rect(30, 95, 550, 48)
        self.type_button = pygame.Rect(600, 95, 220, 48)
        self.sort_button = pygame.Rect(840, 95, 250, 48)
        self.back_button = pygame.Rect(1110, 95, 300, 48)
        self.previous = pygame.Rect(30, 850, 220, 48)
        self.next = pygame.Rect(680, 850, 220, 48)
        self.detail_rect = pygame.Rect(950, 210, 440, 590)
        self.craft_button = pygame.Rect(950, 850, 440, 48)
        self.refresh()

    def filtered_cards(self) -> list[dict]:
        query = normalize(self.query)
        matches = [
            card for card in self.cards
            if (self.card_type is None or card["piece_mode"]["piece_type"] == self.card_type)
            and query in normalize(" ".join([
                card["name"], card["id"], card["piece_mode"]["piece_type"], card["description"],
                *[KEYWORD_LABELS[keyword] for keyword in card["piece_mode"]["keywords"]],
            ]))
        ]
        return sorted(
            matches,
            key=lambda c: (normalize(c["name"]), c["piece_mode"]["cost"]) if self.sort_by_name
            else (c["piece_mode"]["cost"], normalize(c["name"])),
        )

    def refresh(self) -> None:
        self.page = 0
        matches = self.filtered_cards()
        selected_id = self.selected["id"] if self.selected else None
        self.selected = next(
            (card for card in matches if card["id"] == selected_id),
            matches[0] if matches else None,
        )
        self.detail_scroll = 0

    def rows(self) -> list[tuple[dict, pygame.Rect]]:
        return [
            (card, pygame.Rect(30 + (i % 4) * 220, 210 + (i // 4) * 305, 210, 285))
            for i, card in enumerate(self.filtered_cards()[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE])
        ]

    def click(self, point: tuple[int, int]) -> bool:
        self.search_focused = self.search_rect.collidepoint(point)
        if self.search_focused:
            pygame.key.start_text_input()
            return False
        pygame.key.stop_text_input()
        if self.back_button.collidepoint(point):
            return True
        if self.type_button.collidepoint(point):
            self.card_type = TYPES[(TYPES.index(self.card_type) + 1) % len(TYPES)]
            self.refresh()
        elif self.sort_button.collidepoint(point):
            self.sort_by_name = not self.sort_by_name
            self.refresh()
        elif self.previous.collidepoint(point):
            self.page = max(0, self.page - 1)
        elif self.next.collidepoint(point):
            self.page = min(max(0, (len(self.filtered_cards()) - 1) // PAGE_SIZE), self.page + 1)
        else:
            for card, rect in self.rows():
                if rect.collidepoint(point):
                    self.selected = card
                    self.detail_scroll = 0
                    break
        return False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.search_focused = False
            pygame.key.stop_text_input()
            return True
        if self.search_focused:
            if event.type == pygame.TEXTINPUT:
                self.query = (self.query + "".join(c for c in event.text if c.isprintable()))[:100]
                self.refresh()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE:
                self.query = self.query[:-1]
                self.refresh()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                self.search_focused = False
                pygame.key.stop_text_input()
        if event.type == pygame.MOUSEWHEEL and self.detail_rect.collidepoint(pygame.mouse.get_pos()):
            self.detail_scroll = max(0, self.detail_scroll - event.y * 3)
        return False

    def draw(self, app: App) -> None:
        app.text("COLECAO DE CARTAS", (30, 25), GOLD, app.large)
        pygame.draw.rect(app.screen, PANEL, self.search_rect, border_radius=5)
        pygame.draw.rect(app.screen, GOLD if self.search_focused else MUTED, self.search_rect, 2)
        app.paragraph(
            self.query + ("|" if self.search_focused else "") if self.query or self.search_focused
            else "Buscar nome, peca, descricao ou palavra-chave...",
            self.search_rect.inflate(-16, -12), font=app.font,
        )
        app.button(self.type_button, TYPE_LABELS[self.card_type])
        app.button(self.sort_button, "Ordem: nome" if self.sort_by_name else "Ordem: custo de tempo")
        app.button(self.back_button, "Voltar ao Menu")
        matches = self.filtered_cards()
        app.text(f"{len(matches)} de {len(self.cards)} cartas | Clique para ver detalhes", (30, 167), MUTED)
        for card, rect in self.rows():
            piece = card["piece_mode"]
            pygame.draw.rect(
                app.screen, (43, 61, 77),
                rect, border_radius=6,
            )
            pygame.draw.rect(app.screen, GOLD if card is self.selected else MUTED, rect, 3, border_radius=6)
            app.text(f"{piece['cost']} tempo", (rect.x + 12, rect.y + 10), BLUE, app.large)
            art = app.card_art(card, (65, 77))
            if art:
                app.screen.blit(art, (rect.right - 77, rect.y + 12))
            app.paragraph(card["name"], pygame.Rect(rect.x + 12, rect.y + 60, 110 if art else 186, 55), font=app.font)
            app.text(f"{TYPE_LABELS[piece['piece_type']]} ou Manobra", (rect.x + 12, rect.y + 120), MUTED, app.small)
            app.paragraph(card["description"], pygame.Rect(rect.x + 12, rect.y + 148, 186, 92))
            app.text(f"ATQ {piece['attack']} / VIDA {piece['health']}", (rect.x + 12, rect.bottom - 34), GOLD)
        if not matches:
            app.text("Nenhuma carta encontrada. Altere a busca ou o filtro.", (30, 250), MUTED)
        pygame.draw.rect(app.screen, PANEL, (930, 180, 480, 645), border_radius=6)
        if self.selected:
            card = self.selected
            piece = card["piece_mode"]
            available = app.inventory.count(card["id"])
            base_id = card.get("base_id", card["id"])
            sections = [
                card["name"], f"ID: {card['id']}",
                "Disponivel: base liberada (copias livres)" if available is None
                else f"Copias criadas: {available}" if available else "Bloqueada: resolva um puzzle para criar.",
                f"Qualidade: {QUALITY_LABELS.get(card.get('quality', 'basic'), 'Basica')}",
                f"Peca: {TYPE_LABELS[piece['piece_type']]} | Alternativa: Manobra",
                "Lendaria: uma copia por deck entre todas as qualidades."
                if card.get("rarity") == "legendary" else "",
                f"Custo nos dois modos: {piece['cost']} tempo",
                "Puzzle: " + THEMES.get(base_id, ("", "Tema nao configurado"))[1],
            ]
            sections.append(f"Ataque: {piece['attack']} | Vida: {piece['health']}")
            sections.extend([
                "Palavras-chave da Peca: " + (", ".join(KEYWORD_LABELS[k] for k in piece["keywords"]) or "Nenhuma"),
                "", "Descricao:", card["description"], "", "Gatilhos:",
                ", ".join(dict.fromkeys(TRIGGER_LABELS[e["trigger"]] for e in piece["effects"]))
                or "Nenhum efeito disparado.",
                "Manobra: efeito imediato e descarte.",
            ])
            lines = [line for section in sections for line in (app.wrap(section, self.detail_rect.width, app.font) or [""])]
            line_height = app.font.get_linesize()
            capacity = self.detail_rect.height // line_height
            self.detail_scroll = min(self.detail_scroll, max(0, len(lines) - capacity))
            for index, line in enumerate(lines[self.detail_scroll:self.detail_scroll + capacity]):
                app.text(line, (self.detail_rect.x, self.detail_rect.y + index * line_height))
            if len(lines) > capacity:
                app.text("Role o mouse sobre os detalhes para ler mais.", (950, 800), MUTED, app.small)
        app.button(self.craft_button, "Criar carta: resolver puzzle", self.selected is not None and not app.inventory.error)
        app.button(self.previous, "Pagina anterior", self.page > 0)
        app.button(self.next, "Proxima pagina", (self.page + 1) * PAGE_SIZE < len(matches))
        app.text(f"Pagina {self.page + 1} / {max(1, (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE)}", (365, 865), MUTED)
