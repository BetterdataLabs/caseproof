# Security policy

## Supported versions

Security fixes are accepted against the current `main` branch.

## Reporting a vulnerability

Please report vulnerabilities privately through [GitHub Security Advisories](https://github.com/BetterdataLabs/caseproof/security/advisories/new).

Include:

- A description of the issue and the affected component
- Steps to reproduce, or a proof of concept that does not include secrets
- The impact if the issue is exploited

Do not open a public issue, pull request, or discussion for an unfixed vulnerability.

We will acknowledge the report and work on a fix before any public disclosure.

## Operational secrets

Operators must keep these values out of git:

- `CASEPROOF_DEMO_ACCESS_CODE`
- Database URLs and session secrets
- Google Cloud credentials and service-account keys

Use Secret Manager or an equivalent secret store in hosted environments. Rotate any value that may have been shared outside the operator team.
