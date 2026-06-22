"""
A GUI based on the MVP architecture.

The package is responsible for rendering the game using the `pygame-ce` library.
The visual layer has been separated from the logic,
leaving the view controlled by the main presenter.

### Key components:
- `sq64_ui.controller.Controller` - Presenter (MVP). Controls the model and instructs the views to refresh.
- `sq64_ui.gui.Widget` - The foundation of the custom widget framework.
- `sq64_ui.player.Player` - Strategy pattern interface for polymorphic handling of moves (Human/Bot).
"""
