# PulseLab Design System (Cyber Night)

## Core Philosophy
PulseLab utilizes a bespoke immediate-mode GUI rendered directly on Pygame surfaces. The visual aesthetic is "Cyber Night" — a high-contrast, industrial dark theme designed to reduce eye strain during prolonged engineering sessions, while using bright neon accents to highlight critical electrical values.

## Palette (`ui/theme.py`)

- **Background (BG):** `(12, 14, 20)` - Deep void blue/black.
- **Panel Background (PANEL_BG):** `(18, 22, 32)` - Elevated surfaces.
- **Grid Lines (GRID_COL):** `(30, 36, 50)` - Subtle engineering grid.
- **Text Primary (WHITE):** `(240, 245, 255)` - Crisp white with a slight blue tint.
- **Text Muted (DIM):** `(100, 110, 130)` - Secondary text, units.

### Semantic Accents
- **SAFE / OK:** `(0, 200, 120)` - Neon Green (Valid paths, Success messages).
- **ACCENT / SELECTION:** `(0, 150, 255)` - Cyan/Blue (Active tool, Selected component).
- **WARN / VOLTAGE:** `(255, 180, 0)` - Amber (Positive voltage nodes, Warnings).
- **DANGER / GROUND:** `(255, 60, 60)` - Crimson (Errors, Negative/Ground nodes in some visualizers).

### Forge & AI Elements
- **FORGE / HARDWARE:** `(0, 200, 180)` - Teal (KiCad export buttons, PCB generation).
- **AI / KNOWLEDGE:** `(150, 100, 255)` - Purple (LLM generation, semantic review).

## Typography
Fonts are loaded dynamically via `get_fonts()`:
- `title` (Consolas/Monospace 16pt bold): Application Header.
- `md` (Consolas 14pt): Values, Main UI panels.
- `sm` (Consolas 12pt): Descriptions.
- `xs` (Consolas 10pt): Tooltips, Grid coords.

## Component Styling (Visualizer)
Components must follow `COMP_COLORS` defined in the theme to maintain consistency across the schematic, the toolbar, and the property panel.
- Resistors: Muted Green.
- Capacitors: Soft Cyan.
- Inductors: Yellow.
- Semiconductors: Purple.
