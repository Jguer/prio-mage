"""
Main entry point for the Prio Mage CLI application.
"""

import click
from dotenv import load_dotenv
from typing import Optional
from .github_client import GitHubClient
from .calculator import PriorityCalculator

# Load environment variables
load_dotenv()


def get_current_priority(custom_fields: dict) -> Optional[float]:
    """Extract current priority value from custom fields."""
    # Check for priority or prio fields (case insensitive)
    priority_field = None
    for field_name in custom_fields:
        if field_name.lower() in ['priority', 'prio']:
            priority_field = custom_fields[field_name]
            break
    
    if not priority_field:
        return None
    
    field_type = priority_field.get('type', '')
    field_value = priority_field.get('value')
    
    if field_value is None:
        return None
    
    try:
        if field_type == 'number':
            return float(field_value)
        elif field_type == 'text':
            # Try to parse text as float
            return float(field_value)
        elif field_type == 'single_select':
            # For single select, we can't directly compare numerical values
            # So return None to always update (or implement mapping logic)
            return None
    except (ValueError, TypeError):
        return None
    
    return None


@click.group()
@click.version_option()
def cli():
    """Prio Mage - GitHub GraphQL tool for managing issue priorities in Projects V2."""
    pass


@cli.command()
@click.option('--org', help='GitHub organization')
@click.option('--project', type=int, help='GitHub project number')
@click.option('--dry-run', is_flag=True, help='Show what would be updated without making changes')
def update_priorities(org, project, dry_run):
    """Query project items and update priority fields based on calculations.
    
    Only processes items that have impact and effort custom fields set. Due date is optional.
    """
    client = GitHubClient()
    calculator = PriorityCalculator()
    
    if org and project:
        client.set_project(org, project)
    
    click.echo("Fetching project items from GitHub...")
    click.echo("Note: Only processing items with impact and effort fields set. Due date is optional.")
    items = client.get_issues_with_labels()
    
    # Filter to only issues (not PRs) for priority calculation
    issues = [item for item in items if item['content_type'] == 'Issue']
    
    click.echo(f"Found {len(issues)} issues to process")
    
    for issue in issues:
        priority_score = calculator.calculate_priority(issue)
        priority_level = calculator.get_priority_level(priority_score)
        current_status = issue.get('custom_fields', {}).get('Status', {}).get('value', 'No Status')
        
        # Get current priority to check if update is needed
        current_priority = get_current_priority(issue.get('custom_fields', {}))
        
        # Show key field values for context
        custom_fields = issue.get('custom_fields', {})
        due_value = (custom_fields.get('due') or custom_fields.get('Due', {})).get('value', 'No due date')
        impact_value = (custom_fields.get('impact') or custom_fields.get('Impact', {})).get('value', 'No impact')
        effort_value = (custom_fields.get('effort') or custom_fields.get('Effort', {})).get('value', 'No effort')
        
        # Extract goal from labels for display
        goal_weight = calculator._extract_goal_weight(issue.get('labels', []))
        
        # Check if priority needs updating (only update if delta is superior to 2)
        needs_update = True
        if current_priority is not None:
            # Round both to 2 decimal places for comparison (same as calculator output)
            current_rounded = round(current_priority, 2)
            calculated_rounded = round(priority_score, 2)
            needs_update = abs(current_rounded - calculated_rounded) > 2.0
        
        if dry_run:
            current_priority_str = f"{current_priority:.2f}" if current_priority is not None else "None"
            click.echo(f"Would update issue #{issue['number']}: {issue['title']}")
            click.echo(f"  Current Status: {current_status}")
            click.echo(f"  Current Priority: {current_priority_str}, Calculated: {priority_score:.2f} ({priority_level})")
            click.echo(f"  Goal Weight: {goal_weight}, Due: {due_value}, Impact: {impact_value}, Effort: {effort_value}")
            if not needs_update:
                click.echo(f"  ⏭️  Priority unchanged - skipping update")
        else:
            current_priority_str = f"{current_priority:.2f}" if current_priority is not None else "None"
            click.echo(f"Processing issue #{issue['number']}: {issue['title']}")
            click.echo(f"  Current Status: {current_status}")
            click.echo(f"  Current Priority: {current_priority_str}, Calculated: {priority_score:.2f} ({priority_level})")
            click.echo(f"  Goal Weight: {goal_weight}, Due: {due_value}, Impact: {impact_value}, Effort: {effort_value}")
            
            if not needs_update:
                click.echo(f"  ⏭️  Priority unchanged - skipping update")
            else:
                success = client.update_issue_priority(issue['project_item_id'], priority_score)
                if not success:
                    click.echo(f"  ❌ Failed to update issue #{issue['number']}")
                else:
                    click.echo(f"  ✅ Updated Priority field successfully")
    
    if dry_run:
        click.echo("\nDry run completed. Remove --dry-run to apply changes.")
    else:
        click.echo("\nPriority updates completed!")


