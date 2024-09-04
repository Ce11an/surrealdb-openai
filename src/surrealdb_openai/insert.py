"""Insert Wikipedia data into SurrealDB."""

import ast
import string

import pandas as pd
import surrealdb
import tqdm

from surrealdb_openai import loggers

FORMATTED_RECORD_FOR_INSERT_WIKI_EMBEDDING = string.Template(
    """{url: "$url", title: s"$title", text: s"$text", title_vector: $title_vector, content_vector: $content_vector}"""
)

INSERT_WIKI_EMBEDDING_QUERY = string.Template(
    """
    INSERT INTO wiki_embedding [\n $records\n];
    """
)

TOTAL_ROWS = 25000
CHUNK_SIZE = 100


def surreal_insert() -> None:
    """Main entrypoint to insert Wikipedia embeddings into SurrealDB."""
    logger = loggers.setup_logger("SurrealInsert")

    total_chunks = TOTAL_ROWS // CHUNK_SIZE + (
        1 if TOTAL_ROWS % CHUNK_SIZE else 0
    )

    connection = surrealdb.SurrealDB("ws://localhost:8080/rpc")
    connection.signin(data={"username": "root", "password": "root"})
    connection.use_namespace("test")
    connection.use_database("test")

    logger.info("Connected to SurrealDB")

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
                for _, row in chunk.iterrows()
            ]
            connection.query(
                query=INSERT_WIKI_EMBEDDING_QUERY.substitute(
                    records=",\n ".join(formatted_rows)
                )
            )
            pbar.update(1)
