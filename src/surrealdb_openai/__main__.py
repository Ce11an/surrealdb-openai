"""Load and insert Wikipedia embeddings into SurrealDB"""

import ast
import contextlib
import logging
import string
import zipfile

import fastapi
import pandas as pd
import surrealdb
import tqdm
import wget
from fastapi import templating, responses, staticfiles

FORMATTED_RECORD_FOR_INSERT_WIKI_EMBEDDING = string.Template(
    """{url: "$url", title: s"$title", text: s"$text", title_vector: $title_vector, content_vector: $content_vector}"""
)

INSERT_WIKI_EMBEDDING_QUERY = string.Template(
    """
    INSERT INTO wiki_embeddings [\n $records\n];
    """
)

TOTAL_ROWS = 25000
CHUNK_SIZE = 100


def extract_numeric_id(surrealdb_id: str) -> str:
    return surrealdb_id.split(":")[1]


templates = templating.Jinja2Templates(directory="templates")
templates.env.filters["extract_numeric_id"] = extract_numeric_id
database = {}


@contextlib.asynccontextmanager
async def lifespan(_: fastapi.FastAPI):
    connection = surrealdb.AsyncSurrealDB(url="ws://localhost:8080/rpc")
    await connection.connect()
    await connection.signin(data={"username": "root", "password": "root"})
    await connection.use_namespace("test")
    await connection.use_database("test")
    database["surrealdb"] = connection
    yield
    database.clear()


app = fastapi.FastAPI(lifespan=lifespan)
app.mount("/static", staticfiles.StaticFiles(directory="static"), name="static")


@app.get("/", response_class=responses.HTMLResponse)
async def get_index(request: fastapi.Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/new_chat", response_class=responses.HTMLResponse)
async def new_chat(request: fastapi.Request):
    chat_title = "Untitled chat"
    chat_record = await database["surrealdb"].query(
        f"""CREATE ONLY chat SET title = '{chat_title}';"""
    )
    return templates.TemplateResponse(
        "new_chat.html",
        {
            "request": request,
            "chat_id": chat_record.get("id"),
            "chat_title": chat_title,
        },
    )


@app.get("/load_chat/{chat_id}", response_class=responses.HTMLResponse)
async def load_chat(request: fastapi.Request, chat_id: str):
    message_records = await database["surrealdb"].query(
        f"""
        SELECT
            out.role AS role,
            out.content AS content,
            time.written AS time_written
        FROM {chat_id}->sent
        ORDER BY time_written
        FETCH out
        """
    )
    return templates.TemplateResponse(
        "load_chat.html",
        {
            "request": request,
            "messages": message_records,
            "chat_id": chat_id,
        },
    )


@app.get("/conversations", response_class=responses.HTMLResponse)
async def get_conversations(request: fastapi.Request):
    chat_records = await database["surrealdb"].query("""SELECT id, title FROM chat;""")
    return templates.TemplateResponse(
        "conversations.html", {"request": request, "chats": chat_records}
    )


@app.post("/send_message", response_class=responses.HTMLResponse)
async def send_message(
    request: fastapi.Request,
    chat_id: str = fastapi.Form(...),
    content: str = fastapi.Form(...),
):
    message_record = await database["surrealdb"].query(
        f"""CREATE ONLY message SET role = 'user', content = '{content}';"""
    )

    await database["surrealdb"].query(
        f"""
        RELATE {chat_id}->sent->{message_record.get("id")}
            SET time.written = time::now();
        """
    )

    return templates.TemplateResponse(
        "send_message.html",
        {
            "request": request,
            "chat_id": chat_id,
            "content": message_record.get("content"),
        },
    )


@app.get("/get_response/{chat_id}", response_class=responses.HTMLResponse)
async def get_response(request: fastapi.Request, chat_id: str):
    #TODO: Get response from RAG
    response_from_assistant = "This is a simulated response."

    message_record = await database["surrealdb"].query(
        f"""CREATE ONLY message SET role = 'system', content = '{response_from_assistant}';"""
    )

    await database["surrealdb"].query(
        f"""
        RELATE {chat_id}->sent->{message_record.get("id")}
            SET time.written = time::now();
        """
    )

    chat_record = await database["surrealdb"].query(
        f"""
        SELECT title FROM ONLY {chat_id};
        """
    )

    create_title = chat_record["title"] == "Untitled chat"
    return templates.TemplateResponse("system_message.html", {
        "request": request,
        "content": response_from_assistant,
        "create_title": create_title,
        "chat_id": chat_id
    })

@app.get("/create_title/{chat_id}", response_class=responses.PlainTextResponse)
async def create_title(chat_id: str):
    # TODO: get name from OpenAI
    chat_record = await database["surrealdb"].query(
        f"""
        UPDATE ONLY {chat_id} SET title = "I love Annie Nieh-{chat_id};"
        """
    )
    return responses.PlainTextResponse(chat_record.get("title"))


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


def surreal_insert() -> None:
    """Main entrypoint to insert Wikipedia embeddings into SurrealDB."""
    logger = setup_logger("surreal_insert")

    total_chunks = TOTAL_ROWS // CHUNK_SIZE + (
        1 if TOTAL_ROWS % CHUNK_SIZE else 0
    )

    logger.info("Connecting to SurrealDB")
    connection = surrealdb.SurrealDB("ws://localhost:8080/rpc")
    connection.signin(data={"username": "root", "password": "root"})
    connection.use_namespace("test")
    connection.use_database("test")

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
            connection.query(
                query=INSERT_WIKI_EMBEDDING_QUERY.substitute(
                    records=",\n ".join(formatted_rows)
                )
            )
            pbar.update(1)
