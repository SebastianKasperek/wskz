from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx2
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider

from .config import Settings
from .departments import ALLOWED_RECIPIENTS, normalize_recipient
from .mailer import sanitize_header, send_mail

logger = logging.getLogger("router.agent")

_INSTRUCTIONS = """\
Jesteś agentem, który przekazuje zgłoszenia pracowników do właściwego działu.
Jedynym skutecznym działaniem jest wywołanie narzędzia send_email dokładnie jeden raz.
Po wyniku narzędzia odpowiedz jednym słowem: sent.

Wybierz adres wyłącznie na podstawie treści zgłoszenia:

- help-desk@example.com — problem użytkownika końcowego: komputer, laptop, monitor, drukarka, hasło, konto, poczta, aplikacja biurowa, „nie działa”.
- it@example.com — infrastruktura: serwer, sieć, VPN, baza danych, wdrożenie, awaria środowiska, incydent bezpieczeństwa, uprawnienia administracyjne.
- kadry@example.com — kadry i płace: urlop, zwolnienie lekarskie, umowa, wynagrodzenie, PIT, delegacja, czas pracy, świadectwo pracy.
- human-resources@example.com — HR poza kadrami i płacami: rekrutacja, ogłoszenie o pracę, onboarding, szkolenie, benefity, relacje w zespole.
- other@example.com — sprawa nie pasuje jednoznacznie do żadnego działu powyżej.

Przykłady:
- „Nie działa mi komputer” -> help-desk@example.com
- „Chciałbym zgłosić urlop na jutro” -> kadry@example.com
- „Nie działa serwer produkcyjny i VPN” -> it@example.com
- „Chcemy otworzyć rekrutację na analityka” -> human-resources@example.com
- „Poproszę kawę” -> other@example.com

Temat napisz po polsku, jednym krótkim zdaniem. W treści streść sprawę dla działu.
System sam dopisze oryginalną wiadomość i nagłówek Reply-To. Nie podawaj adresu nadawcy w argumentach.
"""


@dataclass(frozen=True, slots=True)
class Delivery:
    to: str
    reply_to: str
    subject: str


@dataclass(slots=True)
class RouteDeps:
    sender_email: str
    original_message: str
    smtp_host: str
    smtp_port: int
    smtp_from: str
    delivery: Delivery | None = None


def build_agent(settings: Settings, http_client: httpx2.AsyncClient) -> Agent[RouteDeps, str]:
    model = OllamaModel(
        settings.ollama_model,
        provider=OllamaProvider(base_url=settings.ollama_base_url, http_client=http_client),
        settings={
            "temperature": 0,
            "max_tokens": 1024,
            "timeout": 240,
            "parallel_tool_calls": False,
            "seed": 7,
        },
    )
    agent: Agent[RouteDeps, str] = Agent(
        model,
        deps_type=RouteDeps,
        instructions=_INSTRUCTIONS,
        retries={"tools": 2, "output": 2},
        name="message-router",
    )

    allowed = ", ".join(ALLOWED_RECIPIENTS)

    @agent.tool(retries=2, description=f"Wyślij e-mail do dokładnie jednego działu. Dozwolone adresy: {allowed}.")
    def send_email(ctx: RunContext[RouteDeps], to: str, subject: str, body: str) -> str:
        """Przekaż zgłoszenie mailem. Wywołaj dokładnie raz.

        Args:
            to: Adres skrzynki działu z dozwolonej listy.
            subject: Krótki temat po polsku.
            body: Streszczenie sprawy dla działu.
        """
        if ctx.deps.delivery is not None:
            return f"Wiadomość została już wysłana do {ctx.deps.delivery.to}."

        try:
            recipient = normalize_recipient(to)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

        clean_subject = sanitize_header(subject)
        if not clean_subject:
            raise ModelRetry("Temat nie może być pusty.")
        clean_subject = clean_subject[:180].rstrip()

        clean_body = body.strip()
        if not clean_body:
            raise ModelRetry("Treść wiadomości nie może być pusta.")

        full_body = (
            f"{clean_body}\n\n"
            "---\n"
            f"Oryginalna wiadomość ({ctx.deps.sender_email}):\n"
            f"{ctx.deps.original_message}"
        )
        # Reply-To bierze się z requestu, a nie z argumentów modelu.
        send_mail(
            host=ctx.deps.smtp_host,
            port=ctx.deps.smtp_port,
            sender=ctx.deps.smtp_from,
            recipient=recipient,
            reply_to=ctx.deps.sender_email,
            subject=clean_subject,
            body=full_body,
        )
        ctx.deps.delivery = Delivery(
            to=recipient,
            reply_to=ctx.deps.sender_email,
            subject=clean_subject,
        )
        logger.info("send_email -> %s reply_to=%s", recipient, ctx.deps.sender_email)
        return f"Wysłano wiadomość do {recipient}."

    return agent
