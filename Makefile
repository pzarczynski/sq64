.PHONY: all gui uci wrapper test perft profile clean match

all: wrapper

gui: wrapper
	uv run -m sq64.gui

uci:
	uv run -m sq64.uci

wrapper:
	@echo '#!/bin/bash' > sq64.sh
	@echo 'cd "$$(dirname "$$0")"' >> sq64.sh
	@echo 'uv run python -u -m sq64.uci' >> sq64.sh
	@chmod +x sq64.sh

test: 
	uv run pytest -v

perft:
	uv run -m sq64.perft

profile:
	uv run -m vmprof -o profile.vmprof -m sq64.perft
	uv run -m vmprof.show profile.vmprof flat

clean:
	rm -rf sq64.sh sq64.bat profile.vmprof
	find . -type d -name "__pycache__" -exec rm -rf {} +

match: wrapper
	cutechess-cli \
		-engine cmd=./sq64.sh name="sq64" \
		-engine cmd=./sunfish.sh name="Sunfish" \
		-each tc=10+0.1 proto=uci \
		-openings file=openings.epd format=epd order=random \
		-repeat -games 2 \
		-rounds 10 \
		-concurrency 4 \
		-recover