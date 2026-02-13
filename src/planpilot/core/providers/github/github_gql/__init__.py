"""Core compatibility wrappers for generated GitHub GraphQL client modules."""

from planpilot.core.providers.github.github_gql.client import GitHubGraphQLClient
from planpilot.core.providers.github.github_gql.exceptions import (
    GraphQLClientError,
    GraphQLClientGraphQLError,
    GraphQLClientGraphQLMultiError,
    GraphQLClientHttpError,
    GraphQLClientInvalidResponseError,
)

__all__ = [
    "GitHubGraphQLClient",
    "GraphQLClientError",
    "GraphQLClientGraphQLError",
    "GraphQLClientGraphQLMultiError",
    "GraphQLClientHttpError",
    "GraphQLClientInvalidResponseError",
]
