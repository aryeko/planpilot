# Plan JSON Schemas

planpilot expects three JSON files as input: `epics.json`, `stories.json`, and `tasks.json`. Each file contains an array of objects following the schemas below.

## epics.json

Each epic represents a high-level initiative containing multiple stories.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique epic identifier (e.g. `"E-1"`) |
| `title` | string | yes | Epic title (used as GitHub issue title) |
| `goal` | string | yes | What this epic aims to achieve |
| `spec_ref` | string or object | yes | Reference to source spec (see [spec_ref format](#spec_ref-format)) |
| `story_ids` | string[] | yes | Ordered list of story IDs belonging to this epic |
| `scope` | object | no | `{ "in": [...], "out": [...] }` -- what's in/out of scope |
| `success_metrics` | string[] | no | Measurable success criteria |
| `risks` | string[] | no | Known risks |
| `assumptions` | string[] | no | Assumptions made |

**Example:**

```json
[
  {
    "id": "E-1",
    "title": "User Authentication",
    "goal": "Allow users to sign up, log in, and manage sessions securely.",
    "spec_ref": { "path": "docs/spec.md", "section": "Authentication", "anchor": "auth" },
    "story_ids": ["S-1", "S-2"],
    "scope": {
      "in": ["Email/password login", "Session management"],
      "out": ["OAuth providers", "2FA"]
    },
    "success_metrics": ["Users can register and log in", "Sessions expire after 24h"],
    "risks": ["Token leakage if secrets misconfigured"],
    "assumptions": ["PostgreSQL available for user storage"]
  }
]
```

## stories.json

Each story represents a PR-sized deliverable within an epic.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique story identifier (e.g. `"S-1"`) |
| `epic_id` | string | yes | ID of the parent epic |
| `title` | string | yes | Story title (used as GitHub issue title) |
| `goal` | string | yes | What this story delivers |
| `spec_ref` | string or object | yes | Reference to source spec |
| `task_ids` | string[] | yes | Ordered list of task IDs belonging to this story |
| `scope` | object | no | `{ "in": [...], "out": [...] }` |
| `success_metrics` | string[] | no | Measurable success criteria |
| `risks` | string[] | no | Known risks |
| `assumptions` | string[] | no | Assumptions made |

**Example:**

```json
[
  {
    "id": "S-1",
    "epic_id": "E-1",
    "title": "User Registration Endpoint",
    "goal": "Implement POST /api/register with validation and persistence.",
    "spec_ref": { "path": "docs/spec.md", "section": "Registration" },
    "task_ids": ["T-1", "T-2"],
    "scope": {
      "in": ["Input validation", "Password hashing", "DB insert"],
      "out": ["Email verification"]
    }
  }
]
```

## tasks.json

Each task is an atomic unit of work within a story.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique task identifier (e.g. `"T-1"`) |
| `story_id` | string | yes | ID of the parent story |
| `title` | string | yes | Task title (used as GitHub issue title) |
| `motivation` | string | yes | Why this task is needed |
| `spec_ref` | string or object | yes | Reference to source spec |
| `requirements` | string[] | yes | What must be implemented |
| `acceptance_criteria` | string[] | yes | How to verify completion |
| `verification` | object | yes | Verification details (see below) |
| `artifacts` | string[] | yes | Files/outputs produced |
| `depends_on` | string[] | yes | Task IDs this task depends on (empty array if none) |
| `scope` | object | no | `{ "in": [...], "out": [...] }` |
| `estimate` | object | no | `{ "tshirt": "M" }` -- mapped to project Size field when `--size-from-tshirt` is enabled |

### verification object

| Field | Type | Description |
|-------|------|-------------|
| `commands` | string[] | Shell commands to run |
| `ci_checks` | string[] | CI checks that must pass |
| `evidence` | string[] | Evidence to collect |
| `manual_steps` | string[] | Manual verification steps (optional) |

**Example:**

```json
[
  {
    "id": "T-1",
    "story_id": "S-1",
    "title": "Add user model and migration",
    "motivation": "Need a users table to store registration data.",
    "spec_ref": { "path": "docs/spec.md", "section": "Data Model" },
    "requirements": [
      "Create User model with email, hashed_password, created_at",
      "Add Alembic migration"
    ],
    "acceptance_criteria": [
      "Migration runs without errors",
      "User model validates email format"
    ],
    "verification": {
      "commands": ["alembic upgrade head", "pytest tests/test_user_model.py"],
      "ci_checks": ["test"],
      "evidence": ["Migration file exists in alembic/versions/"]
    },
    "artifacts": ["src/models/user.py", "alembic/versions/001_add_users.py"],
    "depends_on": [],
    "estimate": { "tshirt": "S" }
  },
  {
    "id": "T-2",
    "story_id": "S-1",
    "title": "Implement registration endpoint",
    "motivation": "Users need an API to create accounts.",
    "spec_ref": { "path": "docs/spec.md", "section": "Registration API" },
    "requirements": [
      "POST /api/register accepts email and password",
      "Returns 201 on success, 422 on validation error"
    ],
    "acceptance_criteria": [
      "Valid registration returns 201 with user ID",
      "Duplicate email returns 409"
    ],
    "verification": {
      "commands": ["pytest tests/test_register.py"],
      "ci_checks": ["test", "lint"],
      "evidence": ["API endpoint responds correctly"]
    },
    "artifacts": ["src/routes/register.py", "tests/test_register.py"],
    "depends_on": ["T-1"],
    "estimate": { "tshirt": "M" }
  }
]
```

## spec_ref format

The `spec_ref` field can be either a string or an object:

**String format:**

```json
"spec_ref": "docs/spec.md#authentication"
```

**Object format (richer):**

```json
"spec_ref": {
  "path": "docs/spec.md",
  "anchor": "authentication",
  "section": "Authentication Flow",
  "quote": "Users authenticate via email/password"
}
```

Only `path` is required in the object format. All other fields are optional.

## Validation rules

planpilot runs two-phase validation before syncing:

### Phase 1: Required fields

Every object must contain all required fields listed in the schema tables above. Missing fields produce clear error messages (e.g. `epic[0] missing required field 'goal'`). Validation stops here if any fields are missing.

### Phase 2: Relational integrity

1. Exactly one epic per run (use `planpilot-slice` for multi-epic plans)
2. Every story's `epic_id` matches an epic in the file
3. Every task's `story_id` matches a story in the file
4. Every `depends_on` reference points to a valid task ID
5. Every `story_ids` entry in an epic matches a story
6. Every `task_ids` entry in a story matches a task
7. No stories or tasks are orphaned (missing from parent's ID list)

> **Note:** There are no silent fallbacks. If `epic_id` is missing from a story or `story_ids` is missing from an epic, validation fails immediately rather than guessing defaults.
