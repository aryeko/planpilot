# Plan JSON Schemas (Minimum)

## epics.json

Array of epic objects. Minimum required fields per epic:

- `id`
- `title`
- `goal`
- `spec_ref`
- `story_ids`

## stories.json

Array of story objects. Minimum required fields per story:

- `id`
- `epic_id`
- `title`
- `goal`
- `spec_ref`
- `task_ids`

## tasks.json

Array of task objects. Minimum required fields per task:

- `id`
- `story_id`
- `title`
- `motivation`
- `spec_ref`
- `requirements`
- `acceptance_criteria`
- `verification`
- `artifacts`
- `depends_on`
