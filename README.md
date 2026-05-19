# Web Scraper v2

A comprehensive web scraping tool that extracts text content from websites and their internal links, outputting the content to organized text files.

## Features

- 🌐 Scrape websites and follow internal links
- 📝 Extract clean text content from HTML pages
- 📁 Output up to 300 organized .txt files
- 🖥️ Command-line interface (CLI) 
- 📓 Jupyter notebook for interactive testing
- 🧪 Comprehensive test suite
- 🎨 Code formatting with Black and isort
- 🔍 Linting with flake8 and type checking with mypy

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Command Line Interface

```bash
# Basic scraping
python -m web_scraper scrape https://example.com

# Specify output directory and max files
python -m web_scraper scrape https://example.com --output-dir ./scraped_docs/scraped_data --max-files 100

# Include external links (default: internal only)
python -m web_scraper scrape https://example.com --include-external

# Restrict to a path prefix (start URL path must begin with this prefix)
python -m web_scraper scrape https://example.com/docs/guide --output-dir ./docs --path-prefix /docs
```

### Jupyter Notebook

Open `scraper_notebook.ipynb` to interactively test and experiment with the scraping functionality.

## Development

### Running Tests
```bash
pytest tests/ -v --cov=web_scraper
```

### Code Formatting
```bash
black web_scraper/ tests/
isort web_scraper/ tests/
```

### Linting
```bash
flake8 web_scraper/ tests/
mypy web_scraper/
```

## Project Structure

```
scraper-main/
├── web_scraper/           # Main package
│   ├── __init__.py
│   ├── scraper.py        # Core scraping logic
│   ├── cli.py            # Command-line interface
│   └── utils.py          # Utility functions
├── tests/                # Test suite
├── scraped_docs/         # Scraped site output (default CLI target: scraped_docs/scraped_data)
├── scraper_notebook.ipynb # Jupyter notebook
├── requirements.txt      # Dependencies
├── setup.cfg            # Configuration
└── README.md            # Documentation
```
