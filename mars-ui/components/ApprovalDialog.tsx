import React, { useState } from 'react';

interface ApprovalDialogProps {
  open: boolean;
  approval: {
    id: string;
    message: string;
    options: string[];
    context: any;
    checkpoint_type?: string;
  } | null;
  onResolve: (resolution: string, feedback?: string) => void;
}

export function ApprovalDialog({ open, approval, onResolve }: ApprovalDialogProps) {
  const [selectedOption, setSelectedOption] = useState<string>('');
  const [feedback, setFeedback] = useState<string>('');

  // Initialize selected option when approval changes
  React.useEffect(() => {
    if (approval && approval.options && approval.options.length > 0) {
      setSelectedOption(approval.options[0]);
    }
  }, [approval]);

  if (!open || !approval) {
    return null;
  }

  const handleSubmit = () => {
    onResolve(selectedOption, feedback || undefined);
    setFeedback('');
  };

  const handleCancel = () => {
    onResolve('rejected', 'Cancelled by user');
    setFeedback('');
  };

  const getCheckpointTitle = (type?: string) => {
    switch (type) {
      case 'after_planning':
        return 'Review Plan';
      case 'before_step':
        return 'Step Approval Required';
      case 'on_error':
        return 'Error Recovery';
      case 'manual_pause':
        return 'Manual Pause';
      default:
        return 'Approval Required';
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-blue-600 text-white px-6 py-4">
          <h2 className="text-xl font-semibold">
            {getCheckpointTitle(approval.checkpoint_type)}
          </h2>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* Message */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Message:
            </label>
            <pre className="bg-gray-50 rounded-md p-4 text-sm whitespace-pre-wrap overflow-x-auto border border-gray-200">
              {approval.message}
            </pre>
          </div>

          {/* Options */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Select Action:
            </label>
            <div className="space-y-2">
              {approval.options.map((option) => (
                <label
                  key={option}
                  className="flex items-center p-3 border rounded-md cursor-pointer hover:bg-gray-50 transition-colors"
                >
                  <input
                    type="radio"
                    name="approval-option"
                    value={option}
                    checked={selectedOption === option}
                    onChange={(e) => setSelectedOption(e.target.value)}
                    className="mr-3 h-4 w-4 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm font-medium text-gray-700 capitalize">
                    {option}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Feedback */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Feedback / Instructions (optional):
            </label>
            <textarea
              rows={4}
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Provide guidance, modifications, or instructions for the agent..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            />
          </div>

          {/* Context (collapsible) */}
          {approval.context && Object.keys(approval.context).length > 0 && (
            <details className="mb-4">
              <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-900">
                View Context Details
              </summary>
              <pre className="mt-2 bg-gray-50 rounded-md p-4 text-xs overflow-auto max-h-48 border border-gray-200">
                {JSON.stringify(approval.context, null, 2)}
              </pre>
            </details>
          )}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-4 flex justify-end space-x-3 border-t border-gray-200">
          <button
            onClick={handleCancel}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
          >
            Submit
          </button>
        </div>
      </div>
    </div>
  );
}
