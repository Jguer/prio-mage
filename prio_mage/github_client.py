"""
GitHub GraphQL client for querying issues and updating custom fields in Projects V2.
"""

import os
import requests
from dataclasses import dataclass
from typing import Any


@dataclass
class Label:
    """Represents a GitHub label."""
    id: str
    name: str
    color: str
    description: str


@dataclass  
class CustomFieldValue:
    """Represents a custom field value in a GitHub project."""
    type: str
    value: Any
    field_id: str


@dataclass
class ProjectItem:
    """Represents a GitHub project item (issue or PR)."""
    project_item_id: str
    content_type: str
    id: str
    number: int
    title: str
    body: str
    created_at: str
    updated_at: str
    author: str
    repository: str
    labels: list[Label]
    assignees: list[str] | None
    comment_count: int
    reaction_count: int
    custom_fields: dict[str, CustomFieldValue]


@dataclass
class ProjectFieldOption:
    """Represents an option for a single-select project field."""
    id: str
    name: str
    color: str


@dataclass
class ProjectField:
    """Represents a project field definition."""
    id: str
    name: str
    data_type: str
    field_type: str
    options: list[ProjectFieldOption] | None = None


@dataclass
class ProjectInfo:
    """Represents project information."""
    project_id: str
    project_title: str
    fields: list[ProjectField]


@dataclass
class RepositoryInfo:
    """Represents repository/project information."""
    id: str
    name: str
    description: str
    url: str
    is_private: bool
    fields: list[ProjectField]


