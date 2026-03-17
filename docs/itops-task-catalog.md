# ITOps Client Demo — Task Catalog

## Design Principle

Every task below reuses **100% of the existing deepresearch pipeline** — the 4-phase flow (Idea → Method → Experiment → Paper), the backend router, database models, LangGraph paper pipeline, frontend wizard, and WebSocket events. No backend code changes needed.

What changes per task:
- **Task description** (pre-filled in SetupPanel)
- **Data files** uploaded by the user (CSV, JSON, logs)
- **Prompt context** (injected via `data_description`)

### How Content Flows (Same as Deepresearch)

```
SetupPanel → POST /api/deepresearch/create { task: description, data_description: context }
  │
  ▼
Phase 1 — Idea Generation
  agents debate ITOps analysis angles for the uploaded data
  output_data["shared"]["research_idea"] → saved to idea.md
  │
  ▼
Phase 2 — Method Development
  methodology designed using {research_idea} from Phase 1
  output_data["shared"]["methodology"] → saved to methods.md
  │
  ▼  
Phase 3 — Experiment Execution
  code generated to analyze uploaded data, produce metrics/charts
  output_data["shared"]["results"] → saved to results.md + plots/
  │
  ▼
Phase 4 — Report Generation (LangGraph)
  full report with analysis, findings, recommendations → PDF/LaTeX
```

Each phase's `output_data["shared"]` accumulates into the next phase's `shared_state` via `build_shared_state()`. Zero changes to this mechanism.

---

## What Makes a Good ITOps Demo Task

| Criterion | Why |
|-----------|-----|
| **Synthetic data is trivial** | Can generate CSV/JSON with a 20-line Python script — no real infra needed |
| **Phase 3 produces charts** | Visually impressive for demos (time-series, heatmaps, bar charts) |
| **Domain is universal** | Every IT org has incidents, alerts, capacity concerns |
| **Results are actionable** | Output reads like a real ops report, not just academic analysis |
| **Runs in < 10 minutes** | Small datasets, straightforward analysis logic |

---

## Task Catalog

### Task 1: Incident Volume Trend Analysis & Forecasting

**Difficulty:** ★☆☆ (Easiest — start here)

**Pre-filled Description:**
> Analyze IT incident ticket data to identify volume trends, seasonal patterns, and category distributions. Build a time-series forecasting model to predict incident volumes for the next 30 days and identify the top contributing categories driving ticket growth.

**Suggested Data (easy to generate):**
- `incidents.csv` — columns: `ticket_id, created_at, resolved_at, category, priority, assignment_group, resolution_time_hours`
- 5,000–10,000 rows, 6 months of data

**What each phase produces:**
| Phase | Output |
|-------|--------|
| 1 — Idea | Research angle: e.g., "Decompose incident trends by category to isolate growth drivers, then apply ARIMA/Prophet for forecasting" |
| 2 — Method | Methodology: time-series decomposition, seasonal-trend analysis, category Pareto, forecasting model selection |
| 3 — Experiment | Code: pandas analysis + matplotlib charts — trend lines, category breakdown bar chart, forecast with confidence intervals |
| 4 — Report | Full report: executive summary, trend analysis, forecast, category hotspots, staffing recommendations |

**Sample data generation script:**
```python
import pandas as pd, numpy as np
from datetime import datetime, timedelta

np.random.seed(42)
n = 8000
categories = ['Network', 'Hardware', 'Software', 'Access/IAM', 'Database', 'Security', 'Other']
priorities = ['P1-Critical', 'P2-High', 'P3-Medium', 'P4-Low']
groups = ['Network Ops', 'Desktop Support', 'App Support', 'DBA Team', 'Security Ops', 'Service Desk']

start = datetime(2025, 9, 1)
dates = [start + timedelta(hours=np.random.exponential(1.3)) for _ in range(n)]
dates.sort()

df = pd.DataFrame({
    'ticket_id': [f'INC{100000+i}' for i in range(n)],
    'created_at': dates,
    'category': np.random.choice(categories, n, p=[0.2, 0.1, 0.25, 0.15, 0.1, 0.1, 0.1]),
    'priority': np.random.choice(priorities, n, p=[0.05, 0.15, 0.5, 0.3]),
    'assignment_group': np.random.choice(groups, n),
    'resolution_time_hours': np.round(np.random.lognormal(3, 1, n), 1),
})
df['resolved_at'] = df['created_at'] + pd.to_timedelta(df['resolution_time_hours'], unit='h')
df.to_csv('incidents.csv', index=False)
```

---

### Task 2: Alert Noise Reduction & Correlation Analysis

**Difficulty:** ★☆☆

**Pre-filled Description:**
> Analyze monitoring alert data to quantify alert noise (non-actionable alerts), identify correlated alert storms, and recommend suppression and grouping rules. Calculate signal-to-noise ratio by monitor, determine alert-to-incident conversion rates, and propose alert tuning recommendations.

**Suggested Data:**
- `alerts.csv` — columns: `alert_id, timestamp, monitor_name, severity, host, service, status (fired/resolved/suppressed), linked_incident_id (nullable)`
- 20,000–50,000 rows, 3 months

**What each phase produces:**
| Phase | Output |
|-------|--------|
| 1 — Idea | Research angle: e.g., "Compute per-monitor noise ratio, temporal clustering to detect storms, and correlation analysis between monitors" |
| 2 — Method | Methodology: noise classification heuristics, sliding-window storm detection, co-occurrence matrix, conversion funnel analysis |
| 3 — Experiment | Code: noise pie chart, top-20 noisiest monitors bar chart, alert storm timeline, correlation heatmap |
| 4 — Report | Full report: alert landscape overview, noise quantification, storm patterns, recommended suppression rules with projected reduction |

**Sample data generation script:**
```python
import pandas as pd, numpy as np
from datetime import datetime, timedelta

np.random.seed(42)
n = 30000
monitors = [f'mon_{x}' for x in ['cpu_high', 'mem_high', 'disk_full', 'http_5xx', 'latency_p99',
            'cert_expiry', 'dns_fail', 'pod_restart', 'node_down', 'backup_fail',
            'queue_depth', 'conn_pool', 'gc_pause', 'log_error_rate', 'healthcheck']]
hosts = [f'prod-app-{i:02d}' for i in range(1, 21)] + [f'prod-db-{i:02d}' for i in range(1, 6)]
services = ['api-gateway', 'auth-service', 'order-service', 'payment-service', 'inventory-service',
            'notification-service', 'search-service', 'analytics-pipeline']

start = datetime(2025, 9, 1)
timestamps = sorted([start + timedelta(minutes=np.random.exponential(4)) for _ in range(n)])

linked = [f'INC{np.random.randint(100000,200000)}' if np.random.random() < 0.12 else None for _ in range(n)]

df = pd.DataFrame({
    'alert_id': [f'ALR{500000+i}' for i in range(n)],
    'timestamp': timestamps,
    'monitor_name': np.random.choice(monitors, n),
    'severity': np.random.choice(['critical', 'warning', 'info'], n, p=[0.1, 0.35, 0.55]),
    'host': np.random.choice(hosts, n),
    'service': np.random.choice(services, n),
    'status': np.random.choice(['fired', 'resolved', 'suppressed'], n, p=[0.5, 0.35, 0.15]),
    'linked_incident_id': linked,
})
df.to_csv('alerts.csv', index=False)
```

---

### Task 3: Mean Time to Resolve (MTTR) Breakdown & Optimization

**Difficulty:** ★★☆

**Pre-filled Description:**
> Analyze incident lifecycle data to decompose Mean Time to Resolve (MTTR) into its sub-components: time-to-detect, time-to-acknowledge, time-to-diagnose, and time-to-fix. Identify bottlenecks by team, priority level, and incident category, and recommend process improvements to reduce overall MTTR.

**Suggested Data:**
- `incident_lifecycle.csv` — columns: `ticket_id, priority, category, assignment_group, detected_at, acknowledged_at, diagnosed_at, fixed_at, resolved_at, root_cause_category, escalation_count`
- 3,000–5,000 rows, 6 months

**What each phase produces:**
| Phase | Output |
|-------|--------|
| 1 — Idea | Research angle: e.g., "MTTR decomposition reveals that diagnosis time dominates P1 incidents — focus on runbook automation and knowledge base improvements" |
| 2 — Method | Methodology: lifecycle phase duration calculation, statistical comparison across groups, bottleneck identification, regression on contributing factors |
| 3 — Experiment | Code: stacked bar chart (MTTR components by team), box plots by priority, heatmap of bottlenecks, trend line of MTTR over time |
| 4 — Report | Full report: MTTR landscape, bottleneck analysis, team comparison, improvement roadmap with projected MTTR reduction |

---

### Task 4: Change Failure Rate & Deployment Risk Scoring

**Difficulty:** ★★☆

**Pre-filled Description:**
> Analyze software deployment and change management records to calculate change failure rates by team, service, change type, and time window. Build a risk scoring model that predicts the likelihood of a change causing an incident based on historical patterns, enabling pre-deployment risk assessment.

**Suggested Data:**
- `changes.csv` — columns: `change_id, timestamp, service, team, change_type (standard/normal/emergency), lines_changed, tests_passed_pct, deploy_window (business/off-hours/weekend), rollback (true/false), caused_incident (true/false), incident_severity`
- 2,000–4,000 rows, 12 months

**What each phase produces:**
| Phase | Output |
|-------|--------|
| 1 — Idea | Research angle: identify risk factors (deploy window, change size, test coverage) that predict change failures |
| 2 — Method | Methodology: failure rate calculation by dimension, logistic regression for risk scoring, feature importance analysis |
| 3 — Experiment | Code: failure rate bar charts by team/service, risk factor correlation matrix, ROC curve for risk model, risk score distribution |
| 4 — Report | Full report: DORA metrics baseline, risk factor analysis, predictive model, deployment guardrail recommendations |

---

### Task 5: Capacity Planning — Server Resource Utilization Forecasting

**Difficulty:** ★★☆

**Pre-filled Description:**
> Analyze server resource utilization metrics (CPU, memory, disk, network) across the infrastructure fleet. Identify servers approaching capacity limits, forecast resource exhaustion timelines, and provide capacity planning recommendations for the next quarter including right-sizing opportunities.

**Suggested Data:**
- `server_metrics.csv` — columns: `timestamp, hostname, cpu_pct, memory_pct, disk_pct, network_mbps, environment (prod/staging/dev), service, instance_type`
- Hourly samples, 50 hosts, 90 days → ~108,000 rows

**What each phase produces:**
| Phase | Output |
|-------|--------|
| 1 — Idea | Research angle: e.g., "Trend analysis with linear extrapolation + peak detection to forecast capacity breaches, plus utilization clustering for right-sizing" |
| 2 — Method | Methodology: per-host trend fitting, headroom calculation, exhaustion date projection, clustering for utilization tiers |
| 3 — Experiment | Code: fleet utilization heatmap, top-10 at-risk hosts trend lines, right-sizing scatter plot, capacity forecast timeline |
| 4 — Report | Full report: fleet health overview, at-risk hosts, right-sizing recommendations (with cost savings), quarterly capacity plan |

---

### Task 6: SLA Compliance & Breach Pattern Analysis

**Difficulty:** ★☆☆

**Pre-filled Description:**
> Analyze service level agreement (SLA) compliance data across IT services. Calculate SLA breach rates by service, priority, and time period. Identify patterns in SLA breaches (time-of-day, day-of-week, team workload) and recommend operational changes to improve compliance rates.

**Suggested Data:**
- `sla_data.csv` — columns: `ticket_id, service, priority, sla_target_hours, actual_hours, breached (true/false), created_at, assignment_group, reassignment_count`
- 5,000 rows, 6 months

**What each phase produces:**
| Phase | Output |
|-------|--------|
| 1 — Idea | Analyze breach patterns across temporal and organizational dimensions to identify systemic causes |
| 2 — Method | Breach rate calculations, logistic regression on breach predictors, temporal pattern analysis |
| 3 — Experiment | Breach rate by service bar chart, day-of-week heatmap, breach prediction ROC, compliance trend line |
| 4 — Report | SLA compliance scorecard, root cause analysis, staffing recommendations, target improvement plan |

---

### Task 7: On-Call Burnout & Escalation Pattern Analysis

**Difficulty:** ★★☆

**Pre-filled Description:**
> Analyze on-call paging data to measure on-call burden distribution across engineers and teams. Identify off-hours page frequency, escalation chains, and alert fatigue indicators. Recommend on-call rotation improvements and page reduction strategies to prevent engineer burnout.

**Suggested Data:**
- `oncall_pages.csv` — columns: `page_id, timestamp, engineer, team, severity, acknowledged_at, resolved_at, escalated (true/false), off_hours (true/false), service, alert_source`
- 5,000–8,000 rows, 6 months

**What each phase produces:**
| Phase | Output |
|-------|--------|
| 1 — Idea | Quantify page burden inequality, correlate with off-hours frequency and escalation rate |
| 2 — Method | Gini coefficient for page distribution, time-of-day analysis, escalation funnel, burnout risk scoring |
| 3 — Experiment | Per-engineer page count distribution, off-hours heatmap, escalation Sankey diagram, burnout risk scatter |
| 4 — Report | On-call health scorecard, burden inequality analysis, rotation recommendations, page reduction targets |

---

### Task 8: Service Dependency & Blast Radius Mapping

**Difficulty:** ★★★

**Pre-filled Description:**
> Analyze service dependency data and historical incident propagation patterns to map blast radius for each critical service. Calculate cascading failure probability, identify single points of failure, and recommend architectural improvements to reduce blast radius.

**Suggested Data:**
- `service_dependencies.csv` — columns: `source_service, target_service, dependency_type (sync/async/data), criticality (hard/soft)`
- `incident_propagation.csv` — columns: `incident_id, origin_service, affected_service, impact_start, impact_end, severity`
- ~100 dependency edges, ~500 propagation records

**What each phase produces:**
| Phase | Output |
|-------|--------|
| 1 — Idea | Graph analysis of service topology + historical propagation to quantify blast radius per service |
| 2 — Method | Network graph construction, PageRank/betweenness centrality, propagation probability estimation, SPOF identification |
| 3 — Experiment | Service dependency graph visualization, blast radius heatmap, centrality ranking table, failure cascade simulation |
| 4 — Report | Architecture risk assessment, SPOF inventory, blast radius rankings, resilience improvement roadmap |

---

### Task 9: Runbook Effectiveness & Automation ROI Analysis

**Difficulty:** ★☆☆

**Pre-filled Description:**
> Analyze runbook usage data alongside incident resolution metrics to measure which runbooks are effective at reducing MTTR, which are outdated or unused, and what the potential ROI would be from automating the top manual runbooks. Prioritize automation candidates by frequency × manual-effort.

**Suggested Data:**
- `runbook_usage.csv` — columns: `incident_id, runbook_id, runbook_name, executed_by, execution_time_minutes, automated (true/false), outcome (success/partial/failed), incident_category`
- 2,000–3,000 rows

**What each phase produces:**
| Phase | Output |
|-------|--------|
| 1 — Idea | Rank runbooks by usage × manual effort, compare MTTR with/without runbook execution |
| 2 — Method | Runbook effectiveness scoring, MTTR impact analysis, automation ROI calculation (time saved × labor cost) |
| 3 — Experiment | Runbook frequency Pareto chart, MTTR comparison box plots, automation ROI bar chart, coverage gap analysis |
| 4 — Report | Runbook health assessment, top automation candidates with projected savings, retirement/update recommendations |

---

### Task 10: Post-Incident Review (PIR) Quality & Follow-Through Tracking

**Difficulty:** ★★☆

**Pre-filled Description:**
> Analyze post-incident review data to measure PIR completion rates, action item follow-through, and time-to-PIR. Identify patterns in repeat incidents that had prior PIR action items left incomplete, and quantify the cost of delayed remediation.

**Suggested Data:**
- `pir_data.csv` — columns: `incident_id, severity, pir_completed (true/false), pir_date, days_to_pir, action_items_count, action_items_completed, action_items_overdue, repeat_incident (true/false), related_prior_incident_id`
- 500–1,000 rows, 12 months

**What each phase produces:**
| Phase | Output |
|-------|--------|
| 1 — Idea | Correlate incomplete action items with repeat incident frequency to quantify remediation debt |
| 2 — Method | Completion rate analysis, repeat-incident correlation, time-to-PIR impact study, remediation debt costing |
| 3 — Experiment | PIR completion funnel chart, action item completion rates by team, repeat incident correlation scatter, remediation debt trend |
| 4 — Report | PIR program health assessment, remediation debt quantification, process improvement recommendations, accountability framework |

---

## Persona-Based Use Cases

### ITOps Manager — Day-to-Day Operational Excellence

> These tasks solve problems an ITOps manager deals with weekly: team performance, ticket backlogs, vendor management, cost control.

---

### Task 11: Team Performance Benchmarking & Workload Balancing

**Difficulty:** ★☆☆ | **Persona:** ITOps Manager

**Pre-filled Description:**
> Analyze IT support team performance data to benchmark teams against each other on key metrics: tickets closed per engineer, average resolution time, first-contact resolution rate, customer satisfaction, and backlog age. Identify workload imbalances, under/over-staffed teams, and recommend rebalancing strategies with projected impact on SLAs.

