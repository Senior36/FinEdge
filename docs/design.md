# Design System & Style Guide: FinEdge Market Intelligence

## 1. Core Visual Identity

**Vibe:** Professional, clean, data-dense but breathable, institutional fintech aesthetic.
**Theme:** "Light Mode" main dashboard with a high-contrast "Dark Mode" sidebar.

### Color Palette

* **Primary Action (Blue):** `#2563EB` (Used for "Re-analyze", "Paper Trade" buttons, Logo icon)
* **Sidebar Background (Dark Navy):** `#0F172A` or `#020617`
* **Main Background (Off-White):** `#F8FAFC`
* **Card Background (White):** `#FFFFFF`
* **Success/Bullish (Green):** `#10B981` (Text) and `#DCFCE7` (Background Pills)
* **Neutral/Text (Dark Grey):** `#1E293B` (Headings)
* **Secondary Text (Light Grey):** `#64748B` (Labels, Meta-data)
* **Border/Divider:** `#E2E8F0`

### Typography

* **Font Family:** `Inter` or `SF Pro Display` (Clean, modern sans-serif).
* **Weights:**
    * *Bold (700):* Prices, Stock Symbols.
    * *Semi-Bold (600):* Navigation links, Card headers.
    * *Regular (400):* Body text, Labels.
    * *Medium (500):* Button text.

## 2. Layout Structure

**Global Layout:** Two-column layout.
1.  **Sidebar (Fixed Left):** Width approx 260px. Dark background. Full height.
2.  **Main Content (Fluid Right):** Light background. Padding approx 32px.

### Sidebar Specification

* **Logo Area:** "FinEdge" text (White, Bold) with a blue gradient square icon.
* **Navigation:** Vertical list.
    * *Idle State:* Text color `#94A3B8`, Icon `#94A3B8`.
    * *Active State:* Text color White, Icon White.
* **Footer Area:** "Alerts" (with Red `#EF4444` badge), "Settings", "Dark Mode" toggle at the bottom.

## 3. UI Component Library

### Cards (The "Stock Tile")

* **Shape:** `border-radius: 12px`.
* **Effect:** Subtle shadow `box-shadow: 0 1px 3px rgba(0,0,0,0.1)`.
* **Padding:** `24px`.
* **Internal Layout:**
    * **Header:** Flex row. Symbol (Left, Bold), Exchange Tag (Right, Grey Pill).
    * **Price Section:** Large font size for price. Green percentage text (+1.85%) next to it.
    * **Micro-Chart:** A smoothed line chart (Sparkline) in green, positioned below price or inline.
    * **Data Grid:** 2x2 or 1x2 grid for "Volume" and "P/E Ratio". Labels small/grey, values dark/bold.
    * **Indicators:** Horizontal stack of status pills.
        * *Sentiment:* Positive (Green text/Green BG).
        * *Technical:* BUY (Green filled pill) or NEUTRAL (Grey filled pill).

### Buttons & Actions

* **Primary Button:** Solid Blue (`#2563EB`). White text. `border-radius: 8px`. Medium font weight. (e.g., "Re-analyze", "Paper Trade").
* **Secondary Button:** White background. Grey Border (`#E2E8F0`). Dark text. (e.g., "Alert", "Export").
* **Tags/Pills:**
    * *Sector Tag:* Light Purple BG (`#F3E8FF`) with Purple text (`#7E22CE`) for "Real Estate".
    * *Exchange Tag:* Light Grey BG with Dark Grey text.

## 4. Page Specifics

### View A: Dashboard (Grid)

* Responsive Grid Layout (`grid-template-columns: repeat(auto-fill, minmax(300px, 1fr))`).
* Gap: `24px`.
* Each item is a "Stock Tile" (defined above).

## 5. Technical Implementation Notes

* Use CSS Flexbox for alignment.
* Use CSS Grid for dashboard layout.
* Charts can be implemented using Recharts or Chart.js styling to match the clean, green line style.
* Ensure high contrast between Sidebar (Dark) and Main Content (Light).
