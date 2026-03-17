// components/metrics/CostBreakdown.tsx

'use client';

import { useState } from 'react';
import { Bot, Cpu, Layers } from 'lucide-react';
import { ModelCost, AgentCost, StepCost } from '@/types/cost';

interface CostBreakdownProps {
  modelBreakdown: ModelCost[];
  agentBreakdown: AgentCost[];
  stepBreakdown: StepCost[];
  totalCost: number;
}

type BreakdownView = 'agent' | 'model' | 'step';

// Color palette for agents/models
const COLORS = [
  { bar: 'bg-blue-500', text: 'text-blue-400', dot: 'bg-blue-400' },
  { bar: 'bg-violet-500', text: 'text-violet-400', dot: 'bg-violet-400' },
  { bar: 'bg-emerald-500', text: 'text-emerald-400', dot: 'bg-emerald-400' },
  { bar: 'bg-amber-500', text: 'text-amber-400', dot: 'bg-amber-400' },
  { bar: 'bg-rose-500', text: 'text-rose-400', dot: 'bg-rose-400' },
  { bar: 'bg-cyan-500', text: 'text-cyan-400', dot: 'bg-cyan-400' },
  { bar: 'bg-pink-500', text: 'text-pink-400', dot: 'bg-pink-400' },
  { bar: 'bg-teal-500', text: 'text-teal-400', dot: 'bg-teal-400' },
];

