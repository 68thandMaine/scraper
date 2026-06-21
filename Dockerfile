FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt setup.py README.md ./
COPY web_scraper ./web_scraper

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e .

COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV SCRAPED_DATA_DIR=/app/scraped_data

VOLUME ["/app/scraped_data"]

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["scrape", "--help"]
