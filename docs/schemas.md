# Plan Schemas

`planpilot` supports two input layouts through `plan_paths` in `planpilot.json`:

1. Unified file (`unified`)
2. Split files (`epics`, `stories`, `tasks`)

## Unified format

`plan_paths`:

```json
{
  "plan_paths": { "unified": ".plans/plan.json" }
}
```

`plan.json`:

```json
{
  "items": [
    {
      "id": "E1",
      "type": "EPIC",
      "title": "Payments Platform",
      "goal": "Unify payment flows",
      "requirements": ["R1"],
      "acceptance_criteria": ["AC1"]
    }
  ]
}
```

## Split format

`plan_paths`:

```json
{
  "plan_paths": {
    "epics": ".plans/epics.json",
    "stories": ".plans/stories.json",
    "tasks": ".plans/tasks.json"
  }
}
```

Split files are arrays. `type` is optional/ignored; loader assigns type by file role.

`epics.json`:

```json
[
  {
    "id": "E1",
    "title": "Payments Platform",
    "goal": "Unify payment flows",
    "requirements": ["R1"],
    "acceptance_criteria": ["AC1"]
  }
]
```

`stories.json`:

```json
[
  {
    "id": "S1",
    "title": "Checkout API",
    "goal": "Expose stable payment endpoint",
    "parent_id": "E1",
    "requirements": ["R2"],
    "acceptance_criteria": ["AC2"]
  }
]
```

`tasks.json`:

```json
[
  {
    "id": "T1",
    "title": "Add idempotency keys",
    "goal": "Prevent duplicate charges",
    "parent_id": "S1",
    "requirements": ["R3"],
    "acceptance_criteria": ["AC3"],
    "depends_on": ["T0"]
  }
]
```

## Common fields

Required for all items:

- `id`
- `title`
- `goal`
- `requirements`
- `acceptance_criteria`

Important optional fields:

- `parent_id`
- `sub_item_ids`
- `depends_on`
- `estimate`
- `verification`
- `scope`
- `spec_ref`

## Validation notes

- IDs must be globally unique.
- Parent type rules:
  - story -> epic
  - task -> story
  - epic cannot have parent
- Reference checks depend on `validation_mode`:
  - `strict`: unresolved refs fail
  - `partial`: unresolved refs allowed when item is not loaded

For full validation semantics, see [modules/plan.md](./modules/plan.md).
