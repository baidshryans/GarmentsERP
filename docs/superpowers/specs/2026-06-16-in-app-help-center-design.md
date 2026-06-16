# In-App Help Center — Design Spec

**Date:** 2026-06-16
**Status:** Approved (design), pending implementation plan
**Author:** baidshryans + Claude

## 1. Goal

Integrate the existing user manual (`docs/USER_MANUAL.md`, ~3,239 lines, 25 chapters) into the ERP frontend as a **searchable, navigable Help Center**, so a user can:

- **Find** how to do a specific entry by searching natural phrases ("how to record a gold scheme payment").
- **Learn** how the overall ERP operates, module by module.
- **Understand** workflows visually via Mermaid diagrams embedded in the manual.

## 2. Decisions (locked during brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Content source / sync | **Single source of truth** — `docs/USER_MANUAL.md` bundled into the frontend at build time. No backend. |
| 2 | Entry point | **Global `?` button in the header** (`src/breadCrumbDecor.jsx`). No sidebar item, no per-page context help, no Ctrl+K (this pass). |
| 3 | Layout | **Drawer + full page.** `?` opens a right slide-over for quick search; an "Open full page →" link goes to a full Help Center at `/help`. |
| 4 | Diagram tech | **Mermaid**, authored as ` ```mermaid ` fenced blocks **inside** `USER_MANUAL.md`; rendered to SVG in-app, lazy-loaded. |
| 5 | Diagram scope | **All workflow chapters** (~20+ diagrams across the 25 chapters). |
| 6 | Search | **Full-text fuzzy + in-page highlighting** (fuse.js) with next/prev match navigation. |

## 3. Architecture & Data Flow

```
docs/USER_MANUAL.md   ← canonical, human-edited (Mermaid blocks live here too)
        │  npm "predev"/"prebuild" runs scripts/sync-manual.mjs (copy)
        ▼
frontend/src/help/manual.generated.md   ← gitignored, imported via Vite ?raw
        │  parsed ONCE at app load
        ▼
