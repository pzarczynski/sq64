from collections.abc import Callable
from dataclasses import dataclass, field

import pygame


@dataclass(slots=True, frozen=True)
class Button:
    surf: pygame.Surface
    on_click: Callable[[], None]
    x: float
    y: float
    width: float | None = None
    height: float | None = None
    bg: tuple[int, int, int] | None = None
    _rect: pygame.Rect = field(init=False)

    def __post_init__(self) -> None:
        w, h = self.surf.get_size()
        width, height = self.width or w, self.height or h
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)

        rect = pygame.Rect(0, 0, width, height)
        rect.center = (self.x, self.y)
        object.__setattr__(self, "_rect", rect)

    def handle_click(self, pos: tuple[int, int]) -> bool:
        if self._rect.collidepoint(pos):
            self.on_click()
            return True
        return False

    def draw(self, screen: pygame.Surface) -> None:
        if self.bg:
            pygame.draw.rect(screen, self.bg, self._rect)
        screen.blit(self.surf, self.surf.get_rect(center=self._rect.center))
