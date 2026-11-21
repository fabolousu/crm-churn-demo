---
name: "CRM CCIAA - PROMOS (Baseline)"
colors:
  primary: "#176B3B"
  surface: "#FFFFFF"
  background: "#F7F7F5"
  textPrimary: "#14181F"
  textSecondary: "#5B6472"
  border: "#E5E0D6"
---
# Design System: CRM CCIAA - PROMOS (Baseline)

## 1. Visual Theme & Atmosphere
This is the baseline design for the CRM CCIAA PROMOS application. The interface presents a dense, data-heavy, professional workspace intended for internal agents. It uses light, warm-toned grays and off-whites for the background, creating a softer alternative to stark white, paired with crisp white surfaces for cards and content areas.

The overall feel is utilitarian but modern. Whitespace is kept compact to maximize data density on lists and forms, while subtle borders and soft shadows define structural boundaries without visual clutter.

## 2. Color Palette & Roles
### Primary Foundation
- **Base Background**: `#F7F7F5` (Warm light gray used for the main canvas)
- **Secondary Background**: `#FAFAF7` (Slightly lighter, used for nested areas or subtle highlights)
- **Content Surface**: `#FFFFFF` (Pure white for cards, panels, and forms)
- **Paper**: `#F6F4EF` (Root body background)

### Accent & Interactive
- **Primary Brand / Action**: `#176B3B` (Vibrant forest green for primary buttons, active links, and selected states)
- **Primary Action Hover**: `#14562F` (Darker green for button hover states)
- **Primary Action Focus**: `#1F8A4C` (Used in focus rings with varying opacity)
- **Action Background Light**: `#E7F4EC` (Very light green for active menu items and selected row backgrounds)
- **Selected Row Highlight**: `#F0F8F3` (Extremely light green for table row selection)
- **Legacy Accent Teal**: `#0F6B5C` (Used in the root radial gradient and some sliders)

### Typography & Text Hierarchy
- **Ink (Text Primary)**: `#14181F` (Near-black for headings and main body text)
- **Muted (Text Secondary)**: `#5B6472` (Slate gray for labels, timestamps, and secondary information)

### Functional States
- **Status Success (Interessato)**: Text `#176B3B`, Background `#E7F4EC`, Ring `#BFE3CD`
- **Status Warning (Da Contattare)**: Text `#8A4B08`, Background `#FBF1E2`, Ring `#EAD3B0`
- **Status Info (In Attesa)**: Text `#1D4E89`, Background `#E8F0FA`, Ring `#C6D8EE`
- **Status Default/Closed**: Text `#4C5563`, Background `#F1EFEA`, Ring `#DDD8CE`
- **Border / Line**: `#E5E0D6` (Used for all structural dividers and input borders)

## 3. Typography Rules
### Hierarchy & Weights
The application relies heavily on system sans-serif fonts for optimal readability and performance. Text sizing is generally small to accommodate high data density.
- **Main Headings**: `15px` to `18px`, `semibold`, `tracking-tight`. Used for page titles and major sections.
- **Subheadings**: `16px`, `semibold`. Used for modal titles.
- **Body Text**: `12.5px` or `13px`. The standard size for data rows, list items, and form inputs.
- **Small Info Text**: `11px` to `12px`, `medium` or `regular`. Used for counts, helper text, and secondary details.
- **Eyebrow / Overline**: `9.5px` to `10.5px`, `semibold`, `uppercase`, wide letter spacing (`tracking-[0.08em]` to `tracking-[0.14em]`). Used for table headers, section labels, and tag labels.

### Spacing Principles
Text spacing is compact. Line heights are standard tailwind defaults, but the small font sizes and tight margins ensure many rows of data fit on a single screen without requiring scrolling.

