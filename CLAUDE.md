# CLAUDE.md

This file provides guidance for AI assistants (Claude and others) working in this repository.

---

## Repository Status

This repository is newly initialized and currently empty. This CLAUDE.md serves as the foundational conventions document. Update it as the codebase grows.

---

## Project Overview

> **TODO:** Fill in once the project has a defined purpose.
>
> - **What it does:** ...
> - **Primary language(s):** ...
> - **Key dependencies:** ...

---

## Repository Structure

> **TODO:** Update this section as directories and files are added.

```
/
├── CLAUDE.md          # This file — AI assistant guidance
└── ...                # Project files to be added
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

> **TODO:** Document the test runner, test file locations, and how to run tests once they exist.

Run tests before committing:

```bash
# Example — replace with actual commands once defined
npm test        # Node.js projects
pytest          # Python projects
go test ./...   # Go projects
```

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

> **TODO:** Define conventions once the primary language is chosen (e.g., `snake_case.py`, `camelCase.js`, `kebab-case.ts`).

---

## Environment Setup

> **TODO:** Document setup steps once the project stack is defined.

```bash
# Clone
git clone https://github.com/koltsis2002-hash/-.git
cd -

# Install dependencies (example)
# npm install / pip install -r requirements.txt / go mod download

# Run locally (example)
# npm start / python main.py / go run .
```

---

## Key Files & Entry Points

> **TODO:** List important files once the project has content.

| File/Directory | Purpose |
|----------------|---------|
| *(empty)*      | *(to be filled in)* |

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
