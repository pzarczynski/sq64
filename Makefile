.PHONY: all uci wrap test perft profile clean match

all: wrap
	uv run sq64-gui

wrap:
	@echo '#!/bin/bash' > sq64.sh
	@echo 'cd "$$(dirname "$$0")"' >> sq64.sh
	@echo 'uv run sq64-uci' >> sq64.sh
	@chmod +x sq64.sh

uci:
	uv run sq64-uci

test: 
	uv run pytest -v

perft:
	uv run sq64-perft 5
	
profile:
	uv run -m vmprof -o profile.vmprof -m sq64.chess 5
	uv run -m vmprof.show profile.vmprof flat

clean:
	rm -rf sq64.sh profile.vmprof .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +

distclean: clean
	rm -rf .venv