## 4. Component Stylings
### Buttons
- **Primary Buttons**: Background `#176B3B`, Text white, rounded (`rounded-md`), `12.5px` font size, `semibold`. They have a hover state of `#14562F` and a focus ring.
- **Secondary / Ghost Buttons**: Transparent background, text `#14181F` at 75% opacity, rounded (`rounded-md`), `12px` font size, `medium`. Hover state adds a subtle background (`bg-ink/[0.05]`) and solidifies the text color.
- **Tags / Chips**: Fully rounded (`rounded-full`), `11.5px` font, `medium`, with a 1px inner ring and a small colored dot indicator.

### Cards & Containers
- **Content Cards**: White background, `rounded-xl`, border `#E5E0D6`, with a subtle custom shadow (`0 1px 2px rgba(20, 24, 31, 0.04), 0 8px 24px -16px rgba(20, 24, 31, 0.18)`).
- **Secondary Panels**: Background `#FAFAF7`, `rounded-lg`, border `#E5E0D6`. Used for model info cards and filter bars.

### Navigation
- **Top Header**: `56px` height, sticky, white background with a bottom border.
- **Sidebar**: `248px` width, light gray background, sticky.
- **Nav Links**: Rounded `md`, `13px` font size, `medium`. Active state uses light green background (`#E7F4EC`) and green text (`#176B3B`). Inactive state is muted ink text with a subtle hover background.

### Inputs & Forms
- **Text Inputs / Selects**: Background `#FAFAF7` or `#F7F7F5`, `rounded-md` or `rounded-lg`, border `#E5E0D6`. Text is `12.5px` or `13px`.
- **Focus State**: Border changes to `#176B3B` (40% opacity), background becomes white, with a green focus ring (`#1F8A4C` at 20% or 30% opacity).
- **Checkboxes**: Custom green accent (`text-[#176B3B]`), `rounded`, with a green focus ring.

## 5. Layout Principles
### Grid & Structure
- **Max Width**: The main application wrapper is constrained to `1500px` centered.
- **Layout Model**: Flexbox is used for the shell (sidebar on the left, main content on the right).
- **Data Tables**: Full width (`w-full`), text left-aligned, with sticky headers or contained within a scrolling overflow container.

### Whitespace Strategy
- **Padding**: Moderate to tight padding. Cards typically use `px-4 py-3`. Table cells use `px-2 py-2.5` or `px-3 py-2.5` to maximize visible rows.
- **Gaps**: Flex gaps (`gap-2`, `gap-3`) are used extensively for spacing out action bars, icons, and tags.

### Alignment & Visual Balance
- Left-aligned text is standard for data readability.
- Action bars are typically split, with primary titles or views on the left and actions (search, columns, filters) on the right.

### Responsive Behavior & Touch
- **Mobile**: The sidebar collapses behind a hamburger menu (`WaffleIcon`). The max-width container takes up full space.
- **Desktop-First**: The UI is optimized for desktop usage (dense tables, hover actions, complex filters).

## 6. Design System Notes for Stitch Generation
### Language to Use
Describe the UI as a "dense, professional CRM dashboard with a light warm gray background, white content cards, and vibrant green primary actions." Emphasize "compact spacing", "data-heavy tables", and "uppercase tracking for small labels."

### Color References
- Primary Green: `#176B3B`
- Dark Ink Text: `#14181F`
- Muted Gray Text: `#5B6472`
- Warm Gray Canvas: `#F7F7F5`
- Structural Border: `#E5E0D6`

### Component Prompts
- **Primary Button**: "A small solid green button with rounded corners, white semi-bold text, and a slightly darker green hover state."
- **Status Chip**: "A pill-shaped tag with a light tinted background, colored text, a 1px inner border, and a small colored dot next to the label."
- **Data Table**: "A dense list view table with uppercase spaced-out headers, alternating row hover effects, and a light gray border between rows."

### Incremental Iteration
When updating this design, focus on keeping the data density high. Do not add excessive padding to tables or lists. Maintain the distinct visual hierarchy between the dark text and the muted, uppercase labels.