function formatAgentName(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

export function CostBreakdown({
  modelBreakdown,
  agentBreakdown,
  stepBreakdown,
  totalCost,
}: CostBreakdownProps) {
  const [activeView, setActiveView] = useState<BreakdownView>('agent');

  const views = [
    { id: 'agent' as const, label: 'By Agent', icon: Bot },
    { id: 'model' as const, label: 'By Model', icon: Cpu },
    { id: 'step' as const, label: 'By Step', icon: Layers },
  ];

  const getPercentage = (cost: number) => {
    return totalCost > 0 ? (cost / totalCost) * 100 : 0;
  };

  const sortedAgents = [...agentBreakdown].sort((a, b) => b.cost - a.cost);
  const sortedModels = [...modelBreakdown].sort((a, b) => b.cost - a.cost);
  const sortedSteps = [...stepBreakdown].sort((a, b) => a.step_number - b.step_number);

  return (
    <div className="bg-gray-900/50 rounded-xl border border-gray-700/50 overflow-hidden">
      {/* Tab Navigation */}
      <div className="flex border-b border-gray-700/50">
        {views.map((view) => (
          <button
            key={view.id}
            onClick={() => setActiveView(view.id)}
            className={`flex-1 flex items-center justify-center gap-1.5 px-4 py-2.5 text-xs font-medium transition-colors ${
              activeView === view.id
                ? 'text-white bg-gray-800/60 border-b-2 border-blue-500'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            <view.icon className="w-3.5 h-3.5" />
            <span>{view.label}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-4">
        {/* ── Agent View ── */}
        {activeView === 'agent' && (
          <div className="space-y-2">
            {sortedAgents.length === 0 ? (
              <EmptyState icon={Bot} label="No agent cost data yet" />
            ) : (
              <>
                {/* Stacked bar overview */}
                <div className="flex h-3 rounded-full overflow-hidden mb-4 bg-gray-800/50">
                  {sortedAgents.map((agent, i) => (
                    <div
                      key={agent.agent}
                      className={`${COLORS[i % COLORS.length].bar} transition-all`}
                      style={{ width: `${getPercentage(agent.cost)}%` }}
                      title={`${formatAgentName(agent.agent)}: $${agent.cost.toFixed(4)}`}
                    />
                  ))}
                </div>

                {/* Agent rows */}
                {sortedAgents.map((agent, i) => {
                  const color = COLORS[i % COLORS.length];
                  return (
                    <div key={agent.agent} className="group p-3 rounded-lg bg-gray-800/30 hover:bg-gray-800/50 transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${color.dot}`} />
                          <span className="text-sm font-medium text-white truncate">
                            {formatAgentName(agent.agent)}
                          </span>
                          {agent.model && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-700/80 text-gray-400 font-mono flex-shrink-0">
                              {agent.model}
                            </span>
                          )}
                        </div>
                        <div className="flex items-baseline gap-1.5 flex-shrink-0 ml-2">
                          <span className="text-sm font-semibold text-white tabular-nums">
                            ${agent.cost.toFixed(4)}
                          </span>
                          <span className="text-[10px] text-gray-500 tabular-nums">
                            {getPercentage(agent.cost).toFixed(0)}%
                          </span>
                        </div>
                      </div>

                      {/* Token details */}
                      <div className="flex items-center gap-4 text-[11px] text-gray-500 pl-[18px]">
                        <span>
                          <span className="text-gray-400 tabular-nums">{agent.input_tokens.toLocaleString()}</span> prompt
                        </span>
                        <span>
                          <span className="text-gray-400 tabular-nums">{agent.output_tokens.toLocaleString()}</span> completion
                        </span>
                        <span>
                          <span className="text-gray-400 tabular-nums">{agent.tokens.toLocaleString()}</span> total
                        </span>
                      </div>
                    </div>
                  );
                })}

                {/* Total row */}
                <div className="flex items-center justify-between pt-2 mt-2 border-t border-gray-700/40 px-3">
                  <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Total</span>
                  <span className="text-sm font-bold text-white tabular-nums">${totalCost.toFixed(4)}</span>
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Model View ── */}
        {activeView === 'model' && (
          <div className="space-y-2">
            {sortedModels.length === 0 ? (
              <EmptyState icon={Cpu} label="No model cost data yet" />
            ) : (
              <>
                {sortedModels.map((model, i) => {
                  const color = COLORS[i % COLORS.length];
                  const pct = getPercentage(model.cost);
                  return (
                    <div key={model.model} className="p-3 rounded-lg bg-gray-800/30">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <Cpu className={`w-3.5 h-3.5 ${color.text}`} />
                          <span className="text-sm font-medium text-white font-mono">{model.model}</span>
                        </div>
                        <div className="flex items-baseline gap-1.5">
                          <span className="text-sm font-semibold text-white tabular-nums">${model.cost.toFixed(4)}</span>
                          <span className="text-[10px] text-gray-500 tabular-nums">{pct.toFixed(0)}%</span>
                        </div>
                      </div>
                      <div className="h-1.5 bg-gray-700/50 rounded-full overflow-hidden mb-1.5">
                        <div className={`h-full ${color.bar} rounded-full transition-all`} style={{ width: `${pct}%` }} />
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-gray-500">
                        <span>
                          <span className="text-gray-400 tabular-nums">{model.tokens.toLocaleString()}</span> tokens
                          <span className="mx-1.5 text-gray-600">|</span>
                          <span className="text-gray-400 tabular-nums">{model.input_tokens.toLocaleString()}</span> in
                          <span className="mx-1 text-gray-600">/</span>
                          <span className="text-gray-400 tabular-nums">{model.output_tokens.toLocaleString()}</span> out
                        </span>
                        <span><span className="text-gray-400 tabular-nums">{model.call_count}</span> calls</span>
                      </div>
                    </div>
                  );
                })}
              </>
            )}
          </div>
        )}

        {/* ── Step View ── */}
        {activeView === 'step' && (
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {sortedSteps.length === 0 ? (
              <EmptyState icon={Layers} label="No step cost data yet" />
            ) : (
              sortedSteps.map((step, i) => {
                const color = COLORS[i % COLORS.length];
                return (
                  <div
                    key={step.step_id}
                    className="flex items-center justify-between p-3 rounded-lg bg-gray-800/30"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className={`text-xs font-bold ${color.text} tabular-nums w-6 text-center`}>
                        {step.step_number}
                      </span>
                      <span className="text-sm text-gray-300 truncate">{step.description}</span>
                    </div>
                    <div className="flex items-baseline gap-2 flex-shrink-0 ml-2">
                      <span className="text-xs text-gray-500 tabular-nums">{step.tokens.toLocaleString()} tok</span>
                      <span className="text-sm font-semibold text-white tabular-nums">${step.cost.toFixed(4)}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState({ icon: Icon, label }: { icon: typeof Bot; label: string }) {
  return (
    <div className="text-center py-8 text-gray-500">
      <Icon className="w-6 h-6 mx-auto mb-2 opacity-40" />
      <p className="text-xs">{label}</p>
    </div>
  );
}
