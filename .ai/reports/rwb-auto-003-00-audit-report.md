
# RWB-AUTO-003-00: Current UI vs DESIGN.md Audit Report

## Audit Date
May 13, 2026

## Overview
This report documents the gaps between the current UI implementation and the DESIGN.md specification for the Research Workbench terminal aesthetic.

---

## 1. Color Scheme Gap Analysis

### Current Implementation
| Element | Current Value |
|---------|---------------|
| Light theme page background | #ffffff |
| Dark theme page background | #1e1e1e (VS Code style) |
| Dark theme card background | #252526 |
| Default accent (vscode scheme) | #007acc |
| Claude scheme accent (dark) | #f59e0b |

### Design Specification
| Element | Spec Value |
|---------|------------|
| Page background | #0D0F14 |
| Panel background | #151922 |
| Elevated background | #1B2130 |
| Sidebar background | #11151D |
| Primary accent | #F59E0B |
| Accent hover | #FBBF24 |
| Status positive | #00C896 |
| Status negative | #FF6B6B |
| Status neutral | #94A3B8 |
| Status warning | #F59E0B |
| Border primary | rgba(255,255,255,0.08) |
| Border soft | rgba(255,255,255,0.04) |

### Gaps Identified
- ❌ Dark theme uses VS Code #1e1e1e instead of deep blue-black #0D0F14
- ❌ Card backgrounds use #252526 instead of #151922
- ❌ No elevated background token (#1B2130)
- ❌ No sidebar-specific background token (#11151D)
- ❌ Missing border tokens (border-primary, border-soft)
- ❌ Missing full status color tokens
- ✅ Claude color scheme already has correct amber accent (#f59e0b)

---

## 2. Typography & Font Usage Audit

### Current Implementation
| Element | Current Setting |
|---------|-----------------|
| UI font | System font stack (-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto...) |
| Mono font (places used) | "SF Mono", "Cascadia Code", "Fira Code", Consolas, monospace |
| Numeric table columns | Already use monospace font |
| Prices/percentages | Some use mono, not all consistently |

### Design Specification
| Element | Spec Value |
|---------|------------|
| UI font | Inter |
| Data/mono font | JetBrains Mono |
| Font sizes | xs:12px, sm:14px, base:16px, lg:18px, xl:20px, 2xl:24px |
| Font weights | normal:400, medium:500, semibold:600 |

### Rules from DESIGN.md
ALL of the following must use mono font:
- Prices
- Percentages
- Timestamps
- Volume
- Market caps

### Gaps Identified
- ❌ Inter not specified as UI font
- ❌ JetBrains Mono not specified as mono font
- ❌ No font size tokens (text-xs through text-2xl)
- ❌ No font weight tokens
- ⚠️ Numeric data uses mono but not consistently JetBrains Mono specifically
- ✅ Table numeric columns already use monospace (good foundation)

---

## 3. Layout Density & Spacing Audit

### Current Implementation
| Element | Current Setting |
|---------|-----------------|
| Table row height | Not explicitly set (compact but no token) |
| Card border radius | 4px-6px |
| Button border radius | 4px |
| Sidebar width | Fixed 48px icon strip |

### Design Specification
| Element | Spec Value |
|---------|------------|
| Table row height (default) | 32px |
| Table row height (compact) | 28px |
| Card border radius | 16px |
| Button border radius | 10px |
| Input border radius | 10px |
| Sidebar expanded width | 240px |
| Sidebar collapsed width | 72px |
| Spacing tokens | 1:4px, 2:8px, 3:12px, 4:16px, 5:20px, 6:24px, 8:32px |

### Gaps Identified
- ❌ No table row height tokens
- ❌ Border radius too small (4px vs 16px cards, 10px buttons)
- ❌ No spacing tokens system
- ❌ Sidebar is fixed 48px instead of expandable 240px/72px
- ✅ Layout is already dense and operational (philosophy followed)

---

## 4. Component Behavior Audit

### Cards
| Aspect | Current | Spec |
|--------|---------|------|
| Hover effect | Subtle brighten | ✅ Subtle brighten only |
| Floating cards | None | ✅ No floating cards |
| Border radius | 4px-6px | ❌ Should be 16px |

### Tables
| Aspect | Current | Spec |
|--------|---------|------|
| Compact rows | Yes | ✅ Yes |
| Sticky header | Not implemented | ❌ Needs sticky header |
| Mono numbers | Yes | ✅ Yes (partial) |
| Numeric alignment | Mixed | ❌ All numeric should be right-aligned |
| Sortable | Some | ⚠️ Partial |
| Filterable | No | ❌ Missing |

### Buttons
| Aspect | Current | Spec |
|--------|---------|------|
| Variants | Primary, Secondary | ✅ Implemented |
| Ghost, Danger | Missing | ❌ Missing |
| Border radius | 4px | ❌ Should be 10px |

### Sidebar
| Aspect | Current | Spec |
|--------|---------|------|
| Width | Fixed 48px | ❌ Should be expandable 240px/72px |
| Active state | Basic highlight | ❌ Needs darker background + accent border + subtle glow |

### Search Bar
| Aspect | Current | Spec |
|--------|---------|------|
| Always visible | Yes | ✅ Yes |
| Command palette feel | Basic | ⚠️ Could be improved |

### Empty States
| Aspect | Current | Spec |
|--------|---------|------|
| Operational feel | Yes | ✅ Already operational, not cutesy |

### AI Insight Panels
| Aspect | Current | Spec |
|--------|---------|------|
| Structure | Signal/confidence/evidence/action | ✅ Already follows spec structure |
| Chatbot style | No | ✅ No chatbot style |

---

## 5. Motion & Animation Audit

### Current Implementation
- fadeIn animation (opacity + translateY 8px)
- Subtle transitions
- No bounce or floating effects observed

### Design Specification
**Allowed:**
- fade transitions
- hover brighten
- subtle pulse

**Forbidden:**
- bounce
- floating motion
- elastic animation
- parallax

### Gaps Identified
- ✅ No forbidden animations currently used
- ⚠️ Should formalize motion tokens (duration-fast, duration-normal, duration-slow)

---

## 6. Design Tokens Audit

### Tokens Missing from Current CSS
- `--bg-page`
- `--bg-panel`
- `--bg-elevated`
- `--bg-sidebar`
- `--border-primary`
- `--border-soft`
- `--text-primary` (exists but different name)
- `--text-secondary` (exists but different name)
- `--text-muted`
- `--accent-primary`
- `--accent-hover`
- `--status-positive`
- `--status-negative`
- `--status-neutral`
- `--status-warning`
- `--font-ui`
- `--font-mono`
- `--text-xs` through `--text-2xl`
- `--font-normal`, `--font-medium`, `--font-semibold`
- `--space-1` through `--space-8`
- `--radius-sm`, `--radius-md`, `--radius-lg`
- `--shadow-sm`, `--shadow-md`, `--shadow-lg`
- `--duration-fast`, `--duration-normal`, `--duration-slow`
- `--sidebar-width-expanded`, `--sidebar-width-collapsed`
- `--table-row-height`, `--table-row-height-compact`

### Tokens That Exist (Need Rename/Map)
- `--bg-body` → `--bg-page`
- `--bg-card` → `--bg-panel`
- `--radius` → `--radius-sm`
- `--radius-sm` → `--radius-sm`
- `--accent` → `--accent-primary`
- `--accent-hover` → `--accent-hover`
- `--success` → `--status-positive`
- `--danger` → `--status-negative`
- `--warning` → `--status-warning`

---

## 7. Charts Audit

### Current Implementation
- Chart.js and D3 integrations exist
- Current chart configuration uses theme colors

### Design Specification
Charts should resemble institutional trading systems:
- Dark backgrounds
- Muted grids
- Minimal labels
- High contrast data
- NO rainbow palettes

### Gaps Identified
- ⚠️ Chart configuration should be updated to use terminal aesthetic colors
- ⚠️ Ensure no rainbow palettes are used

---

## 8. Summary of Gaps by Priority

### High Priority Gaps
1. **Color scheme** - Update to deep blue-black terminal aesthetic
2. **Design tokens** - Implement complete token system from TOKENS.md
3. **Typography** - Implement Inter and JetBrains Mono fonts
4. **Border radius** - Update to 16px cards, 10px buttons/inputs
5. **Table alignment** - Right-align ALL numeric columns
6. **Density** - Formalize 32px/28px table row heights

### Medium Priority Gaps
1. **Chart styling** - Update for institutional look
2. **Motion tokens** - Formalize animation duration tokens
3. **Sidebar** - Make expandable (future scope, keep current for now)
4. **Table sticky header** - Implement sticky headers
5. **Button variants** - Add Ghost and Danger variants

### Low Priority Gaps
1. **Search bar polish** - More command palette feel
2. **Table filterable** - Add filtering
3. **Sidebar active state** - Enhance with glow

---

## 9. Good Parts Already Implemented

✅ **Amber accent already available** via "claude" color scheme  
✅ **Mono font already used** in many places for numeric data  
✅ **Dense layout philosophy** already followed (no decorative elements)  
✅ **All sections structurally implemented** in HTML  
✅ **Theme switching infrastructure** already exists  
✅ **Chart.js and D3 integrations** already in place  
✅ **AI panels follow structure** (signal/confidence/evidence/action)  
✅ **Empty states are operational**, not cutesy  
✅ **No forbidden animations** currently used  
✅ **No floating cards** in current implementation  

---

## 10. Implementation Recommendations

### Phase 1 (Tasks 01-02)
1. Add all design tokens to CSS
2. Update dark theme to use terminal color scheme
3. Make "claude" (amber) the default color scheme

### Phase 2 (Tasks 03-05)
4. Add Inter and JetBrains Mono fonts
5. Update border radius tokens
6. Implement spacing and density tokens

### Phase 3 (Tasks 06-08)
7. Update chart configurations
8. Ensure numeric table alignment
9. Refine motion/animations

### Phase 4 (Tasks 09-14)
10. Start dev server
11. Debug with Playwright
12. Verify all sections
13. Fix identified issues
14. Generate final report

---

## Conclusion

The current implementation has a solid foundation and already follows the terminal philosophy in terms of density and lack of decorative elements. The main gaps are in formalizing the design token system, updating the color scheme to the deep blue-black terminal aesthetic, implementing the correct fonts (Inter/JetBrains Mono), and adjusting border radii and table behavior.

The existing theme switching infrastructure makes this implementation straightforward - we can extend the current system rather than rewriting it.

**Audit Complete ✅**
