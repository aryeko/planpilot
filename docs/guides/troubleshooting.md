# Troubleshooting

## Common failures

| Symptom | Likely cause | Fix |
|---|---|---|
| `ConfigError` on startup | Invalid `planpilot.json` or paths | Validate JSON and `plan_paths`; run `planpilot init --defaults` |
| `AuthenticationError` in apply mode | Missing/invalid token or gh auth | Re-auth `gh`, set `GITHUB_TOKEN`, or use `auth: token` correctly |
| `ProviderError` during discovery | Missing permissions/capability mismatch | Verify repo/projects permissions and board URL ownership |
| `map sync` fails in non-TTY with multiple plan IDs | No `--plan-id` provided | Re-run with `--plan-id <id>` |
| `clean --apply` fails without progress | Parent/constraint failure persists | Re-run after inspecting provider relations and permissions |

## Debug workflow

1. Re-run with `--verbose`.
2. Validate config with `planpilot init --defaults --output /tmp/planpilot.json` and compare.
3. Run local quality gate: `poetry run poe check`.
4. For map-sync issues, start with `planpilot map sync --dry-run`.
5. For cleanup issues, start with `planpilot clean --dry-run`.

## CI and local verification

```bash
poetry run poe check
poetry run poe test-e2e
poetry build
```

## When to inspect docs

- Behavior expectations: `docs/how-it-works.md`
- CLI semantics: `docs/modules/cli.md` and `docs/reference/cli-reference.md`
- SDK behavior: `docs/modules/sdk.md` and `docs/reference/sdk-reference.md`
- Provider internals: `docs/modules/github-provider.md`
