<!-- PLAN_ID: ebcbac1f2062 -->

<!-- TASK_ID: T-3 -->

## Story

* #3

## Motivation

Users need to authenticate and receive session tokens.

## Scope

In:

* (none)

Out:

* (none)

## Requirements

* POST /api/login accepts email and password
* Returns JWT token on valid credentials
* Returns 401 on invalid credentials

## Acceptance criteria

* Valid login returns 200 with JWT token
* Invalid password returns 401
* Token contains user ID and expiration

## Verification

Commands:

* pytest tests/test_login.py -v

CI checks:

* test

Evidence:

* JWT token decodes correctly with expected claims

## Artifacts

* src/routes/login.py
* src/auth/tokens.py
* tests/test_login.py

## Spec reference

* docs/spec.md
* Section: Login API

## Dependencies

Blocked by:

* #4