**Suggested Data:**
- `team_performance.csv` — columns: `month, team, engineer_count, tickets_assigned, tickets_closed, avg_resolution_hours, first_contact_resolution_pct, csat_score, backlog_count, backlog_avg_age_days, escalations_out, escalations_in`
- 12 months × 8 teams = ~96 rows

| Phase | Output |
|-------|--------|
| 1 — Idea | Cross-team comparative analysis with workload-adjusted productivity metrics and staffing model |
| 2 — Method | Per-capita normalization, z-score benchmarking, workload elasticity estimation, rebalancing simulation |
| 3 — Experiment | Team radar chart, productivity scatter (tickets/person vs MTTR), backlog aging heatmap, staffing scenario bar chart |
| 4 — Report | Team scorecard, staffing gap analysis, rebalancing plan with SLA impact projections |

---

### Task 12: Ticket Backlog Aging & Stale Ticket Triage

**Difficulty:** ★☆☆ | **Persona:** ITOps Manager

**Pre-filled Description:**
> Analyze the current open ticket backlog to identify aging patterns, stale tickets, and bottleneck queues. Classify backlog tickets by risk (SLA breach proximity), staleness (days since last update), and complexity (reassignment count, touch count). Recommend a triage action plan: close, escalate, reassign, or merge duplicate tickets.

**Suggested Data:**
- `open_backlog.csv` — columns: `ticket_id, created_at, last_updated, priority, category, assignment_group, current_assignee, status (open/pending/on-hold), reassignment_count, touch_count, sla_target_hours, hours_in_queue, customer_followups`
- 800–2,000 rows (current open tickets)

| Phase | Output |
|-------|--------|
| 1 — Idea | Multi-dimensional aging analysis with SLA-proximity risk scoring and auto-triage classification |
| 2 — Method | Aging bucket analysis, SLA breach probability model, staleness scoring, duplicate detection heuristics |
| 3 — Experiment | Backlog age distribution histogram, SLA breach risk heatmap by queue, stale ticket treemap, triage action breakdown pie chart |
| 4 — Report | Backlog health dashboard, triage action plan (close N, escalate N, reassign N), projected SLA improvement |

---

### Task 13: Vendor/Tool Spend vs. Value Analysis

**Difficulty:** ★★☆ | **Persona:** ITOps Manager

**Pre-filled Description:**
> Analyze IT tool and vendor spend data alongside usage metrics and operational outcomes. Calculate cost-per-ticket, cost-per-alert, and cost-per-resolution for each tool in the IT operations stack. Identify underutilized tools, overlapping capabilities, and consolidation opportunities with projected cost savings.

**Suggested Data:**
- `tool_spend.csv` — columns: `tool_name, category (monitoring/itsm/ci-cd/logging/security), annual_cost, license_type (per-seat/per-host/flat), licensed_units, active_users, monthly_api_calls, tickets_processed, alerts_generated, uptime_pct`
- 20–40 rows (one per tool)
- `tool_overlap.csv` — columns: `tool_a, tool_b, overlapping_capability, overlap_pct`

| Phase | Output |
|-------|--------|
| 1 — Idea | Cost-effectiveness scoring per tool + overlap mapping for consolidation candidates |
| 2 — Method | Unit economics calculation, utilization rate analysis, capability overlap matrix, consolidation scenario modeling |
| 3 — Experiment | Cost-per-unit bar chart by tool, utilization vs cost scatter, overlap Venn/heatmap, consolidation savings waterfall chart |
| 4 — Report | IT tooling ROI scorecard, underutilized tool recommendations, consolidation roadmap with total savings estimate |

---

### Task 14: Shift Handover Effectiveness & Coverage Gap Analysis

**Difficulty:** ★★☆ | **Persona:** ITOps Manager

**Pre-filled Description:**
> Analyze incident and operational data across NOC/SOC shift boundaries to identify coverage gaps, handover failures, and shift-transition incident spikes. Measure per-shift incident volume, resolution rates, and escalation rates. Identify whether incidents created in one shift's final hour get properly handed over or fall through the cracks.

**Suggested Data:**
- `shift_incidents.csv` — columns: `ticket_id, created_at, resolved_at, shift (morning/afternoon/night), shift_start, shift_end, created_during_handover (true/false), handover_notes_present (true/false), resolution_time_hours, escalated (true/false), dropped (true/false)`
- 5,000 rows, 6 months

| Phase | Output |
|-------|--------|
| 1 — Idea | Quantify the "handover tax" — excess MTTR and drop rates during shift boundaries vs mid-shift |
| 2 — Method | Shift boundary ±1hr window analysis, control vs treatment comparison, handover note impact measurement |
| 3 — Experiment | Incident volume by hour-of-day (shift boundaries highlighted), handover drop rate trend, MTTR by shift & handover proximity, notes-present vs absent comparison |
| 4 — Report | Shift coverage assessment, handover failure cost quantification, structured handover process recommendations |

---

### Task 15: Repeat Incident & Known Error Analysis

**Difficulty:** ★☆☆ | **Persona:** ITOps Manager

**Pre-filled Description:**
> Analyze incident data to identify repeat incidents — tickets with the same root cause, affected service, or resolution steps recurring within 30/60/90 day windows. Map repeat incidents to known errors in the knowledge base. Quantify the operational cost of repeat incidents and prioritize permanent fix investments by frequency × effort.

**Suggested Data:**
- `incidents_with_resolution.csv` — columns: `ticket_id, created_at, category, service, root_cause_id, resolution_summary, resolution_time_hours, cost_estimate, known_error_id (nullable), workaround_applied (true/false), permanent_fix_available (true/false)`
- 5,000 rows, 12 months

| Phase | Output |
|-------|--------|
| 1 — Idea | Cluster resolution text to find de-facto duplicates, calculate the cost of not fixing known errors |
| 2 — Method | Root cause frequency analysis, recurrence window calculation, known error coverage gap measurement, fix ROI prioritization |
| 3 — Experiment | Top-20 repeat incident Pareto chart, known error coverage treemap, monthly repeat rate trend, fix ROI priority matrix scatter |
| 4 — Report | Repeat incident landscape, known error gap analysis, prioritized fix list with ROI calculations, knowledge base improvement plan |

---

### IT Architect — Design, Reliability & Modernization

> These tasks address what an IT architect cares about: system reliability, observability maturity, migration planning, technical debt.

---

### Task 16: Observability Maturity Assessment

**Difficulty:** ★★☆ | **Persona:** IT Architect

**Pre-filled Description:**
> Assess the organization's observability maturity by analyzing monitoring coverage, alert quality, dashboard utilization, log retention, trace sampling rates, and SLO adoption across services. Score each service on a 1-5 maturity scale across dimensions (metrics, logs, traces, alerting, dashboards, SLOs) and identify the biggest gaps in observability coverage.

**Suggested Data:**
- `observability_inventory.csv` — columns: `service, has_metrics (true/false), metric_count, has_logs (true/false), log_retention_days, has_traces (true/false), trace_sampling_pct, alert_count, dashboard_count, slo_defined (true/false), slo_count, error_budget_remaining_pct, last_instrumentation_update`
- 40–80 rows (one per service)

| Phase | Output |
|-------|--------|
| 1 — Idea | Multi-dimensional maturity scoring model with gap-weighted prioritization for improvement |
| 2 — Method | Maturity level definition framework, per-dimension scoring rubric, weighted composite score, gap-priority ranking |
| 3 — Experiment | Service maturity heatmap (services × dimensions), maturity distribution histogram, gap analysis radar chart, improvement priority ranking |
| 4 — Report | Observability maturity scorecard, per-team gap analysis, instrumentation roadmap, SLO adoption plan |

---

### Task 17: Cloud Migration Readiness & Risk Assessment

**Difficulty:** ★★★ | **Persona:** IT Architect

**Pre-filled Description:**
> Assess application portfolio readiness for cloud migration by analyzing each application's architecture characteristics, dependencies, data sensitivity, compliance requirements, and operational complexity. Classify each application using the 7R model (Rehost, Replatform, Refactor, Repurchase, Retire, Retain, Relocate) and estimate migration complexity, risk, and projected cost impact.

**Suggested Data:**
- `app_portfolio.csv` — columns: `app_name, business_unit, criticality (high/medium/low), current_hosting (on-prem/colo/hybrid), architecture (monolith/microservices/legacy), language, database_type, data_classification (public/internal/confidential/restricted), compliance_requirements, dependency_count, monthly_compute_cost, monthly_storage_gb, avg_latency_ms, uptime_requirement_pct, last_major_update, team_size`
- 50–150 rows (application portfolio)

| Phase | Output |
|-------|--------|
| 1 — Idea | Multi-factor readiness scoring with 7R classification model and migration wave planning |
| 2 — Method | Readiness rubric definition, 7R decision tree, risk scoring (data sensitivity × dependency complexity × compliance), wave grouping by risk-readiness quadrant |
| 3 — Experiment | 7R classification donut chart, readiness vs risk scatter plot, migration wave timeline, cost impact waterfall |
| 4 — Report | Migration readiness assessment, 7R classification per app, risk register, wave-based migration plan with TCO projections |

---

### Task 18: Technical Debt Quantification in Infrastructure

**Difficulty:** ★★☆ | **Persona:** IT Architect

**Pre-filled Description:**
> Quantify infrastructure technical debt by analyzing the fleet inventory for end-of-life software, unsupported OS versions, unpatched vulnerabilities, expired certificates, legacy protocol usage, and configuration drift from baselines. Calculate a risk-weighted technical debt score per system and estimate remediation effort and cost.

**Suggested Data:**
- `infra_inventory.csv` — columns: `hostname, os, os_version, os_eol_date, last_patched, days_since_patch, open_cve_count, critical_cve_count, cert_expiry_date, legacy_protocols (comma-separated), config_drift_items, environment, service, business_criticality`
- 200–500 rows (infrastructure fleet)

| Phase | Output |
|-------|--------|
| 1 — Idea | Multi-factor tech debt scoring combining EOL risk, vulnerability exposure, certificate health, and config drift |
| 2 — Method | Per-dimension scoring rubric, risk-weighted composite index, remediation effort estimation, prioritization by criticality × debt score |
| 3 — Experiment | Tech debt distribution histogram, EOL timeline chart, CVE exposure heatmap by service, top-20 riskiest systems bar chart |
| 4 — Report | Infrastructure debt register, risk quantification, remediation cost estimates, prioritized remediation sprints |

---

### Task 19: Microservices vs Monolith Performance Comparison

**Difficulty:** ★★☆ | **Persona:** IT Architect

**Pre-filled Description:**
> Compare operational characteristics of microservice-based vs monolithic applications in the portfolio: deployment frequency, failure rate, MTTR, latency profiles, resource efficiency, and operational overhead (on-call pages, incident count per service). Determine whether microservices adoption is delivering the expected operational benefits and identify anti-patterns.

**Suggested Data:**
- `app_ops_metrics.csv` — columns: `app_name, architecture (monolith/microservices/hybrid), service_count, deploy_frequency_per_month, change_failure_rate_pct, mttr_hours, p50_latency_ms, p99_latency_ms, cpu_efficiency_pct, incidents_per_month, pages_per_month, team_size, monthly_infra_cost`
- 30–60 rows (applications)

| Phase | Output |
|-------|--------|
| 1 — Idea | Controlled comparison of DORA metrics and operational efficiency across architecture styles |
| 2 — Method | Architecture-group statistical comparison, per-capita normalization, anti-pattern detection (e.g., distributed monolith), benefit realization scoring |
| 3 — Experiment | DORA metrics comparison box plots, latency distribution by arch type, cost-per-service scatter, anti-pattern identification table |
| 4 — Report | Architecture strategy evaluation, microservices benefit realization assessment, anti-patterns found, recommendations for hybrid approach |

---

### Task 20: Disaster Recovery Readiness & RTO/RPO Gap Analysis

**Difficulty:** ★★☆ | **Persona:** IT Architect

**Pre-filled Description:**
> Assess disaster recovery readiness by analyzing each critical service's stated RTO/RPO targets vs actual DR test results. Identify services with no DR plan, untested plans, or historical test failures. Calculate the gap between business-required recovery objectives and demonstrated recovery capability.

**Suggested Data:**
- `dr_readiness.csv` — columns: `service, business_criticality, rto_target_hours, rpo_target_hours, dr_plan_exists (true/false), last_dr_test_date, dr_test_result (pass/partial/fail/never_tested), actual_rto_hours (nullable), actual_rpo_hours (nullable), backup_frequency, backup_verified (true/false), failover_type (manual/automated/none), data_replication (sync/async/none)`
- 40–80 rows (critical services)

| Phase | Output |
|-------|--------|
| 1 — Idea | RTO/RPO gap analysis with risk scoring based on business criticality × gap magnitude |
| 2 — Method | Target vs. actual comparison, gap quantification, risk scoring matrix, DR test cadence analysis |
| 3 — Experiment | RTO target vs actual gap bar chart, RPO gap scatter plot colored by criticality, DR test coverage pie chart, risk quadrant matrix |
| 4 — Report | DR readiness scorecard, gap register with risk ratings, DR test schedule recommendations, investment priorities for closing gaps |

---

### Task 21: API Gateway & Service Mesh Health Analysis

**Difficulty:** ★★☆ | **Persona:** IT Architect

**Pre-filled Description:**
> Analyze API gateway and service mesh telemetry to assess inter-service communication health: error rates, latency distributions, retry storms, circuit breaker activations, rate limiting hits, and mTLS certificate status. Identify the most fragile service-to-service communication paths and recommend resilience pattern improvements.

**Suggested Data:**
- `api_mesh_metrics.csv` — columns: `timestamp, source_service, destination_service, request_count, error_count, p50_latency_ms, p99_latency_ms, retry_count, circuit_breaker_open_count, rate_limit_hits, mtls_status (valid/expiring/expired/none), protocol (http/grpc/tcp)`
- 10,000–20,000 rows (hourly per service pair, 30 days)

| Phase | Output |
|-------|--------|
| 1 — Idea | Identify fragile communication paths via error rate + retry correlation, circuit breaker analysis, and latency outliers |
| 2 — Method | Per-path error rate trends, retry amplification analysis, circuit breaker frequency scoring, latency percentile comparison |
| 3 — Experiment | Service-pair error rate heatmap, retry storm timeline, latency distribution violin plots, mTLS coverage status chart |
| 4 — Report | Service mesh health scorecard, fragile path inventory, resilience pattern gaps, circuit breaker tuning and retry budget recommendations |

---

### Senior Management / VP/CIO Level — Strategic & Financial

> These tasks produce reports for senior leadership: cost optimization, business alignment, maturity benchmarking, board-level risk summaries.

---

### Task 22: IT Cost Allocation & Chargeback Analysis

**Difficulty:** ★★☆ | **Persona:** VP/CIO

**Pre-filled Description:**
> Analyze IT infrastructure and operations costs to build a transparent cost allocation model across business units. Break down costs by category (compute, storage, network, licensing, labor) and allocate to business units based on consumption metrics. Identify cost anomalies, trending cost drivers, and present chargeback recommendations with projected per-BU impact.

**Suggested Data:**
- `it_costs.csv` — columns: `month, cost_category (compute/storage/network/licensing/labor/support), vendor, amount_usd, business_unit_allocation (JSON or comma-separated), consumption_metric, consumption_value`
- 500–1,000 rows (monthly line items, 12 months)
- `bu_consumption.csv` — columns: `month, business_unit, compute_hours, storage_gb, network_gb, tickets_submitted, headcount`

| Phase | Output |
|-------|--------|
| 1 — Idea | Consumption-based allocation model with trend analysis and anomaly detection |
| 2 — Method | Activity-based costing methodology, per-BU unit economics, year-over-year trend decomposition, anomaly flagging |
| 3 — Experiment | Cost breakdown waterfall chart, per-BU allocation stacked bar, cost trend with anomalies highlighted, chargeback projection table |
| 4 — Report | IT cost transparency report, per-BU chargeback model, cost optimization opportunities, CFO-ready executive summary |

---

### Task 23: DORA Metrics Executive Dashboard & Maturity Benchmarking

**Difficulty:** ★★☆ | **Persona:** VP/CIO

**Pre-filled Description:**
> Calculate and benchmark the organization's four DORA metrics (Deployment Frequency, Lead Time for Changes, Change Failure Rate, MTTR) against industry standards (Elite/High/Medium/Low performers). Track trends over the past 12 months, identify which teams are driving improvement or regression, and provide a maturity roadmap to reach the next performance tier.

**Suggested Data:**
- `dora_metrics.csv` — columns: `month, team, service, deployments, lead_time_hours, change_failures, total_changes, mttr_hours, incidents_from_changes`
- 12 months × 10 teams = ~120 rows

| Phase | Output |
|-------|--------|
| 1 — Idea | Benchmark against DORA State of DevOps tiers, track trajectory, identify team-level drag and lift |
| 2 — Method | Per-metric tier classification, team contribution decomposition, trend direction analysis, bottleneck-to-tier-improvement mapping |
| 3 — Experiment | DORA 4-metric gauge chart vs benchmarks, team ranking by each metric, 12-month trend lines, maturity tier position chart |
| 4 — Report | DORA maturity report (board-ready), per-team scorecards, improvement roadmap to next tier, investment recommendations |

