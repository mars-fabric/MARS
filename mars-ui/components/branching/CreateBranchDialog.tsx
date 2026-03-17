// components/branching/CreateBranchDialog.tsx

'use client';

import { useState } from 'react';
import { X, GitBranch, Lightbulb, Play, FileText, Info } from 'lucide-react';
import { ResumableNode } from '@/types/branching';

interface CreateBranchDialogProps {
  resumableNodes: ResumableNode[];
  onCreateBranch: (
    nodeId: string,
    name: string,
    hypothesis?: string,
    newInstructions?: string,
    executeImmediately?: boolean
  ) => void;
  onClose: () => void;
}

export function CreateBranchDialog({
  resumableNodes,
  onCreateBranch,
  onClose,
}: CreateBranchDialogProps) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [branchName, setBranchName] = useState('');
  const [hypothesis, setHypothesis] = useState('');
  const [newInstructions, setNewInstructions] = useState('');
  const [executeImmediately, setExecuteImmediately] = useState(true);

  const handleSubmit = () => {
    if (!selectedNodeId || !branchName.trim()) return;
    onCreateBranch(
      selectedNodeId,
      branchName.trim(),
      hypothesis.trim() || undefined,
      newInstructions.trim() || undefined,
      executeImmediately
    );
  };

  const selectedNode = resumableNodes.find(n => n.node_id === selectedNodeId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-2xl bg-gray-900 rounded-xl border border-gray-700 shadow-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div className="flex items-center space-x-3">
            <GitBranch className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-white">Create Branch</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 overflow-y-auto flex-1">
          {/* Info Banner */}
          <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <div className="flex items-start space-x-3">
              <Info className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-200">
                <p className="font-medium mb-1">Branch with New Planning</p>
                <p className="text-blue-300/80">
                  Creating a branch will start a NEW planning phase with your instructions.
                  The planner will be aware of all completed work and available files,
                  but will create a fresh plan based on your new instructions.
                </p>
              </div>
            </div>
          </div>

          {/* Select Resume Point */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-3">
              Select Branch Point
            </label>
            <div className="space-y-2 max-h-40 overflow-y-auto pr-2">
              {resumableNodes.map((node) => (
                <button
                  key={node.node_id}
                  onClick={() => setSelectedNodeId(node.node_id)}
                  className={`w-full text-left p-3 rounded-lg border transition-all ${
                    selectedNodeId === node.node_id
                      ? 'border-purple-500 bg-purple-500/20'
                      : 'border-gray-700 hover:border-gray-600'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-white">
                      {node.node_id} (#{node.order_index})
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      node.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                      node.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>
                      {node.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1 truncate">
                    {node.node_type}{node.agent ? ` - ${node.agent}` : ''}
                  </p>
                </button>
              ))}
            </div>
            {selectedNode && (
              <p className="text-xs text-gray-500 mt-2">
                Branch will include all work up to and including {selectedNode.node_id}
              </p>
            )}
          </div>

          {/* Branch Name */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Branch Name *
            </label>
            <input
              type="text"
              value={branchName}
              onChange={(e) => setBranchName(e.target.value)}
              placeholder="e.g., experiment-higher-lr"
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          {/* New Instructions - THE KEY FIELD */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-blue-400" />
                <span>New Instructions for This Branch</span>
              </div>
            </label>
            <textarea
              value={newInstructions}
              onChange={(e) => setNewInstructions(e.target.value)}
              placeholder="Enter new instructions for this branch. The planner will receive these along with context about completed work.

Example:
- Try using a higher learning rate (0.01 instead of 0.001)
- Use a different model architecture (ResNet instead of VGG)
- Focus on optimizing for recall instead of precision"
              className="w-full h-32 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
            <p className="text-xs text-gray-500 mt-2">
              These instructions will be passed to the planner along with a summary of completed work
            </p>
          </div>

          {/* Hypothesis */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              <div className="flex items-center space-x-2">
                <Lightbulb className="w-4 h-4 text-yellow-400" />
                <span>Hypothesis (Optional)</span>
              </div>
            </label>
            <textarea
              value={hypothesis}
              onChange={(e) => setHypothesis(e.target.value)}
              placeholder="What do you expect this branch to achieve? This helps track experiment results."
              className="w-full h-20 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
            />
          </div>

          {/* Execute Immediately Toggle */}
          <div className="flex items-center justify-between p-4 bg-gray-800/50 rounded-lg border border-gray-700">
            <div className="flex items-center space-x-3">
              <Play className="w-5 h-5 text-green-400" />
              <div>
                <p className="text-sm font-medium text-white">Execute Immediately</p>
                <p className="text-xs text-gray-400">Start branch execution right after creation</p>
              </div>
            </div>
            <button
              onClick={() => setExecuteImmediately(!executeImmediately)}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                executeImmediately ? 'bg-green-500' : 'bg-gray-600'
              }`}
            >
              <span
                className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                  executeImmediately ? 'translate-x-7' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 px-6 py-4 border-t border-gray-700 bg-gray-800/50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!selectedNodeId || !branchName.trim()}
            className={`px-6 py-2 font-medium rounded-lg transition-colors flex items-center space-x-2 ${
              !selectedNodeId || !branchName.trim()
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : executeImmediately
                  ? 'bg-green-500 hover:bg-green-600 text-white'
                  : 'bg-purple-500 hover:bg-purple-600 text-white'
            }`}
          >
            {executeImmediately ? (
              <>
                <Play className="w-4 h-4" />
                <span>Create & Execute</span>
              </>
            ) : (
              <>
                <GitBranch className="w-4 h-4" />
                <span>Create Branch</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
