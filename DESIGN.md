---
name: Odin Advisor Console
description: A quiet professional thinking workspace.
colors:
  canvas: "#f7f6f2"
  surface: "#fff"
  sidebar: "#efeee9"
  ink: "#252824"
  muted: "#686b63"
  line: "#dedfd6"
  hover: "#e7e8e0"
  accent: "#b23d36"
  accent-soft: "#f7e9e6"
  positive: "#32704b"
  on-ink: "#fff"
  dark-canvas: "#181b19"
  dark-surface: "#202420"
  dark-sidebar: "#1c201c"
  dark-ink: "#edf0e8"
  dark-muted: "#adb2a7"
  dark-line: "#393f37"
  dark-hover: "#30372e"
  dark-accent: "#ed9287"
  dark-accent-soft: "#3c2826"
  dark-positive: "#8bc7a0"
  dark-on-ink: "#181b19"
typography:
  display:
    fontFamily: "Manrope, 'Segoe UI', sans-serif"
    fontSize: "clamp(38px, 4vw, 62px)"
    fontWeight: 500
    lineHeight: 1.13
    letterSpacing: "-.04em"
  headline:
    fontFamily: "Manrope, 'Segoe UI', sans-serif"
    fontSize: "36px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-.03em"
  title:
    fontFamily: "Manrope, 'Segoe UI', sans-serif"
    fontSize: "16px"
    fontWeight: 700
  body:
    fontFamily: "Manrope, 'Segoe UI', sans-serif"
    fontSize: "14px"
    lineHeight: 1.9
  label:
    fontFamily: "Manrope, 'Segoe UI', sans-serif"
    fontSize: "11px"
    fontWeight: 700
rounded:
  badge: "5px"
  search: "6px"
  control: "7px"
  option: "10px"
  container: "12px"
  dialog: "14px"
spacing:
  compact: "8px"
  control: "12px"
  gutter: "22px"
  content: "40px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink}"
    rounded: "{rounded.control}"
    padding: "12px 18px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "12px"
  navigation:
    textColor: "{colors.muted}"
    rounded: "{rounded.control}"
    padding: "11px 13px"
  navigation-active:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.accent}"
    rounded: "{rounded.control}"
  theme-option:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.option}"
    padding: "15px"
  badge:
    textColor: "{colors.muted}"
    rounded: "{rounded.badge}"
    padding: "5px 8px"
---

# Design System: Odin Advisor Console

## Overview

**Creative North Star: "The Editorial Operations Console"**

A quiet professional thinking workspace. Warm paper surfaces, neutral charcoal type and restrained red accents support reading, decisions and operational work. The authored geometric O with its directional arrow anchors the identity.

**Key Characteristics:**
- Compact navigation and focused task content.
- Flat tonal surfaces, restrained borders and readable data.
- Shared visual language across authentication, advisor, settings and operations.

## Colors

### Primary

Red accent marks active navigation, focus, links and errors; accent-soft marks selection. Primary action buttons use ink rather than red. Both themes use the same semantic roles through CSS custom properties.

### Neutral

Canvas is the page ground; sidebar is the quieter navigation ground; surface carries controls and selected rows. Ink and muted divide primary from supporting text. Line separates sections; hover makes interactive rows visible; on-ink provides button text. The dark-prefixed tokens replace their light equivalents when `data-theme="dark"` is set on the root.

Positive green is reserved for success feedback, not a second brand accent. Tailwind slate, white and blue aliases resolve to these semantic tokens rather than adding a competing palette.

**The Restrained Accent Rule.** Keep red for meaningful states and the brand arrow; let neutral typography and surfaces carry the screen.

## Typography

Self-hosted variable Manrope (weights 200–800), with Segoe UI and sans-serif fallbacks. Display copy is generous and medium weight; interface text is compact. Headings use balanced wrapping and tight tracking.

Login headings use 32px/600; the advisor welcome uses clamp(28px, 3vw, 40px)/500. Settings and operations headings use the headline role, reducing to 30px on mobile. Section titles use 15–16px/700; controls and navigation use 12–13px, badges and secondary labels 10–11px. Transcript prose uses a 1.85 line height; welcome copy uses 1.9. Tables use 12px cells and 10px headers with .05em tracking.

## Layout

The first viewport pairs compact navigation with a focused task region. Workspace navigation is sticky, full viewport height and 236px wide; advisor navigation is 260px. Headers are 68px tall. Settings content is capped at 920px and operations at 1200px, with 40px desktop gutters. Login uses a split narrative/form composition and a 370px form cap.

At 1000px, navigation narrows to 190px (advisor 230px) and content gutters reduce to 28px. At 760px, workspace navigation becomes a 68px icon rail, retaining accessible link names; the advisor uses a 280px sliding drawer with scrim, open and close controls. Login hides its story panel and shows the mobile brand. Theme and password grids stack; content gutters become 22px, advisor gutters 16px. Composer remains below the scrollable transcript. Long links wrap; transcript tables scroll horizontally.

## Elevation & Depth

Tonal layering and fine dividers provide depth. Navigation, content sections and standard buttons stay flat. The composer alone has a faint resting shadow (`0 4px 12px #00000005`), removed on focus. Destructive dialogs use `0 18px 60px #00000030`; mobile scrims use `#0006`.

## Shapes

Gently curved controls use the control radius; badges and search fields are tighter. Theme choices use the option radius, transcript/composer/operations containers the container radius, and destructive dialogs the dialog radius. Borders are typically 1px semantic line. The brand mark uses a charcoal open O and red northeast arrow, rounded strokes (3.5px) in a 32px viewbox; common icons use 1.7px strokes at 18px.

## Components

- **Buttons:** Ink-filled primary actions, 13px/700 and control radius; hover opacity .85. Sidebar tools are transparent, become hover-toned, and use muted-to-ink text. Disabled buttons use .5 opacity and a not-allowed cursor. Pointer presses scale enabled buttons to .97, excluding the scrim and visible keyboard focus.
- **Inputs:** Surface ground, line border and ink text; settings fields have 12px padding. Login fields use canvas. Search fields use 9px 11px padding and the search radius. Caret and focused borders use accent. Composer uses 13px/1.7 text, container radius, 90–220px height and vertical resize.
- **Navigation:** 13px/600, icon/text gap 12px, rows padded 11px 13px. Hover uses hover ground with ink; current rows use surface with accent text. Mobile workspace labels are visually hidden while aria-labels persist.
- **Theme options:** Bordered, flat choices with a small theme preview; selection uses accent border, accent-soft ground and checkmark.
- **Badges:** Compact muted labels with line borders and badge radius. Keep operational data readable rather than decorative.
- **Accessible states:** Keyboard focus uses a 2px accent outline with 3px offset on buttons, links, role buttons, inputs and textareas. Error and success messages accompany their semantic colors. Button background, color, border and transform transitions take 120ms; keyboard-focused buttons respond immediately. The mobile drawer uses 220ms directional easing, with immediate keyboard activation. Reduced-motion preference disables transitions, animations and press transforms. Mobile login/password fields and composer use 16px type. Chat scrolling is immediate.

## Do's and Don'ts

- Do reuse semantic CSS properties for both themes.
- Do keep compact controls, readable transcripts and clear section dividers.
- Do preserve visible keyboard focus and accessible names for icon controls.
- Don't introduce competing brand accent colors or decorative gradients.
- Don't add raised cards or shadows to ordinary workspace sections.
