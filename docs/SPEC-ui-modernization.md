# SPEC: ui-modernization

## 1. Objective
Transform the currently unpolished and bare-bones React frontend into a premium, professional application featuring a glassmorphism design system, dark mode, and dynamic micro-animations. Furthermore, expose missing functional controls (such as the API key configuration) so the frontend is fully usable.

## 2. Design System & Aesthetics
- **Theme:** Deep Dark Mode (e.g., `#0F172A` background).
- **Glassmorphism:** Use `backdrop-filter: blur(12px)` with semi-transparent backgrounds for cards, sidebars, and banners.
- **Typography:** Modern, clean sans-serif (e.g., system-ui, Inter, or Roboto).
- **Colors:** 
  - Primary: Vibrant neon blue/purple gradients for active states.
  - Text: High contrast white/off-white.
  - Error/Warning: Refined, accessible red/yellow tones.
- **Animations:** Subtle CSS transitions (`ease-in-out`) on hovers, button clicks, and modal appearances. No heavy animation libraries (Ponytail Rule #4: Use Native CSS).

## 3. Scope of Work (Components to Rewrite)
1. **`index.css` & Global Layout**
   - Replace generic styling with the Glassmorphism design tokens.
   - Setup CSS variables for colors, spacing, and transition speeds.

2. **`Header.jsx`**
   - Redesign into a sleek top navigation bar.
   - Add an "API Key Config" button that opens a settings modal.

3. **`TaskEntry.jsx`**
   - Transform the input area into a beautiful, floating command bar (similar to Spotlight or Raycast).
   - Add glowing focus states and subtle submit animations.

4. **`TaskStateCard.jsx` & `SystemTelemetry.jsx`**
   - Convert to glass cards.
   - Improve layout of the task status, making the state transitions (STARTING -> OBSERVING -> PLANNING) visually engaging.

5. **`ErrorBanner.jsx`**
   - Make it a non-intrusive but clear toast/banner with smooth slide-in animations.

6. **API Key Setup (New)**
   - Add a simple React state / modal to capture the `OMNIROUTE_API_KEY`. 
   - (Ponytail note: Since backend expects `.env` or `api_keys` table but no endpoint currently exists, we will either mock this or add a tiny endpoint to `routers/system.py` that writes to `system_settings` or `.env`).

## 4. Constraints & Rules (Ponytail)
- **No heavy CSS frameworks:** We will use vanilla CSS / `index.css` to build the glassmorphism system (Rung 4: Native platform feature). Avoid Tailwind unless explicitly requested.
- **No new heavy JS animation libraries:** (Framer Motion etc.). We will use CSS transitions and keyframes.
- **Component Reuse:** We will modify the existing `jsx` files in `frontend/src/components/`, not delete and recreate them from scratch.
- **Maintain existing logic:** Keep all existing `fetch()` calls and state management intact. Only update the visual presentation.

## 5. Acceptance Criteria
- [ ] The app renders with a deep dark glassmorphism theme.
- [ ] `TaskEntry.jsx` looks like a premium command bar.
- [ ] The UI allows the user to input an API key (resolving the "non-functional" complaint).
- [ ] No new NPM dependencies are added unless absolutely necessary.
