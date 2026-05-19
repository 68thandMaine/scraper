#!/usr/bin/env python3
"""
Interactive Web Scraper Example
===============================

This script demonstrates how to use the Web Scraper interactively,
similar to a Jupyter notebook. Run this in IPython or Jupyter for
best experience.

To convert this to a proper notebook, run:
jupyter nbconvert --to notebook notebook_example.py --output scraper_notebook.ipynb
"""

# Cell 1: Import libraries and setup
print("=== Web Scraper v2 - Interactive Example ===\n")

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path.cwd()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from web_scraper import WebScraper
from web_scraper.utils import clean_filename, extract_text_content

print("✓ Libraries imported successfully!")

# Cell 2: Basic scraper initialization
print("\n=== Step 1: Initialize the Web Scraper ===")

# Create a scraper instance with custom settings
scraper = WebScraper(
    max_files=10,  # Limit for demonstration
    delay=1.0,     # Be respectful to servers
    timeout=10,    # 10 second timeout
    user_agent="WebScraper-Demo/2.0"
)

print(f"✓ Scraper initialized with max_files={scraper.max_files}")
print(f"✓ Delay between requests: {scraper.delay}s")

# Cell 3: Test URL validation and basic scraping
print("\n=== Step 2: Test Basic Functionality ===")

# Test utility functions
test_html = """
<html>
    <head><title>Test Page Title</title></head>
    <body>
        <h1>Main Heading</h1>
        <p>This is a paragraph with <strong>bold text</strong>.</p>
        <script>console.log('This should be removed');</script>
        <p>Another paragraph here.</p>
    </body>
</html>
"""

# Extract text content
text_content = extract_text_content(test_html)
print("Extracted text content:")
print("-" * 30)
print(text_content)
print("-" * 30)

# Test filename cleaning
test_titles = [
    "My Blog Post: Adventures in Coding!",
    "File/Path*With?Special<>Chars",
    "<h1>HTML Title</h1>",
    "Very Long Title That Should Be Truncated Because It Exceeds The Maximum Length"
]

print("\nFilename cleaning examples:")
for title in test_titles:
    clean_name = clean_filename(title)
    print(f"'{title}' -> '{clean_name}'")

# Cell 4: Interactive scraping demonstration
print("\n=== Step 3: Interactive Scraping Demo ===")

# Example URLs to try (replace with actual URLs you want to test)
demo_urls = [
    "https://httpbin.org/html",  # Simple test page
    "https://example.com",       # Basic example site
    # Add more URLs here for testing
]

print("Demo URLs available:")
for i, url in enumerate(demo_urls, 1):
    print(f"{i}. {url}")

# Uncomment the following lines to actually scrape
# (Be respectful to servers - don't overuse)

print("\n--- To run actual scraping, uncomment the code below ---")
print("""
# Choose a URL to scrape
url_to_scrape = demo_urls[0]  # Change index as needed

# Scrape a single page first
print(f"Scraping single page: {url_to_scrape}")
single_page_result = scraper.scrape_url(url_to_scrape)

if single_page_result:
    print("✓ Successfully scraped page!")
    print(f"Title: {single_page_result['title']}")
    print(f"Content length: {len(single_page_result['content'])} characters")
    print("First 200 characters of content:")
    print(single_page_result['content'][:200] + "...")
else:
    print("✗ Failed to scrape page")
""")

# Cell 5: Full website scraping
print("\n=== Step 4: Full Website Scraping ===")

print("To scrape a full website, use:")
print("""
# Set up output directory
output_directory = "./scraped_docs/demo_scraped_data"

# Scrape the website
results = scraper.scrape_website(
    start_url="https://example.com",
    output_dir=output_directory,
    include_external=False  # Only internal links
)

# Display results
print("Scraping Results:")
print(f"Files created: {results['files_created']}")
print(f"URLs scraped: {results['urls_scraped']}")  
print(f"URLs failed: {results['urls_failed']}")
print(f"Output directory: {results['output_directory']}")

# Get detailed statistics
stats = scraper.get_stats()
print("\\nDetailed Statistics:")
for key, value in stats.items():
    print(f"{key}: {value}")
""")

# Cell 6: Analyzing scraped content
print("\n=== Step 5: Analyzing Scraped Content ===")

print("To analyze scraped content:")
print("""
import os
from collections import Counter
import re

def analyze_scraped_files(directory):
    '''Analyze the scraped text files.'''
    results = {
        'total_files': 0,
        'total_words': 0,
        'total_characters': 0,
        'word_frequency': Counter(),
        'file_sizes': []
    }
    
    for filename in os.listdir(directory):
        if filename.endswith('.txt'):
            filepath = os.path.join(directory, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Skip metadata lines
                lines = content.split('\\n')
                content_start = 0
                for i, line in enumerate(lines):
                    if line.startswith('-' * 50):
                        content_start = i + 2
                        break
                
                actual_content = '\\n'.join(lines[content_start:])
                
                # Count words
                words = re.findall(r'\\b\\w+\\b', actual_content.lower())
                results['word_frequency'].update(words)
                results['total_words'] += len(words)
                results['total_characters'] += len(actual_content)
                results['file_sizes'].append(len(actual_content))
                results['total_files'] += 1
    
    return results

# Example usage:
# analysis = analyze_scraped_files("./scraped_docs/demo_scraped_data")
# print(f"Total files: {analysis['total_files']}")
# print(f"Total words: {analysis['total_words']:,}")
# print(f"Most common words: {analysis['word_frequency'].most_common(10)}")
""")

# Cell 7: Advanced configuration and tips
print("\n=== Step 6: Advanced Configuration ===")

print("Advanced scraper configurations:")
print("""
# For large websites, increase max_files and adjust delay
large_scraper = WebScraper(
    max_files=500,
    delay=2.0,      # Longer delay for large sites
    timeout=30,     # Longer timeout
    user_agent="My-Research-Bot/1.0 (contact@example.com)"
)

# For faster local testing (be careful!)
fast_scraper = WebScraper(
    max_files=50,
    delay=0.5,      # Shorter delay
    timeout=5,      # Shorter timeout
)

# Include external links (use with caution)
external_scraper = WebScraper(max_files=100)
results = external_scraper.scrape_website(
    "https://example.com",
    include_external=True  # This will follow external links too
)
""")

print("\n" + "="*50)
print("TIPS FOR RESPONSIBLE SCRAPING:")
print("="*50)
print("1. Always check robots.txt first")
print("2. Use appropriate delays between requests")
print("3. Respect server resources and bandwidth")
print("4. Consider the website's terms of service")
print("5. For large-scale scraping, contact the website owner")
print("6. Use appropriate User-Agent strings")
print("7. Handle errors gracefully")
print("8. Store scraped data responsibly")

print("\n✓ Interactive example complete!")
print("Copy and paste code blocks into Jupyter cells to experiment!")
