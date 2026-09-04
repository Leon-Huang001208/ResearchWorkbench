# UI Reference Guide

## Quick Reference

### Before Building Any UI Component

Always read these first:
1. `/docs/design/DESIGN.md` - Design system foundation
2. `/docs/design/TOKENS.md` - Design tokens
3. `/docs/frontend/COMPONENT_RULES.md` - Component guidelines
4. `/docs/frontend/INTERACTION_RULES.md` - Interaction patterns

### Color Reference

| Purpose | Value |
|---------|-------|
| Page Background | `#0D0F14` |
| Panel Background | `#151922` |
| Elevated Panel | `#1B2130` |
| Sidebar Background | `#11151D` |
| Primary Text | `#F3F4F6` |
| Secondary Text | `#9CA3AF` |
| Muted Text | `#6B7280` |
| Primary Accent | `#F59E0B` |
| Hover Accent | `#FBBF24` |
| Positive | `#00C896` |
| Negative | `#FF6B6B` |
| Warning | `#F59E0B` |

### Typography Reference

| Type | Font |
|------|------|
| UI Text | Inter |
| Data/Numbers | JetBrains Mono |

Always use mono font for:
- prices
- percentages
- timestamps
- volume
- market caps

### Layout Reference

| Element | Value |
|---------|-------|
| Card Border Radius | `16px` |
| Button Border Radius | `10px` |
| Input Border Radius | `10px` |
| Default Table Row Height | `32px` |
| Compact Table Row Height | `28px` |
| Expanded Sidebar Width | `240px` |
| Collapsed Sidebar Width | `72px` |

### Spacing Reference

| Token | Value |
|-------|-------|
| `--space-1` | `4px` |
| `--space-2` | `8px` |
| `--space-3` | `12px` |
| `--space-4` | `16px` |
| `--space-5` | `20px` |
| `--space-6` | `24px` |
| `--space-8` | `32px` |

## Checklist for New Components

Before submitting a new component:

- [ ] Reviewed DESIGN.md
- [ ] Followed COMPONENT_RULES.md
- [ ] Used design tokens from TOKENS.md
- [ ] Implemented proper hover states
- [ ] Implemented active states
- [ ] Used mono font for numeric data
- [ ] Numeric data right-aligned in tables
- [ ] No excessive motion or animations
- [ ] No gradients unless explicitly approved
- [ ] No floating effects
- [ ] No decorative shadows
- [ ] Empty states are operational (not playful)
- [ ] AI outputs are evidence-based, not chat-like

## Checklist for Page Layouts

Before submitting a new page:

- [ ] Reviewed PAGE_LAYOUTS.md
- [ ] Followed INTERACTION_RULES.md
- [ ] Global structure consistent (Search + Sidebar + Workspace + Status)
- [ ] High information density
- [ ] Minimal visual noise
- [ ] No decorative elements
- [ ] Every element improves research velocity

## AI Prompt Template

Use this template when asking AI to build components:

```
Build a [component name] for Research Workbench.

Requirements:
- Follow /docs/design/DESIGN.md
- Follow /docs/frontend/COMPONENT_RULES.md
- Dark terminal aesthetic (#0D0F14 page, #151922 panels)
- High density layout
- Mono font for all numeric data
- Subtle hover only (no floating)
- Amber accent (#F59E0B) only
- No gradients, no glossy effects
- [specific functional requirements]

Structure:
[describe the component structure]

Data to display:
[list the data points]

Interactions:
[describe user interactions]
```

## Common Pitfalls to Avoid

❌ Don't use "futuristic" or "premium" as design guidance
❌ Don't add decorative elements
❌ Don't use rainbow colors
❌ Don't make empty states playful
❌ Don't treat AI as a chatbot
❌ Don't generate the entire platform at once

✅ Do focus on research velocity
✅ Do use terminal aesthetic
✅ Do prioritize information density
✅ Do make AI evidence-based
✅ Do build components one at a time
✅ Do reference DESIGN.md in every prompt
