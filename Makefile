.PHONY: help install test lint format clean dev-setup notebook docker-up docker-scrape docs

help:
	@echo "Available commands:"
	@echo "  install        - Install the package and dependencies"
	@echo "  dev-setup      - Set up development environment"
	@echo "  test           - Run tests with coverage"
	@echo "  lint           - Run linting checks"
	@echo "  format         - Format code with black and isort"
	@echo "  clean          - Clean up build artifacts"
	@echo "  notebook       - Create Jupyter notebook from example"
	@echo "  demo           - Run interactive demo"
	@echo "  docker-up      - Start Ollama and ChromaDB services"
	@echo "  docker-scrape  - Run scraper-agent (set URL=...)"
	@echo "  docs           - Start Docusaurus docs locally"

install:
	pip install -r requirements.txt
	pip install -e .

dev-setup:
	pip install -r requirements.txt
	pip install -e .
	@echo "Development environment set up successfully!"
	@echo "Run 'make test' to verify everything is working."

test:
	pytest tests/ -v --cov=web_scraper --cov-report=html --cov-report=term

lint:
	flake8 web_scraper/ tests/
	mypy web_scraper/

format:
	black web_scraper/ tests/
	isort web_scraper/ tests/
	@echo "Code formatted successfully!"

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

notebook:
	@echo "Creating Jupyter notebook..."
	jupyter nbconvert --to notebook notebook_example.py --output scraper_notebook.ipynb
	@echo "Notebook created: scraper_notebook.ipynb"

demo:
	python notebook_example.py

# Development workflow
check: format lint test
	@echo "All checks passed!"

# Quick test command
quick:
	pytest tests/ -x -v

# Run specific test file
test-utils:
	pytest tests/test_utils.py -v

test-scraper:
	pytest tests/test_scraper.py -v

docker-up:
	docker compose up -d ollama chromadb

docker-scrape:
	docker compose --profile scrape run --rm scraper-agent scrape $(URL) $(ARGS)

native-scrape:
	./scripts/scrape-native.sh $(URL) $(ARGS)

docs:
	cd docs && npm install && npm run start
