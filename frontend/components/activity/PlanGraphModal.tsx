"use client";

import { useMemo } from "react";

import type { PlanStep } from "@/types";

type PlanGraphModalProps = {
  steps: PlanStep[];
  mermaid?: string;
  onClose: () => void;
};

export function PlanGraphModal({ steps, mermaid, onClose }: PlanGraphModalProps) {
  const levels = useMemo(() => {
    const result: PlanStep[][] = [];
    const placed = new Set<string>();
    while (placed.size < steps.length) {
      const level = steps.filter(
        (step) => !placed.has(step.id) && step.depends_on.every((dependency) => placed.has(dependency)),
      );
      if (level.length === 0) break;
      level.forEach((step) => placed.add(step.id));
      result.push(level);
    }
    return result;
  }, [steps]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-5" role="dialog" aria-modal="true" aria-label="Execution plan graph">
      <div className="flex max-h-[90dvh] w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#deded9] px-5 py-4">
          <div>
            <h2 className="m-0 text-base font-semibold text-[#1e1e1c]">Execution plan graph</h2>
            {/* <p className="m-0 mt-1 text-xs text-[#74746f]">Dependency-aware agent execution DAG</p> */}
          </div>
          <button type="button" onClick={onClose} className="rounded-md px-3 py-1.5 text-sm text-[#5a5a54] hover:bg-[#f0f0ec]">Close</button>
        </div>

        <div className="overflow-auto p-5">
          {steps.length === 0 ? (
            <p className="rounded-lg bg-[#f7f7f5] p-4 text-sm text-[#74746f]">No specialized agents were selected. The response is direct.</p>
          ) : (
            <div className="flex min-w-max items-center gap-5 rounded-lg bg-[#f7f7f5] p-6">
              {levels.map((level, levelIndex) => (
                <div key={`level-${levelIndex}`} className="flex items-center gap-5">
                  <div className="grid gap-4">
                    {level.map((step) => (
                      <div key={step.id} className="w-48 rounded-lg border border-[#c9d8d6] bg-white p-3 shadow-sm">
                        <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#0f766e]">{step.id}</div>
                        <div className="mt-1 text-sm font-semibold text-[#1e1e1c]">{step.agent}</div>
                        <div className="mt-1 text-xs leading-relaxed text-[#74746f]">{step.purpose}</div>
                        {step.depends_on.length > 0 && <div className="mt-2 text-[10px] text-[#5a5a54]">After: {step.depends_on.join(", ")}</div>}
                      </div>
                    ))}
                  </div>
                  {levelIndex < levels.length - 1 && <div className="text-xl text-[#0f766e]" aria-hidden="true">→</div>}
                </div>
              ))}
            </div>
          )}

          {mermaid && (
            <details className="mt-5">
              <summary className="cursor-pointer text-xs font-semibold text-[#5a5a54]">View Mermaid source</summary>
              <pre className="mt-2 overflow-auto rounded-lg bg-[#1e1e1c] p-4 text-xs leading-relaxed text-[#f7f7f5]">{mermaid}</pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