---

### Task 24: IT Risk Register & Operational Risk Scoring

**Difficulty:** ★★☆ | **Persona:** VP/CIO

**Pre-filled Description:**
> Build a quantified IT operational risk register by analyzing incident history, vulnerability data, compliance audit findings, and business impact records. Score each risk by likelihood × impact, identify top-10 risks requiring immediate attention, track risk trend direction, and present a risk appetite framework with mitigation cost estimates.

**Suggested Data:**
- `risk_inputs.csv` — columns: `risk_id, risk_category (security/availability/compliance/data-loss/vendor/operational), description, likelihood_score (1-5), impact_score (1-5), current_controls, control_effectiveness (strong/moderate/weak/none), incidents_last_12m, estimated_annual_loss_usd, mitigation_cost_usd, mitigation_status (open/in-progress/mitigated), business_owner`
- 30–80 rows (risk register items)

| Phase | Output |
|-------|--------|
| 1 — Idea | Quantified risk matrix with residual risk calculation and cost-benefit prioritization for mitigation |
| 2 — Method | Risk scoring (likelihood × impact × control effectiveness), residual risk calculation, mitigation ROI analysis, trend tracking |
| 3 — Experiment | Risk heat map (5×5 matrix), top-10 risks bar chart, mitigation ROI scatter plot, risk trend direction arrows chart |
| 4 — Report | Executive risk register, top-10 risk profiles with mitigation plans, risk appetite framework, board-ready risk summary |

---

### Task 25: Major Incident Business Impact Analysis

**Difficulty:** ★★☆ | **Persona:** VP/CIO

**Pre-filled Description:**
> Analyze major incident (P1/P2) data to quantify business impact: revenue loss per minute of downtime, customer-facing SLA penalties, productivity hours lost, and brand reputation impact (support ticket surge, social media mentions). Build a business impact model per service that translates availability metrics into financial terms for executive discussions.

**Suggested Data:**
- `major_incidents.csv` — columns: `incident_id, service, severity, start_time, end_time, duration_minutes, customers_affected, transactions_lost, estimated_revenue_impact_usd, sla_penalty_usd, productivity_hours_lost, support_ticket_surge_count, root_cause, preventable (true/false)`
- 50–200 rows (P1/P2 incidents, 24 months)
- `service_revenue.csv` — columns: `service, monthly_revenue_usd, customer_count, transactions_per_hour, revenue_per_transaction`

| Phase | Output |
|-------|--------|
| 1 — Idea | Per-service financial impact modeling with preventability analysis and downtime cost curves |
| 2 — Method | Revenue-per-minute calculation by service, impact aggregation, preventable incident cost quantification, ROI of reliability investment |
| 3 — Experiment | Total business impact by quarter bar chart, cost-of-downtime per minute by service, preventable vs actual pie chart, reliability investment ROI waterfall |
| 4 — Report | Business impact report (CFO-ready), per-service downtime cost model, case for reliability investment with payback period |

---

### Task 26: IT Operations Staffing Model & FTE Optimization

**Difficulty:** ★★☆ | **Persona:** VP/CIO

**Pre-filled Description:**
> Analyze the relationship between IT operations staffing levels, ticket volumes, SLA performance, and automation adoption to build an evidence-based staffing model. Determine optimal FTE-to-ticket ratios by team, quantify the FTE savings from automation initiatives, and forecast staffing needs for the next 12 months based on projected ticket volume growth.

**Suggested Data:**
- `staffing_ops.csv` — columns: `month, team, fte_count, contractor_count, tickets_assigned, tickets_closed, sla_compliance_pct, automation_pct (% of tickets auto-resolved), avg_cost_per_fte_usd, overtime_hours, attrition_count`
- 12 months × 8 teams = ~96 rows

| Phase | Output |
|-------|--------|
| 1 — Idea | Evidence-based staffing model linking FTE levels to SLA outcomes and automation offsets |
| 2 — Method | Productivity ratios, SLA elasticity modeling, automation displacement calculation, forecasting with growth scenarios |
| 3 — Experiment | FTE-to-ticket ratio by team, SLA vs staffing scatter with regression line, automation savings waterfall, 12-month staffing forecast under scenarios |
| 4 — Report | Staffing model report, optimal FTE targets by team, automation investment case, hiring/reduction plan under 3 growth scenarios |

---

### Task 27: Security Incident Response Effectiveness

**Difficulty:** ★★☆ | **Persona:** VP/CIO, CISO

**Pre-filled Description:**
> Analyze security incident response data to measure SOC effectiveness: detection-to-containment time, false positive rates by detection source, severity distribution trends, repeat attack vector frequency, and response playbook adherence. Benchmark against industry standards and identify capability gaps in the security operations program.

**Suggested Data:**
- `security_incidents.csv` — columns: `incident_id, detected_at, contained_at, resolved_at, detection_source (siem/edr/ids/user-report/threat-intel), severity (critical/high/medium/low), attack_vector, false_positive (true/false), playbook_followed (true/false), escalated_to_ir_team (true/false), data_exfiltration (true/false), systems_affected_count, business_impact_category`
- 1,000–3,000 rows, 12 months

| Phase | Output |
|-------|--------|
| 1 — Idea | Detection source ROI analysis, response timeline decomposition, playbook adherence vs outcome correlation |
| 2 — Method | False positive rate by source, MTTC/MTTR benchmarking, playbook compliance scoring, attack vector trend analysis |
| 3 — Experiment | Detection source effectiveness bar chart, response timeline waterfall, false positive rate by source, attack vector trend stacked area chart |
| 4 — Report | SOC effectiveness report, detection source ROI, playbook improvement recommendations, security capability maturity assessment |

---

### Task 28: Cloud Cost Optimization & FinOps Analysis

**Difficulty:** ★★☆ | **Persona:** VP/CIO, Finance

**Pre-filled Description:**
> Analyze cloud infrastructure spending across accounts, services, and teams to identify cost optimization opportunities: idle resources, over-provisioned instances, missed reserved instance/savings plan coverage, data transfer costs, and storage tier mismatches. Quantify potential savings by category and build a FinOps optimization roadmap.

**Suggested Data:**
- `cloud_costs.csv` — columns: `month, cloud_provider (aws/azure/gcp), account, team, service_category (compute/storage/database/network/other), resource_type, resource_count, on_demand_spend_usd, reserved_spend_usd, savings_plan_coverage_pct, avg_utilization_pct, idle_resource_count, idle_resource_cost_usd`
- 300–600 rows (monthly per account/service, 12 months)

| Phase | Output |
|-------|--------|
| 1 — Idea | Multi-lever savings analysis: right-sizing, RI/SP coverage, idle cleanup, storage tiering, data transfer optimization |
| 2 — Method | Per-lever savings estimation, utilization threshold analysis, commitment coverage gap calculation, waste classification |
| 3 — Experiment | Monthly cloud spend trend by category, savings opportunity waterfall chart, utilization distribution histogram, RI coverage gap bar chart |
| 4 — Report | FinOps optimization report, savings by lever with confidence ranges, implementation roadmap by effort/impact, monthly FinOps governance recommendations |

---

### Task 29: IT Service Catalog ROI & Adoption Analysis

**Difficulty:** ★☆☆ | **Persona:** VP/CIO

**Pre-filled Description:**
> Analyze IT service catalog adoption data to measure which services are used, which are underutilized, and what the cost-per-request is for each catalog item. Identify self-service adoption rates vs agent-assisted requests, correlate catalog completeness with user satisfaction, and recommend catalog improvements with projected efficiency gains.

**Suggested Data:**
- `service_catalog.csv` — columns: `catalog_item, category (access/hardware/software/reporting/other), requests_last_12m, self_service_pct, avg_fulfillment_days, cost_per_request_usd, user_satisfaction_score, automation_level (full/partial/manual), last_updated`
- 50–100 rows (catalog items)

| Phase | Output |
|-------|--------|
| 1 — Idea | Catalog effectiveness scoring combining adoption, cost efficiency, satisfaction, and automation level |
| 2 — Method | Request volume vs cost analysis, self-service impact quantification, satisfaction driver analysis, automation ROI estimation |
| 3 — Experiment | Request volume Pareto chart, self-service vs assisted cost comparison, satisfaction by automation level box plot, ROI of automating top manual items |
| 4 — Report | Service catalog health assessment, quick-win automation candidates, catalog redesign recommendations, projected efficiency gains |

---

### Task 30: Multi-Year IT Operational Trend Report

**Difficulty:** ★★☆ | **Persona:** VP/CIO, Board

**Pre-filled Description:**
> Produce a comprehensive multi-year (3-year) IT operations trend report analyzing incident volumes, SLA compliance, MTTR improvement, automation adoption, cost per ticket, staffing efficiency, and customer satisfaction. Identify long-term trends, inflection points, and correlate operational improvements with key initiatives (tool deployments, process changes, org restructures) to demonstrate IT operations maturity progression.

**Suggested Data:**
- `annual_ops_summary.csv` — columns: `quarter, total_incidents, p1_incidents, avg_mttr_hours, sla_compliance_pct, automation_rate_pct, cost_per_ticket_usd, fte_count, tickets_per_fte, csat_score, change_failure_rate_pct, availability_pct`
- 12 rows (quarterly, 3 years)
- `key_initiatives.csv` — columns: `initiative, quarter_launched, category (tool/process/reorg/automation), description, expected_impact`

| Phase | Output |
|-------|--------|
| 1 — Idea | Long-term trend analysis with initiative impact attribution and maturity progression scoring |
| 2 — Method | Time-series trend fitting, intervention analysis (before/after initiatives), composite maturity index construction, projection modeling |
| 3 — Experiment | Multi-metric trend dashboard (12 quarters), initiative impact overlay, maturity index progression chart, forward projection with confidence bands |
| 4 — Report | Multi-year IT ops maturity report (board-ready), initiative ROI attribution, 3-year trajectory narrative, investment case for next phase |

---

### HR / People Operations — Workforce Analytics & Employee Lifecycle

> These tasks address what HR leadership and People Ops teams care about: attrition risk, hiring efficiency, workforce planning, DEI metrics, employee experience, and compliance.

---

### Task 31: Employee Attrition Risk Prediction

**Difficulty:** ★★☆ | **Persona:** HR Director, CHRO

**Pre-filled Description:**
> Analyze employee data to build an attrition risk prediction model using tenure, compensation, performance ratings, manager changes, promotion history, engagement survey scores, and commute distance. Identify the top drivers of voluntary turnover, flag high-risk employees, and recommend targeted retention interventions by risk segment.

**Suggested Data:**
- `employees.csv` — columns: `employee_id, department, role_level (junior/mid/senior/lead/manager/director), hire_date, tenure_months, salary_band, last_raise_pct, last_raise_date, performance_rating (1-5), manager_id, manager_changes_2yr, promotion_last_3yr (true/false), engagement_score (1-10), commute_minutes, remote_pct, training_hours_ytd, voluntary_exit (true/false), exit_date (nullable), exit_reason (nullable)`
- 2,000–5,000 rows

| Phase | Output |
|-------|--------|
| 1 — Idea | Multi-factor attrition model with segment-specific retention levers |
| 2 — Method | Logistic regression / gradient boosting for risk scoring, SHAP values for interpretability, cohort analysis by tenure/dept |
| 3 — Experiment | Feature importance bar chart, attrition rate by department heatmap, risk score distribution, survival curve by tenure band |
| 4 — Report | Attrition risk report, top-10 risk factors, segment-specific retention playbook, projected savings from targeted retention |

**Sample data generation script:**
```python
import pandas as pd, numpy as np
from datetime import datetime, timedelta

np.random.seed(42)
n = 3000
depts = ['Engineering', 'Sales', 'Marketing', 'Support', 'Product', 'Finance', 'HR', 'Operations']
levels = ['Junior', 'Mid', 'Senior', 'Lead', 'Manager', 'Director']

hire_dates = [datetime(2020,1,1) + timedelta(days=int(np.random.uniform(0, 2000))) for _ in range(n)]
tenure = [(datetime(2026,3,1) - d).days / 30 for d in hire_dates]

df = pd.DataFrame({
    'employee_id': [f'EMP{10000+i}' for i in range(n)],
    'department': np.random.choice(depts, n, p=[.25,.15,.1,.15,.1,.1,.05,.1]),
    'role_level': np.random.choice(levels, n, p=[.2,.3,.25,.1,.1,.05]),
    'hire_date': hire_dates,
    'tenure_months': [round(t,1) for t in tenure],
    'salary_band': np.random.choice(['B1','B2','B3','B4','B5','B6'], n),
    'last_raise_pct': np.round(np.random.uniform(0, 15, n), 1),
    'performance_rating': np.random.choice([1,2,3,4,5], n, p=[.02,.08,.35,.4,.15]),
    'manager_changes_2yr': np.random.choice([0,1,2,3], n, p=[.4,.35,.2,.05]),
    'promotion_last_3yr': np.random.choice([True, False], n, p=[.25,.75]),
    'engagement_score': np.round(np.random.normal(7, 1.5, n).clip(1,10), 1),
    'commute_minutes': np.random.choice([0,15,30,45,60,90], n, p=[.3,.15,.2,.15,.15,.05]),
    'remote_pct': np.random.choice([0,20,40,60,80,100], n),
    'training_hours_ytd': np.round(np.random.exponential(20, n), 0),
})
# ~18% attrition
exit_prob = 0.18
exits = np.random.random(n) < exit_prob
df['voluntary_exit'] = exits
df['exit_date'] = [d + timedelta(days=int(np.random.uniform(60, 700))) if e else None for d, e in zip(hire_dates, exits)]
df['exit_reason'] = [np.random.choice(['better-offer','burnout','relocation','career-change','manager','comp']) if e else None for e in exits]
df.to_csv('employees.csv', index=False)
print(f'Generated {len(df)} employees ({exits.sum()} exits) → employees.csv')
```

---

### Task 32: Hiring Funnel Efficiency & Time-to-Fill Analysis

**Difficulty:** ★☆☆ | **Persona:** HR Director, Talent Acquisition Lead

**Pre-filled Description:**
> Analyze recruiting pipeline data to measure hiring funnel conversion rates at each stage (application → screen → interview → offer → accept), time-to-fill by role and department, source effectiveness (referral, job board, agency, direct), and offer acceptance rates. Identify bottlenecks in the hiring process and recommend improvements to reduce time-to-fill and cost-per-hire.

**Suggested Data:**
- `hiring_pipeline.csv` — columns: `requisition_id, department, role_level, source (referral/linkedin/job-board/agency/careers-page), applied_date, screened_date, interview_date, offer_date, accepted_date, rejected_stage (nullable), hired (true/false), time_to_fill_days, cost_source_usd, hiring_manager`
- 2,000–5,000 rows, 12 months

| Phase | Output |
|-------|--------|
| 1 — Idea | Stage-by-stage funnel analysis with source ROI and bottleneck identification |
| 2 — Method | Conversion rate calculation per stage, source cost-effectiveness scoring, time-in-stage analysis, hiring manager throughput benchmarking |
| 3 — Experiment | Funnel conversion chart, source ROI scatter (cost vs quality-of-hire), time-to-fill distribution by dept, bottleneck stage heatmap |
| 4 — Report | Recruiting efficiency report, source optimization recommendations, process bottleneck remediation plan, cost-per-hire reduction targets |

---

### Task 33: Employee Engagement Survey Deep Dive

**Difficulty:** ★☆☆ | **Persona:** HR Director, People Analytics

**Pre-filled Description:**
> Analyze employee engagement survey results across dimensions (manager effectiveness, growth opportunities, compensation satisfaction, work-life balance, belonging, role clarity). Identify the strongest drivers of overall engagement, segment results by department/level/tenure, detect disengagement hotspots, and recommend targeted action plans for the lowest-scoring areas.

**Suggested Data:**
- `engagement_survey.csv` — columns: `employee_id, department, role_level, tenure_bucket (0-1yr/1-3yr/3-5yr/5+yr), remote_pct, overall_engagement (1-10), manager_effectiveness (1-10), growth_opportunities (1-10), comp_satisfaction (1-10), work_life_balance (1-10), belonging (1-10), role_clarity (1-10), would_recommend_employer (1-10), free_text_sentiment (positive/neutral/negative)`
- 1,500–4,000 rows (one per respondent)

| Phase | Output |
|-------|--------|
| 1 — Idea | Driver analysis correlating sub-dimensions with overall engagement, segmented by demographics |
| 2 — Method | Correlation/regression for engagement drivers, department × dimension heatmap, NPS-like segmentation (promoters/passives/detractors), year-over-year delta if historical |
| 3 — Experiment | Engagement driver importance bar chart, department × dimension heatmap, distribution violin plots by tenure, detractor hotspot identification table |
| 4 — Report | Engagement insights report, top-3 drivers of engagement, department-level action plans, manager coaching recommendations |

---

### Task 34: Compensation Equity & Pay Gap Analysis

**Difficulty:** ★★☆ | **Persona:** CHRO, Compensation Manager

