"""
GUI oparte na architekturze MVP.

Pakiet odpowiada za wyświetlanie gry przy użyciu biblioteki `pygame-ce`.
Warstwa wizualna została odseparowana od logiki,
zostawiając widok sterowany przez głównego prezentera.

### Najważniejsze komponenty:
- `sq64_ui.controller.Controller` - Prezenter (MVP). Steruje modelem i nakazuje odświeżenie widoków.
- `sq64_ui.gui.Widget` - Baza autorskiego frameworka widgetów.
- `sq64_ui.player.Player` - Interfejs wzorca Strategii do polimorficznej obsługi ruchów (Człowiek/Bot).
"""
