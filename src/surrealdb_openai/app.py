"""Backend for SurrealDB chat interface."""

import os

import contextlib
import datetime
from typing import AsyncGenerator

import fastapi
import surrealdb
import dotenv
from fastapi import templating, responses, staticfiles


dotenv.load_dotenv()


def extract_id(surrealdb_id: str) -> str:
    """Extract numeric ID from SurrealDB record ID.

    SurrealDB record ID comes in the form of `<table_name>:<unique_id>`.
    CSS classes cannot be named with a `:` so for CSS we extract the ID.

    Args:
        surrealdb_id: SurrealDB record ID.

    Returns:
        ID.
    """
    return surrealdb_id.split(":")[1]


def convert_timestamp_to_date(timestamp: str) -> str:
    """Convert a SurrealDB `datetime` to a readable string.

    The result will be of the format: `April 05 2024, 15:30`.

    Args:
        timestamp: SurrealDB `datetime` value.

    Returns:
        Date as a string.
    """
    parsed_timestamp = datetime.datetime.fromisoformat(timestamp.rstrip("Z"))
    return parsed_timestamp.strftime("%B %d %Y, %H:%M")


templates = templating.Jinja2Templates(directory="templates")
templates.env.filters["extract_id"] = extract_id
templates.env.filters["convert_timestamp_to_date"] = convert_timestamp_to_date
life_span = {}


@contextlib.asynccontextmanager
async def lifespan(_: fastapi.FastAPI) -> AsyncGenerator:
    """FastAPI lifespan to create and destroy objects."""
    openai_token = os.environ["OPENAI_TOKEN"]

    connection = surrealdb.AsyncSurrealDB(url="ws://localhost:8080/rpc")
    await connection.connect()
    await connection.signin(data={"username": "root", "password": "root"})
    await connection.use_namespace("test")
    await connection.use_database("test")
    await connection.set(key="openai_token", value=openai_token)
    life_span["surrealdb"] = connection
    yield
    life_span.clear()


app = fastapi.FastAPI(lifespan=lifespan)
app.mount("/static", staticfiles.StaticFiles(directory="static"), name="static")


@app.get("/", response_class=responses.HTMLResponse)
async def index(request: fastapi.Request) -> responses.HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/chats", response_class=responses.HTMLResponse)
async def create_chat(request: fastapi.Request) -> responses.HTMLResponse:
    """Create a chat."""
    chat_record = await life_span["surrealdb"].query(
        """RETURN fn::create_chat();"""
    )
    return templates.TemplateResponse(
        "create_chat.html",
        {
            "request": request,
            "chat_id": chat_record.get("id"),
            "chat_title": chat_record.get("title"),
        },
    )


@app.get("/chats/{chat_id}", response_class=responses.HTMLResponse)
async def load_chat(
    request: fastapi.Request, chat_id: str
) -> responses.HTMLResponse:
    """Load a chat."""
    message_records = await life_span["surrealdb"].query(
        f"""RETURN fn::load_chat({chat_id})"""
    )
    return templates.TemplateResponse(
        "load_chat.html",
        {
            "request": request,
            "messages": message_records,
            "chat_id": chat_id,
        },
    )


@app.get("/chats", response_class=responses.HTMLResponse)
async def load_all_chats(request: fastapi.Request) -> responses.HTMLResponse:
    """Load all chats."""
    chat_records = await life_span["surrealdb"].query(
        """RETURN fn::load_all_chats();"""
    )
    return templates.TemplateResponse(
        "chats.html", {"request": request, "chats": chat_records}
    )


@app.post(
    "/chats/{chat_id}/send-user-message", response_class=responses.HTMLResponse
)
async def send_user_message(
    request: fastapi.Request,
    chat_id: str,
    content: str = fastapi.Form(...),
) -> responses.HTMLResponse:
    """Send user message."""
    message = await life_span["surrealdb"].query(
        f"""RETURN fn::create_user_message({chat_id}, s"{content}");"""
    )
    return templates.TemplateResponse(
        "send_user_message.html",
        {
            "request": request,
            "chat_id": chat_id,
            "content": message.get("content"),
            "timestamp": message.get("timestamp"),
        },
    )


@app.post(
    "/chats/{chat_id}/send-system-message",
    response_class=responses.HTMLResponse,
)
async def send_system_message(
    request: fastapi.Request, chat_id: str
) -> responses.HTMLResponse:
    """Send system message."""
    message = await life_span["surrealdb"].query(
        f"""RETURN fn::create_system_message({chat_id});"""
    )

    title = await life_span["surrealdb"].query(
        f"""RETURN fn::get_chat_title({chat_id});"""
    )

    return templates.TemplateResponse(
        "send_system_message.html",
        {
            "request": request,
            "content": message.get("content"),
            "timestamp": message.get("timestamp"),
            "create_title": title == "Untitled chat",
            "chat_id": chat_id,
        },
    )


@app.post("/chats/{chat_id}/title", response_class=responses.PlainTextResponse)
async def create_title(chat_id: str) -> responses.PlainTextResponse:
    """Create chat title."""
    title = await life_span["surrealdb"].query(
        f"RETURN fn::generate_chat_title({chat_id});"
    )
    return responses.PlainTextResponse(title.strip('"'))
