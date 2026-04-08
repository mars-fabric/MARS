"""
One-shot prompts for Release Notes pipeline stages 2-4.

Unlike the planning-and-control prompts which split into planner/researcher
pairs, one-shot prompts are unified task descriptions passed directly to
a single agent (researcher) for immediate execution.
"""

# ─── Stage 2a: Base branch analysis ─────────────────────────────────────

oneshot_analysis_base_task = r"""You are a senior software release analyst. Produce a \
**Last Release Branch Summary** for the `{base_branch}` branch of {repo_name}.

Focus ONLY on what existed in `{base_branch}` BEFORE any new changes from `{head_branch}`.

## Diff Context
{diff_context}

## Required Output Sections
Produce a comprehensive Markdown document with these sections:

1. **Release Overview** — High-level summary of the base branch state
2. **Features & Capabilities** — All functionality that exists in the base branch
3. **Architecture & Components** — System architecture, key modules, dependencies
4. **API Surface** — Existing endpoints, interfaces, contracts
5. **Configuration** — Configuration files, settings, environment variables
6. **Database Schema** — Tables, models, migrations present
7. **Infrastructure** — Deployment, CI/CD, Docker, cloud resources
8. **Known Limitations** — Documented or inferred limitations

## Rules
- Reference specific files where applicable
- Do NOT describe new changes from the head branch
- Output clean Markdown with clear section headers
- Be thorough but concise
"""

# ─── Stage 2b: Head branch analysis ────────────────────────────────────

oneshot_analysis_head_task = r"""You are a senior software release analyst. Produce a \
**Current Release Branch Summary** for the `{head_branch}` branch of {repo_name}.

Describe the COMPLETE state of `{head_branch}` with all new changes included \
(compared to `{base_branch}`).

## Diff Context
{diff_context}

## Required Output Sections
Produce a comprehensive Markdown document with these sections:

1. **Release Overview** — High-level summary of the current branch state
2. **New Features & Enhancements** — Everything new or significantly improved
3. **Architecture & Components** — Updated system architecture, new modules
4. **API Surface** — New and changed endpoints, interfaces
5. **Configuration** — New or changed settings, environment variables
6. **Database Schema** — Schema changes, new models, migrations
7. **Infrastructure** — Deployment changes, new services, dependency updates
8. **Bug Fixes** — Issues resolved in this release
9. **Known Limitations** — Remaining limitations users should know about

## Rules
- Reference specific files and commits where applicable
- Describe the COMPLETE state including all new changes
- Output clean Markdown with clear section headers
- Be thorough but concise
"""

# ─── Stage 2c: Comparison analysis ──────────────────────────────────────

oneshot_analysis_comparison_task = r"""You are a senior software release analyst. Produce a \
**Detailed Comparison Report** for {repo_name} comparing `{base_branch}` → `{head_branch}`.

## Diff Context
{diff_context}

## Required Output Sections
Produce a comprehensive Markdown document covering:

1. **Executive Summary** — Brief overview of all changes
2. **New Features** — With file references and impact assessment
3. **Modified Features** — Before vs after comparison
4. **Removed/Deprecated Items** — What was removed and why
5. **Breaking Changes** — What breaks and exactly how to fix it
6. **API Changes** — New, modified, and removed endpoints with examples
7. **Database Changes** — Schema modifications, migrations needed
8. **Configuration Changes** — New or modified config entries
9. **Infrastructure Changes** — Deployment, CI/CD, dependency changes
10. **Performance Impact** — Potential performance implications
11. **Security Changes** — Security-related modifications
12. **Migration Guide** — Step-by-step upgrade instructions
13. **Risk Assessment** — Rate each area as High/Medium/Low risk

## Rules
- Be specific: reference commit SHAs and file paths
- For breaking changes, explain exactly what breaks and how to fix it
- Output clean Markdown with clear section headers
"""

# ─── Stage 3: Release Notes ─────────────────────────────────────────────

oneshot_release_notes_task = r"""You are a senior technical writer specializing in \
software release documentation. Generate comprehensive release notes for \
{repo_name} comparing `{base_branch}` → `{head_branch}`.

## Diff Context
{diff_context}

## Analysis Documents

### Base Branch Analysis
{analysis_base}

### Head Branch Analysis
{analysis_head}

### Comparison Analysis
{analysis_comparison}

{extra_instructions_section}

## Your Task
Produce TWO distinct release notes documents in a single output, \
clearly separated with top-level headers:

### Document 1: Commercial Release Notes
Audience: Non-technical product users and stakeholders.
- **What's New** — New features in plain language
- **Improvements** — Enhancements to existing features
- **Bug Fixes** — Resolved issues that affected users
- **Known Issues** — Remaining limitations
- **Getting Started** — How to access or upgrade

### Document 2: Developer Release Notes
Audience: Engineers and technical teams.
- **Overview** — High-level technical summary
- **New Features** — Detailed technical descriptions with API examples
- **Bug Fixes** — Technical details with references to commits/files
- **Breaking Changes** — What changed, why, and exact migration steps
- **Migration Notes** — Step-by-step upgrade instructions
- **Impact Analysis** — Which systems/services are affected
- **Infrastructure Changes** — Deployment, config, dependency updates
- **API Reference Changes** — New/modified/removed endpoints with examples

## Rules
- Commercial notes: clear, non-technical language; focus on user impact
- Developer notes: technically precise; reference commit SHAs and file paths
- Highlight breaking changes prominently in both documents
- Use bullet points and organized sections for readability
"""

# ─── Stage 4: Migration ─────────────────────────────────────────────────

oneshot_migration_task = r"""You are a senior DevOps and database migration engineer. \
Generate a comprehensive {migration_type} migration script/runbook for \
{repo_name} upgrading from `{base_branch}` to `{head_branch}`.

## Diff Context
{diff_context}

## Analysis
{analysis_comparison}

## Release Notes
{release_notes}

{extra_instructions_section}

## Required Output
Generate a complete migration script for a "{migration_type}" migration:

### For database migrations:
- CREATE TABLE, ALTER TABLE, ADD/DROP COLUMN, index changes (valid SQL)
- Data migrations: INSERT, UPDATE, DELETE for seed data or transformations
- Rollback/downgrade script
- Pre-migration validation checks
- Post-migration verification queries

### For API migrations:
- Endpoint changes (new, modified, deprecated)
- Request/response schema changes
- Backward compatibility notes
- Client migration guide with code examples
- Versioning strategy

### For infrastructure migrations:
- New services, config changes, environment variables
- Ordered deployment steps
- Rollback plan
- Dependency updates
- Configuration file changes

### For comprehensive (full) migrations:
- All of the above categories that apply
- Step-by-step migration plan with dependencies
- Combined rollback plan
- Verification steps

## Structure
1. **Pre-Migration Validation** — Checks before starting
2. **Migration Steps** — Ordered steps with exact commands/scripts
3. **Rollback Procedures** — How to undo each step
4. **Post-Migration Verification** — Verification queries/commands
5. **Timing Estimates** — Approximate duration per step
6. **Risk Levels** — High/Medium/Low per step

Output in Markdown with clear section headers and code blocks.
"""
