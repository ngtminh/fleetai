# JarvisMD / HBA product code

This FleetAI repo is the ticket runner only. Product code lives under
`/Users/minh/repos/hba`. That folder is a container of independent Git
repositories. Run Git commands inside the child repo you are changing.

Read `/Users/minh/repos/hba/.cursor/rules/hba-platform-handoff.mdc` first.

SSH aliases are in `/Users/minh/.ssh/config`. Use `ssh <alias>`. Do not
copy keys or edit that file unless the user asks.

## Repositories

| Ticket service names | Local checkout | Remote | Owns |
|---|---|---|---|
| page load, session activity, annotated transcript UI, copy icon, timestamps, survey, UK time | `/Users/minh/repos/hba/jmd-frontend` | `cto-hba/jmd-frontend` | React/Vite SPA. Regional URLs and flags: public/server-profiles.json |
| annotated transcript pipeline, clinical summary persistence, Save & complete, evaluation snapshots | `/Users/minh/repos/hba/jarvismd-backend` | `cto-hba/jarvismd-backend` | FastAPI session APIs, annotation, Summary, SNOMED proxy, GP apply audit |
| transcription, live transcript, recording gaps, resume/audio | `/Users/minh/repos/hba/transcribe` | `cto-hba/transcribe` | Socket.IO STT. App is transcribe/backend |
| speaker annotation LLM, Summary generation | `/Users/minh/repos/hba/nlp-services` | `healthbridge-inc/nlp-services` | Celery NLP worker for speaker annotation and Summary generation |
| GP consult template | `/Users/minh/repos/hba/jmd-gp-consult-template` | `healthbridge-inc/jmd-gp-consult-template` | GP template UI + extract API. Vendor into jmd-frontend after UI changes |
| SNOMED-CT coder | `/Users/minh/repos/hba/snomed` | `cto-hba/snomed` | SNOMED coding service on its own VM. Browser must not call it |
| chatbot | `/Users/minh/repos/hba/ask-jarvismd` | `healthbridge-inc/ask-jarvismd` | Ask JarvisMD chatbot |
| credits | `/Users/minh/repos/hba/credit-manager` | `healthbridge-inc/credit-manager` | Internal credit API |
| FHIR / SystmOne local probe | `/Users/minh/repos/hba/jmd-xycare` | `healthbridge-inc/jmd-xycare` | Local XYClient/SystmOne probes, not the hosted app |
| world dashboard | `/Users/minh/repos/hba/jmd-world-dashboard` | `healthbridge-inc/jmd-world-dashboard` | Fleet dashboard |
| public site | `/Users/minh/repos/hba/healthbridge-homepage` | `cto-hba/healthbridge-homepage` | HBA public website |
| template source notes | `/Users/minh/repos/hba/jmd-templates` | `cto-hba/jmd-templates` | Template source notes. Not the packaged GP module |

## How a consult flows

`browser mic -> transcribe Socket.IO -> transcript Mongo -> backend normalize -> NLP annotation -> annotated transcript -> Summary -> SNOMED suggestions -> clinician edits -> Save & complete`

If live text is present and annotated text is missing, start in
`jarvismd-backend` annotation code, not the coder.
If a GP template UI change is needed, edit `jmd-gp-consult-template`, then
`npm run vendor:gp-consult-templates -- ../jmd-gp-consult-template` in
`jmd-frontend`. Changing the template repo alone does not update the SPA.

## UK evaluation target

"UK" means `https://jarvismd-trial.xycare.co.uk`, not the older HBA UK VM.

| Role | SSH alias |
|---|---|
| UK deploy / runtime | `staging-uk-jmd-xycare-cicd` |
| UK VM admin | `staging-uk-jmd-xycare-admin` |
| Older HBA UK VM | `prod-uk-jmd` |
| SNOMED host | `snomed-uk` |
| Dev JarvisMD VM | `dev-javismd` |
| AU / SG / KH / MX / CA | `prod-au-cicd`, `prod-sg-cicd`, `prod-kh`, `prod-mex-cicd`, `prod-canada-cicd` |

Frontend profile `uk-xycare` points REST and `/transcribe` at the Xycare origin.

## Work rules for the solver

- Prefer the local checkout over cloning the remote.
- Check `git status --short --branch` in each affected child repo first.
- Keep existing uncommitted work. Do not switch branches.
- Do not commit, push, or deploy unless the user authorized it.
- UK backend develop/CI branch is `staging/uk-xycare`. `prod/uk` is a no-op in CI.
- `staging/uk-xycare` has no XYCare write-back. Do not import `app.services.xyfhir`.
- If jarvismd-backend is not on `staging/uk-xycare`, stop and say so.
- Frontend `main` does not auto-deploy to the Xycare UK container.
- Happy-path tests are not enough. Check adjacent callers and opposite cases.

## How to run tests

Find the test file next to the changed module, then run that file.
Do not skip tests because this map is short. Do not run an unrelated
full suite when a focused file covers the change.

- `jmd-frontend`: `NODE_OPTIONS=--localstorage-file=/tmp/jmd-vitest-localstorage npm run test:run -- <file>` from the repo root. Also `npm run build` for UI/API client changes.
- `jmd-gp-consult-template`: `npm test -- --runInBand` then vendor into `jmd-frontend`.
- `transcribe/backend`: `npm test` and `npm run build`. Live AWS tests skip without credentials.
- `jarvismd-backend`: Python 3.13 only. From `app/`: `python -m pytest app/tests/unit/<module> -q`. macOS system Python 3.9 cannot collect the suite.
- `nlp-services`: `python -m pytest tests/test_<area>.py -q` in an env that has the worker deps.
- `snomed`: `pytest tests/` on that repo. The browser must not call it.
