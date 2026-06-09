---
name: Cyber-Drive OBD System
colors:
  surface: '#121221'
  surface-dim: '#121221'
  surface-bright: '#383849'
  surface-container-lowest: '#0d0d1c'
  surface-container-low: '#1a1a2a'
  surface-container: '#1e1e2e'
  surface-container-high: '#292839'
  surface-container-highest: '#333344'
  on-surface: '#e3e0f7'
  on-surface-variant: '#bbc9cf'
  inverse-surface: '#e3e0f7'
  inverse-on-surface: '#2f2f40'
  outline: '#859398'
  outline-variant: '#3c494e'
  surface-tint: '#3cd7ff'
  primary: '#a8e8ff'
  on-primary: '#003642'
  primary-container: '#00d4ff'
  on-primary-container: '#00586b'
  inverse-primary: '#00677e'
  secondary: '#cdbdff'
  on-secondary: '#370096'
  secondary-container: '#5203d5'
  on-secondary-container: '#c0acff'
  tertiary: '#e0dded'
  on-tertiary: '#302f3b'
  tertiary-container: '#c3c1d1'
  on-tertiary-container: '#4f4f5c'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#b4ebff'
  primary-fixed-dim: '#3cd7ff'
  on-primary-fixed: '#001f27'
  on-primary-fixed-variant: '#004e5f'
  secondary-fixed: '#e8deff'
  secondary-fixed-dim: '#cdbdff'
  on-secondary-fixed: '#20005f'
  on-secondary-fixed-variant: '#4f00d0'
  tertiary-fixed: '#e3e0f1'
  tertiary-fixed-dim: '#c7c5d5'
  on-tertiary-fixed: '#1b1a26'
  on-tertiary-fixed-variant: '#464552'
  background: '#121221'
  on-background: '#e3e0f7'
  surface-variant: '#333344'
typography:
  telemetry-xl:
    fontFamily: Inter
    fontSize: 72px
    fontWeight: '800'
    lineHeight: 80px
    letterSpacing: -0.02em
  telemetry-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.01em
  headline-display:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  body-main:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.1em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  container-max: 1440px
  gutter: 24px
  margin-desktop: 40px
  card-gap: 20px
  section-padding: 32px
---

## Brand & Style
The design system is engineered for high-performance automotive diagnostics, blending **Modern Automotive** precision with a **Cyberpunk-lite** aesthetic. It targets enthusiast drivers and professional technicians who require split-second data legibility in high-stress or low-light environments.

The visual language utilizes "Digital Neon" accents against an ultra-dark canvas to reduce eye strain while highlighting critical telemetry. The style is **Glassmorphic and High-Contrast**, using semi-transparent layers and vibrant glows to simulate a heads-up display (HUD) experience. The emotional response is one of technological superiority, precision, and futuristic control.

## Colors
The palette is built on a "Deep Space" foundation to maximize the luminosity of the neon indicators.

- **Base Background:** #0F0F1A (Deep Navy Black) for maximum contrast.
- **Surface/Card:** #1E1E2E at 60-80% opacity for glassmorphic depth.
- **Primary (Cyan):** Used for titles, active data paths, and primary HUD elements.
- **Secondary (Purple):** Reserved for interactive elements and call-to-action buttons.
- **Semantic Accents:** Standardized automotive alert colors for immediate status recognition.

Glow effects (Outer Glow) should use the primary or secondary hex with a 20-30% opacity blur to simulate neon light emission.

## Typography
The system prioritizes **Inter** for its neutral, highly legible character shapes across all sizes. For technical readouts and monospaced data, **JetBrains Mono** is utilized to provide a developer-centric, "under-the-hood" feel.

Telemetry data (Speed, RPM, Temp) must use the `telemetry` scales with heavy weights to ensure they are readable at a glance from a distance. Labels for these units should always use the `label-mono` style to distinguish metadata from live values.

## Layout & Spacing
The layout follows a **Fluid Grid** model optimized for wide-screen desktop displays. It employs a 12-column structure with generous gutters to maintain a "clean tech" feel and avoid information overload.

- **Global Status Bar:** Fixed to the top or bottom, spanning 100% width, providing persistent connectivity status.
- **Telemetry Grid:** Uses a flexible masonry or CSS grid system where cards span 3, 4, or 6 columns depending on priority.
- **Padding:** A strict 8px base unit system is used. Interior card padding is consistently 24px to allow the glassmorphic background to breathe.

## Elevation & Depth
This design system rejects traditional shadows in favor of **Tonal Layering and Glassmorphism**.

1.  **Background:** Solid #0F0F1A.
2.  **Base Cards:** Background blur (20px-40px) with #1E1E2E at 70% opacity.
3.  **Active/Hover State:** Cards gain a 1px inner stroke of Primary Cyan at 30% opacity and a subtle outer glow.
4.  **Overlays/Modals:** Higher saturation background blur (60px) with a darker overlay to pull focus.

Depth is communicated through "light leaks" and border luminescence rather than physical offset shadows.

## Shapes
The shape language is "Sophisticated Geometric." We use **Rounded (0.5rem)** corners as a default to maintain a modern software feel while avoiding the overly "soft" look of mobile consumer apps. 

- **Cards/Containers:** 16px (1rem) corner radius.
- **Buttons/Inputs:** 8px (0.5rem) corner radius.
- **Circular Indicators:** Used strictly for gauges (RPM, Speed, Fuel) to mimic physical automotive clusters.

## Components

### Buttons
- **Primary (Secondary Purple):** Solid fill #7C4DFF.
  - **Hover:** Brightness increase + 10px glow radius.
  - **Disabled:** 30% opacity with grayscale filter.
- **Outline (Primary Cyan):** 1.5px border #00D4FF with no fill.
  - **Hover:** Fill with 10% Cyan opacity.

### Glassmorphic Cards
Cards feature a 1px border (#FFFFFF, 10% opacity) to catch the "light" of the background. Telemetry cards must include a "Unit Label" in the top-right corner using monospaced type.

### Circular Progress (Gauges)
- **Track:** #1E1E2E solid.
- **Indicator:** Gradient stroke from #00D4FF to #7C4DFF.
- **Critical Zone:** The final 15% of the gauge track should transition to #FF1744 (Error Red) to indicate redlining or danger zones.

### Status Indicators
- **Connected:** Pulsing Success Green dot with "SYSTEM READY" text.
- **Disconnected/Simulation:** Solid Error Red dot with "NO LINK" text.
- **Inputs:** Dark field with Cyan focus rings; text enters in monospaced font for technical accuracy.