useManual()  →  { toc[], sections[], search(query) }
        │
        ├──► HelpDrawer   (global ? in Header → right slide-over: search + content + "Open full page →")
        └──► HelpCenter   (route /help, /help#<section-id>: TOC sidebar + content + search)
```

- **Single source of truth:** The frontend never holds a hand-maintained copy. `scripts/sync-manual.mjs` (Node, zero deps) copies the canonical manual into `frontend/src/help/manual.generated.md`. Wired into `package.json` `predev` and `prebuild` so it runs automatically. The generated file is **gitignored**.
- **Offline / no backend:** The manual is bundled into the JS via Vite's `?raw` import. No API surface, no auth, works if the backend is down.
- **Parse once:** On first use, the raw markdown is parsed into a chapter/section tree and a search index, memoized for the session.

## 4. Components

Each unit is small and single-purpose, communicating via well-defined props/returns.

### Library / logic
- **`src/help/manual.js`** — `parseManual(raw)` → `{ toc, sections }`.
  - Splits on `## N. Title` (chapters) and `### x.y Title` (sections).
  - `slugify(heading)` derives stable IDs from the existing numbering: `"## 14. Gold Scheme Management"` → `14-gold-scheme-management`; `"### 14.3 Recording a Payment"` → `14-3-recording-a-payment`.
  - Each section: `{ id, chapterId, title, level, markdown, plainText, headingPath }`.
- **`src/help/markdown.js`** — `renderMarkdown(md)` → sanitized HTML string using `marked` + `DOMPurify`. Mermaid code blocks are left as `<pre class="mermaid-src">…</pre>` placeholders for `MarkdownView` to hydrate. DOMPurify config allows SVG (so rendered mermaid output survives) but strips scripts.
- **`src/help/helpSearch.js`** — builds a fuse.js index over `{ title, plainText }`; `search(query)` returns ranked `{ section, snippet, matchIndices }`. Snippet = window of text around the first body match.
- **`src/help/useManual.js`** — React hook/context: parses the manual once (memoized module-level), exposes `{ toc, sections, getSection(id), search }`.

### UI
- **`src/help/MarkdownView.jsx`** — takes a section (or whole-chapter) markdown, renders sanitized HTML, then finds `.mermaid-src` blocks and mounts `MermaidDiagram` for each. Accepts an optional `highlightTerms` prop to wrap matches in `<mark>` and expose match elements for next/prev navigation. Styled with Tailwind typography.
- **`src/help/MermaidDiagram.jsx`** — `React.lazy` / dynamic `import('mermaid')`; renders the given mermaid source to SVG on mount; shows a lightweight fallback while loading; renders the raw code in a `<details>` if mermaid fails.
- **`src/help/HelpButton.jsx`** — the `?` icon button; placed in `src/breadCrumbDecor.jsx` (Header). Toggles `HelpDrawer`.
- **`src/help/HelpDrawer.jsx`** — right slide-over (reuses existing UI primitives / Tailwind). Contains: search input (debounced, full-text), result list (chapter → snippet), selected-section `MarkdownView`, and an "Open full page →" link that `navigate('/help#'+id)` and closes the drawer.
- **`src/help/HelpCenter.jsx`** — page at `/help`. Left: TOC (chapters → sections, collapsible). Center: `MarkdownView` of the active section/chapter. Top: search (same `helpSearch`). Reads `location.hash` to deep-link and scroll. Honors `highlightTerms` from a `?q=` param when navigated from search.

### Wiring
- **`src/App.jsx`** — register `{ path: "help", heading: "Help & Manual", component: <HelpCenter /> }` in `appRoutes` (route only; not added to sidebar `navData`).
- **`src/breadCrumbDecor.jsx`** — mount `HelpButton` (+ `HelpDrawer`) in the header so it's available on every page.

## 5. Search Behavior (full-text + highlight)

1. User types in drawer or Help Center search.
2. `helpSearch.search(q)` returns ranked sections with a snippet showing the match in context.
3. Selecting a result opens that section and passes the query terms as `highlightTerms`.
4. `MarkdownView` wraps every matched term in `<mark>` and renders a small **"N matches ▲ ▼"** control that scrolls between hits.

## 6. Diagrams (Mermaid)

- Authored inline in `USER_MANUAL.md` as ` ```mermaid ` blocks, one workflow per process chapter. Examples:
  - **Sales:** sale → invoice → payment/receipt.
  - **Purchase:** PO → goods receipt → purchase voucher.
  - **Manufacturing:** karigar issue → receive → QC → stock (branching).
  - **Gold Scheme:** enroll → pay (×N) → mature → redeem→sale (branch: cancel→settlement).
  - **Accounting:** voucher → double-entry → ledgers/trial balance.
  - …and the remaining workflow chapters.
- **Lazy loading:** mermaid (~1MB) is dynamically imported only when a diagram renders; the entire `/help` route and drawer content are code-split so the main app bundle is unaffected.
- Mermaid theme initialized to match the app (neutral/light), `securityLevel: 'strict'`.

## 7. New Dependencies

- `marked` — markdown → HTML.
- `dompurify` — sanitize rendered HTML (defense-in-depth; manual is trusted but we still sanitize).
- `mermaid` — diagram rendering (lazy).
- `@tailwindcss/typography` — clean prose styling for the manual (the project has no typography plugin today). If adding the plugin is undesirable, fall back to a hand-rolled `.manual-prose` stylesheet.
- `fuse.js` — **already installed.**

## 8. Implementation Phases

1. **Plumbing** — `sync-manual.mjs` + package.json hooks + `manual.js` parser + `markdown.js` + `helpSearch.js` + `useManual.js`. Renders the existing manual as-is (no diagrams yet).
2. **UI** — `HelpButton` in Header, `HelpDrawer`, `HelpCenter` route `/help`, deep-link/hash handling.
3. **Content** — author Mermaid workflow diagrams into every process chapter of `USER_MANUAL.md` (parallelizable across chapters).
4. **Polish** — in-page highlight + next/prev, `?q=` deep links, typography, empty/error states, mobile width for the drawer.

## 9. Testing

- **Unit (parser):** `parseManual` yields the right chapter/section counts; slug IDs are stable and collision-free; mermaid blocks preserved.
- **Unit (search):** sample queries ("scheme payment", "barcode split", "depreciation") return the expected section in the top results.
- **Component:** `MarkdownView` renders headings/lists/tables; `MermaidDiagram` mounts without throwing and degrades gracefully on bad syntax; `HelpDrawer` search → select → render flow; highlight terms produce `<mark>` and next/prev moves through them.
- **Manual/visual:** open `?` from a module page, search "record scheme payment", confirm jump to §14.x with diagram; "Open full page" lands on `/help#…` scrolled to the section.
- **Build:** `npm run build` runs the sync step and produces a bundle that does **not** eagerly include mermaid (verify via chunk output).

## 10. Out of Scope (YAGNI)

Per-page context-sensitive help, Ctrl+K command palette, sidebar nav item, backend-served content/API, in-app manual editing, PDF export, internationalization, offline PWA caching. All are straightforward to add later on top of this framework.

## 11. Risks / Notes

- **Mermaid bundle size** — mitigated by dynamic import + route code-split. Verified in the build test.
- **Heading-numbering dependency** — slug IDs rely on the manual's `N.` / `x.y` numbering. The parser must handle headings without numbers gracefully (fall back to text-slug). Keep numbering consistent when editing the manual.
- **Manual outside frontend root** — solved by the copy step rather than a cross-root Vite import, avoiding `server.fs.allow` fragility.
- **Spec location** — `docs/superpowers/` is gitignored in this repo; this spec is force-added as an intentional deliverable.
