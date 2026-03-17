# Task Implementation Guide

This guide documents the patterns and best practices learned from implementing the AI Weekly task, to be reused for other tasks (Release Notes, Code Review, etc.).

## Architecture Overview

```
Task Component
  ├── Configuration Form (left side)
  ├── Execution View (split layout)
  │   ├── Left 60%: Task Info + Workspace View (collapsible)
  │   └── Right 40%:
  │       ├── Top 40%: Live Console
  │       └── Bottom 60%: Generated Output Display
  └── WebSocket Connection via Context
```

## Key Implementation Patterns

### 1. WebSocket Connection Setup

**Always connect directly like research mode - no REST API needed:**

```typescript
const taskId = `task-type_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

const taskConfig = {
  mode: 'planning-control',
  model: 'gpt-4o',
  plannerModel: 'gpt-4o',
  researcherModel: 'gpt-4.1-2025-04-14',  // Use better model for research
  engineerModel: 'gpt-4o',
  planReviewerModel: 'o3-mini-2025-01-31',
  defaultModel: 'gpt-4.1-2025-04-14',
  defaultFormatterModel: 'o3-mini-2025-01-31',
  maxRounds: 25,
  maxAttempts: 6,
  maxPlanSteps: 3,
  nPlanReviews: 1,
  planInstructions: 'Specific instructions for the workflow',
  agent: 'planner',
  workDir: '~/cmbagent_workdir'
}

await connect(taskId, enhancedTask, taskConfig)
```

### 2. Output File Specification

**Always specify exact output filename in the prompt:**

```typescript
const outputFilename = `task_result_${param1}_${param2}.md`

const taskPrompt = `
Your task description here...

IMPORTANT: Save the final output as "${outputFilename}" in the working directory.

Additional instructions...
`
```

**Why:** Backend generates many intermediate files. Specifying the filename ensures reliable detection.

### 3. File Detection Strategy

**Three-tier priority system:**

```typescript
// 1. Exact match
let resultFile = files.find(f => f.name === expectedFilename)

// 2. "Final" marker
if (!resultFile) {
  resultFile = files.find(f => f.name.toLowerCase().includes('final'))
}

// 3. Most recent
if (!resultFile) {
  files.sort((a, b) => (b.modified || 0) - (a.modified || 0))
  resultFile = files[0]
}
```

### 4. Fetching Generated Results

**Use existing `/api/files` endpoints:**

```typescript
// List files in work directory
const response = await fetch(
  getApiUrl(`/api/files/list?path=${encodeURIComponent(workDir)}`)
)
const data = await response.json()
const files = data.items || []

// Get file content
const contentResponse = await fetch(
  getApiUrl(`/api/files/content?path=${encodeURIComponent(filePath)}`)
)
const contentData = await contentResponse.json()
const content = contentData.content // markdown text
```

### 5. Result Monitoring

**Monitor both WebSocket results and completion status:**

```typescript
useEffect(() => {
  if (!isRunning) return
  
  // Check if we have results from backend
  if (results && results.work_dir && !result) {
    fetchGeneratedReport(results.work_dir)
  }
  
  // Check for completion in console
  if (consoleOutput.length > 0) {
    const lastLog = consoleOutput[consoleOutput.length - 1]
    if (lastLog.includes('✅ Task execution completed') || 
        lastLog.includes('✅ Workflow completed')) {
      setIsRunning(false)
    }
  }
}, [consoleOutput, results, result, isRunning])
```

### 6. Fallback Mechanism

**Always provide fallback when files can't be found:**

```typescript
const parseReportFromConsole = () => {
  const meaningfulLogs = consoleOutput.filter(line => 
    !line.startsWith('✅') && 
    !line.startsWith('🚀') &&
    line.length > 10
  )
  
  setResult({
    fullReport: meaningfulLogs.join('\n'),
    // ... other fields
  })
  
  disconnect()
}
```

### 7. Split Layout Pattern

**60/40 split for workspace and outputs:**

```tsx
<div className="h-[calc(100vh-200px)] flex gap-6">
  {/* Left 60%: Task Progress & Workspace */}
  <div className="flex-[6] flex flex-col space-y-4 overflow-hidden">
    <TaskWorkspaceView 
      dagData={dagData}
      consoleOutput={consoleOutput}
      isCollapsible={true}
      showProgress={true}
    />
  </div>

  {/* Right 40%: Console & Output */}
  <div className="flex-[4] flex flex-col space-y-4 overflow-hidden">
    {/* Console 40% height */}
    <div className="h-[40%] bg-black/30">
      <ConsoleOutput output={consoleOutput} />
    </div>
    
    {/* Output display 60% height */}
    <div className="flex-1 bg-black/30">
      {/* Parsed results display */}
    </div>
  </div>
