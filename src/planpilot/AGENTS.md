# RUNTIME PACKAGE GUIDE

## OVERVIEW
Core runtime package for CLI sync orchestration, plan modeling, rendering, and provider integration.

## STRUCTURE
```text
src/planpilot/
├── cli.py                  # argparse wiring + top-level execution
├── sync/                   # pipeline coordinator + relation logic
├── providers/              # provider abstraction and implementations
├── plan/                   # load/validate/hash plan JSON
├── models/                 # typed domain models (Plan/Project/Sync)
├── rendering/              # issue-body rendering protocol + markdown impl
├── config.py               # SyncConfig
├── exceptions.py           # exception hierarchy
└── slice.py                # multi-epic slicing CLI
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add/change CLI flags | `src/planpilot/cli.py` | Keep dry-run/apply mutually exclusive |
| Change orchestration order | `src/planpilot/sync/engine.py` | Preserve 5-phase flow |
| Add provider capabilities | `src/planpilot/providers/base.py` | Extend ABC first, then implementation |
| Parse/load plan files | `src/planpilot/plan/loader.py` | Raises `PlanLoadError` on input failures |
| Enforce plan relations | `src/planpilot/plan/validator.py` | Aggregates validation errors |
| Update markdown body layout | `src/planpilot/rendering/markdown.py` | Reuse helpers in `components.py` |

## CONVENTIONS
- Keep async boundaries in provider/client layers; domain/model code remains simple and typed.
- Prefer raising project-specific exceptions from `exceptions.py` over raw exceptions.
- Maintain idempotency markers in rendered issue bodies (`plan_id`, entity IDs).
- Avoid coupling `sync/engine.py` to GitHub implementation details.

## ANTI-PATTERNS
- Do not bypass `Provider`/`BodyRenderer` abstractions in orchestration code.
- Do not add untyped runtime functions; mypy strictness is enforced.
- Do not introduce destructive sync semantics (auto-close/delete) in v1 behavior.
