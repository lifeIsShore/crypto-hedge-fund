# I1: Light / Cream Theme
**Improvement (post go-live) | Files: `templates/base.html` + CSS**

---

## Overview

The dashboard currently has a single dark theme. Adding a Cream/Ivory light
mode requires four phases. The architecture is already partially compatible
because the CSS uses some variables — but many colors are hardcoded inline
and in Chart.js configuration.

Your own `missing-parts.md` contains a complete color palette and phase plan.
This document translates that into a concrete implementation sequence.

---

## Phase 1 — Extract all hardcoded colors to CSS variables

In `base.html`, find the `<style>` block and ensure every color references
a CSS variable. Audit for hardcoded values like:
- `rgba(255,255,255,0.02)` → `var(--surface-hover)`
- `#07080a` → `var(--bg)`
- `#00e5a0` → `var(--accent)`
- `#c8d4e8` → `var(--text)`

Define the complete variable set in `:root` (dark theme):
```css
:root {
    --bg:            #07080a;
    --surface:       #0d0f13;
    --surface-hover: rgba(255,255,255,0.02);
    --border:        #1e2535;
    --text:          #c8d4e8;
    --text-muted:    #6b7a99;
    --accent:        #00e5a0;
    --accent-red:    #ff4d6a;
    --accent-yellow: #f5a623;
    --shadow:        0 4px 16px rgba(0,0,0,0.4);
}
```

---

## Phase 2 — Add the light theme class override

Immediately after the `:root` block, add:
```css
html.light-theme {
    --bg:            #fdfaf3;
    --surface:       #ffffff;
    --surface-hover: rgba(51,48,43,0.03);
    --border:        #e6e2d6;
    --text:          #33302b;
    --text-muted:    #8c8479;
    --accent:        #059669;
    --accent-red:    #dc2626;
    --accent-yellow: #d97706;
    --shadow:        0 4px 12px rgba(51,48,43,0.06);
}
```

---

## Phase 3 — Anti-flash script in `<head>`

This must be the very first thing in `<head>` to prevent a dark flash on
page load when light theme is active:

```html
<head>
<script>
  // Anti-flash: apply theme before first paint
  (function() {
    var t = localStorage.getItem('ct-theme');
    if (t === 'light') document.documentElement.classList.add('light-theme');
  })();
</script>
<title>Control Tower</title>
...
```

---

## Phase 4 — Toggle button in navbar

Add to the navigation bar in `base.html`:
```html
<button id="theme-toggle" onclick="toggleTheme()" title="Toggle theme">
  <span id="theme-icon">☀️</span>
</button>
```

Add to the bottom of `base.html` (before `</body>`):
```javascript
function toggleTheme() {
    var html = document.documentElement;
    var isLight = html.classList.toggle('light-theme');
    localStorage.setItem('ct-theme', isLight ? 'light' : 'dark');
    document.getElementById('theme-icon').textContent = isLight ? '🌙' : '☀️';
    // Re-render all Chart.js instances with new colors
    if (window.Chart) {
        var newColor = isLight ? '#33302b' : '#c8d4e8';
        var newGrid  = isLight ? 'rgba(51,48,43,0.08)' : 'rgba(200,212,232,0.08)';
        Chart.defaults.color = newColor;
        Object.values(Chart.instances).forEach(function(chart) {
            if (chart.options.scales) {
                Object.values(chart.options.scales).forEach(function(scale) {
                    if (scale.ticks) scale.ticks.color = newColor;
                    if (scale.grid)  scale.grid.color  = newGrid;
                });
            }
            chart.update('none');  // 'none' = no animation for instant theme switch
        });
    }
}

// Set icon on load
(function() {
    var isLight = document.documentElement.classList.contains('light-theme');
    var icon = document.getElementById('theme-icon');
    if (icon) icon.textContent = isLight ? '🌙' : '☀️';
})();
```

---

## Phase 5 — Special components

These need manual overrides that won't be caught by variable replacement:

**CRT scanline effect** — lower opacity or remove in light mode:
```css
html.light-theme .scanlines::after {
    opacity: 0.01;   /* nearly invisible in light mode */
}
```

**DataTables** — if used, update its CSS variables to match.

**Scrollbar** — add light-mode scrollbar styling:
```css
html.light-theme ::-webkit-scrollbar-track { background: #f0ece2; }
html.light-theme ::-webkit-scrollbar-thumb { background: #c0bbb0; }
```

---

## Testing checklist

- [ ] All chart labels readable in both themes
- [ ] Buy (green) and Sell (red) signals distinguishable in cream mode
- [ ] No "dark flash" on page reload in light mode (anti-flash script working)
- [ ] Theme persists across page navigation and browser restart
- [ ] Mobile layout looks correct in light mode
- [ ] Tooltips and dropdowns use theme variables (not hardcoded backgrounds)
