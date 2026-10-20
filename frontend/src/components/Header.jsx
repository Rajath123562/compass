import React from 'react';
import { motion } from 'framer-motion';

export default function Header({
  connectionStatus = 'connected',
  latency = 0,
  activeView = 'workspace',
  onViewChange = () => {},
  activeWindow = null,
  language = 'en',
  onLanguageChange = () => {},
  onOpenTelemetry = () => {},
  onToggleMobileSidebar = () => {},
  onOpenSidebar = null,
  isMobileSidebarOpen = false,
  uiMode = 'simple',
  onUiModeChange = () => {},
  onEmergencyAbort = null,
}) {
  const isConnected = connectionStatus === 'connected';
  const isKannada = language === 'kn';
  const handleToggle = onToggleMobileSidebar || onOpenSidebar || (() => {});

  const viewTitles = {
    workspace: isKannada ? 'ಕಾರ್ಯಕ್ಷೇತ್ರ' : 'Agent Workspace',
    workflows: isKannada ? 'ಕಾರ್ಯಪ್ರವಾಹಗಳು (DAG)' : 'Autonomous Workflows',
    history: isKannada ? 'ಕಾರ್ಯ ಇತಿಹಾಸ' : 'Audit Trail & History',
    diagnostics: isKannada ? 'ಡಯಾಗ್ನೋಸ್ಟಿಕ್ಸ್' : 'System Diagnostics',
    settings: isKannada ? 'ಸಂರಚನೆ' : 'Settings & Rules',
  };

  return (
    <header className="w-full h-16 flex items-center justify-between px-4 sm:px-6 bg-[#0e1017]/85 backdrop-blur-xl border-b border-white/[0.06] sticky top-0 z-30 flex-shrink-0 select-none">
      {/* Left: Mobile Sidebar Hamburger & View Breadcrumb */}
      <div className="flex items-center gap-3">
        {/* Mobile / Tablet Menu Button */}
        <button
          onClick={handleToggle}
          className="lg:hidden p-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-gray-300 hover:text-white transition-all focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
          aria-label={isMobileSidebarOpen ? 'Close navigation sidebar' : 'Open navigation sidebar'}
          aria-expanded={isMobileSidebarOpen}
        >
          <span className="material-symbols-outlined text-[20px]">
            {isMobileSidebarOpen ? 'close' : 'menu'}
          </span>
        </button>

        {/* View Indicator & Brand Logo */}
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 p-[1px] shadow-sm shadow-blue-500/30 flex items-center justify-center">
            <span className="material-symbols-outlined text-[16px] text-white">
              explore
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-white tracking-tight text-sm hidden sm:inline">
              COMPASS
            </span>
            <span className="text-gray-600 text-xs hidden sm:inline">/</span>
            <span className="text-xs font-medium text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2.5 py-0.5 rounded-full">
              {viewTitles[activeView] || activeView}
            </span>
          </div>
        </div>
      </div>

      {/* Middle: Real-time System Safety & Health Badges */}
      <div className="hidden lg:flex items-center gap-2.5">
        {/* Circuit Breaker Badge */}
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#111927] border border-emerald-500/30 text-[11px] font-mono text-emerald-400">
          <span className="material-symbols-outlined text-[13px]">bolt</span>
          <span>CIRCUIT BREAKER: CLOSED</span>
        </div>

        {/* StaleGuard Badge */}
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#111927] border border-cyan-500/30 text-[11px] font-mono text-cyan-300">
          <span className="material-symbols-outlined text-[13px] animate-spin-slow">sync</span>
          <span>STALEGUARD: 99.8% FRESH</span>
        </div>

        {/* System Armed Badge */}
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#111927] border border-emerald-500/30 text-[11px] font-mono text-emerald-300">
          <span className="material-symbols-outlined text-[13px]">lock</span>
          <span>SYSTEM ARMED</span>
        </div>

        {/* Emergency Abort Button */}
        <button
          onClick={onEmergencyAbort || onOpenTelemetry}
          className="flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 hover:text-white border border-rose-500/40 text-[11px] font-mono font-bold transition-all shadow-[0_0_15px_rgba(239,68,68,0.25)] hover:shadow-[0_0_20px_rgba(239,68,68,0.4)]"
          title="Emergency Abort: Halts all active desktop automation within 56ms"
        >
          <span className="material-symbols-outlined text-[14px]">warning</span>
          <span>EMERGENCY ABORT</span>
        </button>
      </div>

      {/* Right: Telemetry, Latency, Language, Settings */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Connection & Latency Capsule */}
        <div 
          onClick={onOpenTelemetry}
          className="flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] cursor-pointer transition-all text-xs font-mono"
          title="Click to view live hardware telemetry and diagnostics"
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onOpenTelemetry(); }}
        >
          <span className="relative flex h-2 w-2">
            {isConnected ? (
              <>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </>
            ) : (
              <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
            )}
          </span>
          <span className={isConnected ? 'text-gray-300' : 'text-rose-400 font-medium'}>
            {isConnected ? `${latency}ms` : (isKannada ? 'ಸಂಪರ್ಕ ಕಡಿತ' : 'Offline')}
          </span>
        </div>

        {/* Quick Language Toggle */}
        <button
          onClick={() => onLanguageChange(isKannada ? 'en' : 'kn')}
          className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-xs font-semibold text-gray-300 hover:text-white transition-all focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
          title="Switch language: English / ಕನ್ನಡ"
          aria-label="Toggle language between English and Kannada"
        >
          {isKannada ? 'ಕನ್ನಡ' : 'EN'}
        </button>
      </div>
    </header>
  );
}
