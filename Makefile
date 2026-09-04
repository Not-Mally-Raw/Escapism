.PHONY: setup test run benchmark clean

setup:
	@echo "Setting up environment..."
	python3 -m venv .venv
	.venv/bin/pip install -e .

test:
	.venv/bin/pytest tests/

run:
	.venv/bin/python3 src/api/server.py

benchmark:
	.venv/bin/python3 scripts/run_monte_carlo.py

clean:
	rm -rf .venv .pytest_cache .coverage htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
