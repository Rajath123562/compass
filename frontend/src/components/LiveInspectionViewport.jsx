import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function LiveInspectionViewport({
  activeWindow = null,
  activeTask = null,
  onElementSelect = () => {},
  isSimulated = true,
}) {
  const [selectedElement, setSelectedElement] = useState(null);
  const [hoveredTag, setHoveredTag] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Default simulated detected UIA bounding boxes on the active desktop target
  const detectedElements = [
    {
      id: 'elem-header',
      name: 'Smart natural-language goal to view',
      tag: 'Bounding Tags',
      type: 'TextHeader',
      bounds: { x: 30, y: 35, w: 320, h: 28 },
      properties: {
        controlType: 'UIA_TextControlTypeId',
        automationId: 'GoalHeader_01',
        isKeyboardFocusable: false,
        staleGuardFresh: true,
      },
    },
    {
      id: 'elem-edit',
      name: 'Edit Control',
      tag: 'Bounding Boxes',
      type: 'Edit',
      bounds: { x: 30, y: 75, w: 220, h: 80 },
      properties: {
        elementName: 'Recognizer Box/Input',
        controlType: 'UIA_EditControlTypeId',
        automationId: 'DocumentBuffer',
        isKeyboardFocusable: true,
        hwnd: activeWindow?.hwnd ? `0x${activeWindow.hwnd.toString(16).toUpperCase()}` : '0x000713B4',
        coordinates: '192, 168, 307, 321',
        staleGuardFresh: true,
      },
    },
    {
      id: 'elem-action',
      name: 'Action Trigger',
      tag: 'Bounding Propertys',
      type: 'Button',
      bounds: { x: 265, y: 85, w: 105, h: 40 },
      properties: {
        elementName: 'Dispatch Button',
        controlType: 'UIA_ButtonControlTypeId',
        automationId: 'Btn_ActionDispatch',
        isKeyboardFocusable: true,
        coordinates: '265, 85, 370, 125',
        staleGuardFresh: true,
      },
    },
  ];

  const handleElementClick = (elem) => {
    setSelectedElement(elem);
    onElementSelect(elem);
  };

  return (
    <div className={`glass-card rounded-2xl flex flex-col overflow-hidden border border-white/10 transition-all duration-300 relative ${
      isFullscreen ? 'fixed inset-4 z-50 bg-[#090d14]/95 backdrop-blur-2xl' : 'w-full h-full min-h-[460px]'
    }`}>
      {/* Viewport Header Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-white/[0.02] border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-xs font-semibold tracking-wide text-gray-200">
            Live simulated desktop inspection viewport
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-mono">
            UIA v3.0
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Viewport size / fullscreen toggle */}
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1 rounded-md hover:bg-white/10 text-gray-400 hover:text-white transition-all text-xs flex items-center gap-1"
            title={isFullscreen ? 'Exit Fullscreen' : 'Expand Viewport'}
          >
            <span className="material-symbols-outlined text-[16px]">
              {isFullscreen ? 'close_fullscreen' : 'fullscreen'}
            </span>
          </button>
        </div>
      </div>

      {/* Main Viewport Workspace Container */}
      <div className="relative flex-1 p-4 bg-[#0a0e17] overflow-hidden flex items-center justify-center">
        {/* Synthetic OS Target Window Frame */}
        <div className="relative w-full max-w-[560px] h-[340px] rounded-xl bg-[#0f1420] border border-cyan-500/30 shadow-[0_0_40px_rgba(6,182,212,0.12)] flex flex-col overflow-hidden">
          
          {/* OS Title Bar */}
          <div className="flex items-center justify-between px-3 py-1.5 bg-[#141a29] border-b border-white/5 select-none">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[14px] text-cyan-400">
                terminal
              </span>
              <span className="text-[11px] font-mono text-gray-300 truncate max-w-[200px]">
                {activeWindow?.window_title || activeWindow?.app_name || 'Active Desktop Workspace'}
              </span>
            </div>
            
            {/* Window Controls */}
            <div className="flex items-center gap-2 text-gray-400 text-xs">
              <span className="hover:text-white cursor-pointer">—</span>
              <span className="hover:text-white cursor-pointer text-[10px]">□</span>
              <span className="hover:text-rose-400 cursor-pointer">✕</span>
            </div>
          </div>

          {/* Window Canvas / Inner Application Body */}
          <div className="relative flex-1 p-3 bg-gradient-to-br from-[#0c101a] to-[#07090e] overflow-hidden">
            {/* Background Grid Pattern */}
            <div className="absolute inset-0 bg-grid-pattern opacity-20 pointer-events-none" />

            {/* Rendered UIA Bounding Boxes */}
            {detectedElements.map((elem) => {
              const isSelected = selectedElement?.id === elem.id;
              const isHovered = hoveredTag === elem.id;

              return (
                <motion.div
                  key={elem.id}
                  onClick={() => handleElementClick(elem)}
                  onMouseEnter={() => setHoveredTag(elem.id)}
                  onMouseLeave={() => setHoveredTag(null)}
                  whileHover={{ scale: 1.01 }}
                  style={{
                    left: `${elem.bounds.x}px`,
                    top: `${elem.bounds.y}px`,
                    width: `${elem.bounds.w}px`,
                    height: `${elem.bounds.h}px`,
                  }}
                  className={`absolute rounded cursor-pointer transition-all duration-200 border ${
                    isSelected
                      ? 'border-cyan-400 bg-cyan-500/15 shadow-[0_0_15px_rgba(6,182,212,0.4)] z-20'
                      : isHovered
                      ? 'border-cyan-400/80 bg-cyan-500/10 z-10'
                      : 'border-cyan-500/50 bg-cyan-500/5 hover:border-cyan-400'
                  }`}
                >
                  {/* Neon Label Pill */}
                  <div className="absolute -top-3.5 left-1 px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-cyan-500 text-black shadow-sm flex items-center gap-1">
                    <span>{elem.tag}</span>
                  </div>

                  {/* Inner element preview text */}
                  <div className="p-1.5 text-[11px] font-mono text-cyan-200/90 truncate">
                    {elem.name}
                  </div>
                </motion.div>
              );
            })}

            {/* Element Properties Tooltip Card (as in screenshot) */}
            <AnimatePresence>
              {selectedElement && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: 10 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: 5 }}
                  className="absolute bottom-3 left-4 right-4 bg-[#111726]/95 border border-cyan-500/40 rounded-lg p-3 backdrop-blur-xl shadow-2xl z-30 font-mono text-[11px]"
                >
                  <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-white/10 text-cyan-300 font-semibold">
                    <span className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[14px]">tune</span>
                      {selectedElement.name}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedElement(null);
                      }}
                      className="text-gray-400 hover:text-white"
                    >
                      ✕
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-gray-300">
                    <div>
                      <span className="text-gray-500">Element:</span>{' '}
                      <span className="text-gray-200">{selectedElement.properties.controlType || 'Edit Control'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Name:</span>{' '}
                      <span className="text-gray-200 truncate">{selectedElement.properties.elementName || selectedElement.name}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">HWND:</span>{' '}
                      <span className="text-cyan-300">{selectedElement.properties.hwnd || '0x463A2'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Coordinates:</span>{' '}
                      <span className="text-purple-300">{selectedElement.properties.coordinates || '192, 168, 307, 321'}</span>
                    </div>
                  </div>

                  {/* Quick Generative UI Action Button */}
                  <div className="mt-2.5 pt-2 border-t border-white/5 flex items-center justify-between">
                    <span className="text-[10px] text-emerald-400 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      StaleGuard Fresh (&lt;2s)
                    </span>
                    <button
                      onClick={() => onElementSelect(selectedElement)}
                      className="px-2.5 py-1 rounded bg-cyan-500 hover:bg-cyan-400 text-black font-semibold text-[10px] transition-all flex items-center gap-1 shadow-sm"
                    >
                      <span>Auto-Target Control</span>
                      <span className="material-symbols-outlined text-[12px]">bolt</span>
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

          </div>
        </div>
      </div>
    </div>
  );
}
