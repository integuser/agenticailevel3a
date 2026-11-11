# Frontend Changes: Theme Toggle

- **index.html**: Added a fixed top-right `#themeToggle` button with inline sun/moon SVG icons (`aria-label`, `aria-pressed`, `aria-hidden` on icons). Added an inline head script that applies the saved theme before paint (no flash). Bumped asset cache versions.
- **style.css**: Added a `:root[data-theme="light"]` variable set, the `.theme-toggle` styles (circular, matches surface/border/shadow tokens, hover scale, `:focus-visible` ring), icon rotate/fade crossfade, 0.3s color transitions on main surfaces, and a `prefers-reduced-motion` override.
- **script.js**: Added `setupThemeToggle()` which toggles `data-theme` on `<html>`, updates aria attributes, and persists the choice in `localStorage`. Native `<button>` gives Enter/Space keyboard support.

## Light theme refinement
- Light palette in `style.css` (`:root[data-theme="light"]`): `#f8fafc` background, `#ffffff` surface, `#0f172a` primary text (~17:1), `#475569` secondary text (~7.5:1), `#cbd5e1` borders.
- Darker primary (`#1d4ed8`) and user-message colors so white-on-blue and blue-on-white text meet WCAG AA (>= 4.5:1).
- New variables `--code-bg`, `--error-text`, `--success-text` replace hard-coded colors so code blocks and error/success messages adapt to both themes (error `#b91c1c`, success `#15803d` in light).
- Fixed undefined `--primary` reference (now `--primary-color`) and extended theme color transitions to more elements.
