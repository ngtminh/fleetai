"""Fill the prompt with the email and the PDF, ask Sonnet, and write the JSON list."""

from __future__ import annotations

import json
import os
import sys

import boto3
import pymupdf
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from config import (
    EMAIL_PATH,
    PDF_PATH,
    TICKETS_PATH,
    apply_workflow,
    code_context,
    load_tickets,
    normalize_tickets,
    save_tickets,
)
from prompts import PROMPT

DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-6"


def pdf_text(path) -> str:
    document = pymupdf.open(path)
    try:
        return "\n".join(page.get_text() for page in document).strip()
    finally:
        document.close()


def ask_sonnet(prompt: str) -> str:
    region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "").strip()
    if not region:
        raise RuntimeError("AWS_REGION is required")
    model_id = (os.getenv("BEDROCK_MODEL_ID") or DEFAULT_MODEL_ID).strip()
    client = boto3.client("bedrock-runtime", region_name=region)
    try:
        response = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 16000},
        )
    except NoCredentialsError:
        raise RuntimeError("AWS credentials are not configured.")
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError("Bedrock request failed: {0}".format(exc)) from exc
    return response["output"]["message"]["content"][0]["text"]


def parse_json(text: str):
    body = text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[1]
        body = body.removesuffix("```").strip()
    return json.loads(body)


def main() -> None:
    email = EMAIL_PATH.read_text(encoding="utf-8").strip()
    report = pdf_text(PDF_PATH)
    prompt = (
        PROMPT.replace("{{email}}", email)
        .replace("{{report}}", report)
        .replace("{{code_context}}", code_context())
    )
    tickets = apply_workflow(
        normalize_tickets(parse_json(ask_sonnet(prompt))),
        load_tickets(),
    )
    save_tickets(tickets)
    print("Wrote {0} ({1} tickets)".format(TICKETS_PATH, len(tickets)))
    for ticket in tickets:
        repos = ", ".join(
            repo.get("name", "")
            for repo in ticket.get("repos") or []
            if isinstance(repo, dict)
        )
        where = repos or ", ".join(ticket.get("services") or [])
        print("{0}\t{1}\t{2}".format(ticket["id"], ticket["status"], where))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
