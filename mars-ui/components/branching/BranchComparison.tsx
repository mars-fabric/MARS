// components/branching/BranchComparison.tsx

'use client';

import { useState } from 'react';
import {
  X,
  GitBranch,
  Clock,
  DollarSign,
  Layers,
  FileText,
  ArrowRight,
  CheckCircle,
  XCircle,
  Minus,
} from 'lucide-react';
import { BranchComparison, BranchDifference } from '@/types/branching';

interface BranchComparisonProps {
  comparison: BranchComparison;
  onClose: () => void;
  onSwitchToBranch?: (branchId: string) => void;
}

export function BranchComparisonView({
  comparison,
  onClose,
  onSwitchToBranch,
}: BranchComparisonProps) {
  const [activeTab, setActiveTab] = useState<'summary' | 'steps' | 'files'>('summary');

  const { branch_a, branch_b, differences, files_comparison } = comparison;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-4xl max-h-[90vh] overflow-hidden bg-gray-900 rounded-xl border border-gray-700 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div className="flex items-center space-x-4">
            <GitBranch className="w-6 h-6 text-purple-400" />
            <h2 className="text-lg font-semibold text-white">Branch Comparison</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Branch Headers */}
        <div className="grid grid-cols-2 gap-4 px-6 py-4 bg-gray-800/50">
          {/* Branch A */}
          <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-blue-400">{branch_a.name}</span>
              {onSwitchToBranch && (
                <button
                  onClick={() => onSwitchToBranch(branch_a.branch_id)}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  Switch
                </button>
              )}
            </div>
            {branch_a.hypothesis && (
              <p className="text-xs text-gray-400 truncate">{branch_a.hypothesis}</p>
            )}
          </div>

          {/* Branch B */}
          <div className="p-4 bg-purple-500/10 border border-purple-500/30 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-purple-400">{branch_b.name}</span>
              {onSwitchToBranch && (
                <button
                  onClick={() => onSwitchToBranch(branch_b.branch_id)}
                  className="text-xs text-purple-400 hover:text-purple-300"
                >
                  Switch
                </button>
              )}
            </div>
            {branch_b.hypothesis && (
              <p className="text-xs text-gray-400 truncate">{branch_b.hypothesis}</p>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex space-x-2 px-6 py-2 border-b border-gray-700">
          {(['summary', 'steps', 'files'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm rounded-lg transition-colors capitalize ${
                activeTab === tab
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="px-6 py-4 overflow-y-auto max-h-[50vh]">
          {activeTab === 'summary' && (
            <div className="grid grid-cols-2 gap-6">
              {/* Metrics Comparison */}
              {[
                { label: 'Total Steps', icon: Layers, a: branch_a.total_steps, b: branch_b.total_steps },
                { label: 'Completed', icon: CheckCircle, a: branch_a.completed_steps, b: branch_b.completed_steps },
                { label: 'Failed', icon: XCircle, a: branch_a.failed_steps, b: branch_b.failed_steps },
                { label: 'Total Cost', icon: DollarSign, a: `$${branch_a.total_cost.toFixed(4)}`, b: `$${branch_b.total_cost.toFixed(4)}` },
                { label: 'Duration', icon: Clock, a: `${Math.round(branch_a.total_time_seconds)}s`, b: `${Math.round(branch_b.total_time_seconds)}s` },
              ].map((metric) => (
                <div
                  key={metric.label}
                  className="flex items-center justify-between p-4 bg-gray-800/50 rounded-lg"
                >
                  <div className="flex items-center space-x-2">
                    <metric.icon className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-300">{metric.label}</span>
                  </div>
                  <div className="flex items-center space-x-4">
                    <span className="text-sm text-blue-400">{metric.a}</span>
                    <ArrowRight className="w-4 h-4 text-gray-600" />
                    <span className="text-sm text-purple-400">{metric.b}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'steps' && (
            <div className="space-y-2">
              {differences.map((diff, index) => (
                <div
                  key={index}
                  className={`grid grid-cols-2 gap-4 p-3 rounded-lg ${
                    diff.output_differs ? 'bg-yellow-500/10' : 'bg-gray-800/30'
                  }`}
                >
                  {/* Branch A Step */}
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-gray-400">#{diff.step_number}</span>
                    {diff.description_a ? (
                      <>
                        <span className={`w-2 h-2 rounded-full ${
                          diff.status_a === 'completed' ? 'bg-green-400' :
                          diff.status_a === 'failed' ? 'bg-red-400' : 'bg-gray-400'
                        }`} />
                        <span className="text-sm text-gray-300 truncate">
                          {diff.description_a}
                        </span>
                      </>
                    ) : (
                      <span className="text-sm text-gray-500 italic">Not present</span>
                    )}
                  </div>

                  {/* Branch B Step */}
                  <div className="flex items-center space-x-2">
                    {diff.description_b ? (
                      <>
                        <span className={`w-2 h-2 rounded-full ${
                          diff.status_b === 'completed' ? 'bg-green-400' :
                          diff.status_b === 'failed' ? 'bg-red-400' : 'bg-gray-400'
                        }`} />
                        <span className="text-sm text-gray-300 truncate">
                          {diff.description_b}
                        </span>
                      </>
                    ) : (
                      <span className="text-sm text-gray-500 italic">Not present</span>
                    )}
                    {diff.output_differs && (
                      <span className="px-1.5 py-0.5 text-xs bg-yellow-500/30 text-yellow-400 rounded">
                        differs
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'files' && files_comparison && (
            <div className="space-y-2">
              {files_comparison.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 bg-gray-800/30 rounded-lg"
                >
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-300">{file.file_path}</span>
                  </div>
                  <div className="flex items-center space-x-4">
                    {file.in_branch_a ? (
                      <CheckCircle className="w-4 h-4 text-blue-400" />
                    ) : (
                      <Minus className="w-4 h-4 text-gray-600" />
                    )}
                    {file.in_branch_b ? (
                      <CheckCircle className="w-4 h-4 text-purple-400" />
                    ) : (
                      <Minus className="w-4 h-4 text-gray-600" />
                    )}
                    {file.differs && (
                      <span className="px-1.5 py-0.5 text-xs bg-yellow-500/30 text-yellow-400 rounded">
                        modified
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
