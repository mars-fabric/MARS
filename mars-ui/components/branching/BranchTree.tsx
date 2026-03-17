// components/branching/BranchTree.tsx

'use client';

import { useState } from 'react';
import {
  GitBranch,
  GitCommit,
  ChevronRight,
  ChevronDown,
  Play,
  Eye,
  MoreHorizontal,
} from 'lucide-react';
import { Branch } from '@/types/branching';
import { StatusBadge } from '@/components/common/StatusBadge';

interface BranchTreeProps {
  branches: Branch[];
  currentBranchId?: string;
  onSelectBranch: (branchId: string) => void;
  onViewBranch: (branchId: string) => void;
  onCompareBranches: (branchIdA: string, branchIdB: string) => void;
}

function BranchNode({
  branch,
  level,
  currentBranchId,
  selectedForCompare,
  onSelect,
  onView,
  onToggleCompare,
}: {
  branch: Branch;
  level: number;
  currentBranchId?: string;
  selectedForCompare?: string;
  onSelect: (id: string) => void;
  onView: (id: string) => void;
  onToggleCompare: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = branch.children && branch.children.length > 0;
  const isCurrent = branch.branch_id === currentBranchId;
  const isSelectedForCompare = branch.branch_id === selectedForCompare;

  return (
    <div>
      <div
        className={`
          flex items-center p-2 rounded-lg transition-all cursor-pointer
          ${isCurrent ? 'bg-blue-500/20 border border-blue-500/30' : 'hover:bg-gray-700/50'}
          ${isSelectedForCompare ? 'ring-2 ring-purple-500' : ''}
        `}
        style={{ marginLeft: `${level * 24}px` }}
        onClick={() => onSelect(branch.branch_id)}
      >
        {/* Expand/Collapse */}
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
            className="p-1 hover:bg-gray-600 rounded mr-1"
          >
            {expanded ? (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            )}
          </button>
        ) : (
          <div className="w-6 mr-1" />
        )}

        {/* Branch Icon */}
        {branch.is_main ? (
          <GitCommit className="w-4 h-4 text-blue-400 mr-2" />
        ) : (
          <GitBranch className="w-4 h-4 text-purple-400 mr-2" />
        )}

        {/* Branch Info */}
        <div className="flex-grow min-w-0">
          <div className="flex items-center space-x-2">
            <span className={`text-sm font-medium truncate ${isCurrent ? 'text-blue-400' : 'text-white'}`}>
              {branch.name}
            </span>
            {isCurrent && (
              <span className="px-1.5 py-0.5 text-xs bg-blue-500/30 text-blue-300 rounded">
                current
              </span>
            )}
          </div>
          {branch.hypothesis && (
            <p className="text-xs text-gray-400 truncate mt-0.5">
              {branch.hypothesis}
            </p>
          )}
        </div>

        {/* Status */}
        <StatusBadge status={branch.status} size="sm" showLabel={false} />

        {/* Actions */}
        <div className="flex items-center space-x-1 ml-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onView(branch.branch_id);
            }}
            className="p-1.5 hover:bg-gray-600 rounded transition-colors"
            title="View branch"
          >
            <Eye className="w-4 h-4 text-gray-400" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleCompare(branch.branch_id);
            }}
            className={`p-1.5 rounded transition-colors ${
              isSelectedForCompare ? 'bg-purple-500/30 text-purple-400' : 'hover:bg-gray-600 text-gray-400'
            }`}
            title="Select for comparison"
          >
            <GitBranch className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Children */}
      {hasChildren && expanded && (
        <div>
          {branch.children!.map((child) => (
            <BranchNode
              key={child.branch_id}
              branch={child}
              level={level + 1}
              currentBranchId={currentBranchId}
              selectedForCompare={selectedForCompare}
              onSelect={onSelect}
              onView={onView}
              onToggleCompare={onToggleCompare}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function BranchTree({
  branches,
  currentBranchId,
  onSelectBranch,
  onViewBranch,
  onCompareBranches,
}: BranchTreeProps) {
  const [selectedForCompare, setSelectedForCompare] = useState<string | null>(null);

  const handleToggleCompare = (branchId: string) => {
    if (selectedForCompare === null) {
      setSelectedForCompare(branchId);
    } else if (selectedForCompare === branchId) {
      setSelectedForCompare(null);
    } else {
      // Compare the two branches
      onCompareBranches(selectedForCompare, branchId);
      setSelectedForCompare(null);
    }
  };

  if (branches.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-400">
        <div className="text-center">
          <GitBranch className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No branches yet</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {selectedForCompare && (
        <div className="mb-4 p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
          <p className="text-sm text-purple-300">
            Select another branch to compare
          </p>
          <button
            onClick={() => setSelectedForCompare(null)}
            className="mt-2 text-xs text-purple-400 hover:text-purple-300"
          >
            Cancel
          </button>
        </div>
      )}
      {branches.map((branch) => (
        <BranchNode
          key={branch.branch_id}
          branch={branch}
          level={0}
          currentBranchId={currentBranchId}
          selectedForCompare={selectedForCompare || undefined}
          onSelect={onSelectBranch}
          onView={onViewBranch}
          onToggleCompare={handleToggleCompare}
        />
      ))}
    </div>
  );
}
