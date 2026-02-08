<!-- PLAN_ID: ebcbac1f2062 -->

<!-- TASK_ID: T-1 -->

## Story

* #2

## Motivation

Need a users table to store registration data.

## Scope

In:

* (none)

Out:

* (none)

## Requirements

* Create User model with email, hashed_password, created_at
* Add database migration

## Acceptance criteria

* Migration runs without errors
* User model validates email format

## Verification

Commands:

* alembic upgrade head
* pytest tests/test_user_model.py

CI checks:

* test

Evidence:

* Migration file exists in alembic/versions/

## Artifacts

* src/models/user.py
* alembic/versions/001_add_users.py

## Spec reference

* docs/spec.md
* Section: Data Model

## Dependencies

Blocked by:

* (none)
