## Figma Design Implementation

### Trigger
Whenever the user says **"look at the design"** (or similar phrasing like "check the design", "use the Figma design", "pull up the design"), treat this as a Figma MCP workflow. Do not ask for clarification — proceed automatically through all steps below.

### Step-by-Step Workflow

1. **Connect & Discover**
   - Use the Figma MCP to connect to the active Figma file
   - Retrieve and list **all available pages** in the file
   - Inspect each page for frames, components, and assets

2. **Extract Design Specs**
   - Colors, typography (font family, size, weight, line height), spacing, border radius
   - Layout structure (grid, flex, absolute positioning)
   - Component hierarchy and grouping
   - **All exported assets**: logos, icons, images — use them directly, do not substitute with placeholders

3. **Build a React Prototype**
   - Scaffold an interactive React app using only **React and ReactDOM** (already available in the environment)
   - **Do not run `npm install`** for any package that has peer dependencies — if a library requires peer deps, skip it and implement the functionality manually
   - For **charts or graphs**: use `recharts` only if it can be added without peer dependency conflicts; otherwise implement a lightweight SVG chart directly in React
   - For **icons**: use **inline SVG only** — do not import any icon library
   - Wire up basic interactivity (tab switching, modal open/close, navigation state) so the prototype feels clickable
   - Do **not** add features not present in the design

4. **Design Fidelity Rules**
   - Match the Figma color palette exactly — use CSS variables derived from the design tokens
   - Match typography exactly — import Google Fonts via a `<link>` tag or use system fonts as specified in the design
   - Use the **exact logos and images** exported from Figma; never substitute with emoji, text, or generic SVGs
   - Respect spacing and layout proportions from the Figma frames
   - If the design has multiple pages/flows, implement each as a route or view in the prototype

5. **Output**
   - A single self-contained React app (or multi-file if complexity warrants it)
   - Include a brief comment at the top of the main file listing which Figma pages were implemented
   - If anything in the design is ambiguous, make the most reasonable assumption and note it in a comment — do not stop to ask