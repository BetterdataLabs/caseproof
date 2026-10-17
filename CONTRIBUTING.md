# Contributing to CaseProof

Thank you for helping improve CaseProof. This repository is the public source for the invoice-financing document review app.

## Before you start

- Run the app locally from the [README](README.md) and confirm Docker Compose starts cleanly.
- Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) if you are changing review, policy, or agent behaviour.
- Do not commit `.env`, access codes, service-account keys, or cloud project identifiers from a private deployment.

## How to propose a change

1. Fork the repository and create a branch from `main`.
2. Keep the change focused. Prefer one concern per pull request.
3. Follow the existing TypeScript and Python style in the files you touch.
4. Update docs when behaviour or setup steps change.
5. Open a pull request against `main` and describe what changed and how you verified it.

## Local checks

From the repository root:

```bash
test -f .env || cp .env.example .env
docker compose up --build
```

Use the demo accounts from the README after the access-code gate. If you add or change an API contract, exercise the matching web flow.

## What not to include

- Real access codes, API keys, tokens, or credential files
- Private Cloud Run URLs, billing account IDs, or customer data
- Generated runtime data under `.data/`
- Large unrelated refactors in the same pull request as a bug fix

## Security reports

Do not open a public issue for a vulnerability. Follow [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions are licensed under the Apache License 2.0.
