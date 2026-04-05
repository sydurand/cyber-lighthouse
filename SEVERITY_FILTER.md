# Severity Filter for Alerts

## Overview
Added a comprehensive severity filter to the Alerts tab in the Cyber-Lighthouse dashboard.

## Features Implemented

### 1. **Severity Filter Chips**
- **Location**: Top of Alerts tab, below the header
- **Design**: Color-coded filter buttons with counts
- **Severity Levels**:
  - 🔴 **Critical** (red) - RCE, APT, ransomware, active exploitation
  - 🟠 **High** (orange) - Malware, exploits, phishing, supply chain
  - 🟡 **Medium** (yellow) - General threats, advisories  
  - 🟢 **Low** (green) - Informational, podcasts, routine updates

### 2. **Interactive UI Elements**
- Click any severity chip to filter alerts
- Active filter is highlighted with enhanced styling
- Count badges show how many alerts match each severity
- Clear filter button appears when a filter is active
- Empty state message when no alerts match the filter

### 3. **Visual Feedback**
- Filter chips change color when active:
  - Inactive: Semi-transparent background with border
  - Active: Solid color with shadow glow
- Real-time count updates on each filter button
- Active filter indicator shows current selection

### 4. **Reactive Behavior**
- Alerts automatically filter when severity is selected
- Reset pagination when filter changes
- Smooth transitions and animations
- Maintains other filters (tags, sources) alongside severity

## How to Use

1. **Open the Alerts tab** in the dashboard
2. **Look for the "Filter by Severity"** section below the header
3. **Click any severity chip** (All, Critical, High, Medium, Low)
4. **View filtered alerts** - only matching alerts are shown
5. **Clear the filter** by:
   - Clicking "All" button
   - Clicking the "Clear filter" link that appears

## Technical Details

### Frontend Changes

**`static/index.html`**:
- Added severity filter chip UI component
- Updated alert iteration to use `filteredAlerts` computed property
- Added empty state for when no alerts match filter
- Added active filter indicator

**`static/js/app.js`**:
- Added `filterSeverity` reactive state
- Added `filteredAlerts` computed property
- Added `getFilteredCount()` helper function
- Added watcher to reset pagination on filter change
- Exported new properties to template

### Backend Support

The backend already provides severity data via the `/api/alerts` endpoint:
```json
{
  "severity": "critical"
}
```

Severity is automatically detected using keyword analysis in `export_utils.py`:
- **Critical**: RCE, zero-day, APT, ransomware, active exploitation
- **High**: Malware, exploits, phishing, supply chain attacks
- **Medium**: General advisories, non-critical vulnerabilities
- **Low**: Informational content, podcasts, routine updates

## Example Usage Scenarios

### Scenario 1: Security Analyst Triage
1. Open dashboard in morning
2. Click "Critical" filter
3. Review only the most urgent threats
4. Take immediate action on critical items

### Scenario 2: Weekly Review
1. Switch between severity levels
2. Get overview of threat landscape distribution
3. Export critical alerts for management report

### Scenario 3: Focused Investigation
1. Filter to "High" severity
2. Click related tags to narrow down
3. Export filtered results for analysis

## Future Enhancements

Potential improvements:
- [ ] Multi-select severity filters (e.g., show Critical + High together)
- [ ] Severity filter in History tab
- [ ] Save filter presets
- [ ] Filter by severity range (e.g., "High and above")
- [ ] Date + severity combined filters
- [ ] Severity distribution chart

## Files Modified

```
✅ static/index.html     - Added severity filter UI
✅ static/js/app.js      - Added filter logic and state management
✅ export_utils.py       - Severity detection (already implemented)
✅ api/routes.py         - Severity field in responses (already implemented)
✅ api/models.py         - Severity field in models (already implemented)
```

## Testing

To test the severity filter:

1. Navigate to http://localhost:8000
2. Click on the "Alerts" tab
3. You should see severity filter chips at the top
4. Click "Critical" - only critical alerts should display
5. Click "All" or "Clear filter" to reset
6. Verify count badges update correctly

## Screenshot Description

The filter section appears as:

```
┌─────────────────────────────────────────────────────┐
│ 🔍 Filter by Severity:                              │
│                                                      │
│ [≡ All (25)] [☢ Critical (8)] [⚠ High (6)]         │
│ [⚠ Medium (7)] [ℹ Low (4)]                         │
│                                                      │
│ [🔴 CRITICAL] filter active    ✕ Clear filter       │
└─────────────────────────────────────────────────────┘
```

When "Critical" is selected, only alerts with severity=critical are shown.