**Pre-filled Description:**
> Analyze compensation data across the organization to identify pay equity gaps by gender, ethnicity, role level, department, and tenure. Control for legitimate factors (role, experience, performance, location) using regression analysis to isolate unexplained pay gaps. Quantify the cost of closing identified gaps and recommend a remediation plan.

**Suggested Data:**
- `compensation.csv` — columns: `employee_id, gender, ethnicity, department, role_level, role_family, location, tenure_months, performance_rating, base_salary_usd, total_comp_usd (base + bonus + equity), compa_ratio, last_adjustment_date, market_benchmark_usd`
- 2,000–5,000 rows

| Phase | Output |
|-------|--------|
| 1 — Idea | Controlled regression to isolate unexplained pay gaps after accounting for role, performance, experience, and location |
| 2 — Method | Unadjusted gap calculation, multi-variate regression controlling for legitimate factors, residual gap quantification, remediation cost modeling |
| 3 — Experiment | Unadjusted pay gap bars by group, compa-ratio distribution box plots, regression coefficient chart (explained vs unexplained), remediation cost waterfall |
| 4 — Report | Pay equity audit report, adjusted gap findings, remediation cost estimate, compliance-ready documentation, ongoing monitoring framework |

---

### Task 35: Workforce Planning & Headcount Forecasting

**Difficulty:** ★★☆ | **Persona:** CHRO, VP HR

**Pre-filled Description:**
> Build an evidence-based workforce planning model using historical headcount data, attrition rates, hiring velocity, business growth projections, and productivity metrics. Forecast headcount needs by department for the next 12 months under growth, flat, and contraction scenarios. Identify departments at risk of understaffing and quantify the cost of unfilled positions.

**Suggested Data:**
- `workforce_data.csv` — columns: `quarter, department, opening_headcount, hires, voluntary_exits, involuntary_exits, internal_transfers_in, internal_transfers_out, closing_headcount, open_requisitions, revenue_per_employee, avg_time_to_fill_days`
- 12 quarters × 8 departments = ~96 rows
- `business_forecast.csv` — columns: `quarter, department, projected_revenue_growth_pct, new_product_launches, planned_projects`

| Phase | Output |
|-------|--------|
| 1 — Idea | Supply-demand workforce model with scenario analysis and vacancy cost quantification |
| 2 — Method | Attrition forecasting, hiring pipeline capacity estimation, demand modeling from business drivers, gap analysis under scenarios |
| 3 — Experiment | Headcount trend by department, attrition forecast, hiring demand vs capacity gap chart, scenario comparison (growth/flat/contraction) |
| 4 — Report | Workforce planning report, 12-month headcount forecast by department, vacancy risk register, strategic hiring recommendations |

---

### Task 36: DEI (Diversity, Equity & Inclusion) Metrics Dashboard

**Difficulty:** ★★☆ | **Persona:** CHRO, DEI Lead

**Pre-filled Description:**
> Analyze workforce diversity data across the employee lifecycle: representation at each level (entry to executive), hiring pipeline diversity, promotion rate parity, attrition rate parity, and pay equity by demographic group. Track progress against DEI goals, identify pipeline leaks where underrepresented groups drop off, and recommend targeted programs.

**Suggested Data:**
- `dei_data.csv` — columns: `employee_id, gender, ethnicity, age_band, disability_status, veteran_status, department, role_level, hire_date, hired_this_year (true/false), promoted_this_year (true/false), exited_this_year (true/false), performance_rating, salary_band`
- 3,000–5,000 rows

| Phase | Output |
|-------|--------|
| 1 — Idea | Lifecycle funnel analysis by demographic group with representation gap quantification at each level |
| 2 — Method | Representation ratio at each level, promotion/attrition rate parity analysis, hiring pipeline diversity funnel, intersectional analysis |
| 3 — Experiment | Representation pyramid chart by level & group, promotion rate parity bar chart, attrition rate comparison, hiring diversity funnel |
| 4 — Report | DEI dashboard report, pipeline leak identification, progress against goals, targeted program recommendations |

---

### Task 37: Learning & Development ROI Analysis

**Difficulty:** ★☆☆ | **Persona:** HR Director, L&D Manager

**Pre-filled Description:**
> Analyze training and development program data to measure ROI: completion rates, skill assessment improvement, correlation with performance ratings, promotion rates, and retention. Identify which L&D programs have the highest impact on career progression and retention, and which have low engagement. Recommend investment reallocation for maximum workforce development impact.

**Suggested Data:**
- `training_data.csv` — columns: `employee_id, program_name, program_category (technical/leadership/compliance/soft-skills), enrolled_date, completed (true/false), completion_pct, pre_assessment_score, post_assessment_score, cost_per_participant_usd, performance_rating_before, performance_rating_after, promoted_within_12m (true/false), exited_within_12m (true/false)`
- 5,000–10,000 rows (enrollment records)

| Phase | Output |
|-------|--------|
| 1 — Idea | Program-level ROI scoring combining skill gain, performance improvement, promotion uplift, and retention effect |
| 2 — Method | Skill gain calculation, before/after performance comparison, promotion/retention correlation, cost-effectiveness ranking |
| 3 — Experiment | Program completion rate Pareto, skill gain vs cost scatter, promotion lift bar chart by program, retention impact comparison |
| 4 — Report | L&D ROI report, program effectiveness rankings, budget reallocation recommendations, program retirement/refresh candidates |

---

### Task 38: Absenteeism Pattern Analysis & Prediction

**Difficulty:** ★☆☆ | **Persona:** HR Director, Operations Manager

**Pre-filled Description:**
> Analyze employee absence data to identify patterns in unplanned absenteeism: seasonal trends, day-of-week effects, department hotspots, correlation with engagement scores, and manager-level variation. Build a prediction model for absence likelihood and recommend preventive wellness or scheduling interventions.

**Suggested Data:**
- `absences.csv` — columns: `employee_id, department, role_level, manager_id, absence_date, absence_type (sick/personal/family/mental-health/other), planned (true/false), duration_days, consecutive_days, return_date`
- 8,000–15,000 rows (absence records, 12 months)
- `employee_context.csv` — columns: `employee_id, tenure_months, engagement_score, commute_minutes, remote_pct, shift_type (day/night/rotating)`

| Phase | Output |
|-------|--------|
| 1 — Idea | Temporal and organizational pattern analysis with engagement-linked absence prediction |
| 2 — Method | Seasonal decomposition, day-of-week analysis, department/manager hotspot detection, regression with engagement + commute factors |
| 3 — Experiment | Monthly absence trend line, day-of-week heatmap, department absence rate bar chart, engagement vs absence rate scatter |
| 4 — Report | Absenteeism insights report, hotspot identification, predictive risk flags, wellness program and scheduling recommendations |

---

### Task 39: Internal Mobility & Career Pathing Analysis

**Difficulty:** ★★☆ | **Persona:** CHRO, Talent Management

**Pre-filled Description:**
> Analyze internal transfer, promotion, and lateral move data to map actual career paths within the organization. Identify which roles serve as feeder pools for leadership, where career paths stagnate, which departments export vs import talent, and how internal mobility correlates with retention. Recommend career pathing improvements and internal marketplace strategies.

**Suggested Data:**
- `career_moves.csv` — columns: `employee_id, move_date, move_type (promotion/lateral/demotion/reorg), from_department, to_department, from_role_level, to_role_level, from_role_family, to_role_family, tenure_at_move_months, performance_at_move, still_employed (true/false), months_to_next_move (nullable)`
- 3,000–5,000 rows (career moves, 5 years)

| Phase | Output |
|-------|--------|
| 1 — Idea | Career path network analysis with stagnation detection and mobility-retention correlation |
| 2 — Method | Transition probability matrix, career path Sankey mapping, stagnation thresholds (time-in-role percentiles), department talent flow balance |
| 3 — Experiment | Career path Sankey diagram, promotion velocity by department, talent exporter/importer balance chart, stagnation risk by role-level heatmap |
| 4 — Report | Internal mobility report, common career paths mapped, stagnation hotspots, talent flow imbalances, career marketplace recommendations |

---

### Task 40: Employee Onboarding Effectiveness & Time-to-Productivity

**Difficulty:** ★☆☆ | **Persona:** HR Director, Hiring Manager

**Pre-filled Description:**
> Analyze new hire onboarding data to measure time-to-productivity (time until a new hire reaches median output), onboarding satisfaction scores, early attrition rates (exits within 90/180 days), and correlation between onboarding program completion and 12-month retention. Identify which onboarding elements predict success and which departments have the fastest/slowest ramp-up times.

**Suggested Data:**
- `onboarding.csv` — columns: `employee_id, department, role_level, hire_date, orientation_completed (true/false), buddy_assigned (true/false), onboarding_checklist_completion_pct, onboarding_satisfaction (1-10), first_project_date, time_to_first_delivery_days, 90_day_performance_rating, 180_day_performance_rating, manager_satisfaction_score, exited_within_90d (true/false), exited_within_180d (true/false)`
- 500–1,500 rows (new hires, 24 months)

| Phase | Output |
|-------|--------|
| 1 — Idea | Onboarding element effectiveness analysis with time-to-productivity benchmarking and early attrition prediction |
| 2 — Method | Time-to-productivity measurement by department, onboarding element correlation analysis, early attrition risk modeling, buddy program impact assessment |
| 3 — Experiment | Time-to-productivity distribution by department, onboarding completion vs retention scatter, early attrition by onboarding satisfaction, buddy program impact comparison |
| 4 — Report | Onboarding effectiveness report, departmental benchmarks, high-impact program elements, early attrition prevention recommendations |

---

### Finance & Procurement — IT Budget, Vendor Management & Cost Control

> These tasks address what Finance/Procurement teams tied to IT care about: budget variance, vendor negotiations, license optimization, and spend forecasting.

---

### Task 41: IT Budget Variance & Forecast Accuracy Analysis

**Difficulty:** ★☆☆ | **Persona:** IT Finance Manager, CFO

**Pre-filled Description:**
> Analyze IT budget data to measure planned vs actual spend variance by category (hardware, software, cloud, labor, professional services) across quarters. Identify systematic over/under-budgeting patterns, assess forecast accuracy by category, and recommend budgeting methodology improvements to reduce variance.

**Suggested Data:**
- `it_budget.csv` — columns: `quarter, category (hardware/software/cloud/labor/professional-services/maintenance/telecom), planned_usd, actual_usd, variance_usd, variance_pct, approval_count, change_request_count, department`
- 12 quarters × 8 categories × 5 departments = ~480 rows

| Phase | Output |
|-------|--------|
| 1 — Idea | Systematic variance pattern identification with category-specific forecast improvement strategies |
| 2 — Method | Variance decomposition (price vs volume vs timing), forecast accuracy metrics (MAPE, bias), trend analysis, category clustering |
| 3 — Experiment | Budget vs actual waterfall chart, variance trend by category, forecast accuracy improvement over time, bias direction heatmap |
| 4 — Report | Budget performance report, category-level variance analysis, forecast accuracy scorecard, budgeting process recommendations |

---

### Task 42: Software License Utilization & Optimization

**Difficulty:** ★☆☆ | **Persona:** IT Finance Manager, Procurement Lead

**Pre-filled Description:**
> Analyze enterprise software license data to identify utilization rates, shelfware (purchased but unused licenses), license compliance gaps, and upcoming renewal opportunities. Calculate potential savings from right-sizing, consolidation, and renegotiation, and produce a prioritized optimization roadmap.

**Suggested Data:**
- `licenses.csv` — columns: `vendor, product, license_type (per-seat/per-core/enterprise/consumption), total_licenses, active_users, peak_usage, utilization_pct, annual_cost_usd, renewal_date, contract_end_date, auto_renew (true/false), last_audit_date, compliance_status (compliant/over/under)`
- 50–100 rows (one per product)

| Phase | Output |
|-------|--------|
| 1 — Idea | Utilization-based right-sizing with renewal timeline prioritization and consolidation mapping |
| 2 — Method | Utilization threshold analysis, shelfware identification (< 50% utilization), renewal urgency scoring, vendor consolidation opportunities |
| 3 — Experiment | Utilization vs cost scatter plot, shelfware bar chart (wasted spend), renewal timeline with optimization windows, consolidation savings waterfall |
| 4 — Report | License optimization report, shelfware reclamation plan, renewal negotiation playbook, projected annual savings |

---

### Task 43: Vendor Performance Scorecard & Contract Risk Analysis

**Difficulty:** ★★☆ | **Persona:** Procurement Lead, IT Finance

**Pre-filled Description:**
> Build a comprehensive vendor performance scorecard using SLA compliance, incident rates, support response times, contract terms, price competitiveness, and business criticality. Identify high-risk vendor dependencies (single-source, expiring contracts, poor performance) and recommend vendor management actions.

**Suggested Data:**
- `vendor_performance.csv` — columns: `vendor, category, annual_spend_usd, contract_start, contract_end, sla_compliance_pct, support_response_hours, incidents_caused, uptime_pct, price_vs_market_pct, single_source (true/false), switching_cost_estimate, business_criticality (critical/high/medium/low), satisfaction_score (1-10)`
- 30–60 rows (one per vendor)

| Phase | Output |
|-------|--------|
| 1 — Idea | Multi-dimensional vendor scoring with risk-weighted prioritization for management actions |
| 2 — Method | Composite score construction (performance + cost + risk), single-source risk flagging, contract expiry timeline, price benchmarking |
| 3 — Experiment | Vendor scorecard radar charts, risk matrix (performance vs criticality), contract expiry timeline, cost vs performance quadrant |
| 4 — Report | Vendor management report, scorecards with action items, high-risk vendor mitigation plan, renegotiation targets |

---

### Task 44: IT Capital vs OpEx Spend Trend & Cloud Migration Financial Impact

**Difficulty:** ★★☆ | **Persona:** CFO, IT Finance

**Pre-filled Description:**
> Analyze the shift from capital expenditure to operational expenditure as the organization migrates to cloud. Track CapEx/OpEx ratio trends, depreciation schedules for on-prem assets, cloud spend growth trajectory, and total cost of ownership comparison. Project the financial impact of continuing cloud migration on the P&L over 3 years.

**Suggested Data:**
- `capex_opex.csv` — columns: `quarter, category, subcategory, capex_usd, opex_usd, depreciation_usd, asset_book_value_usd, cloud_migration_pct, headcount_infra, headcount_cloud`
- 12 quarters × 6 categories = ~72 rows
- `tco_comparison.csv` — columns: `workload, on_prem_annual_cost, cloud_annual_cost, migration_cost, break_even_months`

| Phase | Output |
|-------|--------|
| 1 — Idea | CapEx/OpEx ratio modeling with cloud migration financial trajectory and TCO break-even analysis |
| 2 — Method | Ratio trend analysis, depreciation runoff modeling, cloud spend growth rate projection, TCO break-even calculation |
| 3 — Experiment | CapEx vs OpEx stacked area chart (quarterly), cloud migration cost curve, TCO comparison bar chart, 3-year P&L projection |
| 4 — Report | IT financial transformation report, CapEx-to-OpEx migration analysis, TCO findings, 3-year financial projection for leadership |

---

### Task 45: Purchase Order Cycle Time & Procurement Bottleneck Analysis

**Difficulty:** ★☆☆ | **Persona:** Procurement Lead

**Pre-filled Description:**
> Analyze IT procurement data to measure purchase order cycle times from request to delivery, identify bottleneck stages (approval, sourcing, contracting, fulfillment), and compare cycle times by vendor, category, and dollar threshold. Recommend process improvements and approval workflow optimizations.

**Suggested Data:**
- `procurement.csv` — columns: `po_id, requested_date, approved_date, sourced_date, contracted_date, delivered_date, category, vendor, amount_usd, approval_tier (auto/manager/director/vp/cfo), requester_department, rush (true/false), rejected (true/false), rejection_reason`
- 1,000–3,000 rows, 12 months

| Phase | Output |
|-------|--------|
| 1 — Idea | Stage-by-stage cycle time decomposition with approval tier and dollar threshold analysis |
| 2 — Method | Per-stage duration calculation, bottleneck identification, approval tier threshold optimization, vendor fulfillment benchmarking |
| 3 — Experiment | Cycle time breakdown stacked bar, bottleneck stage by category heatmap, approval tier threshold analysis, vendor delivery time comparison |
| 4 — Report | Procurement efficiency report, bottleneck remediation plan, approval threshold recommendations, vendor negotiation targets for delivery SLAs |

---

### Project Management / PMO — Delivery, Resources & Portfolio Health

> These tasks address what PMO leaders and delivery managers track: project health, resource utilization, delivery predictability, and portfolio risk.

---

### Task 46: Project Portfolio Health & Risk Dashboard

**Difficulty:** ★★☆ | **Persona:** PMO Director, VP Delivery

**Pre-filled Description:**
> Analyze the active project portfolio to produce a health dashboard: schedule variance, budget variance, scope change frequency, resource utilization, and risk score per project. Classify projects into Red/Amber/Green status using quantitative thresholds, identify projects trending toward distress, and recommend PMO interventions.

