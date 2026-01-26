# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

illogical is a macOS Logic Pro plugin manager built with PySide6 and Briefcase.
It uses `logic-plugin-manager` for Audio Units management and `pyqt-liquidglass` for UI styling.

## Development Commands

```bash
# Type checking
ty check

# Linting and formatting
ruff format
ruff check --fix
```

NEVER run briefcase or any run commands by yourself

## Custom Libraries

This project uses two custom libraries. **Always fetch their documentation via Context7 before working with them:**

- `logic-plugin-manager` - Audio Units plugin management
- `pyqt-liquidglass` - macOS liquid glass UI effects for Qt

## Code Principles

- **Simplicity**: Write simple, straightforward code
- **Readability**: Make code easy to understand
- **Performance**: Consider performance without sacrificing readability
- **Maintainability**: Write code that's easy to update
- **Reusability**: Create reusable components and functions
- **Less Code = Less Debt**: Minimize code footprint
- **NEVER write comments** - code should be self-documenting

## Context7 Usage

Use Context7 MCP tools to fetch up-to-date documentation:
1. Call `resolve-library-id` with the library name to get its ID
2. Call `query-docs` with the library ID and your question
