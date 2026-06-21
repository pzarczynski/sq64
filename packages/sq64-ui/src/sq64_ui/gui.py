from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

import pygame


@dataclass(slots=True, frozen=True)
class Event: ...


@dataclass(slots=True, frozen=True)
class ClickEvent(Event):
    pos: tuple[int, int]


E = TypeVar("E", bound=Event)
Handler = Callable[[E], Any]


class EventBus:
    _handlers: dict[type[Event], set[Callable[[Any], Any]]]

    def __init__(self) -> None:
        self._handlers = defaultdict(set)

    def register(self, event_type: type[E], handler: Handler[E]) -> None:
        self._handlers[event_type].add(handler)

    def unregister(self, event_type: type[E], handler: Handler[E]) -> None:
        self._handlers[event_type].discard(handler)

    def emit(self, event: Event) -> None:
        for handler in self._handlers[type(event)]:
            handler(event)


class RGB(tuple[int, int, int], Enum):
    __slots__ = ()

    BLACK    = (  0,   0,   0)
    WHITE    = (255, 255, 255)
    RED      = (255,   0,   0)
    GREEN    = (  0, 255,   0)
    YELLOW   = (255, 255,   0)
    GRAY     = ( 50,  50,  50)
    DARKGRAY = ( 30,  30,  30)

    def with_alpha(self, alpha: int) -> "ColorLike":
        return (self[0], self[1], self[2], alpha)

ColorLike = RGB | tuple[int, int, int] | tuple[int, int, int, int]


class Widget:
    _rect: pygame.Rect

    def __init__(self) -> None:
        self._rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, screen: pygame.Surface) -> None:
        return

    def handle_event(self, event: Event) -> bool:
        return False

    def layout(self, rect: pygame.Rect) -> None:
        self._rect = rect

W = TypeVar("W", bound=Widget)


class Text(Widget):
    def __init__(self, text: str, color: RGB, scale: float = 0.6) -> None:
        super().__init__()
        self._text = text
        self._color = color
        self._scale = scale
        self._surf: pygame.Surface | None = None

    def set_text(self, text: str) -> None:
        if self._text != text:
            self._text = text
            self._render()

    def _render(self) -> None:
        if not self._text or self._rect.w <= 0 or self._rect.h <= 0:
            self._surf = None
            return

        base_size = 100
        base_font = pygame.font.SysFont(None, base_size)
        text_w, text_h = base_font.size(self._text)

        if text_w == 0 or text_h == 0:
            self._surf = None
            return

        ratio = min(self._rect.w / text_w, self._rect.h / text_h)
        font_size = max(1, int(base_size * ratio * self._scale))
        font = pygame.font.SysFont(None, font_size)
        self._surf = font.render(self._text, True, self._color)

    def layout(self, rect: pygame.Rect) -> None:
        if self._rect == rect and self._surf is not None:
            return

        super().layout(rect)
        self._render()

    def draw(self, screen: pygame.Surface) -> None:
        if self._surf:
            screen.blit(self._surf, self._surf.get_rect(center=self._rect.center))


class Image(Widget):
    def __init__(
        self, surf: pygame.Surface | None = None, padding: float = 0.0,
    ) -> None:
        super().__init__()
        self._orig_surf = surf
        self._padding = padding
        self._surf: pygame.Surface | None = None

    def set_surf(self, surf: pygame.Surface) -> None:
        self._orig_surf = surf
        self.layout(self._rect)

    def layout(self, rect: pygame.Rect) -> None:
        if self._rect == rect and self._surf is not None:
            return

        super().layout(rect)
        if self._orig_surf:
            s = int(min(rect.w, rect.h) * (1 - self._padding))
            self._surf = pygame.transform.smoothscale(self._orig_surf, (s, s))

    def draw(self, screen: pygame.Surface) -> None:
        if self._surf:
            screen.blit(self._surf, self._surf.get_rect(center=self._rect.center))


class Button(Widget):
    def __init__(
        self, child: Widget, on_click: Callable[[], None], bg: RGB | None = None,
    ) -> None:
        super().__init__()
        self._child = child
        self._on_click = on_click
        self._bg = bg

    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        self._child.layout(rect)

    def handle_event(self, event: Event) -> bool:
        if isinstance(event, ClickEvent) and self._rect.collidepoint(event.pos):
            self._on_click()
            return True
        return self._child.handle_event(event)

    def draw(self, screen: pygame.Surface) -> None:
        if self._bg:
            pygame.draw.rect(screen, self._bg, self._rect)
        self._child.draw(screen)

    @classmethod
    def from_text(
        cls,
        text: str,
        onclick: Callable[[], None],
        scale: float = 0.7,
        color: RGB = RGB.WHITE,
        bg: RGB | None = RGB.GRAY,
    ) -> "Button":
        return cls(Text(text, color, scale=scale), on_click=onclick, bg=bg)


class Box(Widget, ABC):
    _children: list[Widget]
    _weights: list[float]

    def __init__(
        self,
        *children: Widget,
        weights: list[float] | None = None,
        spacing: float = 0,
    ) -> None:
        super().__init__()
        assert weights is None or len(weights) == len(children)
        self._spacing = spacing
        self._children = list(children)
        self._weights = weights or ([1.0] * len(children))

    def handle_event(self, event: Event) -> bool:
        return any(c.handle_event(event) for c in reversed(self._children))

    def draw(self, screen: pygame.Surface) -> None:
        for c in self._children:
            c.draw(screen)

    @abstractmethod
    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)

    @classmethod
    def pad(cls, *ch: Widget, pad: float, spacing: float = 0) -> "Box":
        w = [1 - 2 * pad] * len(ch)
        return cls(Widget(), *ch, Widget(), weights=[pad, *w, pad], spacing=spacing)


