from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .types import ProjectFieldIds
from .utils import resolve_option_id


def resolve_project_fields(project: Dict[str, object], status: str, priority: str, iteration: str, size_field: str) -> ProjectFieldIds:
    status_field_id = None
    status_option_id = None
    priority_field_id = None
    priority_option_id = None
    iteration_field_id = None
    iteration_option_id = None
    size_field_id = None
    size_options: List[Dict[str, str]] = []

    iteration_options: List[Dict[str, str]] = []
    active_iteration_id: Optional[str] = None

    now = datetime.now(timezone.utc)

    for field in project.get('fields', {}).get('nodes', []):
        name = field.get('name', '').lower()
        if name == 'status' and 'options' in field:
            status_field_id = field['id']
            status_option_id = resolve_option_id(field['options'], status)
        if name == 'priority' and 'options' in field:
            priority_field_id = field['id']
            priority_option_id = resolve_option_id(field['options'], priority)
        if name == 'iteration' and 'configuration' in field:
            iteration_field_id = field['id']
            iteration_options = field['configuration'].get('iterations', [])
            for it in iteration_options:
                start = it.get('startDate')
                duration = it.get('duration')
                if not start or duration is None:
                    continue
                try:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                except ValueError:
                    continue
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                end_dt = start_dt + timedelta(days=int(duration))
                if start_dt <= now < end_dt:
                    active_iteration_id = it.get('id')
                    break
            if iteration.lower() == 'active':
                iteration_option_id = active_iteration_id
            elif iteration.lower() == 'none':
                iteration_option_id = None
            else:
                for it in iteration_options:
                    if it.get('title', '').lower() == iteration.lower():
                        iteration_option_id = it.get('id')
                        break
        if size_field and name == size_field.lower() and 'options' in field:
            size_field_id = field['id']
            size_options = field['options']

    return ProjectFieldIds(
        status_field_id=status_field_id,
        status_option_id=status_option_id,
        priority_field_id=priority_field_id,
        priority_option_id=priority_option_id,
        iteration_field_id=iteration_field_id,
        iteration_option_id=iteration_option_id,
        size_field_id=size_field_id,
        size_options=size_options,
    )