**Suggested Data:**
- `projects.csv` — columns: `project_id, project_name, sponsor, pm, department, start_date, planned_end_date, forecast_end_date, schedule_variance_days, budget_planned_usd, budget_actual_usd, budget_variance_pct, scope_changes_count, resource_count, resource_utilization_pct, risks_open, risks_high, status (green/amber/red), phase (initiate/plan/execute/close)`
- 30–80 rows (active projects)

| Phase | Output |
|-------|--------|
| 1 — Idea | Multi-factor health scoring with trend-based distress prediction and intervention prioritization |
| 2 — Method | RAG status computation from quantitative thresholds, schedule/budget trend fitting, distress probability scoring, PM workload analysis |
| 3 — Experiment | Portfolio RAG donut chart, schedule vs budget variance scatter, distress probability ranking, PM workload distribution |
| 4 — Report | Portfolio health dashboard, at-risk project profiles with recommended PMO actions, resource rebalancing suggestions |

---

### Task 47: Resource Allocation & Utilization Optimization

**Difficulty:** ★★☆ | **Persona:** PMO Director, Resource Manager

**Pre-filled Description:**
> Analyze resource allocation data across the project portfolio to identify over-allocated and under-allocated team members, skill-demand mismatches, and bench time. Compare planned vs actual utilization, forecast demand-supply gaps for the next quarter, and recommend allocation adjustments.

**Suggested Data:**
- `resource_allocation.csv` — columns: `employee_id, name, skill_primary, skill_secondary, cost_rate_usd, month, project_id, planned_hours, actual_hours, utilization_pct, billable (true/false), bench (true/false)`
- 3,000–8,000 rows (monthly per person per project, 6 months)
- `demand_forecast.csv` — columns: `month, skill, demand_hours, supply_hours`

| Phase | Output |
|-------|--------|
| 1 — Idea | Utilization optimization with skill-demand matching and bench time reduction strategies |
| 2 — Method | Per-person utilization analysis, over/under allocation detection, skill gap heat mapping, demand-supply forecast |
| 3 — Experiment | Utilization distribution histogram, over-allocated top-10 bar chart, skill demand vs supply gap chart, bench time trend |
| 4 — Report | Resource optimization report, reallocation recommendations, skill gap action plan, hiring/contractor targets for demand peaks |

---

### Task 48: Delivery Predictability & Estimation Accuracy

**Difficulty:** ★★☆ | **Persona:** PMO Director, Engineering VP

**Pre-filled Description:**
> Analyze completed project data to measure delivery predictability: what percentage of projects delivered on time and on budget, how accurate were initial estimates, and how did estimation accuracy vary by project type, size, team, and methodology (agile/waterfall/hybrid). Identify systematic estimation biases and recommend calibration improvements.

**Suggested Data:**
- `completed_projects.csv` — columns: `project_id, project_type (new-feature/enhancement/migration/integration/infra), methodology (agile/waterfall/hybrid), team, original_estimate_days, revised_estimate_days, actual_days, original_budget_usd, actual_budget_usd, scope_changes, team_size, on_time (true/false), on_budget (true/false), estimation_accuracy_pct`
- 100–300 rows (completed projects, 3 years)

| Phase | Output |
|-------|--------|
| 1 — Idea | Estimation bias analysis by project type/team/methodology with calibration factor recommendations |
| 2 — Method | Estimation accuracy distribution, systematic bias detection (MAPE, median PE), cohort comparison, reference class forecasting |
| 3 — Experiment | Estimation accuracy distribution histogram, bias by project type box plots, accuracy improvement trend over time, methodology comparison scatter |
| 4 — Report | Estimation accuracy report, bias findings per dimension, calibration factors (multiply estimates by X), process improvement recommendations |

---

### Task 49: Agile Sprint Metrics & Team Velocity Analysis

**Difficulty:** ★☆☆ | **Persona:** Delivery Manager, Scrum Master

**Pre-filled Description:**
> Analyze agile sprint data to measure team velocity trends, sprint commitment vs completion rates, story point accuracy, carry-over patterns, and bug-to-feature ratios. Identify teams with declining velocity, high carry-over, or capacity mismatch. Recommend sprint planning improvements.

**Suggested Data:**
- `sprint_metrics.csv` — columns: `team, sprint_id, sprint_start, sprint_end, committed_points, completed_points, carry_over_points, stories_committed, stories_completed, bugs_fixed, unplanned_work_pct, team_size, avg_velocity_3sprint`
- 200–500 rows (10 teams × 20-50 sprints)

| Phase | Output |
|-------|--------|
| 1 — Idea | Velocity trend analysis with commitment reliability scoring and carry-over pattern identification |
| 2 — Method | Velocity trend fitting per team, commitment ratio calculation, carry-over pattern detection, unplanned work impact analysis |
| 3 — Experiment | Team velocity trend lines, commitment vs completion bar chart, carry-over ratio trend, unplanned work impact scatter |
| 4 — Report | Agile health report, team-level sprint metrics summ, planning accuracy improvements, capacity allocation recommendations |

---

### Task 50: Change Request Impact on Project Delivery

**Difficulty:** ★★☆ | **Persona:** PMO Director, Sponsor

**Pre-filled Description:**
> Analyze the impact of change requests on project delivery outcomes: how much schedule/budget variance is attributable to scope changes, which project types attract the most changes, and at what project stage do changes have the highest impact. Quantify the true cost of change requests including ripple effects on dependent projects.

**Suggested Data:**
- `change_requests.csv` — columns: `cr_id, project_id, requested_date, approved_date, project_phase_at_request, change_type (scope/requirement/design/schedule), estimated_effort_days, actual_effort_days, schedule_impact_days, budget_impact_usd, approved (true/false), requestor_role, dependencies_affected`
- 500–1,500 rows (change requests, 2 years)

| Phase | Output |
|-------|--------|
| 1 — Idea | Change request impact quantification with phase-sensitivity analysis and dependency ripple cost calculation |
| 2 — Method | Phase-of-impact analysis (cost multiplier curve), change type distribution, variance attribution, dependency cascade modeling |
| 3 — Experiment | Change cost multiplier by phase curve, change type distribution donut, variance attributable to CRs vs baseline, impact cascade network |
| 4 — Report | Change management impact report, scope change cost model, gate review improvement recommendations, change budget reserve sizing |

---

### Customer Support / Service Desk — Customer Experience & Operational Metrics

> These tasks address external-facing support operations: customer satisfaction, ticket deflection, knowledge base effectiveness, and support cost optimization.

---

### Task 51: Customer Satisfaction (CSAT) Driver Analysis

**Difficulty:** ★☆☆ | **Persona:** Support Director, CX Leader

**Pre-filled Description:**
> Analyze customer satisfaction survey data alongside ticket attributes to identify the strongest drivers of CSAT scores: resolution time, first-contact resolution, channel (phone/chat/email/self-service), agent experience level, issue complexity, and number of transfers. Build a predictive model for CSAT and recommend operational changes to improve scores.

**Suggested Data:**
- `csat_tickets.csv` — columns: `ticket_id, created_at, resolved_at, channel (phone/chat/email/self-service/portal), category, priority, resolution_time_hours, first_contact_resolution (true/false), transfers_count, agent_id, agent_tenure_months, csat_score (1-5), nps_score (-100 to 100), customer_segment (enterprise/mid-market/smb), customer_tenure_months`
- 5,000–10,000 rows, 6 months

| Phase | Output |
|-------|--------|
| 1 — Idea | Multi-factor CSAT driver analysis with channel × complexity interaction effects |
| 2 — Method | Correlation/regression for CSAT drivers, SHAP interpretability, channel comparison, agent performance segmentation |
| 3 — Experiment | CSAT driver importance bar chart, channel comparison box plots, FCR impact on CSAT scatter, agent tenure vs CSAT curve |
| 4 — Report | CSAT driver report, top-5 actionable improvements with projected CSAT lift, channel strategy recommendations, agent training priorities |

---

### Task 52: Self-Service Deflection & Knowledge Base Effectiveness

**Difficulty:** ★☆☆ | **Persona:** Support Director, Knowledge Manager

**Pre-filled Description:**
> Analyze self-service adoption data to measure ticket deflection rates, knowledge base article effectiveness (views, helpfulness ratings, search success rate), and identify the gap between what customers search for and what articles exist. Quantify the cost savings from deflection and recommend knowledge base improvements.

**Suggested Data:**
- `kb_analytics.csv` — columns: `article_id, title, category, views_last_6m, helpful_yes, helpful_no, helpfulness_pct, linked_tickets_avoided, search_impressions, search_clicks, last_updated, author, word_count`
- 200–500 rows (articles)
- `search_queries.csv` — columns: `query, timestamp, results_count, clicked_article_id (nullable), ticket_created_after (true/false)`
- 10,000–20,000 rows

| Phase | Output |
|-------|--------|
| 1 — Idea | Article effectiveness scoring with search-gap detection and deflection value quantification |
| 2 — Method | Article usefulness scoring (views × helpfulness), search gap identification (queries with zero results → ticket), deflection funnel analysis, content freshness assessment |
| 3 — Experiment | Top articles by deflection value, search gap word cloud / Pareto, deflection funnel chart, content freshness heatmap |
| 4 — Report | Knowledge base effectiveness report, content gap prioritization, retirement/refresh candidates, projected deflection improvements with cost savings |

---

### Task 53: Support Ticket Escalation Pattern & Tier Optimization

**Difficulty:** ★★☆ | **Persona:** Support Director, Operations Manager

**Pre-filled Description:**
> Analyze support ticket escalation patterns to measure escalation rates by tier (L1 → L2 → L3), identify categories that are systematically over-escalated, quantify the cost of unnecessary escalations, and recommend tier boundary adjustments, training investments, and knowledge transfers to improve first-tier resolution rates.

**Suggested Data:**
- `escalation_data.csv` — columns: `ticket_id, category, priority, initial_tier, final_tier, escalation_count, l1_time_minutes, l2_time_minutes, l3_time_minutes, total_resolution_hours, could_have_been_resolved_lower (true/false/unknown), escalation_reason (skill-gap/authority/complexity/policy), cost_per_tier_usd`
- 3,000–5,000 rows, 6 months

| Phase | Output |
|-------|--------|
| 1 — Idea | Escalation funnel analysis with unnecessary escalation identification and tier boundary optimization |
| 2 — Method | Escalation rate by category, unnecessary escalation detection, cost modeling per tier, tier boundary threshold analysis |
| 3 — Experiment | Escalation funnel Sankey, unnecessary escalation rate by category, cost of escalation bar chart, training ROI projection |
| 4 — Report | Escalation optimization report, tier boundary recommendations, L1 training investment case, projected resolution rate improvement |

---

### Task 54: Support Channel Mix & Cost-per-Contact Optimization

**Difficulty:** ★☆☆ | **Persona:** Support Director, CFO

**Pre-filled Description:**
> Analyze support volume and cost across channels (phone, chat, email, self-service portal, AI chatbot) to calculate cost-per-contact, customer satisfaction, and resolution rates by channel. Model the financial impact of shifting volume from high-cost to low-cost channels while maintaining CSAT, and recommend a target channel mix.

**Suggested Data:**
- `channel_metrics.csv` — columns: `month, channel (phone/chat/email/portal/chatbot), ticket_count, avg_handle_time_minutes, cost_per_contact_usd, csat_score, first_contact_resolution_pct, agent_count, agent_utilization_pct`
- 12 months × 5 channels = ~60 rows

| Phase | Output |
|-------|--------|
| 1 — Idea | Channel economics analysis with CSAT-constrained optimization for target mix |
| 2 — Method | Per-channel unit economics, CSAT × cost trade-off modeling, volume shift scenario analysis, agent capacity impact |
| 3 — Experiment | Cost-per-contact by channel bar chart, CSAT vs cost scatter by channel, volume shift savings waterfall, target mix vs current donut comparison |
| 4 — Report | Channel strategy report, cost-per-contact benchmarks, target channel mix with projected savings, migration roadmap |

---

### Task 55: Customer Churn Correlation with Support Experience

**Difficulty:** ★★☆ | **Persona:** CX Leader, VP Customer Success

**Pre-filled Description:**
> Analyze the relationship between customer support experience and churn behavior. Measure how ticket volume, resolution time, CSAT scores, escalation frequency, and unresolved issues correlate with customer renewal decisions. Build a support-experience risk score that flags accounts at churn risk due to poor support outcomes, enabling proactive outreach.

**Suggested Data:**
- `customer_support_churn.csv` — columns: `customer_id, segment (enterprise/mid-market/smb), arr_usd, tickets_last_12m, avg_resolution_hours, avg_csat, escalations, unresolved_tickets, p1_incidents, support_nps, contract_renewal_date, churned (true/false), churn_reason (nullable)`
- 500–2,000 rows (customer accounts)

| Phase | Output |
|-------|--------|
| 1 — Idea | Support-experience churn risk model with threshold identification for proactive intervention |
| 2 — Method | Churn correlation analysis, logistic regression with support features, risk threshold calibration, proactive outreach segmentation |
| 3 — Experiment | Churn rate by CSAT bucket, support features vs churn correlation matrix, risk score distribution, at-risk account identification table |
| 4 — Report | Support-churn correlation report, risk scoring model, proactive intervention playbook, retention ROI estimate |

---

## Market Intelligence / Strategic Research (Tasks 56-65)

### Task 56: Competitive Landscape & Market Positioning

**Difficulty:** ★★☆ | **Persona:** Strategy Analyst, VP Strategy, Product Marketing

**Pre-filled Description:**
> Build a CB Insights-style competitive landscape analysis from a dataset of companies in a target market segment. Map competitors across dimensions: funding stage, employee headcount, product breadth, geographic presence, and customer sentiment. Produce a market map quadrant (Leaders / Challengers / Niche / Emerging), identify white-space opportunities, and summarize each competitor's strategic trajectory.

**Suggested Data:**
- `competitive_landscape.csv` — columns: `company_name, founding_year, hq_country, total_funding_usd, last_round_type (seed/A/B/C/D/IPO), last_round_date, employees, yoy_employee_growth_pct, product_categories (pipe-delimited), customer_count_est, avg_g2_rating, nps_est, key_differentiator, recent_news_summary`
- 30–100 rows (competitors in a segment)

| Phase | Output |
|-------|--------|
| 1 — Idea | Competitive landscape quadrant mapping with strategic positioning thesis |
| 2 — Method | Multi-dimensional scoring model, cluster analysis, growth trajectory classification, white-space identification |
| 3 — Experiment | Market map quadrant chart, funding vs growth scatter, employee growth heatmap, product overlap matrix, competitive positioning table |
| 4 — Report | Full competitive intelligence brief with market map, per-competitor profiles, white-space analysis, and strategic recommendations |

---

### Task 57: Startup & Venture Funding Trend Analysis

**Difficulty:** ★★☆ | **Persona:** VC Analyst, Corporate Development, Innovation Lead

**Pre-filled Description:**
> Analyze venture funding patterns in a technology category over the past 3-5 years. Identify funding seasonality, average round sizes by stage, investor concentration, and mega-round trends. Highlight breakout companies (unusually fast funding progression), detect cooling or heating signals, and produce a market investment thesis.

**Suggested Data:**
- `funding_rounds.csv` — columns: `company_name, round_date, round_type (pre-seed/seed/A/B/C/D+/IPO), amount_usd, pre_money_valuation_usd, lead_investor, investor_count, sector_tags, hq_country, announced_use_of_funds`
- 500–3,000 rows (funding rounds across companies)

| Phase | Output |
|-------|--------|
| 1 — Idea | Funding trend thesis with heating/cooling signals and breakout company identification |
| 2 — Method | Time series decomposition of deal flow, stage-level aggregation, investor network analysis, pace-of-funding velocity metric |
| 3 — Experiment | Quarterly deal volume & value chart, median round size by stage, investor leaderboard, funding velocity table for breakout companies, YoY comparison |
| 4 — Report | Market funding intelligence report with investment thesis, trend visualizations, breakout company profiles, and forward-looking signals |

---

### Task 58: Emerging Technology Adoption & Hype Curve

**Difficulty:** ★★★ | **Persona:** CTO, Innovation Lead, Strategy Analyst

**Pre-filled Description:**
> Map emerging technologies across a Gartner-style hype curve using adoption signals: job postings mentioning the tech, patent filings, funding into related startups, enterprise pilot mentions, and analyst coverage frequency. Classify each technology's maturity stage and estimate time-to-mainstream adoption.

**Suggested Data:**
- `tech_signals.csv` — columns: `technology, quarter, job_postings_count, patent_filings, startup_funding_usd, enterprise_pilots_announced, analyst_mentions, github_stars_delta, stackoverflow_questions_delta, gartner_stage_est (Innovation Trigger/Peak/Trough/Slope/Plateau)`
- 200–800 rows (20-40 technologies × quarterly data)

| Phase | Output |
|-------|--------|
| 1 — Idea | Hype curve positioning with adoption velocity classification and time-to-plateau estimates |
| 2 — Method | Composite adoption index from weighted signals, stage classification algorithm, velocity-based maturity prediction |
| 3 — Experiment | Hype curve visualization, adoption signal radar charts per technology, velocity ranking table, technology readiness matrix |
| 4 — Report | Emerging technology radar report with hype curve, per-technology profiles, adoption recommendations, and investment timing guidance |

