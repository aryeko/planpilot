<!-- PLAN_ID: ebcbac1f2062 -->

<!-- TASK_ID: T-2 -->

## Story

* #2

## Motivation

Users need an API to create accounts.

## Scope

In:

* (none)

Out:

* (none)

## Requirements

* POST /api/register accepts email and password
* Returns 201 on success, 422 on validation error, 409 on duplicate

## Acceptance criteria

* Valid registration returns 201 with user ID
* Duplicate email returns 409
* Missing fields return 422

## Verification

Commands:

* pytest tests/test_register.py -v

CI checks:

* test
* lint

Evidence:

* API endpoint responds correctly

Manual steps:

* Call POST /api/register via curl and verify response

## Artifacts

* src/routes/register.py
* tests/test_register.py

## Spec reference

* docs/spec.md
* Section: Registration API

## Dependencies

Blocked by:

* #4
