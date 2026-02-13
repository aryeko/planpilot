"""Relation helpers for GitHub provider."""

from __future__ import annotations

from planpilot.core.providers.github.github_gql.exceptions import GraphQLClientError


def is_duplicate_relation_error(exc: GraphQLClientError) -> bool:
    """Check if a GraphQL error indicates a relation that already exists."""
    msg = str(exc).lower()
    return (
        "duplicate sub-issues" in msg
        or "may only have one parent" in msg
        or "already exists" in msg
        or "has already been taken" in msg
    )


def is_missing_relation_error(exc: GraphQLClientError) -> bool:
    """Check if a GraphQL error indicates a relation that is already absent."""
    msg = str(exc).lower()
    return "not found" in msg or "does not exist" in msg or "was not found" in msg