</div>
```

### 8. Result Display Structure

**Parse and structure output for better UX:**

```typescript
interface TaskResult {
  fullReport: string           // Complete content for download
  summary?: {                  // Quick overview stats
    dateRange?: string
    itemCount?: number
  }
  highlights?: string[]        // Top items to show
  sections?: Array<{          // Organized sections
    title: string
    items: string[]
  }>
}

// Parse markdown headers and lists
const parseMarkdownContent = (content: string) => {
  const headlines = content.match(/^#{2,3}\s+(.+)$/gm)?.map(h => 
    h.replace(/^#{2,3}\s+/, '')
  )
  
  // Extract sections with list items
  // ...
  
  return structuredData
}
```

### 9. Download Functionality

**Always provide download option:**

```typescript
const downloadReport = () => {
  if (!result?.fullReport) return
  
  const blob = new Blob([result.fullReport], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `task_output_${Date.now()}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
```

## Model Selection Guidelines

| Agent Role | Recommended Model | Purpose |
|------------|------------------|---------|
| Planner | `gpt-4o` | Fast, efficient planning |
| Researcher | `gpt-4.1-2025-04-14` | Deep analysis, information gathering |
| Engineer | `gpt-4o` | Code generation, structured output |
| Plan Reviewer | `o3-mini-2025-01-31` | Critical review, validation |
| Formatter | `o3-mini-2025-01-31` | Final polishing, formatting |

## Common Pitfalls to Avoid

1. ❌ **Don't** use REST API to create tasks - connect WebSocket directly
2. ❌ **Don't** hardcode output filenames - parameterize based on inputs
3. ❌ **Don't** assume only one file - implement priority search
4. ❌ **Don't** forget fallback - parse from console if files fail
5. ❌ **Don't** auto-reconnect after completion - set `shouldReconnect.current = false`
6. ❌ **Don't** disconnect before fetching results - wait for file retrieval

## Task Type Examples

### Release Notes Task
```typescript
const outputFilename = `release_notes_v${version}.md`
const prompt = `Generate release notes for version ${version}...
IMPORTANT: Save as "${outputFilename}"`
```

### Code Review Task
```typescript
const outputFilename = `code_review_${repoName}_${Date.now()}.md`
const prompt = `Review code in ${repoUrl}...
IMPORTANT: Save review as "${outputFilename}"`
```

## Reusable Components

- `TaskWorkspaceView`: Common workspace with DAG/Console toggle
- `ConsoleOutput`: Live console display
- `TopNavigation`: Mode switcher (Research/Tasks)

## Testing Checklist

- [ ] Form validation works
- [ ] WebSocket connects successfully
- [ ] Console shows live updates
- [ ] DAG visualization appears
- [ ] File detection finds correct file
- [ ] Parsed output displays correctly
- [ ] Download button works
- [ ] Fallback triggers if file not found
- [ ] No auto-restart after completion
- [ ] Workspace is collapsible
- [ ] Console and output are scrollable

## Next Steps for New Tasks

1. Copy `AIWeeklyTask.tsx` as template
2. Modify configuration form for task-specific inputs
3. Update prompt template with task instructions
4. Specify output filename pattern
5. Customize result parsing for output format
6. Update result display UI for content type
7. Test with backend workflow

---

**Key Takeaway:** Always follow the research mode pattern - direct WebSocket connection with config object, explicit output filenames in prompts, and smart file detection with fallbacks.