---

### Task 59: Market Sizing & TAM/SAM/SOM Estimation

**Difficulty:** ★★★ | **Persona:** Product Strategy, BD Lead, VP Marketing

**Pre-filled Description:**
> Estimate Total Addressable Market (TAM), Serviceable Addressable Market (SAM), and Serviceable Obtainable Market (SOM) for a product category using bottom-up company data, industry spending surveys, and adoption rates. Compare top-down vs bottom-up estimates and identify the highest-growth sub-segments.

**Suggested Data:**
- `market_data.csv` — columns: `segment, sub_segment, region, year, company_count_est, avg_spend_per_company_usd, adoption_rate_pct, yoy_growth_pct, our_addressable (true/false), our_win_rate_pct`
- 100–500 rows (segment × region × year combinations)

| Phase | Output |
|-------|--------|
| 1 — Idea | TAM/SAM/SOM framework with dual estimation methodology and growth segment identification |
| 2 — Method | Bottom-up sizing (company count × spend × adoption), top-down cross-check, growth-weighted segmentation, SOM calculation from win rates |
| 3 — Experiment | TAM/SAM/SOM waterfall chart, segment growth comparison, region heatmap, top-down vs bottom-up reconciliation table |
| 4 — Report | Market sizing memo with TAM/SAM/SOM figures, methodology appendix, high-growth segment deep-dives, and go-to-market prioritization |

---

### Task 60: Industry Earnings & Revenue Benchmarking

**Difficulty:** ★★☆ | **Persona:** CFO, Strategy Analyst, Investor Relations

**Pre-filled Description:**
> Benchmark a company's financial performance against industry peers using public earnings data. Compare revenue growth, gross margin, operating margin, R&D intensity, sales efficiency, and rule-of-40 metrics. Identify where the company over/under-indexes vs peer median and suggest operational focus areas.

**Suggested Data:**
- `peer_financials.csv` — columns: `company_name, ticker, fiscal_year, quarter, revenue_usd, revenue_yoy_growth_pct, gross_margin_pct, operating_margin_pct, rd_spend_usd, rd_as_pct_revenue, s_and_m_as_pct_revenue, net_retention_pct, arr_usd, employees, revenue_per_employee`
- 50–200 rows (10-20 peer companies × quarterly data)

| Phase | Output |
|-------|--------|
| 1 — Idea | Peer benchmarking framework with rule-of-40 and operational efficiency focus |
| 2 — Method | Percentile ranking across KPIs, peer-median comparison, rule-of-40 calculation, efficiency ratio decomposition |
| 3 — Experiment | Peer benchmark spider chart, growth vs margin scatter, rule-of-40 leaderboard, KPI percentile rank table, trend comparison |
| 4 — Report | Financial benchmarking report with peer ranking, gap analysis, operational improvement recommendations, and board-ready summary |

---

### Task 61: M&A Target Screening & Fit Scoring

**Difficulty:** ★★★ | **Persona:** Corporate Development, VP Strategy, PE Analyst

**Pre-filled Description:**
> Screen potential M&A targets from a long list using strategic fit criteria: technology overlap, customer base complementarity, geographic expansion, revenue multiple, growth rate, and integration complexity. Produce a ranked shortlist with fit scores and flag deal-breaker risks.

**Suggested Data:**
- `ma_targets.csv` — columns: `company_name, sector, revenue_usd, revenue_growth_pct, gross_margin_pct, employee_count, hq_country, technology_stack (pipe-delimited), customer_overlap_pct, geographic_fit_score, product_complementarity_score, estimated_valuation_usd, estimated_revenue_multiple, integration_risk (low/med/high), key_risk_flag`
- 30–80 rows (target companies)

| Phase | Output |
|-------|--------|
| 1 — Idea | M&A screening framework with weighted strategic-fit scoring model |
| 2 — Method | Multi-criteria scoring (technology, market, financial, integration), composite ranking, sensitivity analysis on weight choices |
| 3 — Experiment | Ranked target table with composite scores, fit dimension breakdown chart, valuation vs growth scatter, integration risk matrix |
| 4 — Report | M&A target screening deck with top-10 shortlist, per-target profiles, deal thesis summaries, risk flags, and recommended next steps |

---

### Task 62: Patent & IP Landscape Analysis

**Difficulty:** ★★★ | **Persona:** IP Counsel, CTO, R&D Strategy

**Pre-filled Description:**
> Map the intellectual property landscape in a technology domain by analyzing patent filings, grant rates, citation networks, and assignee concentration. Identify patent thickets, white-space opportunities for new filings, and potential freedom-to-operate risks.

**Suggested Data:**
- `patent_data.csv` — columns: `patent_id, title, abstract_keywords (pipe-delimited), filing_date, grant_date, assignee, assignee_country, ipc_class, citations_received, citations_made, patent_family_size, status (granted/pending/expired), technology_cluster`
- 500–5,000 rows (patents in a domain)

| Phase | Output |
|-------|--------|
| 1 — Idea | IP landscape mapping with thicket identification and white-space opportunity analysis |
| 2 — Method | Assignee concentration analysis, citation network clustering, temporal filing trend analysis, IPC class coverage mapping |
| 3 — Experiment | Patent filing trend chart, assignee leaderboard, citation network visualization, technology cluster heatmap, white-space identification matrix |
| 4 — Report | IP landscape report with competitive patent positioning, freedom-to-operate assessment, white-space recommendations, and R&D filing strategy |

---

### Task 63: Customer Win/Loss & Competitive Deal Analysis

**Difficulty:** ★★☆ | **Persona:** Sales Strategy, Product Marketing, VP Sales

**Pre-filled Description:**
> Analyze win/loss patterns from closed deals to understand competitive dynamics. Identify which competitors appear most often, win-rate by segment and deal size, common loss reasons, feature gap citations, and pricing sensitivity. Produce actionable competitive battle cards.

**Suggested Data:**
- `deal_outcomes.csv` — columns: `deal_id, close_date, segment (enterprise/mid-market/smb), deal_size_usd, outcome (won/lost), primary_competitor, loss_reason (nullable: price/features/integration/relationship/timing/other), feature_gaps_cited (pipe-delimited, nullable), sales_cycle_days, champion_title, decision_maker_title`
- 200–1,000 rows (closed deals over 12-24 months)

| Phase | Output |
|-------|--------|
| 1 — Idea | Competitive deal pattern analysis with win-rate optimization and battle card generation |
| 2 — Method | Win-rate decomposition by competitor × segment × size, loss-reason Pareto analysis, feature gap frequency ranking, pricing elasticity estimation |
| 3 — Experiment | Win-rate heatmap by competitor & segment, loss-reason Pareto chart, feature gap leaderboard, deal size vs win-rate curve, sales cycle comparison |
| 4 — Report | Competitive intelligence report with per-competitor battle cards, pricing guidance, feature prioritization from losses, and sales enablement recommendations |

---

### Task 64: Industry News & Sentiment Pulse

**Difficulty:** ★★☆ | **Persona:** Communications, Strategy Analyst, CMO

**Pre-filled Description:**
> Analyze news and social mention data for a company and its competitors to track share-of-voice, sentiment trends, topic themes, and event-driven spikes. Identify emerging narratives, PR risks, and opportunities to shape the conversation.

**Suggested Data:**
- `news_mentions.csv` — columns: `date, source (news/blog/twitter/linkedin/reddit), company_mentioned, headline_or_text, sentiment_score (-1 to 1), topic_tags (pipe-delimited), reach_estimate, engagement_count, is_crisis_mention (true/false)`
- 1,000–10,000 rows (mentions across companies over 6-12 months)

| Phase | Output |
|-------|--------|
| 1 — Idea | Share-of-voice and sentiment tracking with narrative identification and PR risk alerting |
| 2 — Method | Time series sentiment analysis, share-of-voice calculation, topic clustering, crisis spike detection, competitor sentiment comparison |
| 3 — Experiment | Share-of-voice trend chart, sentiment time series by company, topic word clouds, crisis event timeline, competitor sentiment comparison |
| 4 — Report | Market perception pulse report with share-of-voice dashboard, sentiment analysis, emerging narrative briefs, and communications recommendations |

---

### Task 65: Partner & Ecosystem Health Assessment

**Difficulty:** ★★☆ | **Persona:** VP Partnerships, BD Lead, Channel Strategy

**Pre-filled Description:**
> Evaluate partner ecosystem health: revenue contribution by partner tier, deal registration pipeline, co-sell conversion rates, partner satisfaction, certification levels, and churn risk. Identify top-performing partners for investment and underperformers for remediation or de-prioritization.

**Suggested Data:**
- `partner_ecosystem.csv` — columns: `partner_name, tier (platinum/gold/silver/registered), region, partner_since_date, certified_reps, revenue_influenced_usd, revenue_sourced_usd, deal_registrations_last_12m, co_sell_win_rate_pct, partner_satisfaction_score, training_completion_pct, churn_risk (low/med/high)`
- 50–300 rows (partners)

| Phase | Output |
|-------|--------|
| 1 — Idea | Partner ecosystem health scorecard with tiered performance analysis and investment optimization |
| 2 — Method | Tier-level benchmarking, revenue attribution analysis, partner health composite scoring, churn risk correlation, ROI per partner tier |
| 3 — Experiment | Partner revenue waterfall by tier, co-sell conversion funnel, partner health distribution chart, top/bottom performer tables, churn risk segmentation |
| 4 — Report | Ecosystem health report with partner scorecards, tier migration recommendations, investment reallocation plan, and partner program optimization roadmap |

---

## Recommended Demo Order

### For ITOps Manager audience:

| Order | Task | Why |
|-------|------|-----|
| 1 | **Incident Volume Trends** (Task 1) | Universal, great charts, fast |
| 2 | **Alert Noise Reduction** (Task 2) | Every ops team relates |
| 3 | **Team Performance Benchmarking** (Task 11) | Managers love team comparisons |
| 4 | **MTTR Breakdown** (Task 3) | DORA metrics are hot topic |
| 5 | **Repeat Incident Analysis** (Task 15) | Obvious quick-win identification |

### For IT Architect audience:

| Order | Task | Why |
|-------|------|-----|
| 1 | **Service Dependency & Blast Radius** (Task 8) | Architects love topology views |
| 2 | **Observability Maturity** (Task 16) | Directly actionable gap analysis |
| 3 | **Technical Debt Quantification** (Task 18) | Justifies modernization budget |
| 4 | **DR Readiness & RTO/RPO Gaps** (Task 20) | Board-level risk conversation |
| 5 | **API Gateway & Service Mesh Health** (Task 21) | Deep technical credibility |

### For Senior Management / CIO audience:

| Order | Task | Why |
|-------|------|-----|
| 1 | **DORA Metrics Executive Dashboard** (Task 23) | Industry benchmarks resonate with execs |
| 2 | **Major Incident Business Impact** (Task 25) | Translates IT into $$ — CxOs love this |
| 3 | **Cloud Cost Optimization** (Task 28) | Immediate savings = easy sell |
| 4 | **IT Risk Register** (Task 24) | Board-level risk governance |
| 5 | **Multi-Year Trend Report** (Task 30) | Shows ROI of IT operations investment |

### For HR / CHRO audience:

| Order | Task | Why |
|-------|------|-----|
| 1 | **Employee Attrition Risk** (Task 31) | Every CHRO's #1 concern — visual, actionable |
| 2 | **Compensation Equity & Pay Gap** (Task 34) | Compliance-critical, board asks for this |
| 3 | **Hiring Funnel Efficiency** (Task 32) | Universal pain point, simple data |
| 4 | **DEI Metrics Dashboard** (Task 36) | High visibility, stakeholder interest |
| 5 | **Workforce Planning** (Task 35) | Links HR to business strategy |

### For Finance / Procurement audience:

| Order | Task | Why |
|-------|------|-----|
| 1 | **Software License Utilization** (Task 42) | Immediate savings, everyone has shelfware |
| 2 | **IT Budget Variance** (Task 41) | CFOs relate instantly, clean charts |
| 3 | **Vendor Performance Scorecard** (Task 43) | Actionable procurement leverage |
| 4 | **CapEx vs OpEx Cloud Impact** (Task 44) | Strategic P&L conversation |
| 5 | **PO Cycle Time** (Task 45) | Process improvement, quick wins |

### For PMO / Delivery audience:

| Order | Task | Why |
|-------|------|-----|
| 1 | **Project Portfolio Health** (Task 46) | Every PMO wants a RAG dashboard |
| 2 | **Sprint Metrics & Velocity** (Task 49) | Agile teams relate immediately |
| 3 | **Delivery Predictability** (Task 48) | Estimation accuracy is a universal pain |
| 4 | **Resource Utilization** (Task 47) | Bench time = wasted budget |
| 5 | **Change Request Impact** (Task 50) | Scope creep quantification resonates |

### For Customer Support audience:

| Order | Task | Why |
|-------|------|-----|
| 1 | **CSAT Driver Analysis** (Task 51) | Every support leader asks "what moves CSAT?" |
| 2 | **Channel Mix & Cost-per-Contact** (Task 54) | Direct path to cost savings |
| 3 | **Self-Service Deflection** (Task 52) | Knowledge base ROI, easy data |
| 4 | **Escalation Optimization** (Task 53) | Tier boundary tuning = quick wins |
| 5 | **Churn Correlation** (Task 55) | Links support to revenue — exec appeal |

### For Market Intelligence / Strategy audience:

| Order | Task | Why |
|-------|------|-----|
| 1 | **Competitive Landscape** (Task 56) | CB Insights-style market map, instant visual impact |
| 2 | **Market Sizing — TAM/SAM/SOM** (Task 59) | Every strategy deck needs TAM; familiar framework |
| 3 | **Funding Trend Analysis** (Task 57) | VCs and corp-dev relate immediately |
| 4 | **Win/Loss & Competitive Deal Analysis** (Task 63) | Sales teams love battle cards — high utility |
| 5 | **Peer Benchmarking** (Task 60) | Board-ready financial comparison |
| 6 | **Emerging Tech Hype Curve** (Task 58) | Visual wow factor — Gartner-style output |
| 7 | **M&A Target Screening** (Task 61) | Corp-dev showcase; high strategic value |
| 8 | **News & Sentiment Pulse** (Task 64) | Real-time competitive awareness |
| 9 | **Patent & IP Landscape** (Task 62) | Deep R&D-strategy audience appeal |
| 10 | **Partner Ecosystem Health** (Task 65) | Channel leaders love this scorecard view |

---

## Implementation: Zero Backend Changes Required

### Option A: Use Existing UI As-Is (Fastest)

Just paste the pre-filled description into the SetupPanel text area and upload the generated CSV. The pipeline runs identically — agents adapt to the ITOps domain from the task description alone.

**Steps for a demo:**
1. Run the sample data generation script → get `incidents.csv`
2. Open the app → Create new "Research Paper" task
3. Paste the pre-filled description into the description field
4. Upload `incidents.csv`
5. Click Start → watch Phases 1–4 execute
6. Download the PDF report

### Option B: Add ITOps Vertical to Category Picker (If Vertical Picker Exists)

If `VerticalPicker.tsx` is already implemented from the industry-verticals catalog, add ITOps as a vertical:

