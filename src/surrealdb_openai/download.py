"""Download OpenAI Wikipedia data."""

import zipfile

import wget

from surrealdb_openai import loggers


def download_data() -> None:
    """Extract `vector_database_wikipedia_articles_embedded.csv` to `/data`."""
    logger = loggers.setup_logger("DownloadData")

    logger.info("Downloading Wikipedia")
    wget.download(
        url="https://cdn.openai.com/API/examples/data/"
        "vector_database_wikipedia_articles_embedded.zip",
        out="data/vector_database_wikipedia_articles_embedded.zip",
    )

    logger.info("Extracting to data directory")
    with zipfile.ZipFile(
        "data/vector_database_wikipedia_articles_embedded.zip", "r"
    ) as zip_ref:
        zip_ref.extractall("data")

    logger.info("Extracted file successfully. Please check the data directory")
