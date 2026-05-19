#!/usr/bin/env python3
"""Script to create a Jupyter notebook from the Python example."""

import json
from pathlib import Path

# Read the notebook example file
with open('notebook_example.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Split content into cells based on comments that start with "# Cell"
cells = []
current_cell = []
lines = content.split('\n')

for line in lines:
    if line.startswith('# Cell ') and current_cell:
        # Create a code cell from current content
        cell_content = '\n'.join(current_cell)
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": cell_content.split('\n')
        })
        current_cell = []
    else:
        current_cell.append(line)

# Add the last cell
if current_cell:
    cell_content = '\n'.join(current_cell)
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": cell_content.split('\n')
    })

# Create the notebook structure
notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {
                "name": "ipython",
                "version": 3
            },
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.8.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

# Write the notebook file
with open('scraper_notebook.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook, f, indent=2)

print("✓ Created scraper_notebook.ipynb")
print("You can now open it with: jupyter notebook scraper_notebook.ipynb")
