export interface ModeConfig {
  id: string
  displayName: string
  description: string
  tags: string[]
  icon: string
  color: string
}

export const MARS_MODES: ModeConfig[] = [
  {
    id: 'one-shot',
    displayName: 'Single-Pass Analysis',
    description: 'Execute a single analytical pass on the input without iterative planning. Suitable for well-defined queries with clear scope.',
    tags: ['Analysis', 'Direct'],
    icon: 'Zap',
    color: 'from-blue-500 to-cyan-500',
  },
  {
    id: 'planning-control',
    displayName: 'Multi-Step Research',
    description: 'Break down complex queries into coordinated steps with planning and control flow. Each stage builds on prior results.',
    tags: ['Planning', 'Multi-step'],
    icon: 'Map',
    color: 'from-purple-500 to-indigo-500',
  },
  {
    id: 'idea-generation',
    displayName: 'Hypothesis Generation',
    description: 'Systematically generate, evaluate, and rank multiple hypotheses. Compare alternatives against defined criteria.',
    tags: ['Hypothesis', 'Evaluation'],
    icon: 'Lightbulb',
    color: 'from-amber-500 to-orange-500',
  },
  {
    id: 'ocr',
    displayName: 'Document Extraction',
    description: 'Extract structured text and data from documents and images via OCR. Convert unstructured content into processable output.',
    tags: ['OCR', 'Extraction'],
    icon: 'FileText',
    color: 'from-teal-500 to-green-500',
  },
  {
    id: 'arxiv',
    displayName: 'Literature Review',
    description: 'Retrieve and analyze academic papers and research publications. Identify key findings, methods, and citations.',
    tags: ['Research', 'Academic'],
    icon: 'BookOpen',
    color: 'from-rose-500 to-pink-500',
  },
  {
    id: 'enhance-input',
    displayName: 'Input Enrichment',
    description: 'Augment raw input with OCR, summarization, and multi-source context before processing. Improves downstream analysis quality.',
    tags: ['Enrichment', 'Pre-processing'],
    icon: 'Layers',
    color: 'from-sky-500 to-blue-500',
  },
  {
    id: 'hitl-interactive',
    displayName: 'Human-in-the-Loop',
    description: 'Guided workflow with approval checkpoints at each decision point. Review and steer agent actions before they execute.',
    tags: ['Approval', 'Guided'],
    icon: 'Users',
    color: 'from-emerald-500 to-teal-500',
  },
  {
    id: 'copilot',
    displayName: 'Copilot Chat',
    description: 'Interactive conversational interface for iterative, open-ended queries. Back-and-forth dialogue with persistent context.',
    tags: ['Conversational', 'Iterative'],
    icon: 'MessageSquare',
    color: 'from-violet-500 to-purple-500',
  },
]

export function getModeConfig(modeId: string): ModeConfig | undefined {
  return MARS_MODES.find(m => m.id === modeId)
}

export function getModeDisplayName(modeId: string): string {
  return getModeConfig(modeId)?.displayName || modeId
}
