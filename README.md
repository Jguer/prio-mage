# Prio Mage

A tool that helps you prioritize GitHub issues by automatically calculating priority scores based on impact, effort, and deadlines.

**What it does**: This tool looks at your GitHub Project issues and calculates which ones you should work on first. It only works with issues that have three specific fields filled out: due date, impact score, and effort level.

Based on [Konstantin Valeev's (Jetbrains) presentation, 2024](https://www.youtube.com/watch?v=m7qMfUytiio)

## What This Tool Does

- **Reads Your GitHub Projects**: Gets your issues and pull requests with their custom information
- **Smart Filtering**: Only looks at items that have impact scores, and effort levels set
- **Smart Priority Calculator**: Uses a formula that considers:
  - **Goal Importance**: How important the issue is based on its labels (like Security, Customer needs, etc.)
  - **Impact Score**: The impact number you set (1-100 scale)
  - **Effort Level**: How much work it takes (prevents penalizing big important projects)
  - **How Soon It's Due**: Things due soon get higher priority
  - **Critical Issues**: Security and critical issues always get top priority
- **Priority Scores**: Gives each issue a number from 0-200 (lower numbers = higher priority)
- **Updates Your Project**: Automatically puts the calculated priority scores back into your GitHub Project
- **Shows You How It Works**: Explains exactly how each score was calculated
- **Easy to Use**: Simple command-line interface

## How the Priority Formula Works

The tool uses a smart formula that balances importance with urgency.

**Important**: Lower scores mean higher priority - work on items with lower scores first.

```
Priority = Base Score - Impact Bonus - Effort Adjustment - Urgency Boost
```

### What Goes Into the Calculation:
1. **Base Importance**: Goal Weight × Impact Score
2. **Effort Adjustment**: Makes sure big important projects don't get unfairly penalized
3. **Urgency Boost**: Items due soon get priority bumps
4. **Critical Override**: Security and critical issues always get score 0 (highest priority)

## Required Fields in Your GitHub Project

Your GitHub Project needs these custom fields set up:

1. **`due`** (DATE) - When the issue needs to be done
2. **`impact`** (NUMBER) - How much impact it has (usually 1-10)  
3. **`effort`** (SINGLE_SELECT) - How much work it takes (XS, Small, Medium, Large, XL)
4. **`Priority`** (NUMBER/TEXT/SINGLE_SELECT) - Where the calculated scores go

The tool only processes issues that have the first three fields filled out.

## Goal Types (Based on Issue Labels)

The tool automatically detects what type of goal an issue supports by looking at its labels:

- **Customer Acquisition**: 1.0 (highest weight)
- **Security**: 1.0  
- **Revenue**: 1.0
- **Product Market Fit**: 1.0
- **Customer Retention**: 0.9
- **Compliance**: 0.9
- **User Experience**: 0.8
- **Performance**: 0.8
- **Cost Reduction**: 0.8
- **Technical Debt**: 0.7
- **Scalability**: 0.7
- **Infrastructure**: 0.6
- **Operations**: 0.6
- **General** (no special label): 0.5

## Setup

1. Install the tool:
   ```bash
   uv sync
   ```

2. Copy the settings file and set it up:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` with your GitHub info:
   - `GITHUB_TOKEN`: Your GitHub access token
   - `GITHUB_ORG`: Your organization name (like "my-company")
   - `GITHUB_PROJECT_NUMBER`: Your project number (like 1)

## How to Use It

### See All Issues with Priority Scores
```bash
# Show all issues with their calculated priorities
uv run prio-mage list-issues

# Include pull requests and show all fields
uv run prio-mage list-issues --show-prs --show-fields

# Use different organization and project
uv run prio-mage list-issues --org myorg --project 123
```

### Update Priority Scores
```bash
# See what would change (doesn't actually update anything)
uv run prio-mage update-priorities --dry-run

# Actually update the Priority field with calculated scores
uv run prio-mage update-priorities
```

### Get Project Information
```bash
# Show project details and what fields are available
uv run prio-mage show-project-info
```

### Understand Priority Calculations
```bash
# Get detailed explanation for a specific issue
uv run prio-mage explain-priority --issue-number 1234
```

## What Priority Scores Mean

**Remember**: Lower scores = higher priority (work on these first).

- **Critical (0-20 points)**: Must do now - security issues or extremely urgent
- **High (21-50 points)**: Do soon - high impact and/or due soon  
- **Medium (51-100 points)**: Normal priority work
- **Low (101-160 points)**: Do later when you have time
- **Backlog (160+ points)**: Future work

## How Priority Updates Work

The tool automatically figures out what type of Priority field you have:
- **NUMBER field**: Puts in the exact score (like 156.42)
- **TEXT field**: Puts in the score as text (like "156.42")
- **SINGLE_SELECT field**: Chooses the right option (Critical, High, Medium, Low, Backlog)

## What You Need

- Python 3.10 or newer
- GitHub Personal Access Token that can:
  - Read your repositories
  - Read and write to your projects
  - Access your organization (if using org projects)
- GitHub Project V2 with the required fields: due (DATE), impact (NUMBER), effort (SINGLE_SELECT), Priority (NUMBER/TEXT/SINGLE_SELECT) 