'use client'

import { useState, useEffect, useMemo } from 'react'
import { ArrowLeft, Calendar, Tags, Globe, Sparkles, Download, Loader2, Code } from 'lucide-react'
import { getApiUrl, config } from '@/lib/config'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import TaskWorkspaceView from './TaskWorkspaceView'
import ConsoleOutput from '@/components/ConsoleOutput'

interface AIWeeklyTaskProps {
  onBack: () => void
}

export default function AIWeeklyTask({ onBack }: AIWeeklyTaskProps) {
  const {
    connected,
    connect,
    disconnect,
    currentRunId,
    consoleOutput,
    addConsoleOutput,
    clearConsole,
    dagData,
    isRunning,
    setIsRunning,
    costSummary,
    costTimeSeries,
    results
  } = useWebSocketContext()

  const [taskId, setTaskId] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)
  const [isReportDownloadReady, setIsReportDownloadReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showView, setShowView] = useState<'config' | 'execution'>('config')

  // Form state
  const [dateFrom, setDateFrom] = useState(() => {
    const date = new Date()
    date.setDate(date.getDate() - 7)
    return date.toISOString().split('T')[0]
  })
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().split('T')[0])
  const [topics, setTopics] = useState<string[]>(['llm', 'cv'])
  const [sources, setSources] = useState<string[]>(['github', 'press-releases', 'company-announcements', 'major-releases'])
  const [style, setStyle] = useState<'concise' | 'detailed' | 'technical'>('concise')

  const availableTopics = [
    { id: 'llm', label: 'Large Language Models' },
    { id: 'cv', label: 'Computer Vision' },
    { id: 'rl', label: 'Reinforcement Learning' },
    { id: 'robotics', label: 'Robotics' },
    { id: 'ml-ops', label: 'MLOps' },
    { id: 'ethics', label: 'AI Ethics' }
  ]

  const availableSources = [
    { id: 'github', label: 'GitHub Releases' },
    { id: 'press-releases', label: 'Press Releases' },
    { id: 'company-announcements', label: 'Company Announcements' },
    { id: 'major-releases', label: 'Major Product/Model Releases' }
  ]

  const toggleTopic = (topicId: string) => {
    setTopics(prev =>
      prev.includes(topicId)
        ? prev.filter(t => t !== topicId)
        : [...prev, topicId]
    )
  }

  const toggleSource = (sourceId: string) => {
    setSources(prev =>
      prev.includes(sourceId)
        ? prev.filter(s => s !== sourceId)
        : [...prev, sourceId]
    )
  }

  const gatedDagData = useMemo(() => {
    if (!dagData?.nodes?.length) return dagData
    if (isReportDownloadReady) return dagData

    const nodes = [...dagData.nodes]
    const lastIndex = nodes.length - 1
    const lastNode = nodes[lastIndex]

    if (lastNode?.status === 'completed') {
      nodes[lastIndex] = {
        ...lastNode,
        status: isRunning ? 'executing' : 'pending'
      }
    }

    return { ...dagData, nodes }
  }, [dagData, isReportDownloadReady, isRunning])

  // Download report function
  const downloadReport = () => {
    if (!result?.fullReport) return

    const blob = new Blob([result.fullReport], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ai-weekly-report-${dateFrom}-to-${dateTo}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleGenerate = async () => {
    if (topics.length === 0 || sources.length === 0) {
      setError('Please select at least one topic and one source')
      return
    }

    if (!dateFrom || !dateTo || dateFrom > dateTo) {
      setError('Please select a valid date range (From must be on or before To)')
      return
    }

    setError(null)
    setResult(null)
    setIsReportDownloadReady(false)
    clearConsole()
    setShowView('execution')

    try {
      const taskId = `ai-weekly_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      setTaskId(taskId)

      const reportFilename = `ai_weekly_report_${dateFrom}_to_${dateTo}.md`

      addConsoleOutput(`✅ Task created: ${taskId}`)
      addConsoleOutput(`📅 Date Range: ${dateFrom} to ${dateTo}`)
      addConsoleOutput(`🏷️  Topics: ${topics.join(', ')}`)
      addConsoleOutput(`📰 Sources: ${sources.join(', ')}`)
      addConsoleOutput(`📁 Expected output file: ${reportFilename}`)
      addConsoleOutput(``)

      setIsRunning(true)
      addConsoleOutput(`🚀 Connecting to workflow engine...`)

      // Create task description with actual instructions
      const enhancedTask = `Generate a Professional AI Weekly Report for organization-wide distribution covering ${dateFrom} to ${dateTo}.

AUDIENCE: Technical and non-technical stakeholders across the organization
TONE: Professional, clear, and actionable
QUALITY: Publication-ready content suitable for executive briefings

Topics to cover: ${topics.join(', ')}
Sources to use: ${sources.join(', ')}
Report style: ${style}

Task Requirements:
1. CRITICAL: Use web search tools to find REAL, RECENT, HIGH-QUALITY content
2. CRITICAL DATE FILTER: ONLY include items with publication/announcement/release dates in this inclusive window: ${dateFrom} to ${dateTo}
3. Date filtering is INCLUSIVE (include both boundary dates ${dateFrom} and ${dateTo})
4. Reject any item outside the date range, even if highly relevant
5. Every item must show an explicit date in YYYY-MM-DD format
6. Add this exact line near the top of the report: "Coverage Window (Inclusive): ${dateFrom} to ${dateTo}"
7. Target at least 10 items combined from press releases, company announcements, and major releases; if fewer are available in-range, include the best available verified items and explicitly note the gap
8. If 'press-releases' is selected, prioritize official newsroom/press pages and include as many in-range items as available
9. If 'company-announcements' is selected, prioritize official company announcement/blog channels and include as many in-range items as available
10. If 'major-releases' is selected, prioritize official release notes/changelogs/product launch pages and include as many in-range items as available
11. Keep source diversity: do not let the report be dominated by a single source type
12. ALL links must be ACTUAL working URLs - NO placeholder links like "example.com"
13. Do NOT use archive-style sources (no arxiv.org papers, no archive.org links, no historical retrospective datasets)
14. Focus ONLY on latest releases and official company release channels in the selected date window
15. Date coverage rule: include items across multiple dates in the range, not a single day only
16. Boundary coverage rule: include at least one item from ${dateFrom} and one from ${dateTo} when available; if unavailable, state this explicitly and include nearest in-range dates
17. Search GitHub for trending repos and major releases in AI
18. Search official press releases and company announcements for AI launches and updates
19. Search for major model/tool/platform releases announced in the date range
20. Use tool priority for announcements: announcements_noauth first (keyless RSS coverage), then rss_company_announcements, then newsapi_search, then gnews_search, then prwire_search
21. If a tool fails, continue with remaining tools; do not stop report generation
22. Each topic should target up to 5 significant items with working source links; if fewer exist in-range, include available verified items and explicitly document the shortfall
23. Write in professional ${style} style with clear, concise explanations
24. Include context and business implications for each item
25. For announcement tools, run a broad pass first (use announcements_noauth with an empty or very short query) to collect in-range items, then run focused queries to refine
26. Always attempt source-specific passes when needed: rss_company_announcements for openai, google, microsoft, meta, anthropic, and nvidia
27. Never output a blank template or "no data" report if in-range items were found by tools; include the verified items you have and clearly label any shortfalls

Required Report Structure (5 items per major section):

## 📋 Executive Summary
Professional 3-4 sentence overview highlighting the week's most significant developments and their strategic implications.

## 🔥 Key Highlights
5 most impactful stories of the week. For each item include:
- **Bold headline** - 3-4 sentence comprehensive summary explaining what happened, why it matters, and what changed
- Business impact: Specific implications for industries, markets, or workflows
- Technical significance: What makes this development noteworthy
- [Authoritative source link](url) with publication name and date

## 📣 Press Releases & Company Announcements
5 items from official press/newsroom/company channels. For each include:
- **[Announcement Title](url)** - Company/organization name
  - **Summary**: 3-4 sentences on what was announced and why it matters
  - **Official source type**: Press release, newsroom post, or company announcement
  - **Impact**: Business and technical implications
  - **Date**: YYYY-MM-DD (must be within coverage window)

## 🚨 Major Releases
5 major launches/releases (models, products, platforms, SDKs, framework versions). For each include:
- **[Release Name](url)** - Organization
  - **Summary**: 3-4 sentences on capabilities and what changed
  - **Release notes/changelog highlights**
  - **Who it affects**: teams, users, or industries
  - **Date**: YYYY-MM-DD (must be within coverage window)

## 🚀 Product Launches & Tools
5 major product releases, tools, or platform updates. For each include:
- **[Product/Tool Name](url)** - Company name and product category
  - **Overview**: 3-4 sentences describing what the product does and what problem it solves
  - **Key features**: Main capabilities and technical specifications
  - **Target users**: Who will benefit and primary use cases
  - **Competitive advantage**: What sets it apart from alternatives
  - **Availability**: Release date, pricing model, [GitHub link](url) if open source

## 💡 Technical Breakthroughs by Category
5 items per topic covering significant technical advances:

### ${topics[0] || 'AI Technology'}
- **[Development/Innovation Name](url)** 
  - **Summary**: 3-4 sentences explaining the technical breakthrough and how it works
  - **Technical details**: Key innovations, algorithms, or methodologies
  - **Performance**: Metrics, benchmarks, or improvements over previous approaches
  - **Impact**: Why this matters for the field and potential applications
  - **Source**: Organization/researchers and date

(Repeat detailed format for each topic: ${topics.join(', ')})

## 🏢 Industry & Business News
5 major industry developments. For each include:
- **[Company/Event Name](url)** 
  - **Summary**: 3-4 sentences covering what happened, who is involved, and strategic context
  - **Financial details**: Funding amounts, valuations, deal terms (if applicable)
  - **Strategic rationale**: Why this move matters and what it enables
  - **Market impact**: How this affects the competitive landscape
  - **Industry implications**: Broader trends or signals for the sector
  - **Source**: [Official source](url) with publication date

## 💭 Trends & Strategic Implications
3-5 key insights for organizational decision-making. For each provide:
- **Trend/Pattern**: Clear statement of the emerging trend
  - **Evidence**: 3-4 sentences analyzing the data points and developments that support this trend
  - **Competitive implications**: How this affects market dynamics and competitive positioning
  - **Strategic recommendations**: Specific actions or areas the organization should monitor/consider
  - **Timeline**: Expected evolution (short-term vs long-term impact)

## 📊 Quick Reference Table
Comprehensive table with all 25+ items for easy scanning:

| Category | Title | Organization/Author | Date | Link |
|----------|-------|---------------------|------|------|
| Research | Paper title | Institution | YYYY-MM-DD | [Link](url) |
| Product | Tool name | Company | YYYY-MM-DD | [Link](url) |
| Industry | Event name | Company | YYYY-MM-DD | [Link](url) |
| Technical | Innovation | Source | YYYY-MM-DD | [Link](url) |

---

*Report compiled: ${new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}*
*Coverage period: ${dateFrom} to ${dateTo}*
*Topics: ${topics.join(', ')}*

CRITICAL QUALITY CHECKLIST:
✅ Each item MUST have a 3-4 sentence comprehensive summary (not just headlines)
✅ Include context, implications, and "why it matters" for every entry
✅ NO placeholder links (example.com, placeholder.com, dummy URLs)
✅ Verify all GitHub repos exist (github.com/org/repo format)
✅ Use actual news article URLs from authoritative sources only
✅ Include publication dates for all items (YYYY-MM-DD format)
✅ Professional language suitable for executive distribution
✅ Explain business/technical value - readers should understand significance without clicking links
✅ Add specific details: metrics, names, institutions, funding amounts, performance numbers
✅ If insufficient real sources available, explicitly state: "Limited significant developments found in this category during the reporting period"

WRITING STYLE:
- Each summary should be self-contained and informative
- Use concrete details and specific numbers/metrics where available
- Explain technical concepts clearly for non-technical readers
- Balance depth with readability - aim for executive summary quality
✅ Clear business context and implications for each item
✅ If insufficient real sources available, explicitly state: "Limited significant developments found in this category during the reporting period"

FILE OUTPUT REQUIREMENTS (CRITICAL):
- You MUST save the final report as: "${reportFilename}"
- Use Python's open() function or write_file tool
- Markdown format with proper headers (##, ###) and lists
- Save in current working directory
- Print confirmation: print(f"Report saved to: {os.path.abspath('${reportFilename}')}")

Keep each section concise and actionable. Focus on quality over quantity.`

      // Create config directly like research mode does
      const taskConfig = {
        mode: 'planning-control',
        model: 'gpt-5',
        plannerModel: 'gpt-5',
        researcherModel: 'gpt-5',
        engineerModel: 'gpt-5',
        planReviewerModel: 'gpt-5',
        defaultModel: 'gpt-5',
        defaultFormatterModel: 'gpt-5',
        maxRounds: 18,
        maxAttempts: 6,
        maxPlanSteps: 3,
        nPlanReviews: 1,
        planInstructions: 'Use researcher to gather information from specified sources, then use engineer to analyze and write the report.',
        agent: 'planner',
        workDir: config.workDir
      }

      await connect(taskId, enhancedTask, taskConfig)

    } catch (err: any) {
      setError(err.message)
      addConsoleOutput(`❌ Error: ${err.message}`)
      setIsRunning(false)
    }
  }

  const handleStop = () => {
    disconnect()
    setIsRunning(false)
    addConsoleOutput('🛑 Task execution stopped by user')
  }

  // Monitor workflow completion and fetch results
  useEffect(() => {
    // Check if we have results (workflow may have just completed)
    if (results) {
      console.log('[AIWeeklyTask] Results received:', results)
      if (!isRunning) {
        addConsoleOutput(`📊 Workflow results received`)
      }

      if (results.work_dir) {
        console.log('[AIWeeklyTask] Work directory found:', results.work_dir)
        addConsoleOutput(`📂 Work directory: ${results.work_dir}`)

        if (!result) {
          // We have workflow results with work directory, fetch the generated report
          addConsoleOutput(`🔍 Searching for generated report file...`)
          fetchGeneratedReport(results.work_dir)
        }
      } else {
        console.log('[AIWeeklyTask] No work_dir in results:', Object.keys(results))
        addConsoleOutput(`⚠️ No work_dir found in results`)
      }
    }

    // Monitor for completion in console
    if (connected && currentRunId && consoleOutput.length > 0 && isRunning) {
      const lastLog = consoleOutput[consoleOutput.length - 1]

      // Check for completion indicators
      if (lastLog.includes('✅ Task execution completed') ||
        lastLog.includes('✅ Workflow completed') ||
        lastLog.includes('🎉 Workflow complete')) {
        console.log('[AIWeeklyTask] Detected workflow completion in console')
        setTimeout(() => setIsRunning(false), 1000)  // Small delay to ensure results are received
      }
    }
  }, [consoleOutput, connected, currentRunId, isRunning, results, result])

  // Fetch generated report from work directory
  const fetchGeneratedReport = async (workDir: string) => {
    try {
      addConsoleOutput('📄 Fetching generated report...')
      addConsoleOutput(`📂 Looking in directory: ${workDir}`)

      // Request the file list from work directory using the files API
      const response = await fetch(getApiUrl(`/api/files/list?path=${encodeURIComponent(workDir)}`))

      if (!response.ok) {
        addConsoleOutput(`⚠️ Could not fetch file list (HTTP ${response.status})`)
        addConsoleOutput('⚠️ Parsing from console output instead...')
        parseReportFromConsole()
        return
      }

      const data = await response.json()
      const files = data.items || []

      addConsoleOutput(`📁 Found ${files.length} files in work directory`)

      // Log all markdown files for debugging
      const mdFiles = files.filter((f: any) => f.name.endsWith('.md'))
      if (mdFiles.length > 0) {
        addConsoleOutput(`📝 Markdown files found: ${mdFiles.map((f: any) => f.name).join(', ')}`)
      } else {
        addConsoleOutput('⚠️ No markdown files found in directory')
      }

      // Filter markdown report files
      const markdownFiles = files.filter((f: any) =>
        f.name.endsWith('.md') &&
        f.type === 'file' &&
        (f.name.includes('report') || f.name.includes('weekly') || f.name.includes('output') || f.name.includes('result'))
      )

      if (markdownFiles.length === 0) {
        addConsoleOutput('⚠️ No report files found')
        parseReportFromConsole()
        return
      }

      // Prioritize: 1) Exact filename match, 2) Files with 'final', 3) Most recent
      const expectedFilename = `ai_weekly_report_${dateFrom}_to_${dateTo}.md`
      let reportFile = markdownFiles.find((f: any) => f.name === expectedFilename)

      if (!reportFile) {
        // Try to find file with 'final' in name
        reportFile = markdownFiles.find((f: any) => f.name.toLowerCase().includes('final'))
      }

      if (!reportFile) {
        // Sort by modification time (most recent first)
        markdownFiles.sort((a: any, b: any) => (b.modified || 0) - (a.modified || 0))
        reportFile = markdownFiles[0]
      }

      addConsoleOutput(`📋 Found ${markdownFiles.length} report file(s), loading: ${reportFile.name}`)

      if (reportFile) {
        // Fetch the report content
        const contentResponse = await fetch(
          getApiUrl(`/api/files/content?path=${encodeURIComponent(reportFile.path)}`)
        )

        if (contentResponse.ok) {
          const contentData = await contentResponse.json()
          if (contentData.content && contentData.type === 'text') {
            parseAndSetReport(contentData.content)
            addConsoleOutput(`✅ Report loaded: ${reportFile.name}`)
            disconnect() // Now safe to disconnect
            return
          }
        }
      }

      // No report file found or couldn't read it
      addConsoleOutput('⚠️ No report file found, parsing from console...')
      parseReportFromConsole()

    } catch (err: any) {
      console.error('Error fetching report:', err)
      addConsoleOutput(`⚠️ Error loading report: ${err.message}`)
      parseReportFromConsole()
    }
  }

  // Parse markdown content and extract structured data
  const parseAndSetReport = (content: string) => {
    const lines = content.split('\n')
    const headlines: string[] = []
    const sections: any[] = []
    let currentSection: any = null

    lines.forEach(line => {
      // Extract headlines (lines starting with ## or ###)
      if (line.startsWith('## ')) {
        const headline = line.replace('## ', '').trim()
        if (headline && !headline.toLowerCase().includes('weekly report')) {
          headlines.push(headline)

          // Start a new section
          if (currentSection) sections.push(currentSection)
          currentSection = { title: headline, items: [] }
        }
      } else if (line.startsWith('### ')) {
        const headline = line.replace('### ', '').trim()
        if (headline) {
          headlines.push(headline)
        }
      } else if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
        // Extract list items
        const item = line.trim().replace(/^[-*]\s+/, '')
        if (currentSection && item) {
          currentSection.items.push(item)
        }
      }
    })

    if (currentSection) sections.push(currentSection)

    setResult({
      fullReport: content,
      dateRange: `${dateFrom} to ${dateTo}`,
      itemCount: sections.reduce((acc, s) => acc + s.items.length, 0),
      headlines: headlines.slice(0, 5), // Top 5 headlines
      sections: sections.slice(0, 4)     // First 4 sections
    })
    setIsReportDownloadReady(true)
  }

  // Fallback: Parse report data from console output
  const parseReportFromConsole = () => {
    const reportLines = consoleOutput.filter(line =>
      !line.startsWith('✅') &&
      !line.startsWith('🚀') &&
      !line.startsWith('📊') &&
      !line.startsWith('📁') &&
      line.length > 10
    )

    setResult({
      fullReport: reportLines.join('\n'),
      dateRange: `${dateFrom} to ${dateTo}`,
      itemCount: reportLines.length,
      headlines: ['Report generated successfully'],
      sections: [{
        title: 'Generated Output',
        items: reportLines.slice(0, 10)
      }]
    })
    setIsReportDownloadReady(false)

    addConsoleOutput('✅ Report preview created from execution logs')
    disconnect()
  }

  const pollForResults = async (id: string) => {
    try {
      const response = await fetch(getApiUrl(`/api/tasks/status/${id}`))
      const data = await response.json()

      if (data.status === 'completed' && data.result) {
        setResult(data.result)
        // Keep final step gated until report is confirmed via file-based fetch flow.
        setIsReportDownloadReady(false)
        setIsRunning(false)
        addConsoleOutput('✅ Report generated successfully!')
      } else if (data.status === 'failed') {
        setError(data.error || 'Generation failed')
        setIsRunning(false)
      }
    } catch (err: any) {
      console.error('Error polling results:', err)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">
      {/* Header */}
      <header className="bg-black/20 backdrop-blur-sm border-b border-white/10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center space-x-4">
            <button
              onClick={onBack}
              className="p-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-bold text-white">AI Weekly Report</h1>
              <p className="text-sm text-gray-300">Generate comprehensive AI technology reports</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8">
        {showView === 'config' ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Panel - Configuration */}
            <div className="space-y-6">
              {/* Date Range */}
              <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6">
                <div className="flex items-center space-x-2 mb-4">
                  <Calendar className="w-5 h-5 text-blue-400" />
                  <h2 className="text-lg font-semibold text-white">Date Range</h2>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">From</label>
                    <input
                      type="date"
                      value={dateFrom}
                      onChange={(e) => setDateFrom(e.target.value)}
                      className="w-full px-4 py-2 bg-black/50 border border-white/10 rounded-lg text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">To</label>
                    <input
                      type="date"
                      value={dateTo}
                      onChange={(e) => setDateTo(e.target.value)}
                      className="w-full px-4 py-2 bg-black/50 border border-white/10 rounded-lg text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* Topics */}
              <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6">
                <div className="flex items-center space-x-2 mb-4">
                  <Tags className="w-5 h-5 text-purple-400" />
                  <h2 className="text-lg font-semibold text-white">Topics</h2>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {availableTopics.map(topic => (
                    <button
                      key={topic.id}
                      onClick={() => toggleTopic(topic.id)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${topics.includes(topic.id)
                        ? 'bg-purple-500 text-white'
                        : 'bg-black/50 text-gray-400 hover:text-white border border-white/10'
                        }`}
                    >
                      {topic.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Sources */}
              <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6">
                <div className="flex items-center space-x-2 mb-4">
                  <Globe className="w-5 h-5 text-green-400" />
                  <h2 className="text-lg font-semibold text-white">Sources</h2>
                </div>
                <div className="space-y-3">
                  {availableSources.map(source => (
                    <label
                      key={source.id}
                      className="flex items-center space-x-3 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={sources.includes(source.id)}
                        onChange={() => toggleSource(source.id)}
                        className="w-4 h-4 rounded border-gray-600 text-green-500 focus:ring-green-500"
                      />
                      <span className="text-white">{source.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Style */}
              <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6">
                <div className="flex items-center space-x-2 mb-4">
                  <Sparkles className="w-5 h-5 text-yellow-400" />
                  <h2 className="text-lg font-semibold text-white">Report Style</h2>
                </div>
                <div className="flex space-x-3">
                  {(['concise', 'detailed', 'technical'] as const).map(s => (
                    <button
                      key={s}
                      onClick={() => setStyle(s)}
                      className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${style === s
                        ? 'bg-yellow-500 text-black'
                        : 'bg-black/50 text-gray-400 hover:text-white border border-white/10'
                        }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              {/* Generate Button */}
              <button
                onClick={handleGenerate}
                disabled={isRunning}
                className="w-full px-6 py-4 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 disabled:from-gray-500 disabled:to-gray-600 text-white font-semibold rounded-lg transition-all disabled:cursor-not-allowed flex items-center justify-center space-x-2"
              >
                {isRunning ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Generating Report...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    <span>Generate Report</span>
                  </>
                )}
              </button>
            </div>

            {/* Right Panel - Preview */}
            <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-white">What You'll Get</h2>
              </div>

              <div className="space-y-4 text-gray-300">
                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                    <span className="text-blue-400 text-sm font-semibold">1</span>
                  </div>
                  <div>
                    <h3 className="text-white font-medium mb-1">Official Releases</h3>
                    <p className="text-sm text-gray-400">Latest company and product releases in the selected date range</p>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                    <span className="text-green-400 text-sm font-semibold">2</span>
                  </div>
                  <div>
                    <h3 className="text-white font-medium mb-1">GitHub Releases</h3>
                    <p className="text-sm text-gray-400">Major framework and library updates</p>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                    <span className="text-purple-400 text-sm font-semibold">3</span>
                  </div>
                  <div>
                    <h3 className="text-white font-medium mb-1">Tech Blog Posts</h3>
                    <p className="text-sm text-gray-400">Announcements from AI companies</p>
                  </div>
                </div>

                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 rounded-full bg-yellow-500/20 flex items-center justify-center flex-shrink-0 mt-1">
                    <span className="text-yellow-400 text-sm font-semibold">4</span>
                  </div>
                  <div>
                    <h3 className="text-white font-medium mb-1">Impact Analysis</h3>
                    <p className="text-sm text-gray-400">Categorized by significance and topic</p>
                  </div>
                </div>

                <div className="border-t border-white/10 pt-4 mt-4">
                  <p className="text-xs text-gray-500">
                    The report will be generated using the planning & control workflow with real-time progress updates and DAG visualization.
                  </p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Execution View with Creative Layout */
          <div className="h-[calc(100vh-200px)] flex gap-6">
            {/* Left Side - Task Progress & Workspace (60%) */}
            <div className="flex-[6] flex flex-col space-y-4 overflow-hidden">
              {/* Header with Task Info and Stop Button */}
              <div className="bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg p-4 flex-shrink-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <button
                      onClick={() => setShowView('config')}
                      className="p-2 text-gray-400 hover:text-white transition-colors"
                    >
                      <ArrowLeft className="w-5 h-5" />
                    </button>
                    <div>
                      <h2 className="text-lg font-semibold text-white">Generating Report</h2>
                      <p className="text-sm text-gray-400">
                        {dateFrom} to {dateTo} • {topics.join(', ')}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    {connected && (
                      <div className="flex items-center space-x-2 px-3 py-1.5 bg-green-500/20 rounded-lg">
                        <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                        <span className="text-sm text-green-400">Connected</span>
                      </div>
                    )}
                    {isRunning && (
                      <button
                        onClick={handleStop}
                        className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors text-sm"
                      >
                        Stop
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Workspace View - Collapsible */}
              <div className="flex-1 min-h-0">
                <TaskWorkspaceView
                  dagData={gatedDagData}
                  currentRunId={currentRunId ?? undefined}
                  consoleOutput={consoleOutput}
                  costSummary={costSummary}
                  costTimeSeries={costTimeSeries}
                  isCollapsible={true}
                  defaultCollapsed={false}
                  showProgress={true}
                />
              </div>
            </div>

            {/* Right Side - Console & Output (40%) */}
            <div className="flex-[4] flex flex-col space-y-4 overflow-hidden">
              {/* Console Output - Always Visible, Compact */}
              <div className="h-[40%] bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg overflow-hidden flex flex-col">
                <div className="border-b border-white/10 p-3 flex items-center justify-between flex-shrink-0">
                  <h3 className="text-white font-semibold text-sm flex items-center gap-2">
                    <Code className="w-4 h-4 text-blue-400" />
                    Live Console
                  </h3>
                  {consoleOutput.length > 0 && (
                    <span className="text-xs text-gray-400">{consoleOutput.length} logs</span>
                  )}
                </div>
                <div className="flex-1 overflow-auto">
                  <ConsoleOutput output={consoleOutput} isRunning={isRunning} />
                </div>
              </div>

              {/* Generated Report Output */}
              <div className="flex-1 bg-black/30 backdrop-blur-sm border border-white/10 rounded-lg overflow-hidden flex flex-col">
                <div className="border-b border-white/10 p-3 flex items-center justify-between flex-shrink-0">
                  <h3 className="text-white font-semibold text-sm flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-yellow-400" />
                    Generated Report
                  </h3>
                  {result && (
                    <button
                      onClick={downloadReport}
                      className="flex items-center gap-1 px-3 py-1 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded text-xs transition-colors"
                    >
                      <Download className="w-3 h-3" />
                      Download MD
                    </button>
                  )}
                </div>
                <div className="flex-1 overflow-auto p-4">
                  {result ? (
                    <div className="space-y-4">
                      {/* Summary Stats */}
                      {(result.dateRange || result.itemCount) && (
                        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                          <div className="flex items-center justify-between text-sm">
                            {result.dateRange && (
                              <span className="text-gray-400">📅 {result.dateRange}</span>
                            )}
                            {result.itemCount && (
                              <span className="text-gray-400">📊 {result.itemCount} items</span>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Headlines */}
                      {result.headlines && result.headlines.length > 0 && (
                        <div className="space-y-2">
                          <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                            <span className="text-lg">📌</span>
                            Top Headlines
                          </h4>
                          <div className="space-y-1.5">
                            {result.headlines.map((headline: string, i: number) => (
                              <div key={i} className="text-gray-300 text-xs bg-white/5 rounded p-2 border-l-2 border-blue-400">
                                {headline}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Sections Preview */}
                      {result.sections && result.sections.length > 0 && (
                        <div className="space-y-3">
                          <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                            <span className="text-lg">📑</span>
                            Report Sections
                          </h4>
                          {result.sections.map((section: any, i: number) => (
                            <div key={i} className="bg-white/5 rounded-lg p-3 border border-white/10">
                              <h5 className="text-white font-medium text-sm mb-2">{section.title}</h5>
                              <ul className="space-y-1">
                                {section.items.slice(0, 3).map((item: string, j: number) => (
                                  <li key={j} className="text-gray-400 text-xs flex items-start gap-2">
                                    <span className="text-blue-400 mt-0.5">•</span>
                                    <span>{item}</span>
                                  </li>
                                ))}
                                {section.items.length > 3 && (
                                  <li className="text-gray-500 text-xs italic">
                                    + {section.items.length - 3} more items
                                  </li>
                                )}
                              </ul>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Full Report Preview */}
                      {result.fullReport && (
                        <div className="space-y-2">
                          <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                            <span className="text-lg">📄</span>
                            Full Report Preview
                          </h4>
                          <div className="bg-black/50 rounded-lg p-3 border border-white/10 max-h-64 overflow-y-auto">
                            <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
                              {result.fullReport.substring(0, 2000)}
                              {result.fullReport.length > 2000 && '\n\n... (truncated, download for full report)'}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="h-full flex items-center justify-center text-gray-500">
                      <div className="text-center">
                        <Sparkles className="w-12 h-12 mx-auto mb-3 opacity-50 animate-pulse" />
                        <p className="text-sm">Report will appear here once generated</p>
                        <p className="text-xs text-gray-600 mt-1">Processing...</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