```typescript
// In mars-ui/lib/verticalTasks.ts — add to INDUSTRY_VERTICALS array:
{
  id: 'itops',
  name: 'IT Operations',
  icon: 'Server',
  color: 'from-emerald-500 to-teal-600',
  tasks: [
    // --- ITOps Engineer / Analyst (Tasks 1-10) ---
    {
      id: 'itops-incident-trends',
      name: 'Incident Volume Trend Analysis & Forecasting',
      description: 'Analyze IT incident ticket data to identify volume trends, seasonal patterns, and category distributions. Build a time-series forecasting model to predict incident volumes for the next 30 days and identify the top contributing categories driving ticket growth.',
      suggestedData: 'incidents.csv — ticket_id, created_at, resolved_at, category, priority, assignment_group, resolution_time_hours',
      tags: ['incidents', 'forecasting', 'trend-analysis'],
    },
    {
      id: 'itops-alert-noise',
      name: 'Alert Noise Reduction & Correlation Analysis',
      description: 'Analyze monitoring alert data to quantify alert noise (non-actionable alerts), identify correlated alert storms, and recommend suppression and grouping rules.',
      suggestedData: 'alerts.csv — alert_id, timestamp, monitor_name, severity, host, service, status, linked_incident_id',
      tags: ['alerts', 'noise-reduction', 'correlation'],
    },
    {
      id: 'itops-mttr-breakdown',
      name: 'MTTR Breakdown & Optimization',
      description: 'Analyze incident lifecycle data to decompose Mean Time to Resolve (MTTR) into its sub-components: time-to-detect, time-to-acknowledge, time-to-diagnose, and time-to-fix. Identify bottlenecks by team, priority level, and incident category.',
      suggestedData: 'incident_lifecycle.csv — ticket_id, priority, category, assignment_group, detected_at, acknowledged_at, diagnosed_at, fixed_at, resolved_at',
      tags: ['mttr', 'dora-metrics', 'process-optimization'],
    },
    {
      id: 'itops-change-failure',
      name: 'Change Failure Rate & Deployment Risk Scoring',
      description: 'Analyze software deployment and change management records to calculate change failure rates by team, service, change type, and time window. Build a risk scoring model that predicts the likelihood of a change causing an incident.',
      suggestedData: 'changes.csv — change_id, timestamp, service, team, change_type, lines_changed, tests_passed_pct, deploy_window, rollback, caused_incident',
      tags: ['change-management', 'risk-scoring', 'dora-metrics'],
    },
    {
      id: 'itops-capacity-planning',
      name: 'Capacity Planning — Resource Utilization Forecasting',
      description: 'Analyze server resource utilization metrics (CPU, memory, disk, network) across the infrastructure fleet. Identify servers approaching capacity limits, forecast resource exhaustion timelines, and provide capacity planning recommendations.',
      suggestedData: 'server_metrics.csv — timestamp, hostname, cpu_pct, memory_pct, disk_pct, network_mbps, environment, service, instance_type',
      tags: ['capacity-planning', 'forecasting', 'infrastructure'],
    },
    // --- ITOps Manager (Tasks 11-15) ---
    {
      id: 'itops-team-benchmarking',
      name: 'Team Performance Benchmarking & Workload Balancing',
      description: 'Analyze IT support team performance data to benchmark teams on tickets closed per engineer, resolution time, first-contact resolution rate, and CSAT. Identify workload imbalances and recommend rebalancing strategies with projected SLA impact.',
      suggestedData: 'team_performance.csv — month, team, engineer_count, tickets_assigned, tickets_closed, avg_resolution_hours, first_contact_resolution_pct, csat_score, backlog_count',
      tags: ['team-performance', 'benchmarking', 'staffing', 'manager'],
    },
    {
      id: 'itops-backlog-triage',
      name: 'Ticket Backlog Aging & Stale Ticket Triage',
      description: 'Analyze the current open ticket backlog to identify aging patterns, stale tickets, and bottleneck queues. Classify tickets by SLA breach proximity, staleness, and complexity. Recommend a triage action plan: close, escalate, reassign, or merge duplicates.',
      suggestedData: 'open_backlog.csv — ticket_id, created_at, last_updated, priority, category, assignment_group, status, reassignment_count, sla_target_hours, hours_in_queue',
      tags: ['backlog', 'triage', 'sla', 'manager'],
    },
    {
      id: 'itops-vendor-spend',
      name: 'Vendor/Tool Spend vs. Value Analysis',
      description: 'Analyze IT tool and vendor spend alongside usage metrics and operational outcomes. Calculate cost-per-ticket and cost-per-alert for each tool. Identify underutilized tools, overlapping capabilities, and consolidation opportunities with projected savings.',
      suggestedData: 'tool_spend.csv — tool_name, category, annual_cost, license_type, active_users, monthly_api_calls, tickets_processed',
      tags: ['cost-optimization', 'vendor-management', 'tooling', 'manager'],
    },
    {
      id: 'itops-shift-handover',
      name: 'Shift Handover Effectiveness & Coverage Gap Analysis',
      description: 'Analyze incident data across NOC/SOC shift boundaries to identify coverage gaps, handover failures, and shift-transition incident spikes. Measure the handover tax on MTTR and escalation rates.',
      suggestedData: 'shift_incidents.csv — ticket_id, created_at, shift, created_during_handover, handover_notes_present, resolution_time_hours, escalated, dropped',
      tags: ['shift-management', 'coverage', 'noc', 'manager'],
    },
    {
      id: 'itops-repeat-incidents',
      name: 'Repeat Incident & Known Error Analysis',
      description: 'Identify repeat incidents recurring within 30/60/90 day windows. Map to known errors, quantify the operational cost of repeat incidents, and prioritize permanent fix investments by frequency × effort.',
      suggestedData: 'incidents_with_resolution.csv — ticket_id, created_at, category, service, root_cause_id, resolution_time_hours, known_error_id, workaround_applied, permanent_fix_available',
      tags: ['repeat-incidents', 'known-errors', 'problem-management', 'manager'],
    },
    // --- IT Architect (Tasks 16-21) ---
    {
      id: 'itops-observability-maturity',
      name: 'Observability Maturity Assessment',
      description: 'Assess observability maturity by analyzing monitoring coverage, alert quality, log retention, trace sampling, and SLO adoption across services. Score each service on a 1-5 maturity scale across dimensions.',
      suggestedData: 'observability_inventory.csv — service, has_metrics, metric_count, has_logs, log_retention_days, has_traces, trace_sampling_pct, alert_count, slo_defined, slo_count',
      tags: ['observability', 'maturity', 'slo', 'architect'],
    },
    {
      id: 'itops-cloud-migration-readiness',
      name: 'Cloud Migration Readiness & Risk Assessment',
      description: 'Assess application portfolio readiness for cloud migration. Classify using the 7R model (Rehost, Replatform, Refactor, Repurchase, Retire, Retain, Relocate) and estimate complexity, risk, and cost impact.',
      suggestedData: 'app_portfolio.csv — app_name, business_unit, criticality, architecture, database_type, data_classification, compliance_requirements, dependency_count, monthly_compute_cost',
      tags: ['cloud-migration', '7r-model', 'portfolio', 'architect'],
    },
    {
      id: 'itops-tech-debt',
      name: 'Technical Debt Quantification in Infrastructure',
      description: 'Quantify technical debt by analyzing EOL software, unpatched vulnerabilities, expired certificates, legacy protocols, and config drift. Calculate risk-weighted debt scores and estimate remediation effort.',
      suggestedData: 'infra_inventory.csv — hostname, os, os_version, os_eol_date, last_patched, open_cve_count, critical_cve_count, cert_expiry_date, config_drift_items, business_criticality',
      tags: ['tech-debt', 'vulnerability', 'compliance', 'architect'],
    },
    {
      id: 'itops-microservices-comparison',
      name: 'Microservices vs Monolith Performance Comparison',
      description: 'Compare DORA metrics, latency, resource efficiency, and operational overhead across microservice and monolithic applications. Identify anti-patterns like distributed monoliths.',
      suggestedData: 'app_ops_metrics.csv — app_name, architecture, service_count, deploy_frequency_per_month, change_failure_rate_pct, mttr_hours, p99_latency_ms, incidents_per_month',
      tags: ['architecture', 'microservices', 'dora', 'architect'],
    },
    {
      id: 'itops-dr-readiness',
      name: 'Disaster Recovery Readiness & RTO/RPO Gap Analysis',
      description: 'Assess DR readiness by comparing stated RTO/RPO targets vs actual test results. Identify services with no DR plan, untested plans, or test failures. Calculate business-criticality-weighted gaps.',
      suggestedData: 'dr_readiness.csv — service, business_criticality, rto_target_hours, rpo_target_hours, dr_plan_exists, last_dr_test_date, dr_test_result, actual_rto_hours, actual_rpo_hours',
      tags: ['disaster-recovery', 'rto', 'rpo', 'resilience', 'architect'],
    },
    {
      id: 'itops-api-mesh-health',
      name: 'API Gateway & Service Mesh Health Analysis',
      description: 'Analyze API gateway and service mesh telemetry: error rates, latency, retry storms, circuit breaker activations, rate limiting, mTLS status. Identify fragile service-to-service communication paths.',
      suggestedData: 'api_mesh_metrics.csv — timestamp, source_service, destination_service, request_count, error_count, p99_latency_ms, retry_count, circuit_breaker_open_count',
      tags: ['api-gateway', 'service-mesh', 'resilience', 'architect'],
    },
    // --- Senior Management / VP / CIO (Tasks 22-30) ---
    {
      id: 'itops-cost-allocation',
      name: 'IT Cost Allocation & Chargeback Analysis',
      description: 'Build a transparent cost allocation model across business units. Break down costs by category (compute, storage, licensing, labor) and allocate by consumption metrics. Identify cost anomalies and present chargeback recommendations.',
      suggestedData: 'it_costs.csv — month, cost_category, vendor, amount_usd; bu_consumption.csv — month, business_unit, compute_hours, storage_gb, tickets_submitted',
      tags: ['cost-allocation', 'chargeback', 'finops', 'executive'],
    },
    {
      id: 'itops-dora-executive',
      name: 'DORA Metrics Executive Dashboard & Maturity Benchmarking',
      description: 'Calculate and benchmark DORA metrics (Deployment Frequency, Lead Time, Change Failure Rate, MTTR) against industry standards. Track 12-month trends and provide maturity roadmap.',
      suggestedData: 'dora_metrics.csv — month, team, service, deployments, lead_time_hours, change_failures, total_changes, mttr_hours',
      tags: ['dora', 'benchmarking', 'maturity', 'executive'],
    },
    {
      id: 'itops-risk-register',
      name: 'IT Risk Register & Operational Risk Scoring',
      description: 'Build a quantified IT risk register from incident history, vulnerability data, and compliance findings. Score risks by likelihood × impact, identify top-10 risks, and present mitigation cost-benefit analysis.',
      suggestedData: 'risk_inputs.csv — risk_id, risk_category, likelihood_score, impact_score, current_controls, control_effectiveness, incidents_last_12m, estimated_annual_loss_usd, mitigation_cost_usd',
      tags: ['risk-management', 'compliance', 'governance', 'executive'],
    },
    {
      id: 'itops-major-incident-impact',
      name: 'Major Incident Business Impact Analysis',
      description: 'Quantify P1/P2 business impact: revenue loss per minute, SLA penalties, productivity hours lost. Build per-service cost-of-downtime model for executive financial discussions.',
      suggestedData: 'major_incidents.csv — incident_id, service, severity, duration_minutes, customers_affected, estimated_revenue_impact_usd, sla_penalty_usd; service_revenue.csv — service, monthly_revenue_usd',
      tags: ['business-impact', 'revenue', 'downtime-cost', 'executive'],
    },
    {
      id: 'itops-staffing-model',
      name: 'IT Operations Staffing Model & FTE Optimization',
      description: 'Build an evidence-based staffing model linking FTE levels, ticket volumes, SLA performance, and automation adoption. Forecast staffing needs for next 12 months under growth scenarios.',
      suggestedData: 'staffing_ops.csv — month, team, fte_count, tickets_assigned, tickets_closed, sla_compliance_pct, automation_pct, avg_cost_per_fte_usd',
      tags: ['staffing', 'workforce-planning', 'automation-roi', 'executive'],
    },
    {
      id: 'itops-security-response',
      name: 'Security Incident Response Effectiveness',
      description: 'Measure SOC effectiveness: detection-to-containment time, false positive rates, attack vector trends, playbook adherence. Benchmark against industry standards.',
      suggestedData: 'security_incidents.csv — incident_id, detected_at, contained_at, detection_source, severity, attack_vector, false_positive, playbook_followed',
      tags: ['security', 'soc', 'incident-response', 'executive'],
    },
    {
      id: 'itops-cloud-cost',
      name: 'Cloud Cost Optimization & FinOps Analysis',
      description: 'Identify cloud cost optimization opportunities: idle resources, over-provisioned instances, missed RI/savings plan coverage, storage tier mismatches. Quantify savings by category.',
      suggestedData: 'cloud_costs.csv — month, cloud_provider, account, team, service_category, on_demand_spend_usd, savings_plan_coverage_pct, avg_utilization_pct, idle_resource_cost_usd',
      tags: ['cloud-cost', 'finops', 'optimization', 'executive'],
    },
    {
      id: 'itops-service-catalog-roi',
      name: 'IT Service Catalog ROI & Adoption Analysis',
      description: 'Measure catalog item adoption, cost-per-request, self-service rates, and user satisfaction. Identify automation candidates and catalog improvement opportunities.',
      suggestedData: 'service_catalog.csv — catalog_item, category, requests_last_12m, self_service_pct, avg_fulfillment_days, cost_per_request_usd, user_satisfaction_score, automation_level',
      tags: ['service-catalog', 'self-service', 'adoption', 'executive'],
    },
    {
      id: 'itops-multiyear-trend',
      name: 'Multi-Year IT Operational Trend Report',
      description: 'Produce a 3-year IT ops trend report: incident volumes, SLA compliance, MTTR improvement, automation adoption, cost per ticket, staffing efficiency, and CSAT. Correlate improvements with key initiatives.',
      suggestedData: 'annual_ops_summary.csv — quarter, total_incidents, avg_mttr_hours, sla_compliance_pct, automation_rate_pct, cost_per_ticket_usd, fte_count, csat_score; key_initiatives.csv — initiative, quarter_launched, category, description',
      tags: ['trend-analysis', 'maturity', 'board-report', 'executive'],
    },
    // --- HR / People Operations (Tasks 31-40) ---
    {
      id: 'hr-attrition-risk',
      name: 'Employee Attrition Risk Prediction',
      description: 'Analyze employee data to build an attrition risk prediction model using tenure, compensation, performance ratings, manager changes, promotion history, and engagement scores. Identify top turnover drivers and recommend targeted retention interventions.',
      suggestedData: 'employees.csv — employee_id, department, role_level, tenure_months, salary_band, performance_rating, manager_changes_2yr, engagement_score, voluntary_exit, exit_reason',
      tags: ['attrition', 'retention', 'prediction', 'hr'],
    },
    {
      id: 'hr-hiring-funnel',
      name: 'Hiring Funnel Efficiency & Time-to-Fill Analysis',
      description: 'Analyze recruiting pipeline data to measure funnel conversion rates (application → screen → interview → offer → accept), time-to-fill by role, and source effectiveness. Identify bottlenecks and recommend process improvements.',
      suggestedData: 'hiring_pipeline.csv — requisition_id, department, role_level, source, applied_date, screened_date, interview_date, offer_date, accepted_date, hired, time_to_fill_days, cost_source_usd',
      tags: ['recruiting', 'hiring', 'funnel', 'hr'],
    },
    {
      id: 'hr-engagement-survey',
      name: 'Employee Engagement Survey Deep Dive',
      description: 'Analyze engagement survey results across dimensions (manager effectiveness, growth, compensation, work-life balance, belonging). Identify engagement drivers, detect disengagement hotspots, and recommend targeted action plans.',
      suggestedData: 'engagement_survey.csv — employee_id, department, role_level, tenure_bucket, overall_engagement, manager_effectiveness, growth_opportunities, comp_satisfaction, work_life_balance, belonging',
      tags: ['engagement', 'survey', 'culture', 'hr'],
    },
    {
      id: 'hr-pay-equity',
      name: 'Compensation Equity & Pay Gap Analysis',
      description: 'Analyze compensation data to identify pay equity gaps by gender, ethnicity, and role level. Control for legitimate factors using regression to isolate unexplained gaps. Quantify remediation cost.',
      suggestedData: 'compensation.csv — employee_id, gender, ethnicity, department, role_level, tenure_months, performance_rating, base_salary_usd, total_comp_usd, compa_ratio, market_benchmark_usd',
      tags: ['pay-equity', 'compensation', 'dei', 'hr'],
    },
    {
      id: 'hr-workforce-planning',
      name: 'Workforce Planning & Headcount Forecasting',
      description: 'Build a workforce planning model using headcount data, attrition rates, hiring velocity, and business growth projections. Forecast needs under growth/flat/contraction scenarios and quantify vacancy cost.',
      suggestedData: 'workforce_data.csv — quarter, department, opening_headcount, hires, voluntary_exits, closing_headcount, open_requisitions, revenue_per_employee; business_forecast.csv — quarter, department, projected_revenue_growth_pct',
      tags: ['workforce-planning', 'forecasting', 'headcount', 'hr'],
    },
    {
      id: 'hr-dei-metrics',
      name: 'DEI Metrics Dashboard',
      description: 'Analyze diversity across the employee lifecycle: representation by level, hiring pipeline diversity, promotion rate parity, attrition rate parity, and pay equity by demographic group. Track progress against DEI goals.',
      suggestedData: 'dei_data.csv — employee_id, gender, ethnicity, department, role_level, hired_this_year, promoted_this_year, exited_this_year, performance_rating, salary_band',
      tags: ['dei', 'diversity', 'inclusion', 'hr'],
    },
    {
      id: 'hr-training-roi',
      name: 'Learning & Development ROI Analysis',
      description: 'Measure L&D program ROI: completion rates, skill assessment improvement, correlation with performance and promotion rates, and retention impact. Identify highest-impact programs and recommend budget reallocation.',
      suggestedData: 'training_data.csv — employee_id, program_name, program_category, completed, pre_assessment_score, post_assessment_score, cost_per_participant_usd, promoted_within_12m, exited_within_12m',
      tags: ['training', 'learning', 'roi', 'hr'],
    },
    {
      id: 'hr-absenteeism',
      name: 'Absenteeism Pattern Analysis & Prediction',
      description: 'Identify patterns in unplanned absenteeism: seasonal trends, day-of-week effects, department hotspots, and correlation with engagement scores. Build absence prediction model and recommend interventions.',
      suggestedData: 'absences.csv — employee_id, department, absence_date, absence_type, planned, duration_days; employee_context.csv — employee_id, tenure_months, engagement_score, commute_minutes, remote_pct',
      tags: ['absenteeism', 'wellness', 'prediction', 'hr'],
    },
    {
      id: 'hr-internal-mobility',
      name: 'Internal Mobility & Career Pathing Analysis',
      description: 'Map actual career paths from transfer, promotion, and lateral move data. Identify feeder roles for leadership, career stagnation points, department talent flows, and mobility-retention correlation.',
      suggestedData: 'career_moves.csv — employee_id, move_date, move_type, from_department, to_department, from_role_level, to_role_level, tenure_at_move_months, performance_at_move, still_employed',
      tags: ['career-pathing', 'mobility', 'talent', 'hr'],
    },
    {
      id: 'hr-onboarding',
      name: 'Employee Onboarding Effectiveness & Time-to-Productivity',
      description: 'Measure time-to-productivity for new hires, onboarding satisfaction, early attrition rates, and which onboarding elements predict 12-month success and retention.',
      suggestedData: 'onboarding.csv — employee_id, department, hire_date, onboarding_checklist_completion_pct, onboarding_satisfaction, time_to_first_delivery_days, 90_day_performance_rating, buddy_assigned, exited_within_90d, exited_within_180d',
      tags: ['onboarding', 'time-to-productivity', 'retention', 'hr'],
    },
    // --- Finance & Procurement (Tasks 41-45) ---
    {
      id: 'finance-budget-variance',
      name: 'IT Budget Variance & Forecast Accuracy Analysis',
      description: 'Analyze IT budget planned vs actual spend variance by category across quarters. Identify systematic over/under-budgeting patterns, assess forecast accuracy, and recommend methodology improvements.',
      suggestedData: 'it_budget.csv — quarter, category, planned_usd, actual_usd, variance_usd, variance_pct, department',
      tags: ['budget', 'variance', 'forecasting', 'finance'],
    },
    {
      id: 'finance-license-utilization',
      name: 'Software License Utilization & Optimization',
      description: 'Identify shelfware, license compliance gaps, and right-sizing opportunities. Calculate savings from reclamation, consolidation, and renewal renegotiation.',
      suggestedData: 'licenses.csv — vendor, product, license_type, total_licenses, active_users, utilization_pct, annual_cost_usd, renewal_date, compliance_status',
      tags: ['licensing', 'shelfware', 'cost-optimization', 'finance'],
    },
    {
      id: 'finance-vendor-scorecard',
      name: 'Vendor Performance Scorecard & Contract Risk',
      description: 'Build vendor scorecards from SLA compliance, incidents, support response, pricing, and criticality. Identify single-source risks and renegotiation targets.',
      suggestedData: 'vendor_performance.csv — vendor, category, annual_spend_usd, contract_end, sla_compliance_pct, incidents_caused, single_source, business_criticality, satisfaction_score',
      tags: ['vendor-management', 'risk', 'procurement', 'finance'],
    },
    {
      id: 'finance-capex-opex',
      name: 'CapEx vs OpEx Trend & Cloud Migration Financial Impact',
      description: 'Track the CapEx-to-OpEx shift during cloud migration. Model depreciation runoff, cloud spend trajectory, and TCO break-even for workloads.',
      suggestedData: 'capex_opex.csv — quarter, category, capex_usd, opex_usd, depreciation_usd, cloud_migration_pct; tco_comparison.csv — workload, on_prem_annual_cost, cloud_annual_cost, migration_cost',
      tags: ['capex', 'opex', 'cloud-economics', 'finance'],
    },
    {
      id: 'finance-po-cycle-time',
      name: 'Purchase Order Cycle Time & Procurement Bottleneck Analysis',
      description: 'Measure PO cycle times from request to delivery, identify bottleneck stages, and compare by vendor, category, and approval tier. Recommend workflow optimizations.',
      suggestedData: 'procurement.csv — po_id, requested_date, approved_date, delivered_date, category, vendor, amount_usd, approval_tier, rush, rejected',
      tags: ['procurement', 'cycle-time', 'bottleneck', 'finance'],
    },
    // --- Project Management / PMO (Tasks 46-50) ---
    {
      id: 'pmo-portfolio-health',
      name: 'Project Portfolio Health & Risk Dashboard',
      description: 'Produce a RAG-status portfolio dashboard: schedule variance, budget variance, scope changes, resource utilization, and risk scores. Identify projects trending toward distress.',
      suggestedData: 'projects.csv — project_id, project_name, planned_end_date, forecast_end_date, schedule_variance_days, budget_planned_usd, budget_actual_usd, scope_changes_count, risks_open, status',
      tags: ['portfolio', 'project-health', 'risk', 'pmo'],
    },
    {
      id: 'pmo-resource-allocation',
      name: 'Resource Allocation & Utilization Optimization',
      description: 'Identify over/under-allocated team members, skill-demand mismatches, and bench time. Forecast demand-supply gaps and recommend allocation adjustments.',
      suggestedData: 'resource_allocation.csv — employee_id, skill_primary, month, project_id, planned_hours, actual_hours, utilization_pct, bench; demand_forecast.csv — month, skill, demand_hours, supply_hours',
      tags: ['resource-management', 'utilization', 'skills', 'pmo'],
    },
    {
      id: 'pmo-estimation-accuracy',
      name: 'Delivery Predictability & Estimation Accuracy',
      description: 'Measure on-time/on-budget delivery rates, estimation accuracy by project type and methodology, identify systematic biases, and recommend calibration factors.',
      suggestedData: 'completed_projects.csv — project_id, project_type, methodology, original_estimate_days, actual_days, original_budget_usd, actual_budget_usd, scope_changes, on_time, on_budget',
      tags: ['estimation', 'predictability', 'delivery', 'pmo'],
    },
    {
      id: 'pmo-sprint-metrics',
      name: 'Agile Sprint Metrics & Team Velocity Analysis',
      description: 'Track velocity trends, commitment vs completion rates, carry-over patterns, and bug-to-feature ratios across agile teams. Recommend sprint planning improvements.',
      suggestedData: 'sprint_metrics.csv — team, sprint_id, sprint_start, committed_points, completed_points, carry_over_points, stories_committed, stories_completed, bugs_fixed, unplanned_work_pct',
      tags: ['agile', 'velocity', 'sprint', 'pmo'],
    },
    {
      id: 'pmo-change-request-impact',
      name: 'Change Request Impact on Project Delivery',
      description: 'Quantify how change requests impact schedule and budget by project phase. Calculate cost multipliers for late-stage changes and recommend change budget reserves.',
      suggestedData: 'change_requests.csv — cr_id, project_id, project_phase_at_request, change_type, estimated_effort_days, actual_effort_days, schedule_impact_days, budget_impact_usd, approved',
      tags: ['change-management', 'scope-creep', 'delivery', 'pmo'],
    },
    // --- Customer Support (Tasks 51-55) ---
    {
      id: 'support-csat-drivers',
      name: 'Customer Satisfaction (CSAT) Driver Analysis',
      description: 'Identify strongest drivers of CSAT: resolution time, FCR, channel, agent experience, transfers. Build predictive model and recommend operational changes to improve scores.',
      suggestedData: 'csat_tickets.csv — ticket_id, channel, category, resolution_time_hours, first_contact_resolution, transfers_count, agent_tenure_months, csat_score, customer_segment',
      tags: ['csat', 'customer-experience', 'drivers', 'support'],
    },
    {
      id: 'support-self-service',
      name: 'Self-Service Deflection & Knowledge Base Effectiveness',
      description: 'Measure KB article effectiveness, search success rates, and ticket deflection. Identify content gaps between what customers search for and what exists. Quantify deflection savings.',
      suggestedData: 'kb_analytics.csv — article_id, title, views_last_6m, helpfulness_pct, linked_tickets_avoided; search_queries.csv — query, results_count, clicked_article_id, ticket_created_after',
      tags: ['self-service', 'knowledge-base', 'deflection', 'support'],
    },
    {
      id: 'support-escalation',
      name: 'Ticket Escalation Pattern & Tier Optimization',
      description: 'Analyze L1→L2→L3 escalation rates, identify over-escalated categories, quantify unnecessary escalation costs, and recommend tier boundary adjustments and training investments.',
      suggestedData: 'escalation_data.csv — ticket_id, category, initial_tier, final_tier, escalation_count, escalation_reason, cost_per_tier_usd, could_have_been_resolved_lower',
      tags: ['escalation', 'tier-optimization', 'training', 'support'],
    },
    {
      id: 'support-channel-mix',
      name: 'Channel Mix & Cost-per-Contact Optimization',
      description: 'Calculate cost-per-contact and CSAT by channel (phone/chat/email/self-service/chatbot). Model savings from shifting volume to lower-cost channels while maintaining satisfaction.',
      suggestedData: 'channel_metrics.csv — month, channel, ticket_count, avg_handle_time_minutes, cost_per_contact_usd, csat_score, first_contact_resolution_pct',
      tags: ['channel-mix', 'cost-per-contact', 'optimization', 'support'],
    },
    {
      id: 'support-churn-correlation',
      name: 'Customer Churn Correlation with Support Experience',
      description: 'Analyze how ticket volume, resolution time, CSAT, escalations, and unresolved issues correlate with churn. Build a support-experience risk score for proactive account outreach.',
      suggestedData: 'customer_support_churn.csv — customer_id, segment, arr_usd, tickets_last_12m, avg_csat, escalations, unresolved_tickets, churned, churn_reason',
      tags: ['churn', 'retention', 'customer-success', 'support'],
    },
    // --- Market Intelligence / Strategic Research (Tasks 56-65) ---
    {
      id: 'mi-competitive-landscape',
      name: 'Competitive Landscape & Market Positioning',
      description: 'Build a competitive landscape quadrant from company data: funding, headcount, product breadth, sentiment. Produce a market map with Leaders/Challengers/Niche/Emerging and white-space analysis.',
      suggestedData: 'competitive_landscape.csv — company_name, founding_year, total_funding_usd, last_round_type, employees, yoy_employee_growth_pct, product_categories, customer_count_est, avg_g2_rating, key_differentiator',
      tags: ['competitive-intelligence', 'market-map', 'positioning', 'strategy'],
    },
    {
      id: 'mi-funding-trends',
      name: 'Startup & Venture Funding Trend Analysis',
      description: 'Analyze VC funding patterns: deal flow seasonality, round sizes by stage, investor concentration, mega-round trends, and breakout companies with unusually fast progression.',
      suggestedData: 'funding_rounds.csv — company_name, round_date, round_type, amount_usd, pre_money_valuation_usd, lead_investor, investor_count, sector_tags, hq_country',
      tags: ['venture-capital', 'funding', 'startups', 'strategy'],
    },
    {
      id: 'mi-tech-hype-curve',
      name: 'Emerging Technology Adoption & Hype Curve',
      description: 'Map emerging technologies on a hype curve using job postings, patents, startup funding, enterprise pilots, and analyst mentions. Classify maturity and estimate time-to-mainstream.',
      suggestedData: 'tech_signals.csv — technology, quarter, job_postings_count, patent_filings, startup_funding_usd, enterprise_pilots_announced, analyst_mentions, github_stars_delta',
      tags: ['emerging-tech', 'hype-curve', 'innovation', 'strategy'],
    },
    {
      id: 'mi-market-sizing',
      name: 'Market Sizing — TAM/SAM/SOM Estimation',
      description: 'Estimate TAM, SAM, SOM using bottom-up company data and adoption rates. Compare top-down vs bottom-up and identify highest-growth sub-segments.',
      suggestedData: 'market_data.csv — segment, sub_segment, region, year, company_count_est, avg_spend_per_company_usd, adoption_rate_pct, yoy_growth_pct, our_addressable, our_win_rate_pct',
      tags: ['market-sizing', 'tam', 'sam', 'strategy'],
    },
    {
      id: 'mi-peer-benchmarking',
      name: 'Industry Earnings & Revenue Benchmarking',
      description: 'Benchmark financial performance against peers: revenue growth, margins, R&D intensity, sales efficiency, rule-of-40. Identify over/under-index areas.',
      suggestedData: 'peer_financials.csv — company_name, fiscal_year, quarter, revenue_usd, revenue_yoy_growth_pct, gross_margin_pct, operating_margin_pct, rd_as_pct_revenue, net_retention_pct',
      tags: ['benchmarking', 'financials', 'peer-comparison', 'strategy'],
    },
    {
      id: 'mi-ma-screening',
      name: 'M&A Target Screening & Fit Scoring',
      description: 'Screen M&A targets using strategic fit: technology overlap, customer complementarity, geographic expansion, revenue multiples, and integration risk. Produce ranked shortlist.',
      suggestedData: 'ma_targets.csv — company_name, revenue_usd, revenue_growth_pct, technology_stack, customer_overlap_pct, product_complementarity_score, estimated_revenue_multiple, integration_risk',
      tags: ['m-and-a', 'corporate-dev', 'screening', 'strategy'],
    },
    {
      id: 'mi-patent-landscape',
      name: 'Patent & IP Landscape Analysis',
      description: 'Map IP landscape: patent filings, grant rates, citation networks, assignee concentration. Identify patent thickets, white-space for new filings, and freedom-to-operate risks.',
      suggestedData: 'patent_data.csv — patent_id, title, filing_date, grant_date, assignee, ipc_class, citations_received, patent_family_size, technology_cluster',
      tags: ['patents', 'ip-landscape', 'r-and-d', 'strategy'],
    },
    {
      id: 'mi-win-loss',
      name: 'Customer Win/Loss & Competitive Deal Analysis',
      description: 'Analyze closed-deal win/loss patterns: competitors faced, win-rate by segment and size, loss reasons, feature gaps cited, and pricing sensitivity. Generate competitive battle cards.',
      suggestedData: 'deal_outcomes.csv — deal_id, close_date, segment, deal_size_usd, outcome, primary_competitor, loss_reason, feature_gaps_cited, sales_cycle_days',
      tags: ['win-loss', 'competitive', 'sales-strategy', 'strategy'],
    },
    {
      id: 'mi-news-sentiment',
      name: 'Industry News & Sentiment Pulse',
      description: 'Track share-of-voice, sentiment trends, and emerging narratives for a company and competitors from news and social mentions. Identify PR risks and communication opportunities.',
      suggestedData: 'news_mentions.csv — date, source, company_mentioned, headline_or_text, sentiment_score, topic_tags, reach_estimate, is_crisis_mention',
      tags: ['sentiment', 'share-of-voice', 'pr', 'strategy'],
    },
    {
      id: 'mi-partner-ecosystem',
      name: 'Partner & Ecosystem Health Assessment',
      description: 'Evaluate partner ecosystem: revenue contribution by tier, co-sell conversion, partner satisfaction, certification levels, and churn risk. Identify top performers and remediation targets.',
      suggestedData: 'partner_ecosystem.csv — partner_name, tier, region, revenue_influenced_usd, revenue_sourced_usd, co_sell_win_rate_pct, partner_satisfaction_score, churn_risk',
      tags: ['partnerships', 'ecosystem', 'channel', 'strategy'],
    },
  ],
}
```

