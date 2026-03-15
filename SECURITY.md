# Security Policy

## Supported Versions

Hermit is still evolving quickly. Security fixes are most likely to land on the latest release line and on `main`.

| Version | Supported |
| --- | --- |
| `main` | Yes |
| latest release (`0.2.x` today) | Yes |
| older release lines | Best effort only |

## Reporting a Vulnerability

Please do not open public GitHub issues for suspected vulnerabilities.

Preferred path:

1. Use GitHub's private vulnerability reporting flow for this repository.
2. Include a clear description, impact, affected version or commit, reproduction steps, and any suggested mitigation.
3. If you already have a fix or patch, mention that in the report.

What to include:

- vulnerable component or file path
- attack scenario and required privileges
- proof of concept or reproduction steps
- possible blast radius
- whether credentials, filesystem access, or command execution are involved

## Response Expectations

The maintainer will try to:

- acknowledge the report promptly
- validate severity and scope
- work on a fix or mitigation
- coordinate disclosure timing when a fix is ready

Because Hermit is an early-stage project, response times are best effort rather than SLA-backed.

## Safe Harbor

Good-faith security research that avoids privacy violations, data destruction, service disruption, or public disclosure before a fix is available is welcome.

Please avoid:

- accessing other users' data
- destructive testing against third-party services
- publishing exploit details before maintainers have time to respond
