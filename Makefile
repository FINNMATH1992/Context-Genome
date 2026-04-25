HOST ?= 127.0.0.1
PORT ?= 8765
PYTHON ?= python

.PHONY: run doctor test check clean

run:
	CONTEXT_GENOME_HOST="$(HOST)" CONTEXT_GENOME_PORT="$(PORT)" PYTHON="$(PYTHON)" ./run.sh

doctor:
	$(PYTHON) -B scripts/doctor.py --host "$(HOST)" --port "$(PORT)"

test:
	$(PYTHON) -B -m unittest discover -s tests

check:
	$(PYTHON) -B scripts/doctor.py --json --port 0 >/dev/null
	$(PYTHON) -B -m compileall context_genome skill_garden tests scripts
	$(PYTHON) -B -m unittest discover -s tests
	node --check context_genome/web/app.js
	$(PYTHON) -B scripts/check_repository_hygiene.py

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.py[cod]' -delete
