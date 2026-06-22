"""
Silnik szachowy.

Pakiet rozszerza rdzeń gry o inkrementalną ewaluację pozycji i implementuje
przeszukiwanie drzewa decyzyjnego z użyciem algorytmu **PVS (Alpha-Beta)**.

### Ważne komponenty:
- `sq64_engine.client.UCI` - asynchroniczny klient do komunikacji międzyprocesowej.
"""


from . import client, engine, position, uci
from .client import UCI

__all__ = ["UCI", "client", "engine", "position", "uci"]