class GitHubClient:
    """Client for interacting with GitHub GraphQL API for Projects V2."""
    token: str
    organization: str
    project_number: int
    base_url: str
    headers: dict[str, str]
    
    def __init__(self, token: str | None = None, organization: str | None = None, project_number: int | None = None):
        self.token = token or os.getenv('GITHUB_TOKEN') or ''
        self.organization = organization or os.getenv('GITHUB_ORG', 'tinor-labs')
        self.project_number = project_number or int(os.getenv('GITHUB_PROJECT_NUMBER', '1'))
        self.base_url = 'https://api.github.com/graphql'
        
        if not self.token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable.")
        
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }
    
    def set_project(self, organization: str, project_number: int):
        """Set the target organization and project."""
        self.organization = organization
        self.project_number = project_number
    
    def _execute_query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query."""
        payload = {
            'query': query,
            'variables': variables or {}
        }
        
        response = requests.post(
            self.base_url,
            json=payload,
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"GraphQL query failed: {response.status_code} - {response.text}")
        
        result = response.json()
        
        if 'errors' in result:
            raise Exception(f"GraphQL errors: {result['errors']}")
        
        return result.get('data', {})
    
    def get_issues_with_labels(self) -> list[ProjectItem]:
        """Get all project items (issues/PRs) with their custom field values, filtered for items with due, impact, and effort fields."""
        query = """
        query GetProjectItems($org: String!, $projectNumber: Int!, $cursor: String) {
            organization(login: $org) {
                projectV2(number: $projectNumber) {
                    id
                    title
                    items(first: 100, after: $cursor) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        nodes {
                            id
                            content {
                                __typename
                                ... on Issue {
                                    id
                                    title
                                    number
                                    body
                                    createdAt
                                    updatedAt
                                    author {
                                        login
                                    }
                                    labels(first: 50) {
                                        nodes {
                                            id
                                            name
                                            color
                                            description
                                        }
                                    }
                                    assignees(first: 10) {
                                        nodes {
                                            login
                                        }
                                    }
                                    comments {
                                        totalCount
                                    }
                                    reactions {
                                        totalCount
                                    }
                                    repository {
                                        name
                                        owner {
                                            login
                                        }
                                    }
                                }
                                ... on PullRequest {
                                    id
                                    title
                                    number
                                    body
                                    createdAt
                                    updatedAt
                                    author {
                                        login
                                    }
                                    labels(first: 50) {
                                        nodes {
                                            id
                                            name
                                            color
                                            description
                                        }
                                    }
                                    assignees(first: 10) {
                                        nodes {
                                            login
                                        }
                                    }
                                    comments {
                                        totalCount
                                    }
                                    reactions {
                                        totalCount
                                    }
                                    repository {
                                        name
                                        owner {
                                            login
                                        }
                                    }
                                }
                            }
                            fieldValues(first: 20) {
                                nodes {
                                    __typename
                                    ... on ProjectV2ItemFieldDateValue {
                                        field {
                                            ... on ProjectV2Field {
                                                id
                                                name
                                            }
                                        }
                                        date
                                    }
                                    ... on ProjectV2ItemFieldSingleSelectValue {
                                        field {
                                            ... on ProjectV2SingleSelectField {
                                                id
                                                name
                                            }
                                        }
                                        name
                                    }
                                    ... on ProjectV2ItemFieldNumberValue {
                                        field {
                                            ... on ProjectV2Field {
                                                id
                                                name
                                            }
                                        }
                                        number
                                    }
                                    ... on ProjectV2ItemFieldTextValue {
                                        field {
                                            ... on ProjectV2Field {
                                                id
                                                name
                                            }
                                        }
                                        text
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        all_items: list[ProjectItem] = []
        cursor = None
        
        while True:
            variables = {
                'org': self.organization,
                'projectNumber': self.project_number,
                'cursor': cursor
            }
            
            data = self._execute_query(query, variables)
            organization = data.get('organization', {})
            project = organization.get('projectV2', {})
            items = project.get('items', {})
            
            # Process each project item
            for item in items.get('nodes', []):
                content = item.get('content')
                if not content:
                    continue
                
                # Only process Issues and Pull Requests
                if content.get('__typename') not in ['Issue', 'PullRequest']:
                    continue
                
                # Process labels
                labels = []
                if content.get('labels', {}).get('nodes'):
                    labels = [
                        Label(
                            id=label['id'],
                            name=label['name'],
                            color=label['color'],
                            description=label.get('description', '')
                        )
                        for label in content['labels']['nodes']
                    ]
                
                # Process assignees
                assignees = []
                if content.get('assignees', {}).get('nodes'):
                    assignees = [assignee['login'] for assignee in content['assignees']['nodes']]
                
                # Initialize custom fields dict
                custom_fields: dict[str, CustomFieldValue] = {}
                
                # Process custom fields
                for field_value in item.get('fieldValues', {}).get('nodes', []):
                    field_info = field_value.get('field', {})
                    field_name = field_info.get('name', '')
                    
                    if field_value.get('__typename') == 'ProjectV2ItemFieldSingleSelectValue':
                        custom_fields[field_name] = CustomFieldValue(
                            type='single_select',
                            value=field_value.get('name', ''),
                            field_id=field_info.get('id', '')
                        )
                    elif field_value.get('__typename') == 'ProjectV2ItemFieldTextValue':
                        custom_fields[field_name] = CustomFieldValue(
                            type='text',
                            value=field_value.get('text', ''),
                            field_id=field_info.get('id', '')
                        )
                    elif field_value.get('__typename') == 'ProjectV2ItemFieldNumberValue':
                        custom_fields[field_name] = CustomFieldValue(
                            type='number',
                            value=field_value.get('number', 0),
                            field_id=field_info.get('id', '')
                        )
                    elif field_value.get('__typename') == 'ProjectV2ItemFieldDateValue':
                        custom_fields[field_name] = CustomFieldValue(
                            type='date',
                            value=field_value.get('date', ''),
                            field_id=field_info.get('id', '')
                        )
                
                # Filter: Only include items that have impact and effort fields (due date is optional)
                required_fields = ['impact', 'effort']
                custom_field_names: list[str] = [name.lower() for name in custom_fields.keys()]
                
                has_all_required = all(
                    field.lower() in custom_field_names 
                    for field in required_fields
                )
                
                # Also check that the fields have actual values (not empty)
                if has_all_required:
                    impact_field = None
                    effort_field = None
                    
                    for field_name, field_data in custom_fields.items():
                        field_name_lower = field_name.lower()
                        if field_name_lower == 'impact':
                            impact_field = field_data
                        elif field_name_lower == 'effort':
                            effort_field = field_data
                    
                    # Verify field types and non-empty values
                    valid_item = True
                    
                    if not impact_field or impact_field.type != 'number' or impact_field.value is None:
                        valid_item = False
                    if not effort_field or effort_field.type != 'single_select' or not effort_field.value:
                        valid_item = False
                    
                    if valid_item:
                        # Create ProjectItem dataclass instance
                        project_item = ProjectItem(
                            project_item_id=item['id'],
                            content_type=content['__typename'],
                            id=content['id'],
                            number=content['number'],
                            title=content['title'],
                            body=content.get('body', ''),
                            created_at=content['createdAt'],
                            updated_at=content['updatedAt'],
                            author=content.get('author', {}).get('login', ''),
                            repository=f"{content['repository']['owner']['login']}/{content['repository']['name']}",
                            labels=labels,
                            assignees=assignees,
                            comment_count=content.get('comments', {}).get('totalCount', 0),
                            reaction_count=content.get('reactions', {}).get('totalCount', 0),
                            custom_fields=custom_fields
                        )
                        all_items.append(project_item)
            
            page_info = items.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                break
            
            cursor = page_info.get('endCursor')
        
        return all_items
    
    def get_project_fields(self) -> ProjectInfo:
        """Get project field definitions including options for single select fields."""
        query = """
        query GetProjectFields($org: String!, $projectNumber: Int!) {
            organization(login: $org) {
                projectV2(number: $projectNumber) {
                    id
                    title
                    fields(first: 20) {
                        nodes {
                            __typename
                            ... on ProjectV2Field {
                                id
                                name
                                dataType
                            }
                            ... on ProjectV2SingleSelectField {
                                id
                                name
                                dataType
                                options {
                                    id
                                    name
                                    color
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            'org': self.organization,
            'projectNumber': self.project_number
        }
        
        data = self._execute_query(query, variables)
        organization = data.get('organization', {})
        project = organization.get('projectV2', {})
        
        # Process fields into ProjectField objects
        fields: list[ProjectField] = []
        for field_data in project.get('fields', {}).get('nodes', []):
            field_type = field_data.get('__typename', '')
            options = None
            
            # Process options for single select fields
            if field_type == 'ProjectV2SingleSelectField' and field_data.get('options'):
                options = [
                    ProjectFieldOption(
                        id=option['id'],
                        name=option['name'],
                        color=option['color']
                    )
                    for option in field_data['options']
                ]
            
            project_field = ProjectField(
                id=field_data.get('id', ''),
                name=field_data.get('name', ''),
                data_type=field_data.get('dataType', ''),
                field_type=field_type,
                options=options
            )
            fields.append(project_field)
        
        return ProjectInfo(
            project_id=project.get('id', ''),
            project_title=project.get('title', ''),
            fields=fields
        )
    
    def update_item_field_value(self, project_id: str, item_id: str, field_id: str, value: Any) -> bool:
        """Update a custom field value for a project item."""
        mutation = """
        mutation UpdateProjectV2ItemFieldValue($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
            updateProjectV2ItemFieldValue(input: {
                projectId: $projectId,
                itemId: $itemId,
                fieldId: $fieldId,
                value: $value
            }) {
                projectV2Item {
                    id
                }
            }
        }
        """
        
        variables = {
            'projectId': project_id,
            'itemId': item_id,
            'fieldId': field_id,
            'value': value
        }
        
        try:
            _ = self._execute_query(mutation, variables)
            return True
        except Exception as e:
            print(f"Error updating field: {e}")
            return False
    
    def update_issue_priority(self, item_id: str, priority_score: float) -> bool:
        """Update an issue's priority custom field with the calculated score."""
        # First get the project fields to find the Priority field
        project_info = self.get_project_fields()
        
        priority_field = None
        
        # Find the Priority field (could be number or text field)
        for field in project_info.fields:
            field_name = field.name.lower()
            if field_name in ['priority', 'prio']:
                priority_field = field
                break
        
        if not priority_field:
            print("Priority field not found in project")
            return False
        
        field_type = priority_field.field_type
        field_id = priority_field.id
        
        # Prepare the value based on field type
        if field_type == 'ProjectV2Field' and priority_field.data_type == 'NUMBER':
            # Number field - use the score directly
            value = {'number': priority_score}
        elif field_type == 'ProjectV2Field' and priority_field.data_type == 'TEXT':
            # Text field - use the score as text
            value = {'text': str(round(priority_score, 2))}
        elif field_type == 'ProjectV2SingleSelectField':
            # Single select field - map score to options
            target_option = self._map_score_to_option(priority_score, priority_field.options or [])
            if not target_option:
                print(f"Could not map priority score {priority_score} to available options")
                return False
            value = {'singleSelectOptionId': target_option}
        else:
            print(f"Unsupported field type: {field_type}")
            return False
        
        # Update the field value
        return self.update_item_field_value(
            project_info.project_id,
            item_id,
            field_id,
            value
        )
    
    def _map_score_to_option(self, priority_score: float, options: list[ProjectFieldOption]) -> str | None:
        """Map priority score to single select option ID."""
        # Define score ranges for different priority levels
        if priority_score >= 150:
            target_names = ['critical', 'highest', 'p0']
        elif priority_score >= 120:
            target_names = ['high', 'p1']
        elif priority_score >= 80:
            target_names = ['medium', 'normal', 'p2']
        elif priority_score >= 40:
            target_names = ['low', 'p3']
        else:
            target_names = ['backlog', 'lowest', 'p4']
        
        # Find matching option
        for option in options:
            option_name = option.name.lower()
            for target_name in target_names:
                if target_name in option_name:
                    return str(option.id)
        
        # Fallback to first option if no match found
        if options:
            return str(options[0].id)
        
        return None
  
    def get_repository_info(self) -> RepositoryInfo:
        """Get basic project information."""
        project_info = self.get_project_fields()
        
        return RepositoryInfo(
            id=project_info.project_id,
            name=project_info.project_title,
            description=f"GitHub Project V2 (Organization: {self.organization}, Number: {self.project_number})",
            url=f"https://github.com/orgs/{self.organization}/projects/{self.project_number}",
            is_private=False,  # Projects visibility depends on organization settings
            fields=project_info.fields
        ) 