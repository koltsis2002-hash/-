# CLAUDE.md

This file provides guidance for AI assistants (Claude and others) working in this repository.

---

## Repository Status

The repository holds the 2026 business-insurance brochure of Χρήστος Κόλτσης (Insurance & Financial Advisor), kept as HTML/CSS and printed to PDF.

---

## Project Overview

- **What it does:** Source and print pipeline for the Greek A4 brochure «Επιχειρηματική Ασφάλιση & Στρατηγικός Σχεδιασμός 2026».
- **Primary language(s):** HTML/CSS (Greek content), a small Node.js build script.
- **Key dependencies:** `playwright-core` (prints the PDF with Chromium), `@fontsource/noto-sans` and `@fontsource/noto-sans-display` (embedded fonts).

---

## Repository Structure

```
/
├── CLAUDE.md                                # This file — AI assistant guidance
└── brochure-2026/
    ├── index.html                           # All 10 A4 pages, inline CSS
    ├── assets/logo-full.png, logo-mark.png  # Transparent logos
    ├── build.mjs                            # Renders index.html to PDF, fails if a page overflows
    └── Epixeirimatiki-Asfalisi-2026.pdf     # Built output (committed)
```

---

## Development Workflow

### Branching Strategy

- `main` — production-ready code; never push directly
- `claude/<description>-<id>` — AI-generated changes
- `feat/<description>` — human feature branches
- `fix/<description>` — bug fix branches

### Commit Messages

Use the imperative mood, present tense, and keep the subject line under 72 characters:

```
Add user authentication module
Fix null pointer in payment handler
Refactor data pipeline for clarity
```

Do **not** include AI session URLs, task IDs, or issue references in the subject line unless the project explicitly requires it.

### Pull Requests

- All changes land via PR; no direct pushes to `main`
- AI-authored PRs should be created as **drafts** for human review
- PR descriptions should explain *why*, not just *what* changed

### Testing

There is no test suite. After changing the brochure, rebuild it and check the result:

```bash
cd brochure-2026
npm install
node build.mjs                                  # throws if any page overflows A4
pdfinfo Epixeirimatiki-Asfalisi-2026.pdf        # expect 10 A4 pages
pdftoppm -r 70 -png Epixeirimatiki-Asfalisi-2026.pdf /tmp/p   # inspect pages visually
```

Outside the cloud container, Chromium for Playwright may need `npx playwright install chromium` first.

---

## Code Conventions

### General

- Prefer editing existing files over creating new ones
- Do not add error handling for impossible scenarios — trust internal guarantees
- Three similar lines of code is better than a premature abstraction
- No half-finished implementations; a complete, simple solution beats an elegant, incomplete one

### Comments

- Default to **no comments**
- Only add a comment when the *why* is non-obvious: a hidden constraint, a subtle invariant, or a workaround for a known external bug
- Never write comments that restate what well-named identifiers already say
- No multi-paragraph docstrings or multi-line comment blocks

### Security

- Never commit secrets, credentials, `.env` files, or API keys
- Validate input only at system boundaries (user input, external APIs)
- Avoid command injection, XSS, SQL injection, and OWASP Top 10 vulnerabilities
- Use parameterized queries; never interpolate user input into SQL or shell commands

### File Naming

- Brochure sources use `kebab-case`; the PDF name is the transliterated Greek title.
- Greek all-caps text (eyebrows, cover title) is typed in capitals without accents; do not rely on `text-transform: uppercase`, which keeps the tonos.

---

## Environment Setup

```bash
git clone https://github.com/koltsis2002-hash/-.git
cd -/brochure-2026
npm install
node build.mjs
```

---

## Key Files & Entry Points

| File/Directory | Purpose |
|----------------|---------|
| `brochure-2026/index.html` | Brochure content and layout |
| `brochure-2026/build.mjs` | PDF build with overflow check |
| `brochure-2026/Epixeirimatiki-Asfalisi-2026.pdf` | Final brochure to share |

---

## AI Assistant Instructions

When working in this repository:

1. **Read this file first** before making changes
2. **Check the branch** — develop on the feature branch, never on `main`
3. **Prefer minimal changes** — do not refactor or clean up code outside the scope of the task
4. **No speculative features** — implement only what is explicitly requested
5. **Run tests** after every non-trivial change
6. **Update this file** if the codebase structure, conventions, or workflows change materially
7. **Create draft PRs** for all AI-authored changes; let a human merge

### Forbidden Actions

- Force-pushing to `main`
- Committing `.env` or credential files
- Skipping pre-commit hooks (`--no-verify`)
- Amending already-pushed commits
- Adding unused backward-compatibility shims or re-exports

---

## Updating This File

When the project evolves, update the relevant sections:

- Add the project overview once purpose and stack are decided
- Replace placeholder `TODO` blocks with real content
- Add language-specific linting/formatting commands
- Document any non-obvious architecture decisions
