"""Load and insert Wikipedia embeddings into SurrealDB"""

import ast
import asyncio
import logging
import string
import zipfile

import pandas as pd
import surrealdb
import tqdm
import wget

FORMATTED_RECORD_FOR_INSERT_WIKI_EMBEDDING = string.Template(
    """{url: "$url", title: s"$title", text: s"$text", title_vector: $title_vector, content_vector: $content_vector}"""
)

INSERT_WIKI_EMBEDDING_QUERY = string.Template(
    """
    BEGIN TRANSACTION;
    INSERT INTO wiki_embeddings [\n $records\n];
    COMMIT TRANSACTION;
    """
)

TOTAL_ROWS = 25000
CHUNK_SIZE = 100


def setup_logger(name: str) -> logging.Logger:
    """Configure and return a logger with the given name."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


def get_data() -> None:
    """Extract `vector_database_wikipedia_articles_embedded.csv` to `/data`."""
    logger = setup_logger("get-data")

    logger.info("Downloading Wikipedia")
    wget.download(
        url="https://cdn.openai.com/API/examples/data/"
        "vector_database_wikipedia_articles_embedded.zip",
        out="data/vector_database_wikipedia_articles_embedded.zip",
    )

    logger.info("Extracting")
    with zipfile.ZipFile(
        "data/vector_database_wikipedia_articles_embedded.zip", "r"
    ) as zip_ref:
        zip_ref.extractall("data")

    logger.info("Extracted file successfully. Please check the data folder")


async def _surreal_insert() -> None:
    """Main entrypoint to insert Wikipedia embeddings into SurrealDB."""
    logger = setup_logger("surreal_insert")

    total_chunks = TOTAL_ROWS // CHUNK_SIZE + (
        1 if TOTAL_ROWS % CHUNK_SIZE else 0
    )

    logger.info("Connecting to SurrealDB")
    connection = surrealdb.AsyncSurrealDB("ws://localhost:8080/rpc")
    await connection.connect()
    await connection.signin(data={"username": "root", "password": "root"})
    await connection.use_namespace("test")
    await connection.use_database("test")

    logger.info("Inserting rows into SurrealDB")
    with tqdm.tqdm(total=total_chunks, desc="Inserting") as pbar:
        for chunk in tqdm.tqdm(
            pd.read_csv(
                "data/vector_database_wikipedia_articles_embedded.csv",
                usecols=[
                    "url",
                    "title",
                    "text",
                    "title_vector",
                    "content_vector",
                ],
                chunksize=CHUNK_SIZE,
            ),
        ):
            formatted_rows = [
                FORMATTED_RECORD_FOR_INSERT_WIKI_EMBEDDING.substitute(
                    url=row["url"],
                    title=row["title"]
                    .replace("\\", "\\\\")
                    .replace('"', '\\"'),
                    text=row["text"].replace("\\", "\\\\").replace('"', '\\"'),
                    title_vector=ast.literal_eval(row["title_vector"]),
                    content_vector=ast.literal_eval(row["content_vector"]),
                )
                for _, row in chunk.iterrows()  # type: ignore
            ]
            await connection.query(
                query=INSERT_WIKI_EMBEDDING_QUERY.substitute(
                    records=",\n ".join(formatted_rows)
                )
            )
            pbar.update(1)


def surreal_insert() -> None:
    asyncio.run(_surreal_insert())
