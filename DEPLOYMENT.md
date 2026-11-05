# Setup and deployment

The complete application starts with `app.py`; both agents are included. Publishing a Git branch does not create a hosted deployment. No provider is selected or deployed as part of consolidation.

## Fresh local checkout

Use the default `main` branch for the combined Sprint 2 application. It provides both Manpower budgeting and Tender evaluation from `app.py`, plus the Site Xtown example. Python 3.14 is the tested development version; the project declares `>=3.11,<3.15`.

```powershell
uv sync --frozen --python 3.14
Copy-Item .env.example .env
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8511 --browser.gatherUsageStats false
```

Copy the blank configuration only on a fresh installation. Preserve existing private settings. Without `uv`:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install --require-hashes -r requirements.txt
.venv/Scripts/python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8511 --browser.gatherUsageStats false
```

The requirements are exported from the lockfile. Tests/lint need `uv sync` with its dev dependency group, rather than runtime-only requirements. On another OS use its virtual-environment executable path. Run from the repository root for consistent configuration/storage paths.

If a previously modified package cache causes dependency import failures, use `uv sync --frozen --no-cache` in a fresh checkout/environment. The consolidation verification used fresh locked downloads after detecting modified cached files. Keep the live app's environment separate from installation tests. On Windows, a shorter checkout/test-scratch path avoids snapshot paths exceeding the platform limit.

No key is needed for ordinary examples, calculations or exports. Optional AI requires private `OPENAI_API_KEY` and `OPENAI_MODEL`. Actual `.env`/`.streamlit/secrets.toml` files are ignored. Never put secrets in commands, build arguments, source or sample workbooks. Shared hosts should use server-side secrets.

## Data required on another machine

Git includes synthetic JSON fixtures, reviewed title context, the dated PWM catalogue and authored proposal workbooks. The ordinary proposal and Site Xtown example work without the owner's database. Invented records and illustrative allowances must retain their labels.

Private prepared references are not needed to launch both agents. Without a private activation pointer, the app uses the synthetic fallback. Set `MANPOWER_REFERENCE_SOURCE=synthetic` for an explicit demonstration installation. An authorised private installation can set `MANPOWER_REFERENCE_DIR` and separately provision its approved snapshot and activation pointer. Do not copy raw source workbooks into Git or silently switch versions. See [reference provisioning](docs/PREPARED_REFERENCES.md).

The owner's current v3 source, saved inputs and project revisions are private. Consolidation does not clean/import/regenerate/activate sources. Restored projects need their original reference snapshots to resolve full evidence; missing snapshots must not be replaced with the host's current source.

## Persistence and access

Local mode uses `DATABASE_URL=sqlite:///local_data/plans.db` by default and creates its directory. Back up the database consistently with approved reference snapshots. Budget/proposal revisions preserve original document bytes inside project JSON, so storage needs appropriate access, backups and retention decisions.

Agent 2 tender reviews use JSON download/resume and are not automatically saved in Agent 1's owned revision database. Download before ending the session. Browser drafts are not durable backups.

Shared mode requires:

1. Durable PostgreSQL with TLS, a restricted app account and backups.
2. Private `DEPLOYMENT_MODE=shared`, a `DATABASE_URL` beginning `postgresql+psycopg://`, and an explicit comma-separated `ALLOWED_EMAILS`.
3. Server-side Streamlit `[auth]` settings: callback URL, random cookie secret, client ID/secret, OIDC metadata URL and `expose_tokens=false`. The provider must supply stable issuer/subject and accepted email identity. Consult [Streamlit authentication](https://docs.streamlit.io/develop/concepts/connections/authentication) for the selected host.
4. Optional private model credentials with spend controls if live guidance will be enabled.

Do not expose local mode publicly. Code checks per-officer ownership and optimistic revision conflicts. Team editing is not implemented. Real PostgreSQL/OIDC hosting remains unverified. Test allowed/denied login, ownership after restart/logout, concurrent revisions, restores, durable uploads/references and backup recovery before inviting users. There is no automated upload-retention policy.

## Container packaging

The Dockerfile installs runtime requirements, runs as an unprivileged user and exposes Streamlit on 8501 with a health check. Build from a reviewed checkout. The Docker ignore rules exclude private/generated files.

```powershell
docker build -t fm-manpower-review .
docker run --rm -p 127.0.0.1:8512:8501 --env-file .env -v fm-review-data:/app/local_data fm-manpower-review
```

Port 8512 avoids an existing development app on 8511. The named volume preserves local-mode SQLite/reference files. Shared mode uses PostgreSQL and private OIDC secrets, with HTTPS supplied by the host. No Docker build or hosted deployment is claimed unless separately recorded.

Managed Streamlit hosting must use `app.py` and `requirements.txt` from the same reviewed revision, compatible Python, private server secrets and durable storage. Verify host-specific Python and authentication support when choosing a provider.

## Acceptance

Run offline regression from a checkout containing only publishable files. Exercise both activities, the new-budget example, proposal upload/sample, confirmation invalidation, save/resume, calculations, exports and tender review. Keep model calls disabled. Audit the exact staged publication set with `python -m scripts.audit_shareable`.

Results and limits are recorded in [VALIDATION.md](docs/VALIDATION.md). Hosted persistence/authentication, provider connectivity, native Excel recalculation and comprehensive navigation performance remain separate checks. Only Deployment has an isolated before/after timing result.
