"use client";

import { Settings, Code, ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

interface SessionConfigTabProps {
  config: Record<string, any>;
  context: Record<string, any>;
  plan: any | null;
}

function CollapsibleJSON({
  title,
  icon: Icon,
  data,
  defaultOpen,
}: {
  title: string;
  icon: typeof Settings;
  data: any;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen ?? true);

  const isEmpty =
    data === null ||
    data === undefined ||
    (typeof data === "object" && Object.keys(data).length === 0);

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-gray-750 transition-colors"
      >
        {open ? (
          <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
        )}
        <Icon className="w-4 h-4 text-blue-400 flex-shrink-0" />
        <span className="text-sm font-medium text-gray-300">{title}</span>
        {isEmpty && (
          <span className="text-xs text-gray-500 ml-auto">empty</span>
        )}
      </button>

      {open && (
        <div className="border-t border-gray-700">
          {isEmpty ? (
            <p className="px-3 py-3 text-sm text-gray-500">No data</p>
          ) : (
            <pre className="px-3 py-3 text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap break-words max-h-96 overflow-y-auto">
              {JSON.stringify(data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export function SessionConfigTab({
  config,
  context,
  plan,
}: SessionConfigTabProps) {
  return (
    <div className="h-full overflow-y-auto p-4 space-y-3 bg-gray-900">
      <CollapsibleJSON
        title="Session Configuration"
        icon={Settings}
        data={config}
        defaultOpen={true}
      />
      <CollapsibleJSON
        title="Context Variables"
        icon={Code}
        data={context}
        defaultOpen={false}
      />
      {plan && (
        <CollapsibleJSON
          title="Plan Data"
          icon={Code}
          data={plan}
          defaultOpen={false}
        />
      )}
    </div>
  );
}
