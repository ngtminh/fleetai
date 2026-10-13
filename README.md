# Fleet AI

Fleet AI turns a ticket into a proposed code change using the ticket, optional
image attachments, a description, and the Git-tracked files in a repository.

## Requirements

- Python 3.10+
- Git
- An API key for an OpenAI-compatible chat completions endpoint

Set `OPENAI_API_KEY` and `FLEETAI_MODEL`, then run from the repository:

```sh
export OPENAI_API_KEY=...
export FLEETAI_MODEL=...
python -m fleetai --repo . --description "Python service using SQLite" \
  --image ./ticket-screenshot.png "Add a filter to the issue list"
```

Ticket text can also be read from a file:

```sh
python -m fleetai --repo . --ticket-file ./ticket.txt --image ./mockup.jpg
```

By default, Fleet AI prints a unified diff for review and does not modify files.
Pass `--apply` to validate and apply the generated patch with `git apply`.
Configure another OpenAI-compatible endpoint with `FLEETAI_API_BASE_URL`
(default: `https://api.openai.com/v1/chat/completions`).

The request sends the ticket, description, selected repository text files, and
images to the configured model provider. Review provider terms and avoid using
this tool with repositories or tickets you are not authorized to share. Common
credential files and binary files are excluded from repository context.

Run tests with:

```sh
python -m unittest discover -s tests
```
