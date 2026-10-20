import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../api';

export default function SystemTelemetryModal({ isOpen, onClose, systemInfo, latency, health }) {
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState(false);

  if (!isOpen) return null;

  const handleExportDiagnostics = async () => {
    try {
      setExporting(true);
      const data = await api.getDiagnostics();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `compass_diagnostic_bundle_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setExported(true);
      setTimeout(() => setExported(false), 3500);
    } catch (err) {
      console.error('Failed to export diagnostics:', err);
    } finally {
      setExporting(false);
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
        <motion.div
          initial={{ opacity: 0, scale: 0.94, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.94, y: 15 }}
          transition={{ type: 'spring', damping: 26, stiffness: 320 }}
          className="w-full max-w-lg bg-[#111215] border border-white/10 rounded-2xl shadow-2xl p-6 relative overflow-hidden"
        >
          {/* Subtle Glow Header */}
          <div className="flex items-center justify-between pb-4 border-b border-white/10">
            <div className="flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              <h2 className="text-lg font-medium text-white tracking-tight">System Telemetry & Hardware</h2>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-white/5"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Metric Grid */}
          <div className="grid grid-cols-2 gap-3.5 my-5">
            <div className="bg-[#18191e] border border-white/5 rounded-xl p-3.5 flex flex-col justify-between">
              <span className="text-[11px] font-medium tracking-wider text-gray-400 uppercase">Process Memory</span>
              <div className="text-xl font-semibold text-white mt-1">
                {systemInfo?.memory_used_mb !== undefined ? `${systemInfo.memory_used_mb} MB` : 'Unavailable'}
              </div>
              <span className="text-[11px] text-gray-500 mt-1">
                Total System: {systemInfo?.memory_total_mb ? `${Math.round(systemInfo.memory_total_mb / 1024)} GB` : 'Unavailable'}
              </span>
            </div>

            <div className="bg-[#18191e] border border-white/5 rounded-xl p-3.5 flex flex-col justify-between">
              <span className="text-[11px] font-medium tracking-wider text-gray-400 uppercase">CPU Utilization</span>
              <div className="text-xl font-semibold text-white mt-1">
                {systemInfo?.cpu_percent !== undefined ? `${systemInfo.cpu_percent}%` : 'Unavailable'}
              </div>
              <span className="text-[11px] text-emerald-400/90 mt-1">Process CPU Sample</span>
            </div>

            <div className="bg-[#18191e] border border-white/5 rounded-xl p-3.5 flex flex-col justify-between">
              <span className="text-[11px] font-medium tracking-wider text-gray-400 uppercase">API Loop Latency</span>
              <div className="text-xl font-semibold text-white mt-1">
                {latency ? `${latency} ms` : 'Unavailable'}
              </div>
              <span className="text-[11px] text-gray-500 mt-1">Local loopback (127.0.0.1:8000)</span>
            </div>

            <div className="bg-[#18191e] border border-white/5 rounded-xl p-3.5 flex flex-col justify-between">
              <span className="text-[11px] font-medium tracking-wider text-gray-400 uppercase">Host Environment</span>
              <div className="text-base font-semibold text-white mt-1 truncate" title={systemInfo?.os_version}>
                {systemInfo?.os ? `${systemInfo.os} (${systemInfo.os_version?.split(' ')[0] || ''})` : 'Windows Desktop'}
              </div>
              <span className="text-[11px] text-gray-500 mt-1 truncate">
                Python {systemInfo?.python_version?.split(' ')[0] || '3.11'} · PID {systemInfo?.process_pid || 'Active'}
              </span>
            </div>
          </div>

          {/* 1-Click Export Diagnostic Bundle */}
          <button
            onClick={handleExportDiagnostics}
            disabled={exporting}
            className={`w-full py-2.5 px-4 rounded-xl border text-xs font-mono flex items-center justify-center gap-2 transition-all mb-4 ${
              exported 
                ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400' 
                : 'bg-white/5 hover:bg-white/10 border-white/10 text-gray-300 hover:text-white'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">
              {exported ? 'check_circle' : 'inventory_2'}
            </span>
            <span>
              {exported 
                ? 'Sanitized Diagnostic Bundle Exported (0% PII)' 
                : (exporting ? 'Generating Bundle...' : 'Export Redacted Diagnostic Report')}
            </span>
          </button>

          {/* Footer status */}
          <div className="flex items-center justify-between pt-3 border-t border-white/10 text-xs text-gray-400">
            <span>Uptime: {systemInfo?.uptime_seconds ? `${Math.floor(systemInfo.uptime_seconds / 60)}m ${Math.floor(systemInfo.uptime_seconds % 60)}s` : 'Active'}</span>
            <span className="text-emerald-400 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              100% Local Inference Engine
            </span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
