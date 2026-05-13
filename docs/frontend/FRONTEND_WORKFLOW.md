# Frontend Workflow

# Philosophy

AI generates components.

Humans control architecture.

---

# Workflow

## Step 1

Define workflow.

Example:
User scans signal
User validates evidence
User opens entity
User generates report

---

## Step 2

Define layout.

Sidebar
Main Panel
AI Panel
Evidence Panel

---

## Step 3

Generate components separately.

NEVER generate entire platform at once.

---

## Step 4

Review consistency.

Check:
- spacing
- typography
- hover states
- density
- motion

---

# Session Rules

One session = one objective.

GOOD:
- optimize table density
- redesign sidebar
- improve chart layout

BAD:
- redesign whole platform

---

# AI Prompting

Always reference:
- DESIGN.md
- COMPONENT_RULES.md
- PAGE_LAYOUTS.md

---

# Forbidden Workflow

Avoid:
- giant prompts
- endless patching
- 6-hour chat sessions
- random redesigns

---

# Recommended Stack

Framework:
Next.js

UI:
shadcn/ui

Styling:
TailwindCSS

State:
Zustand

Tables:
TanStack Table

Charts:
TradingView / Recharts

Motion:
Framer Motion (minimal)
