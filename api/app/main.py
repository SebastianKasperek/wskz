from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx2
from fastapi import FastAPI, HTTPException
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior

from .agent import RouteDeps, build_agent
from .config import Settings
from .schemas import MessageIn, MessageOut

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("router")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    http_client = httpx2.AsyncClient(timeout=httpx2.Timeout(240.0, connect=10.0))
    app.state.settings = settings
    app.state.http_client = http_client
    app.state.agent = build_agent(settings, http_client)
    logger.info("Agent gotowy, model=%s", settings.ollama_model)
    try:
        yield
    finally:
        await http_client.aclose()


app = FastAPI(
    title="Message Router",
    summary="Router zgłoszeń: lokalny model wybiera dział i sam wysyła e-mail.",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "docs": "/api/v1/docs",
        "messages": "/api/v1/messages",
        "mail_ui": "http://localhost:8025",
    }


@app.get("/api/v1/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/v1/messages",
    response_model=MessageOut,
    tags=["routing"],
    summary="Przekaż zgłoszenie do właściwego działu",
)
async def submit_message(payload: MessageIn) -> MessageOut:
    settings: Settings = app.state.settings
    deps = RouteDeps(
        sender_email=str(payload.email),
        original_message=payload.message,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_from=settings.smtp_from,
    )
    prompt = (
        "Przekaż zgłoszenie narzędziem send_email, dokładnie raz.\n\n"
        f"Nadawca: {deps.sender_email}\n"
        f"Treść:\n{payload.message}"
    )
    nudge = ""

    for attempt in range(1, 4):
        try:
            await app.state.agent.run(prompt + nudge, deps=deps)
        except (ModelAPIError, UnexpectedModelBehavior) as exc:
            logger.warning("Próba %s nie doszła do wysyłki: %s", attempt, exc)
            if deps.delivery is not None:
                break
            if attempt == 3:
                raise HTTPException(
                    status_code=502,
                    detail="Model nie przekazał zgłoszenia. Spróbuj ponownie.",
                ) from exc
        except Exception as exc:
            logger.exception("Błąd routingu")
            if deps.delivery is not None:
                break
            raise HTTPException(
                status_code=502,
                detail="Nie udało się wysłać zgłoszenia.",
            ) from exc

        if deps.delivery is not None:
            break
        nudge = (
            "\n\nPoprzednia odpowiedź nie wywołała send_email. "
            "Wywołaj to narzędzie teraz i wybierz jeden dozwolony adres."
        )
        logger.info("Agent nie wywołał send_email, próba %s", attempt + 1)

    if deps.delivery is None:
        raise HTTPException(
            status_code=502,
            detail="Agent nie użył narzędzia wysyłki e-mail.",
        )

    return MessageOut(
        status="sent",
        to=deps.delivery.to,
        reply_to=deps.delivery.reply_to,
        subject=deps.delivery.subject,
    )
