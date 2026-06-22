# sq64 - silnik szachowy + interfejs graficzny

## Uruchomienie

Jedyne narzędzie wymagane do uruchomienia projektu to `uv`.

### Instalacja `uv`
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Uruchomienie GUI
```bash
make
```

### Komunikacja z silnikiem poprzez UCI
```bash
make uci
```

#### Eksport jako skrypt (do uzycia z innym GUI np. Arena)

```bash
make wrap
./sq64.sh
```

### Testy
```bash
make test
```

### Problemy
Jeżeli z jakiegoś powodu pojawiłyby się problemy (lub potrzeba budowania zależności) można zmienić wersję pythona z używanego przeze mnie PyPy (Python z kompuilatorem JIT) na zwykłego CPythona
```bash
uv python pin cpython@3.11
make
```

## Dokumentacja

Dokumentacja znajduje się pod adresem https://pzarczynski.github.io/sq64/.

Do tworzenia dokumentacji częsciowo używałem AI i jest to jedyne wykorzystanie AI w tym projekcie.

## Opis

Przez złożoność projektu musiałem rozdzielić go na kilka pakietów:

### `sq64-chess`
Implementuje zasady gry (FIDE) i generator ruchów. Stan planszy oparty jest na [reprezentacji 0x88](https://www.chessprogramming.org/0x88). Zawiera mechanizm do testowania wydajności i poprawności generatora ([perft](https://www.chessprogramming.org/Perft)).

### `sq64-engine`
Prosty silnik wykorzystujący [PVS](https://www.chessprogramming.org/Principal_Variation_Search) (używany np. w Stockfishu, rozszerzenie algorytmu [Alpha-Beta](https://www.chessprogramming.org/Alpha-Beta)) Wykorzystuje też kilka optymalizacji takich jak: [LMR](https://www.chessprogramming.org/Late_Move_Reductions), [NMP](https://www.chessprogramming.org/Null_Move_Pruning), [Quiescence Search](https://www.chessprogramming.org/Quiescence_Search) oraz [tablice transpozycji](https://www.chessprogramming.org/Transposition_Table). Komunikacja z interfejsem zachodzi przez [UCI](https://www.chessprogramming.org/UCI).

### `sq64-ui`
GUI napisane z wykorzystaniem biblioteki `pygame-ce` i architektury MVP. Zawiera prosty framework do zarządzania oknami, menu i nakładkami. Oddziela logikę od renderowania, używając pasywnych widoków aktualizowanych przez główny kontroler, który też polimorficznie zarządza wejściem od gracza i bota.

## Diagram klas

![Diagram klas](diagram.png)
