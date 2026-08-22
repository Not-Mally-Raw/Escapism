.PHONY: setup test clean

setup:
	@echo "Setting up Razorpay Revenue Recovery environment..."
	uv venv .venv
	uv pip install -e ".[dev]"
	@echo "Setup complete! Run 'make test' to verify."

test:
	.venv/bin/pytest

clean:
	rm -rf .venv
	rm -rf .pytest_cache
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
