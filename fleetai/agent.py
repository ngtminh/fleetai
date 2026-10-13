import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MAX_CONTEXT_CHARS = 100_000
MAX_FILE_CHARS = 20_000
MAX_IMAGE_BYTES = 10 * 1024 * 1024
DEFAULT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
SENSITIVE_NAMES = {
    ".env",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
}
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def _is_sensitive(path):
    name = path.name.lower()
    return (
        name in SENSITIVE_NAMES
        or name.startswith(".env.")
        or name.endswith(SENSITIVE_SUFFIXES)
        or "secret" in name
    )


def collect_codebase(repo, max_chars=MAX_CONTEXT_CHARS):
    """Collect bounded text from tracked repository files."""
    root = Path(repo).resolve()
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    sections = []
    used_chars = 0

    for relative_name in result.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
        if not relative_name:
            continue
        relative_path = Path(relative_name)
        if _is_sensitive(relative_path):
            continue

        file_path = (root / relative_path).resolve()
        if not file_path.is_relative_to(root) or not file_path.is_file():
            continue
        try:
            content = file_path.read_bytes()
        except OSError:
            continue
        if b"\0" in content:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue

        remaining = max_chars - used_chars
        if remaining <= 0:
            break
        text = text[: min(MAX_FILE_CHARS, remaining)]
        section = f"### {relative_name}\n```\n{text}\n```"
        sections.append(section)
        used_chars += len(section)

    if not sections:
        return "(No eligible tracked text files found.)"
    return "\n\n".join(sections)


def _image_content(image_path):
    path = Path(image_path)
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"Unsupported image type: {path}")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError(f"Image exceeds the 10 MiB limit: {path}")
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
    }


def _clean_patch(response_text):
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if not text:
        raise ValueError("The model returned an empty patch.")
    return text + "\n"


def generate_patch(ticket, description, codebase, images, api_key, model, endpoint):
    content = [
        {
            "type": "text",
            "text": (
                f"Ticket:\n{ticket}\n\n"
                f"Additional description:\n{description or '(none)'}\n\n"
                f"Repository context:\n{codebase}\n\n"
                "Implement the ticket in this codebase. Return only a unified "
                "diff that can be applied at the repository root. Do not include "
                "markdown fences or explanatory prose. Do not invent files or "
                "APIs that are unsupported by the provided context."
            ),
        }
    ]
    content.extend(_image_content(image) for image in images)

    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a careful software implementation agent. "
                        "Make the smallest complete change requested by the ticket."
                    ),
                },
                {"role": "user", "content": content},
            ],
        }
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=120) as response:
            response_data = json.loads(response.read())
    except HTTPError as error:
        raise RuntimeError(f"Model request failed with HTTP {error.code}.") from None
    except URLError as error:
        raise RuntimeError(f"Could not reach the model endpoint: {error.reason}") from None
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        raise RuntimeError("The model endpoint returned an invalid response.") from error

    try:
        response_text = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("The model endpoint returned an invalid response.") from None
    if not isinstance(response_text, str):
        raise RuntimeError("The model response did not contain a text patch.")
    return _clean_patch(response_text)


def apply_patch(repo, patch):
    root = Path(repo).resolve()
    for args in (["git", "apply", "--check", "-"], ["git", "apply", "-"]):
        result = subprocess.run(
            args,
            cwd=root,
            input=patch,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            detail = result.stderr.strip() or "git apply rejected the patch"
            raise RuntimeError(detail)


def _read_ticket(args):
    if args.ticket_file:
        return Path(args.ticket_file).read_text(encoding="utf-8")
    if args.ticket is not None:
        return args.ticket
    raise ValueError("Provide ticket text or --ticket-file.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a code change from a ticket and repository context."
    )
    parser.add_argument("ticket", nargs="?", help="Ticket text")
    parser.add_argument("--ticket-file", help="Read ticket text from a file")
    parser.add_argument("--repo", default=".", help="Git repository root (default: .)")
    parser.add_argument("--description", default="", help="Additional project context")
    parser.add_argument(
        "--image", action="append", default=[], help="Ticket image (may be repeated)"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Validate and apply the generated patch"
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("FLEETAI_MODEL")
    endpoint = os.environ.get("FLEETAI_API_BASE_URL", DEFAULT_ENDPOINT)
    if not api_key:
        parser.error("Set OPENAI_API_KEY before running Fleet AI.")
    if not model:
        parser.error("Set FLEETAI_MODEL before running Fleet AI.")

    try:
        ticket = _read_ticket(args)
        codebase = collect_codebase(args.repo)
        patch = generate_patch(
            ticket,
            args.description,
            codebase,
            args.image,
            api_key,
            model,
            endpoint,
        )
        if args.apply:
            apply_patch(args.repo, patch)
            print("Patch applied.")
        else:
            sys.stdout.write(patch)
    except (OSError, ValueError, subprocess.CalledProcessError, RuntimeError) as error:
        print(f"fleetai: {error}", file=sys.stderr)
        return 1
    return 0