@cli.command()
@click.option('--org', help='GitHub organization')
@click.option('--project', type=int, help='GitHub project number')
@click.option('--show-prs', is_flag=True, help='Also show pull requests')
@click.option('--show-fields', is_flag=True, help='Show all custom field values')
def list_issues(org, project, show_prs, show_fields):
    """List all project items with their current status and calculated priorities.
    
    Only shows items that have impact and effort custom fields set. Due date is optional.
    """
    client = GitHubClient()
    calculator = PriorityCalculator()
    
    if org and project:
        client.set_project(org, project)
    
    click.echo("Fetching project items from GitHub...")
    click.echo("Note: Only showing items with impact and effort fields set. Due date is optional.")
    items = client.get_issues_with_labels()
    
    if not show_prs:
        items = [item for item in items if item['content_type'] == 'Issue']
    
    click.echo(f"\nFound {len(items)} items:\n")
    
    for item in items:
        content_type = "PR" if item['content_type'] == 'PullRequest' else "Issue"
        
        if item['content_type'] == 'Issue':
            priority_score = calculator.calculate_priority(item)
            priority_level = calculator.get_priority_level(priority_score)
            priority_display = f"{priority_score:.2f} ({priority_level})"
        else:
            priority_display = 'N/A'
        
        labels = [label['name'] for label in item.get('labels', [])]
        
        click.echo(f"{content_type} #{item['number']}: {item['title']}")
        click.echo(f"  Repository: {item['repository']}")
        click.echo(f"  Labels: {', '.join(labels) if labels else 'None'}")
        
        if item['content_type'] == 'Issue':
            click.echo(f"  Calculated Priority: {priority_display}")
            
            # Show goal weight derived from labels
            goal_weight = calculator._extract_goal_weight(item.get('labels', []))
            click.echo(f"  Goal Weight (from labels): {goal_weight}")
        
        # Show required custom fields prominently
        custom_fields = item.get('custom_fields', {})
        if custom_fields:
            # Show key fields first
            key_fields = ['Status', 'Priority', 'due', 'impact', 'effort']
            click.echo(f"  Key Fields:")
            for field_name in key_fields:
                # Check both capitalized and lowercase versions
                field_data = custom_fields.get(field_name) or custom_fields.get(field_name.lower()) or custom_fields.get(field_name.capitalize())
                if field_data:
                    value = field_data.get('value', 'N/A')
                    if field_name.lower() == 'due' and value:
                        # Format date nicely
                        try:
                            from datetime import datetime
                            due_date = datetime.fromisoformat(value.replace('Z', '+00:00'))
                            days_until = (due_date - datetime.now(due_date.tzinfo)).days
                            if days_until < 0:
                                value = f"{value} (OVERDUE by {abs(days_until)} days)"
                            elif days_until == 0:
                                value = f"{value} (DUE TODAY)"
                            elif days_until <= 3:
                                value = f"{value} (due in {days_until} days)"
                            else:
                                value = f"{value} (due in {days_until} days)"
                        except:
                            pass  # Keep original value if parsing fails
                    
                    click.echo(f"    {field_name}: {value}")
            
            # Show all other fields if requested
            if show_fields:
                other_fields = {k: v for k, v in custom_fields.items() 
                              if k.lower() not in [f.lower() for f in key_fields]}
                if other_fields:
                    click.echo(f"  Other Fields:")
                    for field_name, field_data in other_fields.items():
                        value = field_data.get('value', 'N/A')
                        click.echo(f"    {field_name}: {value}")
        
        click.echo()