class HBox(Box):
    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        if not self._children:
            return
        spacing = self._spacing * rect.w
        total_spacing = spacing * (len(self._children) - 1)
        available_w = rect.w - total_spacing
        total_weight = sum(self._weights)
        x = rect.x
        for c, w in zip(self._children, self._weights, strict=True):
            w_px = (w / total_weight) * available_w if total_weight > 0 else 0
            c.layout(pygame.Rect(int(x), rect.y, int(w_px), rect.h))
            x += w_px + spacing


class VBox(Box):
    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        if not self._children:
            return
        spacing = self._spacing * rect.h
        total_spacing = spacing * (len(self._children) - 1)
        available_h = rect.h - total_spacing
        total_weight = sum(self._weights)
        y = rect.y
        for c, w in zip(self._children, self._weights, strict=True):
            h_px = (w / total_weight) * available_h if total_weight > 0 else 0
            c.layout(pygame.Rect(rect.x, int(y), rect.w, int(h_px)))
            y += h_px + spacing


class StackBox(Box):
    def __init__(self, *children: Widget) -> None:
        super().__init__(*children, spacing=0)
        self._active_index = 0

    def set_active(self, index: int) -> None:
        if 0 <= index < len(self._children):
            self._active_index = index

    def handle_event(self, event: Event) -> bool:
        if not self._children:
            return False
        return self._children[self._active_index].handle_event(event)

    def draw(self, screen: pygame.Surface) -> None:
        if self._children:
            self._children[self._active_index].draw(screen)

    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        for c in self._children:
            c.layout(rect)


class Grid(Widget, Generic[W]):
    _cells: list[W]

    def __init__(
        self,
        factory: Callable[[], W],
        rows: int = 1,
        cols: int = 1,
        spacing: float = 0,
        bg: Image | None = None,
    ) -> None:
        super().__init__()
        self._rows = rows
        self._cols = cols
        self._spacing = spacing
        self._bg = bg

        self._cells = [factory() for _ in range(rows * cols)]

    def __setitem__(self, rowcol: tuple[int, int], widget: W) -> None:
        row, col = rowcol
        self._cells[row * self._cols + col] = widget

    def __getitem__(self, rowcol: tuple[int, int]) -> W:
        row, col = rowcol
        return self._cells[row * self._cols + col]

    def __iter__(self) -> Iterable[W]:
        yield from self._cells

    def set_bg(self, bg: Image) -> None:
        self._bg = bg

    def handle_event(self, event: Event) -> bool:
        return any(c and c.handle_event(event) for c in reversed(self._cells))

    def draw(self, screen: pygame.Surface) -> None:
        if self._bg:
            self._bg.draw(screen)
        for c in self._cells:
            if c:
                c.draw(screen)

    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        if self._bg:
            self._bg.layout(rect)

        cell_w = rect.w / self._cols
        cell_h = rect.h / self._rows
        spacing_w = cell_w * self._spacing
        spacing_h = cell_h * self._spacing
        for r in range(self._rows):
            for c in range(self._cols):
                cell = self._cells[r * self._cols + c]
                if cell:
                    x = rect.x + c * cell_w + spacing_w / 2
                    y = rect.y + r * cell_h + spacing_h / 2
                    w = cell_w - spacing_w
                    h = cell_h - spacing_h
                    cell.layout(pygame.Rect(x, y, w, h))


K = TypeVar("K")


class WidgetDict(Widget, Generic[K]):
    def __init__(self, x: dict[K, Widget] | None = None) -> None:
        super().__init__()
        self._widgets = x or {}

    def __setitem__(self, key: K, widget: Widget) -> None:
        self._widgets[key] = widget

    def __getitem__(self, key: K) -> Widget | None:
        return self._widgets.get(key)

    def clear(self) -> None:
        self._widgets.clear()

    def pop(self, key: K) -> Widget | None:
        return self._widgets.pop(key, None)

    def handle_event(self, event: Event) -> bool:
        return any(
            w.handle_event(event) for w in reversed(list(self._widgets.values()))
        )

    def draw(self, screen: pygame.Surface) -> None:
        for _, w in sorted(self._widgets.items()):
            w.draw(screen)

    def layout(self, rect: pygame.Rect) -> None:
        super().layout(rect)
        for _, w in sorted(self._widgets.items()):
            w.layout(rect)


class Window(ABC, Generic[W]):
    root: W

    def __init__(self, width: float, height: float, title: str) -> None:
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()
        self.running = False
        self.bus = EventBus()

    def set_root(self, root: W) -> None:
        self.root = root
        if self.running:
            self.root.layout(self.screen.get_rect())

    def run(self) -> None:
        self.running = True
        self.root.layout(self.screen.get_rect())
        while self.running:
            dt = self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.root.layout(self.screen.get_rect())
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.root.handle_event(ClickEvent(event.pos))
            self.update(dt)
            self.screen.fill((30, 30, 30))
            self.root.draw(self.screen)
            pygame.display.flip()
        pygame.quit()

    @abstractmethod
    def update(self, dt: int) -> None: ...
