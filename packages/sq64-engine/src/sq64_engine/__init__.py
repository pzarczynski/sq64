"""
Chess engine.

This package extends the game core with incremental position evaluation and implements
decision tree search using the **PVS (Alpha-Beta)** algorithm.

### Important components:
- `sq64_engine.client.UCI` - an asynchronous client for interprocess communication.
"""


from . import client, engine, position, uci
from .client import UCI

__all__ = ["UCI", "client", "engine", "position", "uci"]
