# Alert Card Redesign

## Overview
Completely redesigned the alert cards in the Cyber-Lighthouse dashboard to remove the collapse/expand functionality and improve the presentation with clear, structured sections for Alert, Impact, and Tags.

---

## What Changed

### ❌ Removed Features
- **Collapse/Expand functionality** - Alerts are now always fully visible
- **"Auto-collapse old" toggle** - No longer needed
- **Expand/collapse chevron icon** - Removed from header
- **Opacity for old alerts** - All alerts now have equal visibility

### ✅ New Design

**Alert cards now have a clean, structured layout with 4 distinct sections:**

```
┌────────────────────────────────────────────────────────────┐
│  [🔴 CRITICAL]  [🔗 3 sources]  [📅 2026-04-04]     [🔖] │
│                                                            │
│  Critical Cisco IMC auth bypass gives attackers Admin      │
│  access                                                     │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │ 🚨 Alert                                            │   │
│  │ Cisco patched a critical IMC authentication bypass │   │
│  │ allowing unauthenticated attackers to gain admin   │   │
│  │ access.                                             │   │
│  ├────────────────────────────────────────────────────┤   │
│  │ 💥 Impact                                           │   │
│  │ Organizations deploying Cisco IMC systems face     │   │
│  │ full administrative compromise.                     │   │
│  ├────────────────────────────────────────────────────┤   │
│  │ 🏷️ Tags                                             │   │
│  │ [#Cisco] [#AuthBypass] [#CriticalVuln] [#Patch]    │   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
│  🔗 Sources:                                               │
│  BleepingComputer: https://www.bleepingcomputer.com/...   │
└────────────────────────────────────────────────────────────┘
```

---

## Section Breakdown

### 1. **Header Section** (Top)
**Layout:** Flexbox with title, badges, and bookmark

**Elements:**
- **Alert Title** - Bold, prominent white text
- **Severity Badge** - Color-coded with icon
  - 🔴 Critical (red)
  - 🟠 High (orange)
  - 🟡 Medium (yellow)
  - 🟢 Low (green)
- **Multi-Source Badge** - Purple badge showing source count
- **Date Badge** - Calendar icon with date
- **Bookmark Button** - Icon button (top-right corner)

**Design:**
```
┌──────────────────────────────────────────────┐
│ Critical Cisco IMC auth bypass...      [🔖] │
│ [🔴 CRITICAL] [🔗 3 sources] [📅 2026-04-04]│
└──────────────────────────────────────────────┘
```

---

### 2. **Tags Section** (Below Header)
**Layout:** Flexible wrapping tag badges

**Features:**
- Up to 8 tags displayed (increased from 5)
- Clickable tags that filter articles
- Each tag has a small tag icon
- Hover effect changes background color
- Tags are in blue badges with borders

**Design:**
```
┌──────────────────────────────────────────────┐
│ [🏷️ Cisco] [🏷️ AuthBypass] [🏷️ Critical]    │
│ [🏷️ IMC] [🏷️ PatchAvailable]                │
└──────────────────────────────────────────────┘
```

---

### 3. **Analysis Section** (Alert/Impact/Tags)
**Layout:** Structured card with sections

**Three Sub-Sections:**

#### **🚨 Alert** (Red header)
- What the threat is
- Active exploitation or vulnerability details
- Displayed in bright text (slate-200)

#### **💥 Impact** (Orange header, separated by border)
- Who/what is affected
- Potential damage or risk
- Displayed in normal text (slate-300)

#### **🏷️ Tags** (Blue header, separated by border)
- Clickable tag badges
- Rendered as small blue badges
- Can filter alerts by clicking

**Design:**
```
┌─────────────────────────────────────────────┐
│ 🚨 Alert                                     │
│ Cisco patched a critical IMC auth bypass    │
│ allowing unauthenticated attackers access    │
│ ──────────────────────────────────────────── │
│ 💥 Impact                                    │
│ Organizations face full administrative       │
│ compromise of IMC systems                    │
│ ──────────────────────────────────────────── │
│ 🏷️ Tags                                      │
│ [#Cisco] [#AuthBypass] [#Critical] [#Patch]  │
└─────────────────────────────────────────────┘
```

---

### 4. **Sources Section** (Bottom)
**Layout:** List of source links

**Features:**
- Source name in gray
- Clickable links open in new tab
- Truncated URLs with hover underline
- Multiple sources shown if alert is deduplicated