### Option C: Prompt Hint Enhancement (Optional, ~10 Lines)

To make agents produce more ops-flavored output, add a domain hint to `data_description` before passing it to the pipeline:

```python
# In the router or a thin wrapper, prepend domain context:
ITOPS_CONTEXT = """
DOMAIN CONTEXT: This is an IT Operations analysis task. 
Frame all findings as operational insights with actionable recommendations.
Use ITOps terminology (MTTR, MTTA, SLA, P1/P2/P3, NOC, runbook, blast radius).
Structure recommendations as: Quick Wins (< 1 week), Medium-Term (1-4 weeks), Strategic (1-3 months).
Include quantified impact estimates where possible (e.g., "projected 23% reduction in P1 MTTR").
"""

# Prepend to data_description:
data_description = ITOPS_CONTEXT + "\n\n" + user_provided_description
```

This is entirely optional — the agents already adapt well from the task description alone.

---

## Quick-Start: Run Your First ITOps Demo in 5 Minutes

```bash
# 1. Generate sample data
python -c "
import pandas as pd, numpy as np
from datetime import datetime, timedelta
np.random.seed(42)
n = 8000
cats = ['Network','Hardware','Software','Access/IAM','Database','Security','Other']
pris = ['P1-Critical','P2-High','P3-Medium','P4-Low']
grps = ['Network Ops','Desktop Support','App Support','DBA Team','Security Ops','Service Desk']
start = datetime(2025, 9, 1)
dates = sorted([start + timedelta(hours=np.random.exponential(1.3)) for _ in range(n)])
df = pd.DataFrame({
    'ticket_id': [f'INC{100000+i}' for i in range(n)],
    'created_at': dates,
    'category': np.random.choice(cats, n, p=[.2,.1,.25,.15,.1,.1,.1]),
    'priority': np.random.choice(pris, n, p=[.05,.15,.5,.3]),
    'assignment_group': np.random.choice(grps, n),
    'resolution_time_hours': np.round(np.random.lognormal(3, 1, n), 1),
})
df['resolved_at'] = df['created_at'] + pd.to_timedelta(df['resolution_time_hours'], unit='h')
df.to_csv('incidents.csv', index=False)
print(f'Generated {len(df)} incidents → incidents.csv')
"

# 2. Start backend + frontend (if not already running)
# 3. Create "Research Paper" task in UI
# 4. Paste description, upload incidents.csv, click Start
# 5. Watch the 4-phase pipeline produce an ITOps analysis report
```
