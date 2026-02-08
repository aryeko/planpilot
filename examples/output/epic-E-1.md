<!-- PLAN_ID: ebcbac1f2062 -->

<!-- EPIC_ID: E-1 -->

## Goal

Allow users to sign up, log in, and manage sessions securely.

## Scope

In:

* Email/password login
* Session tokens
* Password hashing

Out:

* OAuth providers
* Two-factor authentication

## Success metrics

* Users can register with email and password
* Sessions expire after 24 hours
* Passwords stored as bcrypt hashes

## Risks

* Token leakage if secrets are misconfigured

## Assumptions

* PostgreSQL is available for user storage

## Spec reference

* docs/spec.md#auth
* Section: Authentication

## Stories

* [ ] #2 User Registration
* [ ] #3 User Login and Sessions