**Design:**
```
┌─────────────────────────────────────────────┐
│ 🔗 Sources:                                  │
│ BleepingComputer: https://www.bleepingc...  │
│ SANS_ISC: https://isc.sans.edu/diary/...    │
└─────────────────────────────────────────────┘
```

---

## Visual Design

### Color-Coded Borders
Alert cards have severity-based border colors:

| Severity | Border Color | Hover Border |
|----------|-------------|----------------|
| Critical | Red (50%) | Red (70%) |
| High | Orange (40%) | Orange (60%) |
| Medium | Yellow (30%) | Yellow (50%) |
| Low | Slate (50%) | Slate (60%) |

### Hover Effects
- **Shadow**: Increases on hover (`hover:shadow-2xl`)
- **Border**: Becomes more opaque
- **Smooth transition**: 300ms duration

### Spacing
- **Card padding**: 6 units (24px)
- **Section spacing**: 4 units (16px)
- **Internal section padding**: 4 units (16px)

---

## Technical Implementation

### Files Modified

**`static/index.html`** (lines 415-500):
- Removed collapse/expand functionality
- Redesigned card layout with 4 sections
- Changed from clickable header to static display
- Moved bookmark button to top-right corner
- Enhanced tag display (up to 8 tags)
- Improved source links section

**`static/js/app.js`**:
- Added `renderAlertAnalysis()` function
  - Detects 🚨 ALERT / 💥 IMPACT / 🏷️ TAGS format
  - Creates structured HTML with sections
  - Converts tags to clickable badges
  - Falls back to markdown rendering for other formats
- Exposed `filterByTag` globally for onclick handlers
- Removed `collapseOldAlerts` references

### CSS Classes Used

**Card Container:**
```css
rounded-xl border shadow-lg transition-all duration-300
bg-gradient-to-br from-slate-800 to-slate-900
```

**Analysis Box:**
```css
bg-slate-900/50 border border-slate-700/50 rounded-lg
```

**Tag Badges:**
```css
px-3 py-1 rounded-full text-xs font-medium
bg-blue-500/15 text-blue-300 border border-blue-500/25
cursor-pointer hover:bg-blue-500/25 transition-all duration-200
```

---

## Benefits

### For Users
1. **Faster Scanning** - All info visible immediately
2. **Clear Structure** - Alert, Impact, Tags clearly separated
3. **Better Hierarchy** - Severity stands out with colors
4. **Quick Filtering** - Click tags directly from cards
5. **Consistent Layout** - No hidden content

### For Analysts
1. **Efficient Triage** - See all details at a glance
2. **Better Context** - Impact section shows affected assets
3. **Faster Navigation** - Tags filter without leaving page
4. **Multi-Source Visibility** - Source count badge shows coverage

### For Performance
1. **Simpler DOM** - No expand/collapse state management
2. **Fewer Click Handlers** - Reduced event listeners
3. **Better Rendering** - Vue doesn't track expand states

---

## Comparison: Before vs After

### Before
```
┌──────────────────────────────┐
│ Title...              [▼]   │
│ [Tags...]                    │
│ Date         [Bookmark]      │
└──────────────────────────────┘
  ↓ Click to expand
┌──────────────────────────────┐
│ [Analysis text...]           │
│ Sources:...                  │
└──────────────────────────────┘
```

### After
```
┌──────────────────────────────┐
│ Title             [🔖]       │
│ [Severity] [Sources] [Date]  │
│ [Tags...]                    │
│ ┌──────────────────────────┐│
│ │ 🚨 Alert: ...            ││
│ │ 💥 Impact: ...           ││
│ │ 🏷️ Tags: #Tag #Tag      ││
│ └──────────────────────────┘│
│ Sources:...                 │
└──────────────────────────────┘
```

---

## How to Use

1. **Open Alerts tab** at http://localhost:8000
2. **Scan alert cards** - All information visible
3. **Read sections**:
   - Header: Title, severity, sources, date
   - Tags: Click to filter
   - Analysis: Alert details, impact, tags
   - Sources: Click to visit original article
4. **Bookmark important alerts** with star icon
5. **Filter by severity** using chips at top

---

## Future Enhancements

Potential improvements:
- [ ] Add "Copy alert" button for sharing
- [ ] Add "Share to Teams/Slack" button
- [ ] Add timeline view for related alerts
- [ ] Add priority flag (star/flag icon)
- [ ] Add assignee field for team workflows
- [ ] Add status tracking (new/acknowledged/resolved)
