# COMPASS Frontend Design System Specification

**Design System:** COMPASS Precision Dark System  
**Framework:** Tailwind CSS v4 (`@theme` Engine)  
**Primary Aesthetic:** Calm, information-dense, precision engineering desktop interface  

---

## 1. Design Philosophy

COMPASS is designed as serious desktop productivity software for operating an autonomous AI computer-use agent. The visual direction intentionally avoids:
- Neon glowing card borders or gratuitous cyberpunk aesthetics.
- Low-contrast light gray typography on dark surfaces.
- Disorienting perpetual motion or fake activity animations.
- Generic AI chat templates that conceal real execution mechanics.

Instead, the system utilizes high-contrast legible typography, subtle structural borders, authentic live indicators, and predictable interaction conventions.

---

## 2. Centralized Design Tokens (`index.css`)

### 2.1 Surface & Background Palette
```css
--color-stitch-bg: #0b0d12;              /* Deep canvas background */
--color-stitch-bg-elevated: #11141b;     /* Primary surface cards and sidebars */
--color-stitch-bg-card: rgba(22, 26, 35, 0.7); /* Translucent backdrop-filtered panels */
--color-stitch-sidebar: #0e1017;         /* Persistent desktop sidebar */
```

### 2.2 Semantic Status & Accent Colors
```css
--color-accent-blue: #3b82f6;            /* Primary action, planning, selection */
--color-accent-cyan: #06b6d4;            /* Realtime stream tokens, tool telemetry */
--color-accent-purple: #8b5cf6;          /* DAG workflows, multi-node pipelines */
--color-accent-emerald: #10b981;         /* Verified success, healthy backend, OCR pass */
--color-accent-amber: #f59e0b;           /* Human approval required, paused state */
--color-accent-rose: #f43f5e;            /* Emergency STOP, failed step, disconnection */
```

### 2.3 Typography & Hierarchy
```css
--font-inter: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
```
- **Primary Page Headings**: `text-2xl font-semibold text-white tracking-tight`
- **Section & Card Titles**: `text-sm font-semibold text-white`
- **Capsule & Metadata Labels**: `text-[11px] font-semibold text-gray-400 uppercase tracking-wider`
- **Body & Explanatory Text**: `text-xs text-gray-300 leading-relaxed`
- **Technical Metrics & Identifiers**: `font-mono text-xs font-medium`

### 2.4 Focus, Borders, and Radii Conventions
- **Focus Ring**: `*:focus-visible { outline: 2px solid #3b82f6; outline-offset: 2px; }`
- **Standard Border**: `border-white/5` (subtle) up to `border-white/15` (interactive hover)
- **Container Radius**: `rounded-2xl` (cards), `rounded-3xl` (executive command capsule), `rounded-xl` (inputs/buttons)

---

## 3. Reusable UI Components & State Semantics

### 3.1 9-Stage Task Execution Pipeline Tracker
Implemented in `TaskStateCard.jsx`, the pipeline breaks down computer tasks into distinct, technically honest phases:
1. `SUBMITTED`: User goal received by backend.
2. `PLANNING`: Semantic decomposition into concrete Windows actions.
3. `AWAITING_APPROVAL`: Safety evaluation gating sensitive mouse/keyboard interactions.
4. `EXECUTING`: Native Windows UIA input dispatched.
5. `ACTION_EXECUTED`: Win32 event acknowledged.
6. `VERIFYING`: WinRT OCR state verification and target screen digest.
7. `RECOVERING`: Automated self-correction if initial verification score drops.
8. `COMPLETED`: Terminal verified state with evidence cards.
9. `FAILED`: Terminal error state with actionable diagnostics.

### 3.2 Dual-Mode Responsive Sidebar
- **Desktop (>= 1024px)**: Fixed static navigation bar with workstream indicators and session cleanup.
- **Mobile (< 1024px)**: Slide-over drawer actuated by the header hamburger button with backdrop overlay (`bg-black/60 backdrop-blur-sm`) and focus containment.

### 3.3 Executive Command Capsule (`TaskEntry.jsx`)
- Textarea with auto-sizing and keyboard submission (`Enter` sends, `Shift+Enter` multiline).
- Model selector with local Ollama, Claude Opus 5.5, and OpenRouter routes.
- Dual Guidance Switch: `Chat` (advisory & vision analysis) vs `Guide` (native Windows computer control).
- Preset suggestion chips for one-click common productivity scenarios.

### 3.4 Ground-Truth Telemetry Badges
- **Loopback Latency**: Real ping measurement to FastAPI on every health poll (e.g., `37ms loopback`).
- **Memory Footprint**: Process RSS memory directly from `psutil` via `/api/system/info`.
- **Active Window Capsule**: Reports real foreground window title and app name via Win32 `GetForegroundWindow`.
