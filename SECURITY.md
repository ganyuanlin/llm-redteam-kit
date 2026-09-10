# Security policy

## Purpose and scope

LLM Red Team Kit (LRTK) is a security testing framework. It is intended
**only** for evaluating large language model deployments for which the
operator holds explicit, documented authorization. It is not an
exploitation toolkit and must not be used against third-party services
without permission or in ways that violate their terms of service.

By installing, copying or using LRTK you accept responsibility for:

- obtaining written authorization before testing any target;
- respecting local laws and regulations, platform terms and privacy
  policies;
- recording the authorizing party, engagement scope, time window and tester
  identity in every run (`run.authorization`);
- handling all generated artifacts according to your organization's data
  classification rules.

## What LRTK does to keep you safe

1. **No hardcoded credentials.** API keys are referenced by environment
   variable name (`api_key_env`) and read lazily at request time.
2. **Log redaction.** The logging layer masks sensitive keys (`api_key`,
   `authorization`, `token`, `secret`, `password`, ...) and common credential
   patterns (`sk-...`, `Bearer ...`) in every log record.
3. **No secrets in persistence.** Only run metadata, prompts, responses and
   scores are written to memory backends and reports; request headers and
   key material are never stored.
4. **Benign placeholder content.** Shipped prompts and personas are harmless
   training placeholders. They describe the *shape* of risky requests (e.g.
   "reveal the system prompt") without containing unlawful instructions or
   real-world targets.
5. **Deterministic offline mode.** `MockTarget` and the default demo need no
   network and no paid API, so CI pipelines and contributors cannot
   accidentally send traffic to a real provider.
6. **Bounded execution.** Targets honor configured timeouts, retry limits
   and minimum request intervals.

## Responsible testing checklist

Before running an engagement, confirm:

- [ ] You have written authorization referencing the exact target and scope.
- [ ] The authorization is entered under `run.authorization` in the config.
- [ ] You are using a dedicated, least-privilege API key with spending caps.
- [ ] Output storage (`./runs`) is encrypted/access-controlled as required.
- [ ] Reports are shared only with parties covered by the engagement NDA.
- [ ] Prompt content respects privacy regulations and contains no personal
      data unless explicitly in scope and approved.

## Reporting a vulnerability in LRTK

If you discover a security weakness in LRTK itself (for example a logging
path that leaks secrets, an unsafe default, or a dependency advisory), please
**do not open a public issue**. Instead, email the maintainers at
`security@example.com` with:

- a description of the issue and its impact;
- steps to reproduce, ideally with a minimal configuration;
- any suggested remediation.

We aim to acknowledge reports within two business days and to provide a
remediation plan within ten. Please give us a reasonable disclosure window
before publishing details.

## Out of scope

- Findings derived from running LRTK against systems you do not own or lack
  authorization to test.
- Social engineering, denial-of-service or physical attacks.
- Vulnerabilities in third-party LLM providers; report those through the
  affected provider's own disclosure process.
