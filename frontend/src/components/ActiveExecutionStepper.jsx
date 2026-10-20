import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function ActiveExecutionStepper({
  activeTask = null,
  onStop = () => {},
  pendingApproval = null,
  onConfirmAction = () => {},
}) {
  const [activeStepIndex, setActiveStepIndex] = useState(2); // Step 3 active by default
  const [isLogExpanded, setIsLogExpanded] = useState(true);

  // Extract steps from activeTask or use the high-fidelity verified steps from the screenshot
  const taskSteps = [
    {
      id: 1,
      title: 'Locate Edit Control',
      status: 'VERIFIED',
      completed: true,
      duration: '42ms',
      detail: 'Found UIA EditControl with HWND target verified',
    },
    {
      id: 2,
      title: 'Foreground Sync',
      status: 'COMPLETE',
      completed: true,
      duration: '18ms',
      detail: 'SetForegroundWindow synchronized with Windows message pump',
    },
    {
      id: 3,
      title: 'Dispatch Keystrokes',
      status: 'IN PROGRESS',
      completed: false,
      active: true,
      duration: '5.02 ms',
      detail: 'Injecting verified keystroke sequence via low-level SendInput',
    },
  ];

  return (
    <div className="glass-card rounded-2xl p-5 flex flex-col justify-between text-white border border-white/10 w-full h-full min-h-[460px] relative overflow-hidden">
      {/* Stepper Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-cyan-400">
            format_list_bulleted
          </span>
          <span className="text-sm font-semibold tracking-wide text-gray-200">
            Active execution stepper
          </span>
        </div>
        <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          State: EXECUTING
        </span>
      </div>

      {/* Steps Progression List */}
      <div className="flex-1 py-4 flex flex-col gap-3 overflow-y-auto pr-1">
        {taskSteps.map((step, idx) => {
          const isSelected = activeStepIndex === idx;

          return (
            <div key={step.id} className="flex flex-col">
              {/* Step Row */}
              <div
                onClick={() => setActiveStepIndex(isSelected ? -1 : idx)}
                className={`flex items-center justify-between p-2.5 rounded-xl cursor-pointer transition-all ${
                  isSelected
                    ? 'bg-white/[0.06] border border-cyan-500/30'
                    : 'hover:bg-white/[0.03] border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  {/* Status Indicator Icon */}
                  {step.completed ? (
                    <div className="w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center text-black font-bold text-[12px] shadow-sm shadow-emerald-500/30">
                      ✓
                    </div>
                  ) : step.active ? (
                    <div className="relative flex items-center justify-center w-5 h-5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                      <span className="w-3.5 h-3.5 rounded-full bg-cyan-500 border-2 border-[#090d14]"></span>
                    </div>
                  ) : (
                    <div className="w-5 h-5 rounded-full bg-white/10 flex items-center justify-center text-gray-400 text-xs">
                      {step.id}
                    </div>
                  )}

                  {/* Step Title and State */}
                  <span className={`text-xs font-medium ${step.completed ? 'text-gray-300' : step.active ? 'text-cyan-300 font-semibold' : 'text-gray-500'}`}>
                    {step.id}. {step.title}
                  </span>
                  <span className={`text-[10px] font-mono ${step.completed ? 'text-emerald-400' : step.active ? 'text-cyan-400' : 'text-gray-500'}`}>
                    - {step.status}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {step.completed && (
                    <span className="text-emerald-400 text-xs">✓</span>
                  )}
                  {step.active && (
                    <span className="text-gray-400 text-[10px] transition-transform duration-200">
                      {isSelected ? '▲' : '▼'}
                    </span>
                  )}
                </div>
              </div>

              {/* Expanded Step Details (Specifically for Active Step) */}
              <AnimatePresence>
                {isSelected && step.active && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="pl-8 pr-2 pt-2 pb-1 flex flex-col gap-3 font-mono text-[11px]"
                  >
                    {/* Real-Time Postcondition Telemetry Pill Bar */}
                    <div className="bg-[#0b101a] border border-cyan-500/20 rounded-lg p-2.5 flex flex-col gap-1.5">
                      <span className="text-[10px] text-gray-400 uppercase tracking-wider">
                        Real-time postcondition telemetry
                      </span>
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="text-emerald-400 font-semibold">VERIFIED</span>
                        <span className="text-gray-600">•</span>
                        <span className="text-cyan-300">5.02 ms</span>
                        <span className="text-gray-600">•</span>
                        <span className="text-purple-300">COMPLETE</span>
                        <span className="text-gray-600">•</span>
                        <span className="text-gray-400">0.02% drift</span>
                      </div>
                    </div>

                    {/* Micro-Graphs Section */}
                    <div className="grid grid-cols-2 gap-2.5">
                      {/* Micro-Graph 1: Latency Waveform */}
                      <div className="bg-[#0b101a] border border-white/5 rounded-lg p-2 flex flex-col justify-between">
                        <span className="text-[9px] text-gray-400 mb-1">Micro-graph (Latency)</span>
                        <div className="h-10 w-full flex items-center">
                          <svg className="w-full h-full" viewBox="0 0 100 30" preserveAspectRatio="none">
                            <path
                              d="M0 20 Q 15 5, 25 18 T 50 12 T 75 22 T 100 10"
                              fill="none"
                              stroke="#06b6d4"
                              strokeWidth="2"
                              strokeLinecap="round"
                            />
                          </svg>
                        </div>
                      </div>

                      {/* Micro-Graph 2: Memory RSS Step Line */}
                      <div className="bg-[#0b101a] border border-white/5 rounded-lg p-2 flex flex-col justify-between">
                        <span className="text-[9px] text-gray-400 mb-1">Micro-graph (Memory RSS)</span>
                        <div className="h-10 w-full flex items-center">
                          <svg className="w-full h-full" viewBox="0 0 100 30" preserveAspectRatio="none">
                            <path
                              d="M0 25 L 30 25 L 35 10 L 80 9 L 100 8"
                              fill="none"
                              stroke="#8b5cf6"
                              strokeWidth="2"
                              strokeLinecap="round"
                            />
                          </svg>
                        </div>
                      </div>
                    </div>

                    {/* AI Reasoning Log Container */}
                    <div className="bg-[#0b101a] border border-white/5 rounded-lg p-2.5 flex flex-col gap-1 text-[10px]">
                      <span className="text-cyan-400 font-semibold uppercase tracking-wider flex items-center gap-1">
                        <span className="material-symbols-outlined text-[12px]">psychology</span>
                        AI reasoning log
                      </span>
                      <p className="text-gray-300 leading-relaxed">
                        Locate Edit Control · Dispatch Keystrokes into active target window. Focus verified via SetForegroundWindow.
                      </p>
                      <p className="text-emerald-400 font-mono">
                        Step 2. Verifier confirmed external WM_GETTEXT string integrity.
                      </p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>

      {/* Stepper Footer Controls */}
      <div className="pt-3 border-t border-white/[0.08] flex items-center justify-between text-xs">
        <span className="text-gray-400 font-mono text-[11px]">
          Target: Notepad.exe
        </span>
        <button
          onClick={onStop}
          className="px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30 font-semibold transition-all flex items-center gap-1"
        >
          <span className="material-symbols-outlined text-[14px]">cancel</span>
          <span>Halt Stepper</span>
        </button>
      </div>
    </div>
  );
}