@cli.command()
@click.option('--org', help='GitHub organization')  
@click.option('--project', type=int, help='GitHub project number')
@click.option('--issue-number', type=int, multiple=True, required=True, help='Issue number(s) to analyze')
def explain_priority(org, project, issue_number):
    """Show detailed explanation of how priority was calculated for specific issue(s) using the production formula."""
    client = GitHubClient()
    calculator = PriorityCalculator()
    
    if org and project:
        client.set_project(org, project)
    
    issue_numbers = list(issue_number)  # Convert tuple to list
    click.echo(f"Fetching issues: {', '.join(f'#{num}' for num in issue_numbers)}...")
    items = client.get_issues_with_labels()
    
    # Find all requested issues
    found_issues = []
    missing_issues = []
    
    for item in items:
        if item['content_type'] == 'Issue' and item['number'] in issue_numbers:
            found_issues.append(item)
    
    found_numbers = {issue['number'] for issue in found_issues}
    missing_issues = [num for num in issue_numbers if num not in found_numbers]
    
    # Report missing issues
    if missing_issues:
        click.echo(f"❌ Issues not found in project: {', '.join(f'#{num}' for num in missing_issues)}")
    
    if not found_issues:
        click.echo("No issues found to analyze.")
        return
    
    # Process each found issue
    for i, target_issue in enumerate(found_issues):
        if i > 0:  # Add separator between issues
            click.echo("\n" + "="*80 + "\n")
        
        explanation = calculator.get_priority_explanation(target_issue)
        
        click.echo(f"🔍 Production Formula Priority Analysis for Issue #{target_issue['number']}")
        click.echo(f"Title: {target_issue['title']}")
        click.echo(f"Repository: {target_issue['repository']}")
        click.echo(f"Final Priority Score: {explanation['total_score']:.2f}")
        click.echo(f"Priority Level: {explanation['priority_level']}")
        
        factors = explanation.get('factors', {})
        
        if factors.get('critical_override'):
            click.echo(f"\n🚨 Critical Override Applied")
            click.echo(f"This issue has critical severity labels and receives maximum priority (200.0)")
            continue
        
        click.echo(f"\n📊 Production Formula Breakdown:")
        click.echo(f"  Goal Weight: {factors.get('goal_weight', 0):.2f}")
        click.echo(f"  Impact: {factors.get('impact', 0):.2f}")
        click.echo(f"  Effort (days): {factors.get('effort_days', 0):.2f}")
        click.echo(f"  Importance Base (Goal Weight × Impact): {factors.get('goal_weight_times_impact', 0):.2f}")
        
        click.echo(f"\n🔧 Effort Adjustment:")
        click.echo(f"  Effort Threshold: {factors.get('effort_threshold', 0):.2f}")
        click.echo(f"  Effort Logistic Component: {factors.get('effort_logistic_denominator', 0):.2f}")
        click.echo(f"  Base Score (S): {factors.get('base_score_S', 0):.2f}")
        
        if factors.get('days_till_due_date') is not None:
            click.echo(f"\n⏰ Due Date Urgency:")
            click.echo(f"  Days Till Due: {factors.get('days_till_due_date', 0):.2f}")
            click.echo(f"  Median Working Time: {factors.get('median_working_time', 0):.2f}")
            click.echo(f"  Due Date Logistic Component: {factors.get('due_date_logistic_denominator', 0):.2f}")
            click.echo(f"  Due Date Urgency Applied: ✅")
        else:
            click.echo(f"\n⏰ Due Date Urgency: Not Applied (no due date)")
        
        # Show current custom fields
        custom_fields = target_issue.get('custom_fields', {})
        if custom_fields:
            click.echo(f"\n🏷️  Current Custom Fields:")
            for field_name, field_data in custom_fields.items():
                value = field_data.get('value', 'N/A')
                click.echo(f"  {field_name}: {value}")


@cli.command()
@click.option('--org', help='GitHub organization')
@click.option('--project', type=int, help='GitHub project number')
def show_project_info(org, project):
    """Show detailed information about the GitHub project and its fields."""
    client = GitHubClient()
    
    if org and project:
        client.set_project(org, project)
    
    click.echo("Fetching project information...")
    project_info = client.get_repository_info()
    
    click.echo(f"\nProject: {project_info['name']}")
    click.echo(f"Description: {project_info['description']}")
    click.echo(f"URL: {project_info['url']}")
    
    click.echo(f"\nCustom Fields:")
    for field in project_info.get('fields', []):
        field_type = field.get('__typename', 'Unknown')
        field_name = field.get('name', 'Unnamed')
        data_type = field.get('dataType', 'Unknown')
        
        click.echo(f"  {field_name} ({data_type})")
        
        # Show options for single select fields
        if field_type == 'ProjectV2SingleSelectField' and 'options' in field:
            for option in field['options']:
                click.echo(f"    - {option['name']} (Color: {option.get('color', 'Default')})")


if __name__ == '__main__':
    cli() 