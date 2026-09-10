# Compliance & ethics

LLM Red Team Kit exists to make models **safer**, by giving defenders a
repeatable way to measure failure modes before adversaries do. That mission
only holds when the tool is used lawfully and transparently.

## Authorization requirements

You may only run LRTK against a target when:

1. you own the deployment, or
2. you hold **written authorization** from the system owner that names:
   - the in-scope targets and accounts;
   - the testing window;
   - the authorized testers;
   - permitted techniques and data handling;
   - an emergency contact and stop condition.

Every engagement configuration must populate:

```yaml
run:
  authorization:
    owner: "Authorizing party / tester name"
    scope: "Exact systems and models in scope"
    contact: "security@example.com"
    reference: "ticket-or-contract-id"
```

These fields are copied into every report (`JSON`, `Markdown`, `HTML`,
`SARIF`). Do not leave them blank for real engagements.

## User responsibilities

- Comply with all applicable laws, regulations and export controls.
- Respect provider terms of service and abuse-prevention systems; LRTK is not
  a tool for bypassing them.
- Do not process personal data unless it is explicitly in scope and handled
  under your organization's privacy obligations.
- Apply least privilege to API keys (dedicated projects, spend limits,
  IP restrictions where available).
- Store run artifacts in access-controlled locations; prompts and responses
  may reveal sensitive information about your environment.

## How LRTK reduces misuse risk

- **No weaponized payload library.** Shipped prompts are short, clearly
  labeled placeholders ("reveal the system prompt", "developer mode"). They
  exercise test harness logic without supplying operational harmful content.
- **No victim targeting.** Nothing in the repository identifies real people,
  organizations or services as targets.
- **No stealth features.** Requests identify your configured client
  normally; there is no fingerprint spoofing or rate-limit evasion beyond
  polite client-side throttling configured by the tester.
- **Auditability.** The complete configuration, prompts, responses, scores,
  timestamps and authorization metadata are persisted per run.
- **Secret hygiene.** Credentials come only from environment variables;
  logs redact `api_key`, `authorization`, `token`, `secret`, `password` and
  common credential shapes; secrets never enter databases or reports.

## Report handling

Treat reports as sensitive security artifacts:

- share on a need-to-know basis under your engagement NDA;
- redact third-party information before wider circulation;
- use SARIF output for CI gating but restrict raw HTML/JSON bundles;
- retain for the period required by your security policy, then delete
  `runs/` data securely.

## Interpreting results responsibly

A "success" verdict means a configured criterion fired under controlled
conditions. It indicates a robustness gap to triage and fix — not permission
to exploit it. False positives happen; combine deterministic scorers with
human review before drawing conclusions.

## If something goes wrong

Stop the engagement, preserve the relevant run records under
`./runs/<run-id>/`, notify the authorizing party, and follow your incident
response process. Suspected vulnerabilities in LRTK itself should be
reported privately per [SECURITY.md](../SECURITY.md).
