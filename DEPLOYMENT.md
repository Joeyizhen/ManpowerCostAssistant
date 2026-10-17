# Deployment preparation — no deployment performed

The hosting provider remains undecided. The app can be packaged as a container or reviewed for Streamlit hosting. Local review and a running localhost link are not shared deployment.

## Required shared-hosting configuration

1. Provision a durable PostgreSQL database using a hosting account chosen by the officer. Use TLS and a database user restricted to the app's tables. Back up the database; original uploads are stored in versioned project JSON, not an ephemeral upload directory. Snapshots have no automatic deletion policy in this release.
2. Configure an OIDC provider and callback URL privately. Use a provider that supplies a stable `sub`, issuer and email. Restrict allowed emails explicitly. This release offers per-officer project ownership, not team edit sharing.
3. In the host's server-side secrets, set `DEPLOYMENT_MODE="shared"`, `DATABASE_URL="postgresql+psycopg://...?...sslmode=require"`, `ALLOWED_EMAILS`, `OPENAI_API_KEY` and `OPENAI_MODEL`.
4. Put the Streamlit `[auth]` configuration into server-side `secrets.toml`/Secrets settings: callback URL, random cookie secret, client ID, client secret, OIDC metadata URL and `expose_tokens=false`. See the official [Streamlit authentication guide](https://docs.streamlit.io/develop/concepts/connections/authentication).
5. Verify login, denied access, stable project ownership after logout/restart, parallel-tab conflict handling, durable restores, backups, live model access and spend limits on the selected host before inviting testers. The code checks local SQLite owner isolation; a real PostgreSQL/identity-provider combination has not been exercised.
6. Separately authorise publication. Review the intended file list for secrets, real data, student IDs, previous prototype or Pulse content. Do not publish `BUILD_BRIEF.md` unchanged: it includes private local source paths and an author email from the handoff. `.env`, secrets, local databases, uploads, outputs and environments are ignored. `.dockerignore` also excludes the brief from the runtime image.

Do not assume an ephemeral SQLite file survives cloud restarts. Do not expose `DEPLOYMENT_MODE=local` on a public host. Project sharing between authenticated officers would need an explicit access model and tests in a future iteration.

## Container packaging

The supplied Dockerfile runs the app and provides a health check. It has not been built or published here. For a later local container check (not cloud deployment):

```powershell
docker build -t fm-manpower-review .
docker run --rm -p 127.0.0.1:8511:8501 --env-file .env -v fm-review-data:/app/local_data fm-manpower-review
```

The named volume makes local container storage durable. Shared mode should instead use the remote PostgreSQL store and an OIDC secrets mount, with HTTPS handled by the chosen host. Do not provide secrets as Docker build arguments.

Streamlit hosting uses `app.py` and `requirements.txt`, with privately configured Secrets settings. Verify its supported Python version and compatible dependency resolution when a host is chosen. Development verification here uses Python 3.14; other supported Python versions have not been tested.

## Publication status

The collaboration preparation creates local Git metadata and a reviewed local baseline/feature branch where checks permit. No push, hosted database, identity-provider registration or cloud deployment has been performed. Original private notes are excluded from tracking; shareable handover and publication steps are in `docs/HANDOVER.md` and `docs/COLLABORATION.md`. The previous prototype's Git staging and files remain untouched.
