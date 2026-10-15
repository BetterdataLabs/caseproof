# Local development

The [README](../README.md#run-locally) runs the production demo. Use the development configuration to edit and test the same checkout while the app stays running.

## Start with live reload

Complete the README's project and Google credential setup, then run from the repository root:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build --detach --wait
```

Open **http://localhost:3400**. Docker mounts this checkout's backend source, policies and web source into the running containers. The web refreshes after edits; the API, worker and dispatcher restart automatically when their Python source changes. Let active agent work finish before editing worker code.

PostgreSQL is available on **127.0.0.1:56543** for tools and local tests. The app, documents and database use the same Docker volumes as the production demo. Development dependencies and the Next.js cache use separate volumes.

If another checkout already serves port 3400, stop its application processes before starting this checkout.

## Use live reload by default on one machine

On Linux or macOS, create a local override from the repository root:

```bash
ln -s compose.dev.yaml compose.override.yaml
docker compose up --build --detach --wait
```

On Windows, copy `compose.dev.yaml` to `compose.override.yaml` instead. The override is ignored by Git, so the default startup for teammates remains the production demo. With this override present, plain `docker compose` commands use live reload for this checkout.

## Logs, updates and shutdown

```bash
docker compose -f compose.yaml -f compose.dev.yaml ps --all
docker compose -f compose.yaml -f compose.dev.yaml logs --follow api worker dispatcher web
```

Source edits reload automatically. After changing dependencies, Dockerfiles, environment variables or migrations, rerun the startup command with `--build`. Database migrations run during initialization.

To stop:

```bash
docker compose -f compose.yaml -f compose.dev.yaml down
```

Saved cases and documents remain in the named volumes.

## Verify changes

Follow the [review workflow](../README.md#review-workflow) through the running app. This exercises the configured Google model, so it uses the project's model quota and billing.

When the local backend tests are available, point them at this checkout's PostgreSQL instance:

```bash
cd services/backend
uv sync --frozen
CASEPROOF_TEST_DATABASE_PORT=56543 uv run pytest -q
```

The suite resets only the dedicated `caseproof_test` database and uses stubbed model responses. It does not reset the running app's `caseproof` database. Test files remain local.

## Return to the production demo

Remove the local override if you created it, then start using the base configuration:

```bash
rm -f compose.override.yaml
docker compose -f compose.yaml up --build --detach --wait
```

This rebuilds the production web image and keeps the saved app data.
