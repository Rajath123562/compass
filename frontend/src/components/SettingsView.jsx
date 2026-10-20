import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

export default function SettingsView({
  models = [],
  language = 'en',
  onLanguageChange,
}) {
  const SAVED_MODEL_KEY = 'compass_selected_model';
  const SAVED_MODE_KEY = 'compass_selected_mode';
  const SAVED_SAFETY_KEY = 'compass_safety_tier';
  const SAVED_OVERLAY_KEY = 'compass_overlay_enabled';
  const SAVED_CLAUDE_OPTIN_KEY = 'compass_claude_optin';
  const SAVED_CLAUDE_ITER_KEY = 'compass_claude_max_iter';

  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem(SAVED_MODEL_KEY) || '');
  const [defaultMode, setDefaultMode] = useState(() => localStorage.getItem(SAVED_MODE_KEY) || 'assist');
  const [safetyTier, setSafetyTier] = useState(() => localStorage.getItem(SAVED_SAFETY_KEY) || 'balanced');
  const [overlayEnabled, setOverlayEnabled] = useState(() => localStorage.getItem(SAVED_OVERLAY_KEY) !== 'false');
  const [claudeOptIn, setClaudeOptIn] = useState(() => localStorage.getItem(SAVED_CLAUDE_OPTIN_KEY) === 'true');
  const [claudeMaxIter, setClaudeMaxIter] = useState(() => parseInt(localStorage.getItem(SAVED_CLAUDE_ITER_KEY) || '15', 10));
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [claudeStatus, setClaudeStatus] = useState({ is_configured: false, model: 'claude-opus-5-5', toolset: 'computer_toolset_20260801' });
  const [savedAlert, setSavedAlert] = useState(false);
  const [keySavedAlert, setKeySavedAlert] = useState(false);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/ai/claude_status')
      .then(r => r.json())
      .then(data => {
        if (data) setClaudeStatus(data);
      })
      .catch(() => {});
  }, []);

  const isKannada = language === 'kn';

  const t = {
    title: isKannada ? 'ಸಿಸ್ಟಮ್ ಸಂರಚನೆ ಮತ್ತು ಭದ್ರತಾ ನಿಯಮಗಳು' : 'Settings & Safety Guardrails',
    subtitle: isKannada
      ? 'AI ಮಾಡೆಲ್, ಭಾಷೆ, ಸುರಕ್ಷತಾ ಮಿತಿಗಳು ಮತ್ತು ಡೆಸ್ಕ್‌ಟಾಪ್ ಮೇಲ್ಪದರ ಆಯ್ಕೆಗಳನ್ನು ಕಾನ್ಫಿಗರ್ ಮಾಡಿ.'
      : 'Configure AI model routing, interface language, safety boundaries, and HUD overlay preferences.',
    aiSection: isKannada ? 'AI ಮಾಡೆಲ್ ಮತ್ತು ರೂಟಿಂಗ್' : 'AI Model & Inference Routing',
    aiDesc: isKannada ? 'ಸ್ಥಳೀಯ Ollama ಅಥವಾ ಬಾಹ್ಯ API ಮಾಡೆಲ್ ಆಯ್ಕೆಮಾಡಿ.' : 'Choose preferred local model or cloud gateway for planning.',
    claudeSection: isKannada ? 'ಕ್ಲಾಡ್ ಓಪಸ್ 5.5 ಕಂಪ್ಯೂಟರ್ ಬಳಕೆ' : 'Claude Opus 5.5 Computer Use',
    claudeDesc: isKannada ? 'ನೇಟಿವ್ ವಿಂಡೋಸ್ ಕಂಪ್ಯೂಟರ್ ನಿಯಂತ್ರಣಕ್ಕಾಗಿ ಅಧಿಕೃತ ಆಂಥ್ರೋಪಿಕ್ ಪ್ರೊಟೊಕಾಲ್.' : 'Official Anthropic Messages API (claude-opus-5-5, computer_toolset_20260801).',
    langSection: isKannada ? 'ಇಂಟರ್ಫೇಸ್ ಭಾಷೆ (Digital Literacy & Governance)' : 'Interface Language (Digital Literacy & Governance)',
    langDesc: isKannada ? 'ಕನ್ನಡ ಮತ್ತು ಇಂಗ್ಲಿಷ್ ನಡುವೆ ಸುಲಭವಾಗಿ ಬದಲಾಯಿಸಿ.' : 'Switch between English and Kannada for regional administrative accessibility.',
    safetySection: isKannada ? 'ಕಾರ್ಯಾಚರಣಾ ಸುರಕ್ಷತಾ ಮಿತಿ' : 'Execution Safety & Approval Policy',
    safetyDesc: isKannada ? 'ಡೆಸ್ಕ್‌ಟಾಪ್ ಕ್ರಿಯೆಗಳಿಗೆ ಅನುಮೋದನೆ ಅಗತ್ಯತೆಗಳನ್ನು ನಿಗದಿಪಡಿಸಿ.' : 'Define when COMPASS must pause and request human authorization before clicking.',
    overlaySection: isKannada ? 'ವಿಷುವಲ್ HUD ಮೇಲ್ಪದರ' : 'Visual HUD Screen Overlay',
    overlayDesc: isKannada ? 'ಗುರಿ ಬಟನ್‌ಗಳು ಮತ್ತು ಬಾಕ್ಸ್‌ಗಳ ಮೇಲೆ ನೀಲಿ ಹೈಲೈಟ್ ತೋರಿಸಿ.' : 'Render PySide6 transparent bounding-box highlights over targeted desktop controls.',
    saveBtn: isKannada ? 'ಆಯ್ಕೆಗಳನ್ನು ಉಳಿಸಿ' : 'Save Preferences',
    savedMsg: isKannada ? 'ಆಯ್ಕೆಗಳನ್ನು ಯಶಸ್ವಿಯಾಗಿ ಉಳಿಸಲಾಗಿದೆ!' : 'Preferences successfully saved!',
    strict: isKannada ? 'ಕಠಿಣ (ಪ್ರತಿಯೊಂದು ಕ್ರಿಯೆಗೂ ಅನುಮೋದನೆ)' : 'Strict (Approve every action)',
    balanced: isKannada ? 'ಸಮತೋಲನ (ಮಧ್ಯಮ ಮತ್ತು ಹೆಚ್ಚಿನ ಅಪಾಯದ ಕ್ರಿಯೆಗಳಿಗೆ ಅನುಮೋದನೆ)' : 'Balanced (Approve Medium & High risk)',
    autonomous: isKannada ? 'ಸ್ವಾಯತ್ತ (ಕೇವಲ ಕ್ರಿಟಿಕಲ್ ಕ್ರಿಯೆಗಳಿಗೆ ಅನುಮೋದನೆ)' : 'Autonomous (Only Critical risk gated)',
  };

  const handleSave = () => {
    localStorage.setItem(SAVED_MODEL_KEY, selectedModel);
    localStorage.setItem(SAVED_MODE_KEY, defaultMode);
    localStorage.setItem(SAVED_SAFETY_KEY, safetyTier);
    localStorage.setItem(SAVED_OVERLAY_KEY, overlayEnabled ? 'true' : 'false');
    localStorage.setItem(SAVED_CLAUDE_OPTIN_KEY, claudeOptIn ? 'true' : 'false');
    localStorage.setItem(SAVED_CLAUDE_ITER_KEY, claudeMaxIter.toString());
    setSavedAlert(true);
    setTimeout(() => setSavedAlert(false), 3000);
  };

  const handleUpdateApiKey = async () => {
    if (!apiKeyInput.trim()) return;
    try {
      const res = await fetch('http://127.0.0.1:8000/api/ai/claude_config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKeyInput.trim() }),
      });
      const data = await res.json();
      if (data.is_configured) {
        setClaudeStatus(prev => ({ ...prev, is_configured: true, status: 'ready' }));
        setKeySavedAlert(true);
        setApiKeyInput('');
        setTimeout(() => setKeySavedAlert(false), 3000);
      }
    } catch (err) {
      console.error('Failed to configure Anthropic API key:', err);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto py-8 px-6 flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white tracking-tight flex items-center gap-2.5">
            <span className="material-symbols-outlined text-[26px] text-blue-400">tune</span>
            {t.title}
          </h1>
          <p className="text-sm text-gray-400 mt-1">{t.subtitle}</p>
        </div>

        {savedAlert && (
          <div className="px-3.5 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
            <span className="material-symbols-outlined text-[16px]">check_circle</span>
            {t.savedMsg}
          </div>
        )}
      </div>

      <div className="space-y-4">
        {/* Language Selection Card (Digital Literacy & Governance) */}
        <div className="p-5 bg-[#121418] border border-white/5 rounded-2xl flex flex-col gap-3">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-blue-400">translate</span>
              {t.langSection}
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">{t.langDesc}</p>
          </div>

          <div className="grid grid-cols-2 gap-3 mt-1">
            <button
              onClick={() => onLanguageChange('en')}
              className={`p-3.5 rounded-xl border text-left flex items-center justify-between transition-all ${
                language === 'en'
                  ? 'bg-blue-600/15 border-blue-500/40 text-white shadow-sm'
                  : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200'
              }`}
            >
              <div>
                <span className="text-xs font-semibold block">English</span>
                <span className="text-[11px] text-gray-500">Standard English UI & Voice prompts</span>
              </div>
              {language === 'en' && <span className="material-symbols-outlined text-blue-400 text-[18px]">check</span>}
            </button>

            <button
              onClick={() => onLanguageChange('kn')}
              className={`p-3.5 rounded-xl border text-left flex items-center justify-between transition-all ${
                language === 'kn'
                  ? 'bg-blue-600/15 border-blue-500/40 text-white shadow-sm'
                  : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-gray-200'
              }`}
            >
              <div>
                <span className="text-xs font-semibold block">ಕನ್ನಡ (Kannada)</span>
                <span className="text-[11px] text-gray-500">ಸ್ಥಳೀಯ ಆಡಳಿತ ಮತ್ತು ಸಾಕ್ಷರತೆ ಬೆಂಬಲ</span>
              </div>
              {language === 'kn' && <span className="material-symbols-outlined text-blue-400 text-[18px]">check</span>}
            </button>
          </div>
        </div>

        {/* AI Model Routing Card */}
        <div className="p-5 bg-[#121418] border border-white/5 rounded-2xl flex flex-col gap-3">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-purple-400">neurology</span>
              {t.aiSection}
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">{t.aiDesc}</p>
          </div>

          <div className="mt-1">
            <label className="text-[11px] font-medium text-gray-400 block mb-1.5 uppercase font-mono">
              Primary Model Target
            </label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full bg-[#16181d] border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500/40 cursor-pointer font-mono"
            >
              {models.length === 0 ? (
                <option value="">local/ollama/qwen2.5:3b-instruct (Default Offline)</option>
              ) : (
                models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.id} ({m.provider || 'local'})
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="mt-2">
            <label className="text-[11px] font-medium text-gray-400 block mb-1.5 uppercase font-mono">
              Default Guidance Mode
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setDefaultMode('assist')}
                className={`p-3 rounded-xl border text-xs font-medium text-left transition-all ${
                  defaultMode === 'assist'
                    ? 'bg-blue-600/15 border-blue-500/40 text-white'
                    : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-white'
                }`}
              >
                <span className="font-semibold block">Assist (Step-by-Step Computer Control)</span>
                <span className="text-[10px] text-gray-500 mt-0.5 block">Plan & execute native actions on Windows</span>
              </button>

              <button
                onClick={() => setDefaultMode('chat')}
                className={`p-3 rounded-xl border text-xs font-medium text-left transition-all ${
                  defaultMode === 'chat'
                    ? 'bg-blue-600/15 border-blue-500/40 text-white'
                    : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-white'
                }`}
              >
                <span className="font-semibold block">Chat (Advisory & Vision Analysis)</span>
                <span className="text-[10px] text-gray-500 mt-0.5 block">Answer questions without taking physical input</span>
              </button>
            </div>
          </div>
        </div>

        {/* Claude Opus 5.5 Computer Use Card */}
        <div className="p-5 bg-[#121418] border border-white/5 rounded-2xl flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px] text-amber-400">desktop_windows</span>
                {t.claudeSection}
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">{t.claudeDesc}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded-lg text-[10px] font-mono font-medium border bg-white/[0.03] text-gray-300 border-white/10">
                computer_toolset_20260801
              </span>
              <span className={`px-2.5 py-1 rounded-lg text-[10px] font-semibold border flex items-center gap-1.5 ${
                claudeStatus.is_configured
                  ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                  : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${claudeStatus.is_configured ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                {claudeStatus.is_configured ? 'Ready & Connected' : 'API Key Required'}
              </span>
            </div>
          </div>

          {/* Cloud Desktop Control Consent Opt-In */}
          <div className="p-3.5 bg-black/40 border border-white/5 rounded-xl flex items-center justify-between">
            <div className="pr-4">
              <span className="text-xs font-semibold text-white block">Enable Cloud Desktop Control</span>
              <span className="text-[11px] text-gray-400 block mt-0.5 leading-snug">
                Transmits real-time desktop screen captures and goal context to Anthropic Claude Opus 5.5 Messages API. All actions remain strictly gated by COMPASS local safety checks.
              </span>
            </div>
            <button
              onClick={() => setClaudeOptIn(!claudeOptIn)}
              className={`w-12 h-6 rounded-full transition-colors relative p-0.5 flex items-center shrink-0 ${
                claudeOptIn ? 'bg-amber-600' : 'bg-white/10'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full bg-white transition-transform ${
                  claudeOptIn ? 'translate-x-6' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* Iteration Budget & API Key */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-medium text-gray-400 block mb-1.5 uppercase font-mono">
                Max Agent Iterations (1-30)
              </label>
              <input
                type="number"
                min="1"
                max="30"
                value={claudeMaxIter}
                onChange={(e) => setClaudeMaxIter(Math.max(1, Math.min(30, parseInt(e.target.value) || 15)))}
                className="w-full bg-[#16181d] border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-amber-500/40 font-mono"
              />
            </div>

            <div>
              <label className="text-[11px] font-medium text-gray-400 block mb-1.5 uppercase font-mono">
                Anthropic API Key {claudeStatus.is_configured && '(Configured)'}
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  placeholder={claudeStatus.is_configured ? '••••••••••••••••••••••••' : 'sk-ant-api03-...'}
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  className="flex-1 bg-[#16181d] border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-amber-500/40 font-mono"
                />
                <button
                  onClick={handleUpdateApiKey}
                  disabled={!apiKeyInput.trim()}
                  className="px-3.5 py-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 disabled:opacity-30 border border-amber-500/30 rounded-xl text-xs font-medium transition-all"
                >
                  Set Key
                </button>
              </div>
            </div>
          </div>

          {keySavedAlert && (
            <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px]">check_circle</span>
              Anthropic API Key securely configured on COMPASS server!
            </div>
          )}
        </div>

        {/* Safety Policy Card */}
        <div className="p-5 bg-[#121418] border border-white/5 rounded-2xl flex flex-col gap-3">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-amber-400">security</span>
              {t.safetySection}
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">{t.safetyDesc}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-1">
            {[
              { id: 'strict', label: 'Strict', desc: t.strict },
              { id: 'balanced', label: 'Balanced (Recommended)', desc: t.balanced },
              { id: 'autonomous', label: 'Autonomous', desc: t.autonomous },
            ].map((tier) => (
              <button
                key={tier.id}
                onClick={() => setSafetyTier(tier.id)}
                className={`p-3.5 rounded-xl border text-left transition-all ${
                  safetyTier === tier.id
                    ? 'bg-amber-500/15 border-amber-500/40 text-white'
                    : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-white'
                }`}
              >
                <span className="text-xs font-semibold block">{tier.label}</span>
                <span className="text-[10px] text-gray-500 mt-1 block leading-snug">{tier.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* HUD Visual Overlay Card */}
        <div className="p-5 bg-[#121418] border border-white/5 rounded-2xl flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] text-emerald-400">visibility</span>
              {t.overlaySection}
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">{t.overlayDesc}</p>
          </div>

          <button
            onClick={() => setOverlayEnabled(!overlayEnabled)}
            className={`w-12 h-6 rounded-full transition-colors relative p-0.5 flex items-center ${
              overlayEnabled ? 'bg-blue-600' : 'bg-white/10'
            }`}
          >
            <div
              className={`w-5 h-5 rounded-full bg-white transition-transform ${
                overlayEnabled ? 'translate-x-6' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Save Button */}
      <div className="pt-2 flex justify-end">
        <button
          onClick={handleSave}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-blue-500/25 transition-all flex items-center gap-2 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
        >
          <span className="material-symbols-outlined text-[16px]">save</span>
          {t.saveBtn}
        </button>
      </div>
    </div>
  );
}
