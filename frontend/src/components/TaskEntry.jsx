import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function TaskEntry({ 
  onStart, 
  onStop, 
  isSubmitting, 
  activeTask, 
  isConnected, 
  models = [], 
  activeWindow = null 
}) {
  const [goal, setGoal] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  
  const SAVED_MODEL_KEY = 'compass_selected_model';
  const SAVED_MODE_KEY = 'compass_selected_mode';

  const [selectedModel, setSelectedModel] = useState(() => {
    return localStorage.getItem(SAVED_MODEL_KEY) || '';
  });

  const [selectedMode, setSelectedMode] = useState(() => {
    return localStorage.getItem(SAVED_MODE_KEY) || 'assist';
  });

  React.useEffect(() => {
    if (selectedModel) {
      localStorage.setItem(SAVED_MODEL_KEY, selectedModel);
    } else if (models.length > 0) {
      const saved = localStorage.getItem(SAVED_MODEL_KEY);
      const exists = models.some(m => m.id === saved);
      if (saved && exists) {
        setSelectedModel(saved);
      } else {
        const best = models.find(m => m.id.includes('qwen2.5:3b'))?.id
          || models.find(m => m.id.includes('coder'))?.id
          || models.find(m => m.provider === 'ollama')?.id
          || models[0].id;
        setSelectedModel(best);
        localStorage.setItem(SAVED_MODEL_KEY, best);
      }
    }
  }, [models, selectedModel]);

  const handleModeChange = (mode) => {
    setSelectedMode(mode);
    localStorage.setItem(SAVED_MODE_KEY, mode);
  };

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!goal.trim() || isSubmitting || !isConnected) return;
    onStart(goal, selectedModel, selectedMode);
    setGoal('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleChipClick = (chipPrompt, chipMode) => {
    setGoal(chipPrompt);
    if (chipMode && chipMode !== selectedMode) {
      handleModeChange(chipMode);
    }
  };

  const formatModelLabel = (model) => {
    const rawId = model.id || '';
    const id = rawId.toLowerCase();
    if (id.includes('claude-opus-5-5') || id.includes('claude-opus')) return '✨ Claude Opus 5.5 · Native Computer Use';
    if (id.includes('k2-horizon') || id.includes('3.7b')) return '🔬 K2-Horizon · 3.7B Local';
    if (id.includes('qwen')) {
      const size = id.match(/(\d+(\.\d+)?b)/)?.[1]?.toUpperCase() || 'Local';
      return `🧠 Qwen · ${size}`;
    }
    if (id.includes('gemma')) {
      const size = id.match(/(\d+(\.\d+)?b)/)?.[1]?.toUpperCase() || 'Local';
      return `💎 Gemma · ${size}`;
    }
    if (id.includes('nemotron')) return '⚡ Nemotron 3.5 Lightning (Free)';
    if (id.includes('gemini-pro')) return '🌐 Gemini Pro (OpenRouter)';
    if (id.includes('claude-3-haiku')) return '🌐 Claude 3 Haiku (OpenRouter)';
    if (id.includes('coder')) return '💻 Qwen Coder · 1.5B';
    if (id.includes('7b') || id.includes('8b')) return '🔬 Heavy Analysis · 7B';
    const cleanId = rawId
      .replace(/^local\/(ollama|lmstudio)\//i, '')
      .replace(/^openrouter\//i, '')
      .replace(/:free$/i, ' (Free)');
    return model.display_name || cleanId;
  };

  const availableModels = React.useMemo(() => {
    const list = [...models];
    if (!list.some(m => m.id === 'claude-opus-5-5')) {
      list.push({
        id: 'claude-opus-5-5',
        provider: 'anthropic',
        display_name: '✨ Claude Opus 5.5 · Native Computer Use',
        capabilities: ['computer_use', 'vision']
      });
    }
    return list;
  }, [models]);

  const isBusy = activeTask && activeTask.state !== 'COMPLETED' && activeTask.state !== 'FAILED' && activeTask.state !== 'STOPPED';

  const suggestionChips = [
    { label: '📄 Summarize Window', prompt: 'Summarize the key information and purpose of the active foreground window.', mode: 'chat' },
    { label: '📊 Extract Table', prompt: 'Extract any data tables visible on screen into clean structured CSV format.', mode: 'assist' },
    { label: '🐞 Explain Screen Error', prompt: 'Explain the error or issue currently visible on screen and suggest a concrete fix.', mode: 'chat' },
    { label: '📋 Action Items', prompt: 'Extract a clean bulleted checklist of actionable next steps from my current view.', mode: 'chat' }
  ];

  return (
    <div className="w-full flex flex-col gap-3">
      <motion.form 
        onSubmit={handleSubmit} 
        layout
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className={`w-full bg-[#14161a]/90 backdrop-blur-2xl border rounded-3xl overflow-hidden flex flex-col transition-all duration-300 shadow-2xl relative z-10
          ${isFocused ? 'border-blue-500/50 shadow-blue-500/10' : 'border-white/10 hover:border-white/20'}`}
      >
        <textarea 
          className="w-full bg-transparent border-none text-white placeholder-gray-400 p-6 resize-none focus:outline-none focus:ring-0 text-base leading-relaxed scrollbar-hide"
          placeholder="Ask anything, or describe what to do on your screen... (Press Enter to send)"
          rows={3}
          value={goal}
          onChange={e => setGoal(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          disabled={!isConnected || isSubmitting || isBusy}
        />
        
        {/* Bottom Control Bar */}
        <motion.div 
          layout
          className="w-full px-4 sm:px-5 pb-4 flex flex-wrap justify-between items-center text-gray-400 gap-2.5 border-t border-white/[0.04] pt-3"
        >
          <div className="flex items-center gap-2">
             {models && models.length > 0 ? (
                <div className="relative">
                  <select 
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    disabled={!isConnected || isSubmitting || isBusy}
                    className="bg-black/50 border border-white/10 hover:border-white/20 text-gray-200 text-xs rounded-xl px-3 py-1.5 focus:outline-none transition-all cursor-pointer font-medium pr-7 appearance-none max-w-[200px] truncate"
                    title="Select AI Model"
                  >
                    {availableModels.map(model => (
                      <option key={model.id} value={model.id} className="bg-[#18191e] text-white">
                        {formatModelLabel(model)}
                      </option>
                    ))}
                  </select>
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400 text-[10px]">▼</span>
                </div>
             ) : (
                <span className="text-xs opacity-50 px-3 py-1.5 bg-black/40 rounded-xl border border-white/5">
                  Connecting to local engine...
                </span>
             )}
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* Mode Toggle */}
            <div className="flex bg-black/50 border border-white/10 rounded-xl p-1 h-8 relative">
              <motion.div
                layout
                className="absolute top-1 bottom-1 rounded-lg bg-white/15"
                initial={false}
                animate={{
                  left: selectedMode === 'chat' ? '4px' : '50%',
                  right: selectedMode !== 'chat' ? '4px' : '50%',
                }}
                transition={{ type: 'spring', stiffness: 450, damping: 35 }}
              />
              <button
                type="button"
                onClick={() => handleModeChange('chat')}
                className={`text-xs px-3 rounded-lg transition-colors duration-200 flex items-center gap-1.5 relative z-10 ${
                  selectedMode === 'chat' ? 'text-white font-medium' : 'text-gray-400 hover:text-white'
                }`}
              >
                <span>💬</span> Chat
              </button>
              <button
                type="button"
                onClick={() => handleModeChange('assist')}
                className={`text-xs px-3 rounded-lg transition-colors duration-200 flex items-center gap-1.5 relative z-10 ${
                  selectedMode !== 'chat' ? 'text-white font-medium' : 'text-gray-400 hover:text-white'
                }`}
              >
                <span>🧭</span> Guide
              </button>
            </div>

            <AnimatePresence mode="wait">
              {isBusy ? (
                <motion.button 
                  key="stop"
                  type="button" 
                  onClick={onStop}
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.8, opacity: 0 }}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  className="px-4 py-1.5 rounded-xl bg-red-500/20 text-red-300 border border-red-500/30 text-xs font-medium hover:bg-red-500/30 transition-all flex items-center gap-1.5"
                >
                  <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
                  Stop
                </motion.button>
              ) : (
                <motion.button 
                  key="start"
                  type="submit" 
                  disabled={!goal.trim() || isSubmitting || !isConnected}
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.8, opacity: 0 }}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  className={`px-5 py-1.5 rounded-xl text-xs font-medium transition-all shadow-md flex items-center gap-1.5 ${
                    !goal.trim() || isSubmitting || !isConnected
                      ? 'bg-white/5 text-gray-500 cursor-not-allowed border border-white/5'
                      : 'bg-white text-black hover:bg-gray-100 border border-white'
                  }`}
                >
                  {isSubmitting ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-1 h-3 w-3 text-black" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Thinking...
                    </>
                  ) : (
                    <>
                      Send <span>↵</span>
                    </>
                  )}
                </motion.button>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </motion.form>

      {/* Suggestion Chips */}
      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="w-full flex items-center gap-2 overflow-x-auto py-1 scrollbar-hide px-1"
      >
        <span className="text-[11px] font-medium text-gray-500 uppercase tracking-wider shrink-0 mr-1">
          Suggestions:
        </span>
        {suggestionChips.map((chip, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleChipClick(chip.prompt, chip.mode)}
            disabled={!isConnected || isSubmitting || isBusy}
            className="text-xs shrink-0 px-3 py-1.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/5 hover:border-white/15 text-gray-300 transition-all active:scale-95 flex items-center gap-1.5"
          >
            {chip.label}
          </button>
        ))}
      </motion.div>
    </div>
  );
}
