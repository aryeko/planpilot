"""GraphQL query and mutation constants for the GitHub provider."""

FETCH_PROJECT = """
query($org: String!, $number: Int!) {
  organization(login: $org) {
    projectV2(number: $number) {
      id
      fields(first: 100) {
        nodes {
          ... on ProjectV2FieldCommon { id name }
          ... on ProjectV2SingleSelectField { id name options { id name } }
          ... on ProjectV2IterationField {
            id name configuration { iterations { id title startDate duration } }
          }
        }
      }
    }
  }
}
"""

FETCH_REPO = """
query($owner: String!, $name: String!, $label: String!) {
  repository(owner: $owner, name: $name) {
    id
    issueTypes(first: 100) { nodes { id name } }
    labels(query: $label, first: 1) { nodes { id name } }
  }
}
"""

SEARCH_ISSUES = """
query($searchQuery: String!, $after: String) {
  search(query: $searchQuery, type: ISSUE, first: 100, after: $after) {
    nodes {
      ... on Issue { id number body }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

CREATE_ISSUE = """
mutation($input: CreateIssueInput!) {
  createIssue(input: $input) {
    issue { id number url }
  }
}
"""

UPDATE_ISSUE_TYPE = """
mutation($id: ID!, $issueTypeId: ID!) {
  updateIssue(input: {id: $id, issueTypeId: $issueTypeId}) {
    issue { id }
  }
}
"""

FETCH_PROJECT_ITEMS = """
query($projectId: ID!, $after: String) {
  node(id: $projectId) {
    ... on ProjectV2 {
      items(first: 100, after: $after) {
        nodes { id content { ... on Issue { id } } }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""

ADD_PROJECT_ITEM = """
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}
"""

UPDATE_PROJECT_FIELD = """
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId,
    itemId: $itemId,
    fieldId: $fieldId,
    value: $value
  }) {
    projectV2Item { id }
  }
}
"""

FETCH_ISSUE_RELATIONS = """
query($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on Issue {
      id
      parent { id }
      blockedBy(first: 100) { nodes { id } }
    }
  }
}
"""

ADD_SUB_ISSUE = """
mutation($issueId: ID!, $subIssueId: ID!) {
  addSubIssue(input: {issueId: $issueId, subIssueId: $subIssueId}) {
    issue { id }
  }
}
"""

ADD_BLOCKED_BY = """
mutation($issueId: ID!, $blockingIssueId: ID!) {
  addBlockedBy(input: {issueId: $issueId, blockingIssueId: $blockingIssueId}) {
    issue { id }
  }
}
"""
