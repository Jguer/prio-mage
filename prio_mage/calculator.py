"""
Priority calculation logic for GitHub issues in Projects V2 using production formula.
"""

import math
from typing import Any, Dict, List
from datetime import datetime, timezone


class PriorityCalculator:
    """Calculate priority scores for GitHub issues using the production formula with logistic functions."""
    
    def __init__(self):
        # Goal weights based on strategic focus
        self.goal_weights = {
            # Customer-focused goals
            'customer acquisition': 1.0,
            'customer retention': 0.9,
            'user experience': 0.8,
            'product market fit': 1.0,
            
            # Technical goals
            'technical debt': 0.7,
            'performance': 0.8,
            'security': 1.0,
            'scalability': 0.7,
            'infrastructure': 0.6,
            
            # Business goals
            'revenue': 1.0,
            'cost reduction': 0.8,
            'compliance': 0.9,
            'operations': 0.6,
            
            # Default
            'general': 1.0,
        }
        
        # Status-based goal weight multipliers
        self.status_multipliers = {
            'blocked': 1.5,     # Highest priority to unblock work
            'in progress': 1.3, # High priority to finish started work
            'todo': 1.2,        # Boosted priority for TODO items
            'next': 1.1,        # Moderate priority for queued items  
            'ready': 1.0,       # Baseline for prepared items
            'done': 0.0,        # Completed items get zero priority
            'backlog': 0.8,     # Lower priority for backlog items
            'cancelled': 0.0,   # Cancelled items get zero priority
            'on hold': 0.6,     # Lowest priority for paused items
        }
        
        # Effort size mappings to implementation time (in days)
        # Using 75th percentile of historical data for variability
        self.effort_days = {
            'xs': 1.5,
            'small': 3.0,
            's': 3.0,
            'medium': 8.0,
            'm': 8.0,
            'large': 20.0,
            'l': 20.0,
            'xl': 40.0,
        }
        
        # Fixed baseline working time for deadline calculations (not effort-dependent)
        self.baseline_working_time = 60
        
        # Severity toggle for critical issues
        self.critical_labels = {
            'critical', 'severity:critical', 'security', 'hotfix', 
            'urgent', 'P0', 'P1', 'P2'
        }
    
    def calculate_priority(self, issue: Dict[str, Any]) -> float:
        """Calculate priority score using the production formula."""
        
        # Check for critical severity override
        if self._is_critical_issue(issue):
            return 0.0  # Minimum score = maximum priority for critical issues
        
        # Extract custom fields
        custom_fields = issue.get('custom_fields', {})
        
        # Get Goal Weight from labels (fallback to impact if no goal found)
        base_goal_weight = self._extract_goal_weight(issue.get('labels', []))
        
        # Apply status-based multiplier to goal weight
        status_multiplier = self._get_status_multiplier(custom_fields)
        goal_weight = base_goal_weight * status_multiplier
        
        # Get Impact from custom field
        impact = self._get_impact_value(custom_fields)
        
        # Get Effort from custom field
        effort_days = self._get_effort_days(custom_fields)
        
        # Get due date
        due_date = self._get_due_date(custom_fields)
        
        # Calculate the production formula
        priority = self._calculate_production_formula(
            goal_weight, impact, effort_days, due_date
        )
        
        # Round to 2 decimal places to ensure GraphQL API compatibility (max 8 allowed)
        return round(priority, 2)
    
    def _calculate_production_formula(self, goal_weight: float, impact: float, 
                                         effort_days: float, due_date: datetime | None = None) -> float:
        """
        Calculate priority using the exact formula provided:
        
        S = 200 - (Goal weight × Impact) - (Goal weight × Impact) / (1 + e^(-0.6 × (Effort - (0.05 × Goal weight × Impact + 5))))
        Priority = S - S / (1 + e^(-0.2 × (Days till due date - (Median working time × 1.5)))
        
        Note: LOWER scores indicate HIGHER priority (more urgent/important items to work on first).
        """
        # Calculate the product of Goal Weight and Impact, as it's used multiple times
        goal_impact_product = goal_weight * impact

        # --- Calculate the intermediate Score (S) ---
        # This part of the formula evaluates the task without considering the due date.
        try:
            s_exponent = -0.6 * (effort_days - (0.05 * goal_impact_product + 5))
            s_denominator = 1 + math.exp(s_exponent)
            s_score = 200 - goal_impact_product - (goal_impact_product / s_denominator)
        except OverflowError:
            # If the exponent is too large, the denominator is effectively infinite,
            # making the fraction term zero.
            s_score = 200 - goal_impact_product

        # --- Calculate the final Priority using the S-Score and time factors ---
        # This part adjusts the S-Score based on urgency.
        if due_date:
            days_till_due_date = self._calculate_days_till_due(due_date)
            median_working_time = self.baseline_working_time  # Using baseline_working_time as median_working_time
            
            try:
                priority_exponent = -0.2 * (days_till_due_date - (median_working_time * 1.5))
                priority_denominator = 1 + math.exp(priority_exponent)
                final_priority = s_score - (s_score / priority_denominator)
            except OverflowError:
                # If the exponent is too large, the denominator is effectively infinite,
                # making the fraction zero. This means the task is not urgent at all.
                final_priority = s_score - 0
        else:
            # If no due date, just return S
            final_priority = s_score

        # Clamp to the allowed range [0, 200]
        return max(0.0, min(200.0, final_priority))
    
    def _is_critical_issue(self, issue: Dict[str, Any]) -> bool:
        """Check if issue has critical severity labels or custom field."""
        # Check labels first
        labels = issue.get('labels', [])
        for label in labels:
            label_name = label.get('name', '').lower()
            if any(critical_label in label_name for critical_label in self.critical_labels):
                return True
        
        # Check custom fields for critical field
        custom_fields = issue.get('custom_fields', {})
        critical_field = custom_fields.get('critical') or custom_fields.get('Critical')
        if critical_field and critical_field.get('value'):
            critical_value = critical_field.get('value', '').lower().strip()
            # Check if the value indicates critical severity
            if critical_value == 'critical':
                return True
        
        return False
    
    def _extract_goal_weight(self, labels: List[Dict[str, Any]]) -> float:
        """Extract goal weight from issue labels."""
        goal_weight = 0.5  # Default
        
        for label in labels:
            label_name = label.get('name', '').lower()
            
            # Check for goal-related labels
            for goal_key, weight in self.goal_weights.items():
                if goal_key.replace(' ', '') in label_name.replace(' ', '').replace('-', '').replace('_', ''):
                    goal_weight = max(goal_weight, weight)
        
        return goal_weight
    
    def _get_status_multiplier(self, custom_fields: Dict[str, Any]) -> float:
        """Get status-based multiplier from custom fields."""
        status_field = custom_fields.get('Status') or custom_fields.get('status')
        if not status_field or not status_field.get('value'):
            return 1.0  # Default multiplier if no status
        
        status_value = status_field.get('value', '').lower().strip()
        
        # Check for exact matches first
        if status_value in self.status_multipliers:
            return self.status_multipliers[status_value]
        
        # Check for partial matches
        for status_key, multiplier in self.status_multipliers.items():
            if status_key in status_value:
                return multiplier
        
        return 1.0  # Default multiplier for unknown status values
    
    def _get_impact_value(self, custom_fields: Dict[str, Any]) -> float:
        """Get impact value from custom fields."""
        impact_field = custom_fields.get('impact') or custom_fields.get('Impact')
        if not impact_field or impact_field.get('value') is None:
            return 5.0  # Default medium impact
        
        impact_value = impact_field.get('value', 5.0)
        return float(impact_value)
    
    def _get_effort_days(self, custom_fields: Dict[str, Any]) -> float:
        """Get effort in days from custom fields."""
        effort_field = custom_fields.get('effort') or custom_fields.get('Effort')
        if not effort_field or not effort_field.get('value'):
            return 8.0  # Default medium effort
        
        effort_value = effort_field.get('value', '').lower().strip()
        
        # Check for exact matches first
        if effort_value in self.effort_days:
            return self.effort_days[effort_value]
        
        # Check for partial matches
        for effort_key, days in self.effort_days.items():
            if effort_key in effort_value:
                return days
        
        return 8.0  # Default for unknown effort values
    
    def _get_due_date(self, custom_fields: Dict[str, Any]) -> datetime | None:
        """Get due date from custom fields."""
        due_field = custom_fields.get('due') or custom_fields.get('Due')
        if not due_field or not due_field.get('value'):
            return None
        
        try:
            due_date_str = due_field.get('value')
            return datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    
    def _calculate_days_till_due(self, due_date: datetime | None) -> float:
        """Calculate days until due date."""
        if not due_date:
            return float('inf')  # No urgency if no due date
        
        now = datetime.now(timezone.utc)
        
        # Ensure both datetimes are timezone-aware
        if due_date.tzinfo is None:
            # If due_date is naive, assume it's in UTC
            due_date = due_date.replace(tzinfo=timezone.utc)
        elif now.tzinfo is None:
            # If now is naive, make it UTC-aware
            now = now.replace(tzinfo=timezone.utc)
        
        days_till_due = (due_date - now).total_seconds() / (24 * 3600)
        return days_till_due
    
    def get_priority_level(self, priority_score: float) -> str:
        """
        Convert numerical priority score to level string.
        
        Note: Lower priority scores indicate HIGHER urgency/importance.
        - "High" priority items should be worked on first
        - "Low" priority items should be worked on later
        """
        if priority_score < 10:
            return "Critical"
        elif priority_score <= 20:
            return "High"
        elif priority_score <= 50:
            return "Medium"
        elif priority_score <= 100:
            return "Low"
        elif priority_score <= 160:
            return "Backlog"
        else:
            return "Icebox"
    
    def get_priority_explanation(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed explanation of how priority was calculated."""
        custom_fields = issue.get('custom_fields', {})

        # Check for critical override
        is_critical = self._is_critical_issue(issue)
        if is_critical:
            return {
                'total_score': 0.0,
                'priority_level': 'Critical',
                'explanation': 'Critical severity override - minimum score = maximum priority',
                'factors': {
                    'critical_override': True
                }
            }

        # Extract components
        base_goal_weight = self._extract_goal_weight(issue.get('labels', []))
        status_multiplier = self._get_status_multiplier(custom_fields)
        goal_weight = base_goal_weight * status_multiplier
        impact = self._get_impact_value(custom_fields)
        effort_days = self._get_effort_days(custom_fields)
        due_date = self._get_due_date(custom_fields)

        # Calculate intermediate values using the exact formula
        goal_impact_product = goal_weight * impact
        
        # Initialize variables
        s_exponent = None
        s_denominator = None
        priority_exponent = None
        priority_denominator = None
        
        # Calculate S score with overflow protection
        try:
            s_exponent = -0.6 * (effort_days - (0.05 * goal_impact_product + 5))
            s_denominator = 1 + math.exp(s_exponent)
            s_score = 200 - goal_impact_product - (goal_impact_product / s_denominator)
        except OverflowError:
            s_score = 200 - goal_impact_product
        
        # Calculate due date components if due date exists
        if due_date:
            days_till_due_date = self._calculate_days_till_due(due_date)
            median_working_time = self.baseline_working_time
            
            try:
                priority_exponent = -0.2 * (days_till_due_date - (median_working_time * 1.5))
                priority_denominator = 1 + math.exp(priority_exponent)
                final_priority = s_score - (s_score / priority_denominator)
            except OverflowError:
                final_priority = s_score - 0
        else:
            days_till_due_date = None
            final_priority = s_score

        total_score = round(max(0.0, min(200.0, final_priority)), 2)

        explanation = {
            'total_score': total_score,
            'priority_level': self.get_priority_level(total_score),
            'factors': {
                'base_goal_weight': base_goal_weight,
                'status_multiplier': status_multiplier,
                'goal_weight': goal_weight,
                'impact': impact,
                'effort_days': effort_days,
                'goal_impact_product': goal_impact_product,
                'goal_weight_times_impact': goal_impact_product,  # Alias for CLI display
                'effort_threshold': 0.05 * goal_impact_product + 5,  # For CLI display
                'effort_logistic_denominator': s_denominator,  # Alias for CLI display
                'base_score_S': s_score,  # Alias for CLI display
                's_exponent': s_exponent,
                's_denominator': s_denominator,
                's_score': s_score,
                'days_till_due_date': days_till_due_date,
                'median_working_time': self.baseline_working_time if due_date else None,
                'due_date_logistic_denominator': priority_denominator,  # Alias for CLI display
                'priority_exponent': priority_exponent,
                'priority_denominator': priority_denominator,
                'final_priority_before_clamp': final_priority,
            }
        }

        return explanation 