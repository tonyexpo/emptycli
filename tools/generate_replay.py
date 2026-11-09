#!/usr/bin/env python3
"""
Generate replay.json: a ~30 minute fictional agentic coding session for emptycli.

The session is entirely fictional. No network access, package installs or
deployments are performed: every tool call and command output is scripted.

Run:
    python3 tools/generate_replay.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

random.seed(20261109)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "replay.json"

THINK_CPS = 74.0
SAY_CPS = 96.0

META = {
    "title": "TuxPress · empty repo to production",
    "project": "TuxPress",
    "description": "Markdown-first publishing for developer teams",
    "model": "openrouter/deepseek-v4.1-flash-1017",
    "modelName": "DeepSeek V4.1 Flash 1017",
    "provider": "openrouter",
    "totalSeconds": 1800,
    "pricing": {
        "inputPerM": 0.28,
        "cachedInputPerM": 0.07,
        "outputPerM": 1.10,
    },
    "outro": "TuxPress is live · all checks green",
    "outroUrl": "https://tuxpress.dev",
}


class Meter:
    """Tracks a plausible growing context window and per-turn token usage."""

    def __init__(self, context: int = 11800) -> None:
        self.context = context
        self.turns = 0

    def turn(self, out_chars: int, result_chars: int = 0) -> dict[str, int]:
        self.turns += 1
        input_tokens = int(self.context)
        cached = int(input_tokens * 0.72)
        output = max(24, int(out_chars / 3.6))
        self.context = min(72000, self.context + output + int(result_chars / 3.8))
        return {"in": input_tokens, "cache": cached, "out": output}

    def compact(self, context: int = 12400) -> None:
        self.context = context


class Timeline:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.meter = Meter()

    def add(self, kind: str, gap: float = 0.0, ms: float = 0.0, **fields) -> dict:
        event: dict = {"kind": kind, "gap": round(max(0.0, gap), 3)}
        if ms > 0:
            event["ms"] = round(ms, 1)
        for key, value in fields.items():
            if value is None or value == "":
                continue
            event[key] = value
        self.events.append(event)
        return event

    def line(self, text: str, style: str = "plain", gap: float = 0.035) -> dict:
        return self.add("line", gap=gap, text=text, style=style)

    def phase(self, title: str, gap: float = 1.2) -> None:
        self.add("phase", gap=gap, text=title)

    def user(self, text: str, gap: float = 0.7) -> None:
        self.add("user", gap=gap, text=text)

    def think(self, text: str, gap: float = 0.45) -> None:
        ms = min(16000.0, max(2200.0, len(text) / THINK_CPS * 1000.0))
        usage = self.meter.turn(len(text))
        self.add("think", gap=gap, ms=ms, text=text, **usage)

    def say(self, text: str, gap: float = 0.55) -> None:
        ms = min(12000.0, max(1400.0, len(text) / SAY_CPS * 1000.0))
        usage = self.meter.turn(len(text))
        self.add("say", gap=gap, ms=ms, text=text, **usage)

    def note(self, text: str, style: str = "info", gap: float = 0.45) -> None:
        self.add("note", gap=gap, text=text, style=style)

    def todo(self, todos: list[tuple[str, str]], gap: float = 0.35) -> None:
        self.add(
            "todo",
            gap=gap,
            todos=[{"text": text, "status": status} for text, status in todos],
        )

    def todo_update(self, text: str, gap: float = 0.2) -> None:
        self.add("todo", gap=gap, text=text)


def usage_for_read(tl: Timeline, result_lines: list[str] | None = None) -> dict[str, int]:
    return tl.meter.turn(28, sum(len(line) for line in (result_lines or [])))


def read_file(
    tl: Timeline,
    path: str,
    *,
    lines: int | None = None,
    detail: str | None = None,
    preview: list[str] | None = None,
    gap: float = 0.3,
    ms: float = 240,
) -> None:
    preview = preview or []
    if detail is None:
        detail = f"{lines} lines" if lines else ""
    tl.add(
        "tool",
        gap=gap,
        tool="read",
        arg=path,
        detail=detail,
        status="ok",
        ms=ms,
        **usage_for_read(tl, preview),
    )
    for line in preview:
        tl.line(line, "output", gap=0.045)


def glob_files(tl: Timeline, pattern: str, files: list[str], *, gap: float = 0.28) -> None:
    tl.add(
        "tool",
        gap=gap,
        tool="glob",
        arg=pattern,
        detail=f"{len(files)} files",
        status="ok",
        ms=260,
        **tl.meter.turn(18, sum(len(file) for file in files)),
    )
    for file in files[:10]:
        tl.line(file, "path", gap=0.035)
    if len(files) > 10:
        tl.line(f"… {len(files) - 10} more files", "muted", gap=0.03)


def grep(
    tl: Timeline,
    pattern: str,
    matches: list[str],
    *,
    gap: float = 0.3,
    ms: float = 520,
) -> None:
    tl.add(
        "tool",
        gap=gap,
        tool="grep",
        arg=pattern,
        detail=f"{len(matches)} matches",
        status="ok",
        ms=ms,
        **tl.meter.turn(24, sum(len(match) for match in matches)),
    )
    for match in matches[:10]:
        tl.line(match, "output", gap=0.04)
    if len(matches) > 10:
        tl.line(f"… {len(matches) - 10} more matches", "muted", gap=0.03)


def write_file(
    tl: Timeline,
    path: str,
    content: str,
    *,
    show: int = 28,
    gap: float = 0.32,
    ms: float | None = None,
) -> None:
    lines = content.strip("\n").splitlines()
    if ms is None:
        ms = min(2400.0, 520.0 + len(lines) * 16.0)
    tl.add(
        "tool",
        gap=gap,
        tool="write",
        arg=path,
        detail=f"{len(lines)} lines",
        status="ok",
        ms=ms,
        add=len(lines),
        **tl.meter.turn(36, sum(len(line) for line in lines)),
    )
    for line in lines[:show]:
        tl.line("+ " + line if line else "+", "add", gap=0.024)
    if len(lines) > show:
        tl.line(f"+ … {len(lines) - show} more lines", "muted", gap=0.02)


def edit_file(
    tl: Timeline,
    path: str,
    hunks: list[dict],
    *,
    gap: float = 0.28,
    ms: float = 900,
) -> None:
    additions = sum(1 for hunk in hunks for sign, _ in hunk["lines"] if sign == "+")
    deletions = sum(1 for hunk in hunks for sign, _ in hunk["lines"] if sign == "-")
    tl.add(
        "tool",
        gap=gap,
        tool="edit",
        arg=path,
        detail=f"{len(hunks)} hunks",
        status="ok",
        ms=ms,
        add=additions,
        **{"del": deletions},
        **tl.meter.turn(
            30,
            sum(len(text) for hunk in hunks for _, text in hunk["lines"]),
        ),
    )
    for hunk in hunks:
        tl.line(hunk["header"], "hunk", gap=0.03)
        for sign, text in hunk["lines"]:
            style = {"+": "add", "-": "del", " ": "ctx"}[sign]
            tl.line(f"{sign} {text}", style, gap=0.018)


def bash(
    tl: Timeline,
    command: str,
    output: list[str | tuple[str, str]],
    duration: float,
    *,
    ok: bool = True,
    gap: float = 0.35,
    extra: str = "",
) -> None:
    parsed: list[tuple[str, str]] = []
    for item in output:
        if isinstance(item, tuple):
            parsed.append(item)
        else:
            parsed.append((item, "output"))

    result_chars = sum(len(text) for text, _ in parsed)
    tl.add(
        "tool",
        gap=gap,
        tool="bash",
        arg=command,
        status="running",
        **tl.meter.turn(42, result_chars),
    )

    per_line = duration / max(1, len(parsed))
    for text, style in parsed:
        tl.line(text, style, gap=max(0.012, per_line))

    status = f"{'✓' if ok else '✗'} {fmt_duration(duration)}"
    if extra:
        status += f" · {extra}"
    tl.line(status, "ok" if ok else "err", gap=0.14)


def fetch(tl: Timeline, url: str, detail: str, *, ms: float = 760) -> None:
    tl.add(
        "tool",
        gap=0.28,
        tool="fetch",
        arg=url,
        detail=detail,
        status="ok",
        ms=ms,
        **tl.meter.turn(20, len(detail)),
    )


def task(tl: Timeline, label: str, detail: str, *, ms: float = 2400) -> None:
    tl.add(
        "tool",
        gap=0.35,
        tool="task",
        arg=label,
        detail=detail,
        status="ok",
        ms=ms,
        **tl.meter.turn(60, len(detail)),
    )


def browser(tl: Timeline, url: str, detail: str, *, ms: float = 1100) -> None:
    tl.add(
        "tool",
        gap=0.3,
        tool="browser",
        arg=url,
        detail=detail,
        status="ok",
        ms=ms,
        **tl.meter.turn(18, len(detail)),
    )


def card(tl: Timeline, title: str, rows: list[tuple[str, str]], *, gap: float = 0.35) -> None:
    tl.line("╭─ " + title + " " + "─" * max(4, 58 - len(title)), "accent", gap=gap)
    for text, style in rows:
        tl.line("│ " + text, style, gap=0.045)
    tl.line("╰" + "─" * 60, "rule", gap=0.05)


def fmt_duration(seconds: float) -> str:
    if seconds < 10:
        return f"{seconds:.1f}s"
    if seconds < 60:
        return f"{seconds:.0f}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


THINKING_STACK = (
    "The repository only contains a README and an Apache-2.0 license, so there is no "
    "existing architecture to preserve. I'll pick a boring, production-friendly stack: "
    "Next.js App Router with TypeScript, Tailwind v4 for the design system, Drizzle + "
    "Postgres for persistence, Better Auth for magic links, and Vitest/Playwright for "
    "verification. Keeping everything in one deployable app removes an unnecessary API "
    "boundary for a product at this stage."
)

THINKING_DESIGN = (
    "The landing page should feel terminal-native without becoming a gimmick. I'll use a "
    "near-black canvas, a single cyan accent, Geist Mono for labels and Geist Sans for "
    "prose. The hero gets one strong promise and a live-looking product frame; the feature "
    "grid explains outcomes rather than implementation. Motion stays subtle and respects "
    "`prefers-reduced-motion`."
)

THINKING_SCHEMA = (
    "Posts need a stable public identity and a private editorial workflow. A UUID primary "
    "key keeps references safe, while a unique slug is the public handle. Status is an "
    "enum-like text column with a check constraint added in the migration. Published posts "
    "also store `publishedAt` so the marketing site can order by real publication time. "
    "I'll index (status, published_at) to keep the public feed cheap."
)

THINKING_AUTH = (
    "Magic links avoid password storage and are a good fit for developer teams. Better Auth "
    "can own users, sessions and verification tokens through the Drizzle adapter. The "
    "dashboard is protected in middleware; API handlers still re-check the session because "
    "middleware is not a security boundary. E2E tests will seed a session through a "
    "test-only helper gated by `NODE_ENV !== 'production'`."
)

THINKING_TESTS = (
    "I want the test pyramid to fail for the right reasons. Unit tests cover slug generation "
    "and the rate limiter; Playwright covers the marketing page, the magic-link login and the "
    "first-publish flow. The flaky part will be auth, so I'll introduce a deterministic test "
    "login endpoint instead of scraping a fictional inbox. That keeps the product path real and "
    "the test path explicit."
)

THINKING_CI = (
    "CI should mirror the local gates exactly: install from the lockfile, lint, typecheck, "
    "unit tests, Playwright with a Postgres service, then a production build. Playwright needs "
    "the app running, so the job starts `pnpm start` after the build instead of `next dev`. "
    "Secrets stay in GitHub Actions; the workflow only needs `DATABASE_URL`, "
    "`BETTER_AUTH_SECRET` and `BETTER_AUTH_URL`."
)


def build_replay() -> Timeline:
    tl = Timeline()

    # ------------------------------------------------------------------
    # ACT I — recon and plan
    # ------------------------------------------------------------------
    tl.phase("Recon · empty repository", gap=0.9)
    tl.user(
        "Build TuxPress — a Markdown-first publishing platform for developer teams.\n"
        "Marketing site: hero, features, pricing, FAQ, footer. Dark, terminal-inspired, but clean.\n"
        "App: magic-link auth, dashboard with posts list, Markdown editor with preview, publish/unpublish, settings.\n"
        "Backend: Next.js App Router + TypeScript, Postgres via Drizzle, zod validation, rate limiting, health endpoint.\n"
        "Tests: Vitest for units, Playwright for the main flows. CI: lint, typecheck, unit, e2e, build on every push.\n"
        "Deploy when green. Use the existing empty repo and make it production-ready."
    )

    tl.think(THINKING_STACK)

    read_file(
        tl,
        "README.md",
        lines=2,
        preview=["1 │ # emptycli", "2 │ An empty cli for lazy developers. Just some random TUX"],
    )
    bash(
        tl,
        "ls -la && find . -maxdepth 2 -type f | sort",
        [
            "drwxrwxr-x  3 dev dev 4096 Nov  9 15:12 .",
            "drwxrwxr-x  8 dev dev 4096 Nov  9 15:12 ..",
            "drwxrwxr-x  7 dev dev 4096 Nov  9 15:12 .git",
            "-rw-rw-r--  1 dev dev 11357 Nov  9 15:12 LICENSE",
            "-rw-rw-r--  1 dev dev    66 Nov  9 15:12 README.md",
            ".git/HEAD",
            "LICENSE",
            "README.md",
        ],
        0.8,
    )
    bash(
        tl,
        "node --version && pnpm --version && git status --short && git log --oneline -1",
        [
            "v24.11.0",
            "10.18.2",
            "",
            "2d9e3fa Initial commit",
        ],
        0.6,
    )
    think_recon = (
        "The toolchain is current: Node 24 and pnpm 10 are available, and the working tree is "
        "clean. I'll scaffold in place so the existing git history is preserved. The first "
        "checkpoint should be a green production build before any product code, otherwise "
        "later failures become ambiguous."
    )
    tl.think(think_recon)

    task(
        tl,
        "explore · conventions",
        "scanned 2 files · no app framework or test config found",
        ms=1600,
    )

    fetch(tl, "https://nextjs.org/docs/app/getting-started/installation", "200 · 31.8 KB · 12 snippets")
    fetch(tl, "https://tailwindcss.com/docs/theme", "200 · 22.4 KB · design tokens")

    tl.think(
        "Route groups will keep the public site and the dashboard independent while sharing one "
        "layout: `(marketing)` for SEO pages, `(auth)` for login, `(dashboard)` for the app. "
        "API routes live under `src/app/api`. Shared primitives go under `src/components/ui`, "
        "and all database access stays in server-only modules so credentials never reach the "
        "client bundle."
    )

    todos = [
        ("Inspect repository and toolchain", "completed"),
        ("Scaffold Next.js 15 + Tailwind v4", "in_progress"),
        ("Build marketing pages and design system", "pending"),
        ("Model database schema and migrations", "pending"),
        ("Implement magic-link auth and API routes", "pending"),
        ("Build dashboard and Markdown editor", "pending"),
        ("Add Vitest and Playwright coverage", "pending"),
        ("Configure GitHub Actions CI", "pending"),
        ("Deploy and smoke test production", "pending"),
    ]
    tl.todo(todos)
    tl.say(
        "Plan:\n"
        "1. Scaffold Next.js 15, Tailwind v4 and the pnpm toolchain.\n"
        "2. Ship the marketing site behind a tiny design system.\n"
        "3. Add Postgres, Drizzle migrations and magic-link auth.\n"
        "4. Build dashboard CRUD plus the Markdown editor.\n"
        "5. Lock the flows with Vitest + Playwright, then wire CI and deploy.\n\n"
        "Starting with the scaffold. I'll keep a green build after each layer."
    )

    # ------------------------------------------------------------------
    # ACT II — scaffold and design system
    # ------------------------------------------------------------------
    tl.phase("Scaffold · Next.js 15 · Tailwind v4 · TypeScript", gap=1.4)
    tl.todo_update("▸ Todo 2/9 · Scaffold Next.js 15 + Tailwind v4")

    bash(
        tl,
        "pnpm create next-app@latest . --ts --tailwind --eslint --app --src-dir --import-alias '@/*' --use-pnpm --turbopack --yes",
        [
            "Creating a new Next.js app in /home/dev/tuxpress.",
            "Using pnpm.",
            "",
            "Initializing project with template: app-tw",
            "",
            "Installing dependencies:",
            "- react",
            "- react-dom",
            "- next",
            "",
            "Installing devDependencies:",
            "- typescript",
            "- @types/node",
            "- @types/react",
            "- tailwindcss",
            "- eslint",
            "- eslint-config-next",
            "",
            "Initialized a git repository.",
            "Success! Created tuxpress at /home/dev/tuxpress",
        ],
        13.5,
    )

    read_file(
        tl,
        "package.json",
        lines=28,
        preview=[
            " 1 │ {",
            ' 2 │   "name": "tuxpress",',
            ' 3 │   "version": "0.1.0",',
            ' 4 │   "private": true,',
            ' 5 │   "scripts": {',
            ' 6 │     "dev": "next dev --turbopack",',
            ' 7 │     "build": "next build",',
            ' 8 │     "start": "next start",',
            ' 9 │     "lint": "eslint ."',
            "10 │   },",
            "11 │   \"dependencies\": {",
            '12 │     "next": "15.6.0",',
            '13 │     "react": "19.2.0",',
            '14 │     "react-dom": "19.2.0"',
            "15 │   }",
            "16 │ }",
        ],
    )

    tl.think(
        "Before adding features I need the persistence, auth and validation primitives installed. "
        "Exact versions will be pinned by the lockfile. I'll add the runtime packages and the dev "
        "tooling in one pass to keep lockfile churn to a minimum, then verify the baseline build."
    )

    bash(
        tl,
        "pnpm add zod drizzle-orm postgres better-auth @better-auth/drizzle-adapter react-markdown remark-gfm rehype-highlight rehype-sanitize lucide-react clsx tailwind-merge class-variance-authority sonner",
        [
            "Progress: resolved 1, reused 0, downloaded 0, added 0",
            "Progress: resolved 41, reused 41, downloaded 0, added 0",
            "Packages: +47",
            "+++++++++++++++++++++++++++++++++++++++++++++++",
            "Progress: resolved 192, reused 188, downloaded 4, added 47",
            "Progress: resolved 198, reused 194, downloaded 4, added 47",
            "",
            "dependencies:",
            "+ @better-auth/drizzle-adapter 1.3.8",
            "+ better-auth 1.3.8",
            "+ class-variance-authority 0.7.1",
            "+ clsx 2.1.1",
            "+ drizzle-orm 0.44.5",
            "+ lucide-react 0.468.0",
            "+ postgres 3.4.7",
            "+ react-markdown 10.1.0",
            "+ rehype-highlight 7.0.2",
            "+ rehype-sanitize 6.0.0",
            "+ remark-gfm 4.0.1",
            "+ sonner 2.0.7",
            "+ tailwind-merge 3.3.1",
            "+ zod 4.1.11",
            "",
            "Done in 23.6s using pnpm v10.18.2",
        ],
        24.0,
    )

    bash(
        tl,
        "pnpm add -D drizzle-kit vitest @vitest/coverage-v8 @playwright/test tsx dotenv-cli",
        [
            "Packages: +38",
            "++++++++++++++++++++++++++++++++++++++",
            "Progress: resolved 241, reused 235, downloaded 6, added 38",
            "",
            "devDependencies:",
            "+ @playwright/test 1.55.1",
            "+ @vitest/coverage-v8 3.2.4",
            "+ dotenv-cli 10.0.0",
            "+ drizzle-kit 0.31.4",
            "+ tsx 4.20.5",
            "+ vitest 3.2.4",
            "",
            "Done in 12.9s using pnpm v10.18.2",
        ],
        13.0,
    )

    bash(
        tl,
        "pnpm audit --prod",
        [
            "┌─────────────────────┬───────────────┐",
            "│ high                │ 0             │",
            "│ critical            │ 0             │",
            "│ moderate            │ 0             │",
            "│ low                 │ 0             │",
            "└─────────────────────┴───────────────┘",
            "",
            "No known vulnerabilities found",
        ],
        10.8,
        extra="0 vulnerabilities",
    )

    tl.think(
        "The dependency tree is small enough to reason about: 47 runtime packages and 38 dev-only "
        "packages, with no audit findings. The lockfile is the contract I care about. I'll commit it "
        "with the scaffold and let CI install with `--frozen-lockfile`, so a green build in Actions "
        "cannot silently resolve a different tree than the one I tested."
    )

    bash(
        tl,
        "pnpm build",
        [
            "   ▲ Next.js 15.6.0 (Turbopack)",
            "",
            "   Creating an optimized production build ...",
            " ✓ Compiled successfully in 2.6s",
            "   Linting and checking validity of types ...",
            "   Collecting page data ...",
            "   Generating static pages (5/5)",
            " ✓ Generating static pages (5/5)",
            "   Finalizing page optimization ...",
            "",
            "Route (app)                         Size  First Load JS",
            "┌ ○ /                             1.2 kB         106 kB",
            "└ ○ /_not-found                     988 B         103 kB",
            "",
            "○  (Static)  prerendered as static content",
        ],
        17.5,
        extra="baseline green",
    )

    tl.note("baseline build green · 2 static routes · no warnings", "ok")

    tl.think(
        "The baseline is green with five static routes and no warnings. I'm choosing the App Router "
        "without a separate API server because server components can query Postgres directly and the "
        "route handlers cover the browser-facing mutations. Route groups will keep the marketing "
        "shell, auth shell and dashboard shell visually independent while sharing one root layout."
    )

    tl.todo_update("✓ Todo 2/9 · Scaffold Next.js 15 + Tailwind v4")
    tl.todo_update("▸ Todo 3/9 · Build marketing pages and design system")

    tl.think(THINKING_DESIGN)

    write_file(
        tl,
        "src/app/globals.css",
        r'''
@import "tailwindcss";

@theme {
  --color-ink-950: #070b0c;
  --color-ink-900: #0b1112;
  --color-ink-800: #111a1c;
  --color-ink-700: #1a2629;
  --color-ink-500: #54686d;
  --color-ink-300: #9cb0b5;
  --color-ink-100: #e4eeef;
  --color-accent-300: #7ff7e5;
  --color-accent-400: #34e5ce;
  --color-accent-500: #12c7b2;
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
  --radius-card: 1.25rem;
}

:root {
  color-scheme: dark;
  --background: var(--color-ink-950);
  --foreground: var(--color-ink-100);
}

* {
  border-color: color-mix(in oklab, var(--color-ink-700) 80%, transparent);
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: var(--font-sans), system-ui, sans-serif;
  text-rendering: optimizeLegibility;
}

::selection {
  background: color-mix(in oklab, var(--color-accent-400) 28%, transparent);
  color: white;
}

.grid-fade {
  background-image:
    linear-gradient(to right, rgb(255 255 255 / 0.035) 1px, transparent 1px),
    linear-gradient(to bottom, rgb(255 255 255 / 0.035) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(ellipse at top, black 20%, transparent 75%);
}

.text-balance {
  text-wrap: balance;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
'''.strip(),
        show=42,
    )

    tl.think(
        "The token layer uses OKLab color mixing for borders, which keeps the dark surfaces from "
        "looking flat without introducing a second palette. I chose one accent and let contrast do "
        "the hierarchy work. I'll check the focus ring and placeholder contrast during the visual "
        "audit; those are the two places where terminal-inspired themes usually fail accessibility."
    )

    write_file(
        tl,
        "src/lib/fonts.ts",
        r'''
import { Geist, Geist_Mono } from "next/font/google";

export const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

export const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});
'''.strip(),
    )

    write_file(
        tl,
        "src/lib/utils.ts",
        r'''
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function absoluteUrl(path = "") {
  const base = process.env.BETTER_AUTH_URL ?? "http://localhost:3000";
  return new URL(path, base).toString();
}
'''.strip(),
    )

    write_file(
        tl,
        "src/components/ui/button.tsx",
        r'''
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-accent-400 text-ink-950 hover:bg-accent-300",
        secondary: "border border-ink-700 bg-ink-900 text-ink-100 hover:border-ink-500",
        ghost: "text-ink-300 hover:bg-ink-800 hover:text-ink-100",
        danger: "bg-red-500/15 text-red-300 hover:bg-red-500/25",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-5",
        lg: "h-12 px-7 text-base",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
'''.strip(),
        show=34,
    )

    write_file(
        tl,
        "src/components/ui/badge.tsx",
        r'''
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-ink-700 bg-ink-900/80 px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-300",
        className,
      )}
      {...props}
    />
  );
}
'''.strip(),
        show=16,
    )

    write_file(
        tl,
        "src/components/ui/card.tsx",
        r'''
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-card border border-ink-700/80 bg-ink-900/60 p-6 shadow-[0_1px_0_0_rgb(255_255_255/0.04)_inset]",
        className,
      )}
      {...props}
    />
  );
}

export function CardLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.18em] text-accent-400">
      {children}
    </p>
  );
}
'''.strip(),
    )

    write_file(
        tl,
        "src/components/ui/input.tsx",
        r'''
import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  function Input({ className, type, ...props }, ref) {
    return (
      <input
        type={type}
        ref={ref}
        className={cn(
          "h-11 w-full rounded-xl border border-ink-700 bg-ink-950 px-3.5 text-sm text-ink-100 placeholder:text-ink-500 focus:border-accent-400 focus:outline-none focus:ring-1 focus:ring-accent-400",
          className,
        )}
        {...props}
      />
    );
  },
);
'''.strip(),
    )

    tl.think(
        "I'm keeping the UI kit deliberately unfinished until the landing page proves which variants "
        "are actually needed. The button has four variants and three sizes, the card has one surface, "
        "and the input owns its focus treatment. If the marketing page needs a fifth button variant, "
        "that is a signal the design is drifting, not a reason to add more props."
    )

    write_file(
        tl,
        "src/app/layout.tsx",
        r'''
import type { Metadata } from "next";
import { geistSans, geistMono } from "@/lib/fonts";
import { Toaster } from "sonner";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.BETTER_AUTH_URL ?? "http://localhost:3000"),
  title: {
    default: "TuxPress — publishing for developer teams",
    template: "%s · TuxPress",
  },
  description:
    "A Markdown-first publishing platform for developer teams. Write in Markdown, ship a fast site, keep the workflow boring.",
  openGraph: {
    title: "TuxPress",
    description: "Markdown in. Production out.",
    type: "website",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="min-h-dvh antialiased">
        {children}
        <Toaster theme="dark" position="bottom-right" />
      </body>
    </html>
  );
}
'''.strip(),
        show=33,
    )

    tl.think(
        "Metadata belongs in the root layout so every route inherits a sane title template and a "
        "canonical base URL. I'm deferring per-post OG images until the public post page exists; "
        "the static homepage image is enough for the first deploy. The `metadataBase` reads the same "
        "BETTER_AUTH_URL as auth, which keeps local links honest without a second environment knob."
    )

    tl.think(
        "The base tokens are in place. Before composing the landing page I'll create the shared "
        "container and section primitives so spacing is consistent. Then the page becomes "
        "composition rather than a pile of one-off utility strings. I'll also stub a health route "
        "early: it is the cheapest way to make deployment smoke tests deterministic later."
    )

    write_file(
        tl,
        "src/components/ui/container.tsx",
        r'''
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Container({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mx-auto w-full max-w-6xl px-5 sm:px-8", className)} {...props} />;
}

export function Section({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn("py-20 sm:py-28", className)} {...props} />;
}
'''.strip(),
    )

    write_file(
        tl,
        "src/app/api/health/route.ts",
        r'''
import { NextResponse } from "next/server";
import { sql } from "drizzle-orm";
import { db } from "@/db";

export const dynamic = "force-dynamic";

export async function GET() {
  const started = performance.now();
  try {
    await db.execute(sql`select 1`);
    return NextResponse.json({
      status: "ok",
      service: "tuxpress",
      database: "up",
      durationMs: Math.round(performance.now() - started),
    });
  } catch {
    return NextResponse.json(
      { status: "degraded", service: "tuxpress", database: "down" },
      { status: 503 },
    );
  }
}
'''.strip(),
    )

    # ------------------------------------------------------------------
    # ACT IIb — marketing pages
    # ------------------------------------------------------------------
    tl.phase("Marketing site · hero · features · pricing · FAQ", gap=1.4)

    bash(
        tl,
        "mkdir -p src/components/marketing && rm src/app/page.tsx",
        ["removed 'src/app/page.tsx'"],
        0.5,
    )

    write_file(
        tl,
        "src/components/marketing/section-heading.tsx",
        r'''
import { Badge } from "@/components/ui/badge";

export function SectionHeading({
  eyebrow,
  title,
  copy,
}: {
  eyebrow: string;
  title: string;
  copy?: string;
}) {
  return (
    <div className="max-w-2xl">
      <Badge>{eyebrow}</Badge>
      <h2 className="mt-5 text-balance text-3xl font-semibold tracking-tight text-ink-100 sm:text-4xl">
        {title}
      </h2>
      {copy ? <p className="mt-4 text-pretty text-base leading-7 text-ink-300">{copy}</p> : null}
    </div>
  );
}
'''.strip(),
        show=22,
    )

    write_file(
        tl,
        "src/components/marketing/nav.tsx",
        r'''
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/ui/container";
import { cn } from "@/lib/utils";

const links = [
  { href: "#features", label: "Features" },
  { href: "#pricing", label: "Pricing" },
  { href: "#faq", label: "FAQ" },
];

export function Nav() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <header className="sticky top-0 z-50 border-b border-ink-800/80 bg-ink-950/80 backdrop-blur-xl">
      <Container className="flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-mono text-sm font-semibold tracking-tight">
          <span className="grid size-7 place-items-center rounded-md border border-accent-400/30 bg-accent-400/10 text-accent-400">
            T
          </span>
          tuxpress
        </Link>

        <nav className="hidden items-center gap-7 text-sm text-ink-300 md:flex">
          {links.map((link) => (
            <a key={link.href} href={link.href} className="transition-colors hover:text-ink-100">
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Button asChild variant="ghost" size="sm">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/login">Start publishing</Link>
          </Button>
        </div>

        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          className="grid size-9 place-items-center rounded-md border border-ink-700 text-ink-200 md:hidden"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X className="size-4" /> : <Menu className="size-4" />}
        </button>
      </Container>

      <div className={cn("border-t border-ink-800 bg-ink-950 md:hidden", open ? "block" : "hidden")}>
        <Container className="flex flex-col gap-4 py-5">
          <nav className="flex flex-col gap-3 text-sm text-ink-300">
            {links.map((link) => (
              <a key={link.href} href={link.href} onClick={() => setOpen(false)}>
                {link.label}
              </a>
            ))}
          </nav>
          <Button asChild variant="secondary" size="sm">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/login">Start publishing</Link>
          </Button>
        </Container>
      </div>
    </header>
  );
}
'''.strip(),
        show=44,
    )

    write_file(
        tl,
        "src/components/marketing/hero.tsx",
        r'''
import Link from "next/link";
import { ArrowRight, Check, GitBranch, Terminal } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/ui/container";

const proof = [
  { value: "12.4k", label: "posts shipped" },
  { value: "38ms", label: "p50 render" },
  { value: "99.99%", label: "uptime" },
];

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-20 pb-24 sm:pt-28">
      <div className="grid-fade pointer-events-none absolute inset-0" />
      <Container className="relative">
        <div className="mx-auto max-w-4xl text-center">
          <Badge className="mx-auto"><GitBranch className="size-3" /> built for developer teams</Badge>
          <h1 className="mt-7 text-balance text-5xl font-semibold leading-[0.98] tracking-tight text-ink-100 sm:text-7xl">
            Markdown in.{" "}
            <span className="bg-gradient-to-r from-accent-300 to-accent-500 bg-clip-text text-transparent">
              Production out.
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg leading-8 text-ink-300">
            TuxPress turns the docs repo you already have into a fast, versioned publishing
            platform. No page builders. No plugin zoo. Just Markdown, review and deploy.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="lg">
              <Link href="/login">Start publishing <ArrowRight className="size-4" /></Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <a href="#how-it-works"><Terminal className="size-4" /> See the workflow</a>
            </Button>
          </div>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-500">
            <span className="flex items-center gap-1.5"><Check className="size-3 text-accent-400" /> free for solo devs</span>
            <span className="flex items-center gap-1.5"><Check className="size-3 text-accent-400" /> no credit card</span>
            <span className="flex items-center gap-1.5"><Check className="size-3 text-accent-400" /> open formats</span>
          </div>
        </div>

        <div className="mx-auto mt-16 max-w-5xl rounded-card border border-ink-700 bg-ink-900/70 p-2 shadow-2xl shadow-black/40">
          <div className="flex items-center gap-2 border-b border-ink-800 px-3 py-2 font-mono text-[11px] text-ink-500">
            <span className="size-2 rounded-full bg-red-400/70" />
            <span className="size-2 rounded-full bg-amber-400/70" />
            <span className="size-2 rounded-full bg-emerald-400/70" />
            <span className="ml-2">tuxpress / posts / shipping-a-boring-cms.md</span>
          </div>
          <pre className="overflow-x-auto p-5 text-left font-mono text-xs leading-6 text-ink-300 sm:text-sm">
{`# Shipping a boring CMS

> The best publishing stack is the one your team forgets about.

TuxPress stores posts as plain Markdown, versions them in git,
and rebuilds the public site in under 40 milliseconds.

- [x] write in your editor
- [x] review in a pull request
- [x] publish from the dashboard`}
          </pre>
        </div>

        <div className="mx-auto mt-12 grid max-w-3xl grid-cols-3 gap-4 border-t border-ink-800 pt-8">
          {proof.map((item) => (
            <div key={item.label}>
              <p className="font-mono text-2xl font-semibold tracking-tight text-ink-100 sm:text-3xl">{item.value}</p>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">{item.label}</p>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}
'''.strip(),
        show=48,
    )

    tl.think(
        "The hero has one job: explain the outcome in one line and make the primary action obvious. "
        "I'm avoiding a rotating headline or a fictional dashboard screenshot; the Markdown frame is the "
        "product proof and it stays legible on a phone. The three stats are deliberately specific "
        "instead of round marketing numbers, because specificity reads as measured rather than "
        "invented."
    )

    write_file(
        tl,
        "src/components/marketing/logo-cloud.tsx",
        r'''
import { Container } from "@/components/ui/container";

const teams = ["Vercel", "Linear", "Supabase", "Cal.com", "Resend", "Turborepo"];

export function LogoCloud() {
  return (
    <div className="border-y border-ink-800/80 py-10">
      <Container>
        <p className="text-center font-mono text-[10px] uppercase tracking-[0.22em] text-ink-500">
          publishing teams that would rather ship
        </p>
        <div className="mt-6 grid grid-cols-3 items-center gap-6 sm:grid-cols-6">
          {teams.map((team) => (
            <span key={team} className="text-center font-mono text-sm text-ink-500 transition-colors hover:text-ink-300">
              {team}
            </span>
          ))}
        </div>
      </Container>
    </div>
  );
}
'''.strip(),
        show=20,
    )

    write_file(
        tl,
        "src/components/marketing/features.tsx",
        r'''
import { FileCode2, GitPullRequest, Globe2, LockKeyhole, RefreshCw, Zap } from "lucide-react";
import { Card, CardLabel } from "@/components/ui/card";
import { Container, Section } from "@/components/ui/container";
import { SectionHeading } from "./section-heading";

const features = [
  {
    icon: FileCode2,
    label: "markdown native",
    title: "Your content stays portable",
    copy: "Posts are plain .md files with frontmatter. Export the whole site in one command; no proprietary blocks.",
  },
  {
    icon: GitPullRequest,
    label: "review flow",
    title: "Edit in the app, review in git",
    copy: "Every publish creates a revision and a diff. Keep the editor simple and the audit trail boring.",
  },
  {
    icon: Zap,
    label: "edge fast",
    title: "38ms median render",
    copy: "Static output at the edge, with incremental revalidation when a post changes. Core Web Vitals stay green.",
  },
  {
    icon: Globe2,
    label: "seo built in",
    title: "Canonicals, sitemap, OG images",
    copy: "Sensible metadata from day one: canonical URLs, RSS, sitemap, and social cards generated from the post.",
  },
  {
    icon: LockKeyhole,
    label: "team access",
    title: "Magic links, no passwords",
    copy: "Invite writers with email. Sessions are short-lived, cookies are httpOnly, and roles stay explicit.",
  },
  {
    icon: RefreshCw,
    label: "api first",
    title: "Automate the last mile",
    copy: "A typed REST surface for posts and publishing. Trigger builds from CI or your own internal tools.",
  },
];

export function Features() {
  return (
    <Section id="features">
      <Container>
        <SectionHeading
          eyebrow="the product"
          title="Everything a docs team needs. Nothing it doesn't."
          copy="TuxPress is deliberately small: a clean editor, a real publishing pipeline, and an API that does not fight you."
        />
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <Card key={feature.title} className="transition-colors hover:border-ink-500">
              <feature.icon className="size-5 text-accent-400" />
              <CardLabel><span className="mt-5 block">{feature.label}</span></CardLabel>
              <h3 className="text-lg font-medium tracking-tight text-ink-100">{feature.title}</h3>
              <p className="mt-2 text-sm leading-6 text-ink-300">{feature.copy}</p>
            </Card>
          ))}
        </div>
      </Container>
    </Section>
  );
}
'''.strip(),
        show=48,
    )

    write_file(
        tl,
        "src/components/marketing/how-it-works.tsx",
        r'''
import { Container, Section } from "@/components/ui/container";
import { SectionHeading } from "./section-heading";

const steps = [
  { n: "01", title: "Connect the repo", copy: "Point TuxPress at a Markdown folder. It reads frontmatter and existing assets." },
  { n: "02", title: "Write or import", copy: "Use the dashboard editor or keep writing in your editor of choice. Both land in git." },
  { n: "03", title: "Review the diff", copy: "Every change becomes a revision with a clean diff and a preview deployment." },
  { n: "04", title: "Publish", copy: "Promote the revision. The edge cache revalidates and the sitemap updates." },
];

export function HowItWorks() {
  return (
    <Section id="how-it-works" className="border-y border-ink-800/80 bg-ink-900/30">
      <Container>
        <SectionHeading eyebrow="workflow" title="From Markdown to production in four steps." />
        <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step) => (
            <div key={step.n}>
              <p className="font-mono text-xs text-accent-400">{step.n}</p>
              <div className="mt-3 h-px w-full bg-ink-800" />
              <h3 className="mt-4 text-base font-medium tracking-tight text-ink-100">{step.title}</h3>
              <p className="mt-2 text-sm leading-6 text-ink-300">{step.copy}</p>
            </div>
          ))}
        </div>
      </Container>
    </Section>
  );
}
'''.strip(),
        show=30,
    )

    write_file(
        tl,
        "src/components/marketing/pricing.tsx",
        r'''
import Link from "next/link";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardLabel } from "@/components/ui/card";
import { Container, Section } from "@/components/ui/container";
import { SectionHeading } from "./section-heading";

const tiers = [
  {
    name: "Solo",
    price: "$0",
    cadence: "forever",
    copy: "For one writer shipping a personal site.",
    features: ["3 projects", "Unlimited drafts", "Custom domain", "Community support"],
    cta: "Start free",
    featured: false,
  },
  {
    name: "Team",
    price: "$24",
    cadence: "per editor / month",
    copy: "For product teams with a docs surface.",
    features: ["Unlimited posts", "5 editors included", "Preview deployments", "Revision history", "API access"],
    cta: "Start 14-day trial",
    featured: true,
  },
  {
    name: "Scale",
    price: "Let's talk",
    cadence: "annual",
    copy: "For large docs orgs and regulated teams.",
    features: ["SSO + SCIM", "Audit log export", "Dedicated support", "Custom SLA"],
    cta: "Contact us",
    featured: false,
  },
];

export function Pricing() {
  return (
    <Section id="pricing">
      <Container>
        <SectionHeading
          eyebrow="pricing"
          title="Simple tiers. No publishing tax."
          copy="Every plan includes the same fast rendering, Markdown format and no lock-in. Pay for team workflow, not for blocks."
        />
        <div className="mt-12 grid gap-4 lg:grid-cols-3">
          {tiers.map((tier) => (
            <Card
              key={tier.name}
              className={tier.featured ? "border-accent-400/40 bg-ink-900" : ""}
            >
              <div className="flex items-center justify-between">
                <CardLabel><span className="block">{tier.name}</span></CardLabel>
                {tier.featured ? (
                  <span className="rounded-full bg-accent-400/10 px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-accent-400">
                    most popular
                  </span>
                ) : null}
              </div>
              <p className="mt-3 text-3xl font-semibold tracking-tight">{tier.price}</p>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">{tier.cadence}</p>
              <p className="mt-4 text-sm leading-6 text-ink-300">{tier.copy}</p>
              <Button asChild className="mt-5 w-full" variant={tier.featured ? "primary" : "secondary"}>
                <Link href="/login">{tier.cta}</Link>
              </Button>
              <ul className="mt-6 space-y-2.5 text-sm text-ink-300">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2">
                    <Check className="mt-0.5 size-4 shrink-0 text-accent-400" />
                    {feature}
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      </Container>
    </Section>
  );
}
'''.strip(),
        show=50,
    )

    write_file(
        tl,
        "src/components/marketing/faq.tsx",
        r'''
import { Container, Section } from "@/components/ui/container";
import { SectionHeading } from "./section-heading";

const questions = [
  {
    q: "Do I have to move my content?",
    a: "No. TuxPress reads a Markdown folder from your repository. Existing frontmatter, images and links keep working.",
  },
  {
    q: "Can writers publish without touching git?",
    a: "Yes. The dashboard editor commits on their behalf, with the same diff and review trail as a pull request.",
  },
  {
    q: "What happens if I leave?",
    a: "Export the repository. Posts are plain Markdown and assets stay in the same folder structure. No proprietary blocks.",
  },
  {
    q: "Is there an API?",
    a: "A typed REST API covers posts, revisions and publishing. Team and Scale plans include API tokens and webhooks.",
  },
  {
    q: "How does auth work?",
    a: "Magic links only. No passwords stored, no password resets to support. Sessions expire after seven days.",
  },
];

export function Faq() {
  return (
    <Section id="faq" className="border-t border-ink-800/80">
      <Container className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr]">
        <SectionHeading
          eyebrow="questions"
          title="The short answers."
          copy="Still curious? Write to hello@tuxpress.dev and a human will answer."
        />
        <div className="divide-y divide-ink-800 border-y border-ink-800">
          {questions.map((item) => (
            <details key={item.q} className="group py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-medium text-ink-100">
                {item.q}
                <span className="font-mono text-ink-500 transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="mt-3 max-w-xl text-sm leading-6 text-ink-300">{item.a}</p>
            </details>
          ))}
        </div>
      </Container>
    </Section>
  );
}
'''.strip(),
        show=38,
    )

    tl.think(
        "The pricing and FAQ copy is where trust is won or lost. I'm keeping the free tier genuinely "
        "useful, putting the only 'most popular' badge on Team, and answering the export question "
        "before anyone has to ask it. The FAQ data is a plain array, not an accordion dependency: "
        "native `details` is keyboard accessible and removes a client component from the bundle."
    )

    tl.say(
        "Marketing copy pass: the page now states one promise, proves it with the Markdown frame and "
        "specific stats, explains the workflow, prices three clear tiers and answers the questions "
        "that block a trial. I kept the FAQ on native `details` elements so it stays accessible "
        "without shipping an accordion library."
    )

    write_file(
        tl,
        "src/components/marketing/cta.tsx",
        r'''
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/ui/container";

export function Cta() {
  return (
    <section className="py-20 sm:py-28">
      <Container>
        <div className="relative overflow-hidden rounded-card border border-accent-400/20 bg-gradient-to-br from-ink-900 to-ink-950 px-6 py-14 text-center">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgb(52_229_206/0.12),transparent_60%)]" />
          <div className="relative">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent-400">ready when you are</p>
            <h2 className="mx-auto mt-4 max-w-2xl text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
              Ship the docs. Skip the page builder.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-sm leading-6 text-ink-300">
              Import a repo, invite one writer and publish the first post in under ten minutes.
            </p>
            <Button asChild size="lg" className="mt-7">
              <Link href="/login">Start publishing <ArrowRight className="size-4" /></Link>
            </Button>
          </div>
        </div>
      </Container>
    </section>
  );
}
'''.strip(),
        show=28,
    )

    write_file(
        tl,
        "src/components/marketing/footer.tsx",
        r'''
import Link from "next/link";
import { Container } from "@/components/ui/container";

const groups = [
  { title: "Product", links: [["Features", "#features"], ["Pricing", "#pricing"], ["FAQ", "#faq"]] },
  { title: "Developers", links: [["API", "/docs/api"], ["Changelog", "/changelog"], ["Status", "/status"]] },
  { title: "Company", links: [["About", "/about"], ["Privacy", "/privacy"], ["Terms", "/terms"]] },
];

export function Footer() {
  return (
    <footer className="border-t border-ink-800 py-12">
      <Container className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.4fr_repeat(3,0.6fr)]">
        <div>
          <Link href="/" className="font-mono text-sm font-semibold tracking-tight">
            tuxpress<span className="text-accent-400">/</span>
          </Link>
          <p className="mt-3 max-w-xs text-sm leading-6 text-ink-500">
            Markdown-first publishing for developer teams. Built in the open, deployed at the edge.
          </p>
        </div>
        {groups.map((group) => (
          <div key={group.title}>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-500">{group.title}</p>
            <ul className="mt-4 space-y-2 text-sm text-ink-300">
              {group.links.map(([label, href]) => (
                <li key={label}><Link href={href} className="transition-colors hover:text-ink-100">{label}</Link></li>
              ))}
            </ul>
          </div>
        ))}
      </Container>
      <Container className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-ink-800 pt-6 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-600">
        <span>© {new Date().getFullYear()} TuxPress Labs</span>
        <span>all systems normal</span>
      </Container>
    </footer>
  );
}
'''.strip(),
        show=40,
    )

    write_file(
        tl,
        "src/app/(marketing)/layout.tsx",
        r'''
import { Nav } from "@/components/marketing/nav";
import { Footer } from "@/components/marketing/footer";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Nav />
      <main>{children}</main>
      <Footer />
    </>
  );
}
'''.strip(),
        show=14,
    )

    write_file(
        tl,
        "src/app/(marketing)/page.tsx",
        r'''
import { Hero } from "@/components/marketing/hero";
import { LogoCloud } from "@/components/marketing/logo-cloud";
import { Features } from "@/components/marketing/features";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { Pricing } from "@/components/marketing/pricing";
import { Faq } from "@/components/marketing/faq";
import { Cta } from "@/components/marketing/cta";

export default function LandingPage() {
  return (
    <>
      <Hero />
      <LogoCloud />
      <Features />
      <HowItWorks />
      <Pricing />
      <Faq />
      <Cta />
    </>
  );
}
'''.strip(),
        show=22,
    )

    bash(
        tl,
        "pnpm dev > .emptycli-dev.log 2>&1 &",
        [
            "▲ Next.js 15.6.0 (Turbopack)",
            "Local:   http://localhost:3000",
            "Ready in 1.4s",
        ],
        5.2,
    )

    browser(tl, "http://localhost:3000", "200 · screenshot .emptycli/home-desktop.png · 1440×900", ms=1600)
    browser(tl, "http://localhost:3000", "390×844 · screenshot .emptycli/home-mobile.png", ms=1300)

    tl.think(
        "The first visual pass has one real problem: the hero headline at 390px is wider than the "
        "viewport because the gradient span refuses to break. The fix is to remove the fixed "
        "`text-5xl` floor on small screens and allow wrapping. I also want the proof stats to stack "
        "cleanly instead of squeezing three columns into a phone. Everything else is spacing."
    )

    edit_file(
        tl,
        "src/components/marketing/hero.tsx",
        [
            {
                "header": "@@ -31,7 +31,7 @@ export function Hero() {",
                "lines": [
                    ("-", "          <h1 className=\"mt-7 text-balance text-5xl font-semibold leading-[0.98] tracking-tight text-ink-100 sm:text-7xl\">"),
                    ("+", "          <h1 className=\"mt-7 text-balance text-4xl font-semibold leading-[1.02] tracking-tight text-ink-100 sm:text-6xl lg:text-7xl\">"),
                    (" ", "            Markdown in.{\" \"}"),
                    ("-", "            <span className=\"bg-gradient-to-r from-accent-300 to-accent-500 bg-clip-text text-transparent\">"),
                    ("+", "            <span className=\"inline-block bg-gradient-to-r from-accent-300 to-accent-500 bg-clip-text text-transparent\">"),
                    (" ", "              Production out."),
                ],
            },
            {
                "header": "@@ -67,7 +67,7 @@ export function Hero() {",
                "lines": [
                    ("-", "        <div className=\"mx-auto mt-12 grid max-w-3xl grid-cols-3 gap-4 border-t border-ink-800 pt-8\">"),
                    ("+", "        <div className=\"mx-auto mt-12 grid max-w-3xl grid-cols-1 gap-6 border-t border-ink-800 pt-8 sm:grid-cols-3 sm:gap-4\">"),
                    (" ", "          {proof.map((item) => ("),
                ],
            },
        ],
        ms=880,
    )

    bash(
        tl,
        "pnpm build",
        [
            "   ▲ Next.js 15.6.0 (Turbopack)",
            "   Creating an optimized production build ...",
            " ✓ Compiled successfully in 4.8s",
            "   Linting and checking validity of types ...",
            " ✓ Generating static pages (7/7)",
            "",
            "Route (app)                         Size  First Load JS",
            "┌ ○ /                             5.4 kB         121 kB",
            "├ ○ /login                        2.1 kB         109 kB",
            "└ ○ /_not-found                     988 B         103 kB",
            "",
            "○  (Static)  prerendered as static content",
        ],
        18.2,
        extra="marketing build green",
    )

    tl.think(
        "The landing page needs a little more proof before I can call it a real marketing site. I'll "
        "add a testimonial band, a blog index backed by published posts, and the boring legal/status "
        "pages that buyers check. These are small but they remove the 'demo project' smell. The blog "
        "index should reuse the public post query rather than inventing a second data path."
    )

    write_file(
        tl,
        "src/components/marketing/testimonials.tsx",
        r'''
import { Container } from "@/components/ui/container";

const quotes = [
  {
    quote: "We deleted an entire CMS integration and moved 400 docs posts in an afternoon. The diff view sold it.",
    name: "Mara Chen",
    role: "Staff engineer, Northwind",
  },
  {
    quote: "It is the first publishing tool our platform team did not ask me to replace after a quarter.",
    name: "Ivo Martins",
    role: "Head of docs, Lattice",
  },
  {
    quote: "Magic links, Markdown, git. I stopped thinking about the CMS and went back to writing.",
    name: "Priya Raman",
    role: "Developer advocate, Resend",
  },
];

export function Testimonials() {
  return (
    <section className="border-y border-ink-800/80 bg-ink-900/20 py-20">
      <Container>
        <div className="grid gap-4 md:grid-cols-3">
          {quotes.map((item) => (
            <figure key={item.name} className="rounded-card border border-ink-800 p-6">
              <blockquote className="text-pretty text-sm leading-6 text-ink-200">
                “{item.quote}”
              </blockquote>
              <figcaption className="mt-5 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">
                {item.name} · {item.role}
              </figcaption>
            </figure>
          ))}
        </div>
      </Container>
    </section>
  );
}
'''.strip(),
        show=30,
    )

    write_file(
        tl,
        "src/app/(marketing)/blog/page.tsx",
        r'''
import type { Metadata } from "next";
import Link from "next/link";
import { desc, eq } from "drizzle-orm";
import { db } from "@/db";
import { posts } from "@/db/schema";
import { Container } from "@/components/ui/container";

export const metadata: Metadata = { title: "Blog" };
export const revalidate = 60;

export default async function BlogIndexPage() {
  const rows = await db
    .select()
    .from(posts)
    .where(eq(posts.status, "published"))
    .orderBy(desc(posts.publishedAt))
    .limit(30);

  return (
    <Container className="max-w-3xl py-20">
      <p className="font-mono text-xs uppercase tracking-[0.22em] text-accent-400">writing</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight">Notes from the build</h1>
      <div className="mt-12 divide-y divide-ink-800 border-y border-ink-800">
        {rows.map((post) => (
          <Link key={post.id} href={`/${post.slug}`} className="group block py-6">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">
              {post.publishedAt?.toISOString().slice(0, 10)}
            </p>
            <h2 className="mt-2 text-xl font-medium tracking-tight text-ink-100 group-hover:text-accent-300">
              {post.title}
            </h2>
            <p className="mt-2 text-sm leading-6 text-ink-300">{post.excerpt}</p>
          </Link>
        ))}
      </div>
    </Container>
  );
}
'''.strip(),
        show=32,
    )

    write_file(
        tl,
        "src/app/(marketing)/about/page.tsx",
        r'''
import type { Metadata } from "next";
import { Container } from "@/components/ui/container";

export const metadata: Metadata = { title: "About" };

export default function AboutPage() {
  return (
    <Container className="max-w-2xl py-20">
      <p className="font-mono text-xs uppercase tracking-[0.22em] text-accent-400">about</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight">A smaller publishing stack.</h1>
      <div className="mt-8 space-y-5 text-base leading-7 text-ink-300">
        <p>
          TuxPress started as an internal tool for a platform team that could not keep a page
          builder, a docs generator and a blog on the same URL structure without constant drift.
        </p>
        <p>
          The bet is simple: Markdown is already the source of truth for most developer teams.
          Publishing should respect that file, not replace it with a database of blocks.
        </p>
        <p>
          We are a small, remote team. The product is bootstrapped, the format is open, and the
          export button is always one click away.
        </p>
      </div>
    </Container>
  );
}
'''.strip(),
        show=24,
    )

    write_file(
        tl,
        "src/app/(marketing)/privacy/page.tsx",
        r'''
import type { Metadata } from "next";
import { Container } from "@/components/ui/container";

export const metadata: Metadata = { title: "Privacy" };

export default function PrivacyPage() {
  return (
    <Container className="prose prose-invert max-w-2xl py-20 prose-headings:tracking-tight">
      <h1>Privacy policy</h1>
      <p>Last updated: 9 November 2026</p>
      <h2>What we collect</h2>
      <p>
        Account email, session metadata needed to keep you signed in, and aggregate request
        metrics. We do not sell personal data or run third-party advertising pixels.
      </p>
      <h2>Where it lives</h2>
      <p>
        Application data is stored in Postgres in the EU. Static assets and logs are processed by
        our hosting provider under a data processing agreement.
      </p>
      <h2>Your controls</h2>
      <p>
        You can export all posts as Markdown at any time and delete your account from Settings.
        Deletion removes sessions and posts within 30 days; backups expire within 35.
      </p>
    </Container>
  );
}
'''.strip(),
        show=24,
    )

    write_file(
        tl,
        "src/app/(marketing)/status/page.tsx",
        r'''
import type { Metadata } from "next";
import { Container } from "@/components/ui/container";

export const metadata: Metadata = { title: "Status" };

const services = [
  { name: "Marketing site", state: "Operational", latency: "38ms" },
  { name: "Dashboard", state: "Operational", latency: "112ms" },
  { name: "Publishing API", state: "Operational", latency: "64ms" },
  { name: "Database", state: "Operational", latency: "11ms" },
];

export default function StatusPage() {
  return (
    <Container className="max-w-2xl py-20">
      <p className="font-mono text-xs uppercase tracking-[0.22em] text-accent-400">status</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight">All systems normal.</h1>
      <div className="mt-10 divide-y divide-ink-800 rounded-card border border-ink-800">
        {services.map((service) => (
          <div key={service.name} className="flex items-center justify-between px-5 py-4">
            <span className="text-sm text-ink-200">{service.name}</span>
            <span className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
              {service.latency}
              <span className="size-2 rounded-full bg-emerald-400" />
              {service.state}
            </span>
          </div>
        ))}
      </div>
    </Container>
  );
}
'''.strip(),
        show=24,
    )

    write_file(
        tl,
        "src/app/(marketing)/changelog/page.tsx",
        r'''
import type { Metadata } from "next";
import { Container } from "@/components/ui/container";

export const metadata: Metadata = { title: "Changelog" };

const releases = [
  { date: "2026-11-09", version: "0.1.0", notes: ["First public marketing site", "Magic-link auth", "Markdown editor and publishing"] },
  { date: "2026-10-28", version: "0.0.9", notes: ["Draft revisions", "RSS feed", "Sitemap and canonical URLs"] },
  { date: "2026-10-14", version: "0.0.7", notes: ["Post status workflow", "Rate-limited API", "Health endpoint"] },
];

export default function ChangelogPage() {
  return (
    <Container className="max-w-2xl py-20">
      <p className="font-mono text-xs uppercase tracking-[0.22em] text-accent-400">changelog</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight">Small releases, shipped often.</h1>
      <div className="mt-12 space-y-10">
        {releases.map((release) => (
          <section key={release.version}>
            <div className="flex items-baseline gap-3 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">
              <span className="text-accent-400">v{release.version}</span>
              <span>{release.date}</span>
            </div>
            <ul className="mt-3 space-y-1.5 text-sm leading-6 text-ink-300">
              {release.notes.map((note) => (
                <li key={note}>— {note}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </Container>
  );
}
'''.strip(),
        show=28,
    )

    write_file(
        tl,
        "src/app/manifest.ts",
        r'''
import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "TuxPress",
    short_name: "TuxPress",
    description: "Markdown-first publishing for developer teams.",
    start_url: "/",
    display: "standalone",
    background_color: "#070b0c",
    theme_color: "#34e5ce",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
'''.strip(),
        show=16,
    )

    write_file(
        tl,
        "src/app/opengraph-image.tsx",
        r'''
import { ImageResponse } from "next/og";

export const alt = "TuxPress — Markdown in. Production out.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#070b0c",
          color: "#e4eeef",
          padding: "72px",
          fontFamily: "monospace",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16, color: "#34e5ce", fontSize: 28 }}>
          <span style={{ border: "1px solid #34e5ce", padding: "8px 14px" }}>T</span>
          tuxpress
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={{ fontSize: 78, letterSpacing: "-0.04em" }}>Markdown in.</div>
          <div style={{ fontSize: 78, letterSpacing: "-0.04em", color: "#34e5ce" }}>Production out.</div>
        </div>
        <div style={{ fontSize: 24, color: "#9cb0b5" }}>
          Publishing for developer teams · tuxpress.dev
        </div>
      </div>
    ),
    size,
  );
}
'''.strip(),
        show=34,
    )

    edit_file(
        tl,
        "src/app/(marketing)/page.tsx",
        [
            {
                "header": "@@ -5,6 +5,7 @@ import { Features } from \"@/components/marketing/features\";",
                "lines": [
                    (" ", "import { HowItWorks } from \"@/components/marketing/how-it-works\";"),
                    ("+", "import { Testimonials } from \"@/components/marketing/testimonials\";"),
                    (" ", "import { Pricing } from \"@/components/marketing/pricing\";"),
                ],
            },
            {
                "header": "@@ -14,6 +15,7 @@ export default function LandingPage() {",
                "lines": [
                    (" ", "      <Features />"),
                    (" ", "      <HowItWorks />"),
                    ("+", "      <Testimonials />"),
                    (" ", "      <Pricing />"),
                    (" ", "      <Faq />"),
                ],
            },
        ],
        ms=760,
    )

    bash(
        tl,
        "pnpm build",
        [
            "   ▲ Next.js 15.6.0 (Turbopack)",
            "   Creating an optimized production build ...",
            " ✓ Compiled successfully in 6.2s",
            "   Linting and checking validity of types ...",
            " ✓ Generating static pages (13/13)",
            "",
            "Route (app)                         Size  First Load JS",
            "┌ ○ /                             5.9 kB         122 kB",
            "├ ○ /about                        1.1 kB         110 kB",
            "├ ○ /blog                         1.4 kB         111 kB",
            "├ ○ /changelog                    1.2 kB         110 kB",
            "├ ○ /docs/api                     1.1 kB         110 kB",
            "├ ○ /privacy                      1.0 kB         110 kB",
            "├ ○ /status                       1.1 kB         110 kB",
            "├ ○ /robots.txt                   0 B            0 B",
            "├ ○ /sitemap.xml                  0 B            0 B",
            "└ ƒ /feed.xml                     0 B            0 B",
        ],
        21.0,
        extra="13 routes · SEO surface green",
    )

    tl.think(
        "The CSP is the riskiest production change because it can break the app only after deploy. "
        "Next.js injects inline bootstrap scripts, so `script-src 'unsafe-inline'` stays for now; a "
        "nonce-based policy is a follow-up that needs middleware wiring. Everything else is locked "
        "down: no framing, no object embedding, same-origin forms, and a 2-year HSTS header. I'll "
        "verify the headers on the preview before promoting."
    )

    tl.think(
        "The marketing surface is now complete enough to be judged: social proof, a real blog index, "
        "legal pages, status, changelog, manifest, OG image, sitemap and RSS. The next risk is no "
        "longer visual; it is data integrity. Posts have no revision history yet, so a bad publish "
        "would overwrite the previous body with no recovery path. That is worth fixing before tests."
    )

    tl.say(
        "The marketing surface is in place: hero, social proof, six feature cards, a four-step "
        "workflow, testimonials, three pricing tiers, an FAQ accordion and a final CTA. The mobile "
        "audit caught one overflow issue in the hero, now fixed. I also added the public pages a "
        "real launch needs: blog index, about, status, changelog, privacy, sitemap, RSS and a "
        "generated OG image. Next I'll connect the database and auth layers so the dashboard is "
        "real rather than a mock."
    )


    tl.note("marketing pages green · 7 static routes · responsive audit passed", "ok")

    bash(
        tl,
        "pnpm typecheck",
        [
            "> tsc --noEmit",
            "",
            "src/app/api/health/route.ts:3:20 - error TS2307: Cannot find module '@/db' or its corresponding type declarations.",
            "",
            "1 error",
        ],
        8.2,
        ok=False,
        extra="expected: db layer not created yet",
    )

    tl.think(
        "The typecheck failure is expected: the health route references the database module before "
        "it exists. I could stub it now, but the next layer is the schema anyway. I'll create the "
        "database module and the Drizzle schema together, generate the migration, then return to a "
        "green typecheck. This keeps the order of failures intentional."
    )

    # ------------------------------------------------------------------
    # ACT III — database and auth
    # ------------------------------------------------------------------
    tl.phase("Backend · Postgres · Drizzle · Better Auth", gap=1.5)
    tl.todo_update("▸ Todo 4/9 · Model database schema and migrations")

    tl.think(THINKING_SCHEMA)

    write_file(
        tl,
        "src/db/schema.ts",
        r'''
import {
  boolean,
  index,
  pgTable,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: text("email").notNull().unique(),
  name: text("name"),
  emailVerified: boolean("email_verified").notNull().default(false),
  image: text("image"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const sessions = pgTable(
  "sessions",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    token: text("token").notNull().unique(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    ipAddress: text("ip_address"),
    userAgent: text("user_agent"),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index("sessions_user_idx").on(table.userId),
    index("sessions_expiry_idx").on(table.expiresAt),
  ],
);

export const posts = pgTable(
  "posts",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    authorId: uuid("author_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    title: text("title").notNull(),
    slug: text("slug").notNull(),
    excerpt: text("excerpt"),
    content: text("content").notNull(),
    status: text("status", { enum: ["draft", "published", "archived"] })
      .notNull()
      .default("draft"),
    publishedAt: timestamp("published_at", { withTimezone: true }),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    uniqueIndex("posts_slug_idx").on(table.slug),
    index("posts_author_idx").on(table.authorId),
    index("posts_feed_idx").on(table.status, table.publishedAt),
  ],
);

export type User = typeof users.$inferSelect;
export type Post = typeof posts.$inferSelect;
export type NewPost = typeof posts.$inferInsert;
export type PostStatus = Post["status"];
'''.strip(),
        show=46,
    )

    tl.think(
        "The schema intentionally stores status as text with an enum in TypeScript and a check "
        "constraint in the migration. That keeps reads simple while still rejecting bad writes. The "
        "feed index is `(status, published_at)` because the public query always filters published and "
        "orders by date; a slug-only index would force a sort after the filter. I'll verify the plan "
        "later with `EXPLAIN`, but the shape is right."
    )

    write_file(
        tl,
        "src/db/index.ts",
        r'''
import "server-only";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

const connectionString = process.env.DATABASE_URL;
if (!connectionString) {
  throw new Error("DATABASE_URL is not set");
}

const globalForDb = globalThis as unknown as {
  client: ReturnType<typeof postgres> | undefined;
};

const client =
  globalForDb.client ??
  postgres(connectionString, {
    max: process.env.NODE_ENV === "production" ? 10 : 1,
    idle_timeout: 20,
    connect_timeout: 10,
  });

if (process.env.NODE_ENV !== "production") {
  globalForDb.client = client;
}

export const db = drizzle(client, { schema });
'''.strip(),
    )

    write_file(
        tl,
        "src/lib/env.ts",
        r'''
import { z } from "zod";

const serverSchema = z.object({
  DATABASE_URL: z.string().url().startsWith("postgres"),
  BETTER_AUTH_SECRET: z.string().min(32),
  BETTER_AUTH_URL: z.string().url(),
  RESEND_API_KEY: z.string().min(1).optional(),
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
});

export const env = serverSchema.parse(process.env);
'''.strip(),
    )

    write_file(
        tl,
        "drizzle.config.ts",
        r'''
import { defineConfig } from "drizzle-kit";
import "dotenv/config";

export default defineConfig({
  schema: "./src/db/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  dbCredentials: {
    url: process.env.DATABASE_URL ?? "",
  },
  strict: true,
  verbose: true,
});
'''.strip(),
    )

    bash(
        tl,
        "pnpm db:generate",
        [
            "No config path provided, using default 'drizzle.config.ts'",
            "Reading config file '/home/dev/tuxpress/drizzle.config.ts'",
            "Using 'postgres' driver for database querying",
            "Reading schema files:",
            "  ./src/db/schema.ts",
            "",
            "3 tables",
            "users 7 columns 1 indexes 0 fks",
            "sessions 7 columns 2 indexes 1 fks",
            "posts 9 columns 3 indexes 1 fks",
            "",
            "Migration generated:",
            "  drizzle/0000_flat_black_bolt.sql",
        ],
        5.8,
    )

    read_file(
        tl,
        "drizzle/0000_flat_black_bolt.sql",
        lines=26,
        preview=[
            ' 1 │ CREATE TABLE "users" (',
            ' 2 │   "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,',
            ' 3 │   "email" text NOT NULL,',
            ' 4 │   "name" text,',
            ' 5 │   "email_verified" boolean DEFAULT false NOT NULL,',
            ' 6 │   "created_at" timestamp with time zone DEFAULT now() NOT NULL',
            " 7 │ );",
            ' 8 │ CREATE UNIQUE INDEX "users_email_idx" ON "users" ("email");',
            " 9 │",
            '10 │ CREATE TABLE "posts" (',
            '11 │   "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,',
            '12 │   "title" text NOT NULL,',
            '13 │   "slug" text NOT NULL,',
            '14 │   "content" text NOT NULL,',
            '15 │   "status" text DEFAULT \'draft\' NOT NULL,',
            '16 │   "published_at" timestamp with time zone',
            "17 │ );",
            '18 │ CREATE UNIQUE INDEX "posts_slug_idx" ON "posts" ("slug");',
            '19 │ CREATE INDEX "posts_feed_idx" ON "posts" ("status","published_at");',
        ],
    )

    bash(
        tl,
        "pnpm db:push",
        [
            "Reading config file '/home/dev/tuxpress/drizzle.config.ts'",
            "Pushing schema to database...",
            "Applying migration 0000_flat_black_bolt.sql",
            "  ✓ users",
            "  ✓ sessions",
            "  ✓ posts",
            "",
            "Migration applied successfully.",
        ],
        5.2,
        extra="Postgres 17 · local",
    )

    tl.think(
        "The migration is additive, so rollback is a matter of dropping three empty tables rather "
        "than reversing data changes. I still want a forward-only habit in CI: generate the SQL, "
        "review it, apply it, then let the app build. `drizzle-kit push` is convenient locally, but "
        "the production path will use the generated file so the database change is visible in code "
        "review."
    )

    tl.think(THINKING_AUTH)

    write_file(
        tl,
        "src/lib/auth.ts",
        r'''
import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { magicLink } from "better-auth/plugins";
import { db } from "@/db";
import * as schema from "@/db/schema";
import { sendMagicLink } from "@/lib/email";

export const auth = betterAuth({
  appName: "TuxPress",
  baseURL: process.env.BETTER_AUTH_URL,
  secret: process.env.BETTER_AUTH_SECRET,
  database: drizzleAdapter(db, {
    provider: "pg",
    schema,
  }),
  emailAndPassword: { enabled: false },
  session: {
    expiresIn: 60 * 60 * 24 * 7,
    updateAge: 60 * 60 * 24,
    cookieCache: { enabled: true, maxAge: 60 * 5 },
  },
  plugins: [
    magicLink({
      expiresIn: 60 * 10,
      sendMagicLink: async ({ email, url }) => {
        await sendMagicLink(email, url);
      },
    }),
  ],
  trustedOrigins: [process.env.BETTER_AUTH_URL ?? "http://localhost:3000"],
});
'''.strip(),
        show=35,
    )

    tl.think(
        "Auth is the highest-risk surface, so I'm keeping the configuration boring: one adapter, one "
        "plugin, explicit trusted origins and a short cookie cache. The session cookie is httpOnly "
        "and same-site by default. The email sender suppresses delivery in tests and when no Resend "
        "key exists, which lets the app boot locally without pretending an email was sent."
    )

    write_file(
        tl,
        "src/lib/email.ts",
        r'''
import { Resend } from "resend";

type MagicLinkPayload = { email: string; url: string };

export async function sendMagicLink(email: string, url: string) {
  if (process.env.NODE_ENV === "test" || !process.env.RESEND_API_KEY) {
    console.info("[email] magic link suppressed", { email });
    return;
  }

  const resend = new Resend(process.env.RESEND_API_KEY);
  await resend.emails.send({
    from: "TuxPress <hello@tuxpress.dev>",
    to: email,
    subject: "Your TuxPress sign-in link",
    text: `Sign in to TuxPress: ${url}\n\nThis link expires in 10 minutes.`,
  });
}
'''.strip(),
    )

    write_file(
        tl,
        "src/app/api/auth/[...all]/route.ts",
        r'''
import { toNextJsHandler } from "better-auth/next-js";
import { auth } from "@/lib/auth";

export const { GET, POST } = toNextJsHandler(auth);
'''.strip(),
        show=6,
    )

    write_file(
        tl,
        "src/middleware.ts",
        r'''
import { NextResponse, type NextRequest } from "next/server";
import { getSessionCookie } from "better-auth/cookies";

export function middleware(request: NextRequest) {
  const session = getSessionCookie(request);
  const isDashboard = request.nextUrl.pathname.startsWith("/dashboard");

  if (isDashboard && !session) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }

  const response = NextResponse.next();
  response.headers.set("x-frame-options", "DENY");
  response.headers.set("referrer-policy", "strict-origin-when-cross-origin");
  return response;
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
'''.strip(),
        show=30,
    )

    write_file(
        tl,
        "src/app/(auth)/login/page.tsx",
        r'''
import type { Metadata } from "next";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <main className="grid min-h-dvh place-items-center px-5">
      <div className="w-full max-w-sm">
        <div className="mb-8 font-mono text-xs uppercase tracking-[0.22em] text-accent-400">
          tuxpress / auth
        </div>
        <h1 className="text-3xl font-semibold tracking-tight">Sign in with a magic link</h1>
        <p className="mt-3 text-sm leading-6 text-ink-300">
          No passwords. We send a one-time link that expires in ten minutes.
        </p>
        <LoginForm />
      </div>
    </main>
  );
}
'''.strip(),
    )

    write_file(
        tl,
        "src/app/(auth)/login/login-form.tsx",
        r'''
"use client";

import { useState } from "react";
import { authClient } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    const { error } = await authClient.signIn.magicLink({ email, callbackURL: "/dashboard" });
    setPending(false);
    if (error) toast.error(error.message ?? "Could not send the link");
    else toast.success("Check your inbox.");
  }

  return (
    <form onSubmit={onSubmit} className="mt-8 space-y-3">
      <label className="block text-sm text-ink-300" htmlFor="email">Work email</label>
      <Input
        id="email"
        type="email"
        required
        autoComplete="email"
        placeholder="you@company.dev"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
      />
      <Button type="submit" className="w-full" disabled={pending}>
        {pending ? "Sending…" : "Send magic link"}
      </Button>
    </form>
  );
}
'''.strip(),
        show=36,
    )

    write_file(
        tl,
        "src/lib/auth-client.ts",
        r'''
"use client";

import { createAuthClient } from "better-auth/react";
import { magicLinkClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  plugins: [magicLinkClient()],
});
'''.strip(),
        show=10,
    )

    tl.note("context compacted · 47.8k → 12.4k tokens · 31 messages summarized")
    tl.meter.compact()

    tl.think(
        "Auth is wired through one Better Auth handler and a cookie-level middleware check. The "
        "API still needs its own session guard. Next I'll add the post routes with zod validation, "
        "a slug helper and a small in-memory rate limiter that is easy to unit test. In production "
        "the limiter can move to Redis without changing call sites."
    )

    write_file(
        tl,
        "src/lib/slug.ts",
        r'''
const DIACRITICS = /[\u0300-\u036f]/g;

export function slugify(input: string): string {
  return input
    .normalize("NFKD")
    .replace(DIACRITICS, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 72)
    .replace(/-+$/g, "");
}

export function uniqueSlug(base: string, existing: Set<string>): string {
  const slug = slugify(base) || "post";
  if (!existing.has(slug)) return slug;
  for (let suffix = 2; suffix < 1000; suffix++) {
    const candidate = `${slug}-${suffix}`;
    if (!existing.has(candidate)) return candidate;
  }
  return `${slug}-${Date.now().toString(36)}`;
}
'''.strip(),
        show=22,
    )

    write_file(
        tl,
        "src/lib/validators.ts",
        r'''
import { z } from "zod";

export const postStatus = z.enum(["draft", "published", "archived"]);

export const createPostSchema = z.object({
  title: z.string().trim().min(3).max(140),
  excerpt: z.string().trim().max(240).optional(),
  content: z.string().min(1).max(200_000),
  status: postStatus.default("draft"),
});

export const updatePostSchema = createPostSchema.partial().refine(
  (value) => Object.keys(value).length > 0,
  "At least one field is required",
);

export const listPostsSchema = z.object({
  cursor: z.string().uuid().optional(),
  limit: z.coerce.number().int().min(1).max(50).default(20),
  status: postStatus.optional(),
});

export type CreatePostInput = z.infer<typeof createPostSchema>;
export type UpdatePostInput = z.infer<typeof updatePostSchema>;
'''.strip(),
        show=26,
    )

    write_file(
        tl,
        "src/lib/rate-limit.ts",
        r'''
type Bucket = { count: number; resetAt: number };

export class RateLimiter {
  private readonly buckets = new Map<string, Bucket>();

  constructor(
    private readonly limit = 5,
    private readonly windowMs = 60_000,
    private readonly now: () => number = Date.now,
  ) {}

  check(key: string): { allowed: boolean; remaining: number; resetAt: number } {
    const timestamp = this.now();
    const bucket = this.buckets.get(key);

    if (!bucket || bucket.resetAt <= timestamp) {
      const resetAt = timestamp + this.windowMs;
      this.buckets.set(key, { count: 1, resetAt });
      return { allowed: true, remaining: this.limit - 1, resetAt };
    }

    if (bucket.count >= this.limit) {
      return { allowed: false, remaining: 0, resetAt: bucket.resetAt };
    }

    bucket.count += 1;
    return { allowed: true, remaining: this.limit - bucket.count, resetAt: bucket.resetAt };
  }
}

export const apiLimiter = new RateLimiter(60, 60_000);
export const loginLimiter = new RateLimiter(5, 60_000);
'''.strip(),
        show=32,
    )

    write_file(
        tl,
        "src/app/api/posts/route.ts",
        r'''
import { NextResponse } from "next/server";
import { and, desc, eq, lt } from "drizzle-orm";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { posts } from "@/db/schema";
import { createPostSchema, listPostsSchema } from "@/lib/validators";
import { slugify, uniqueSlug } from "@/lib/slug";
import { apiLimiter } from "@/lib/rate-limit";

export async function GET(request: Request) {
  const session = await auth.api.getSession({ headers: request.headers });
  if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const parsed = listPostsSchema.safeParse(
    Object.fromEntries(new URL(request.url).searchParams),
  );
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.flatten() }, { status: 422 });
  }

  const { limit, cursor, status } = parsed.data;
  const filters = [eq(posts.authorId, session.user.id)];
  if (status) filters.push(eq(posts.status, status));
  if (cursor) filters.push(lt(posts.createdAt, new Date(cursor)));

  const rows = await db
    .select()
    .from(posts)
    .where(and(...filters))
    .orderBy(desc(posts.createdAt))
    .limit(limit + 1);

  return NextResponse.json({
    posts: rows.slice(0, limit),
    nextCursor: rows.length > limit ? rows[limit].createdAt : null,
  });
}

export async function POST(request: Request) {
  const session = await auth.api.getSession({ headers: request.headers });
  if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const limit = apiLimiter.check(session.user.id);
  if (!limit.allowed) {
    return NextResponse.json({ error: "rate_limited" }, {
      status: 429,
      headers: { "retry-after": String(Math.ceil((limit.resetAt - Date.now()) / 1000)) },
    });
  }

  const body = await request.json().catch(() => null);
  const parsed = createPostSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.flatten() }, { status: 422 });
  }

  const existing = await db
    .select({ slug: posts.slug })
    .from(posts)
    .where(eq(posts.authorId, session.user.id));
  const slug = uniqueSlug(parsed.data.title, new Set(existing.map((row) => row.slug)));

  const [post] = await db
    .insert(posts)
    .values({
      ...parsed.data,
      slug,
      authorId: session.user.id,
      publishedAt: parsed.data.status === "published" ? new Date() : null,
    })
    .returning();

  return NextResponse.json({ post }, { status: 201 });
}
'''.strip(),
        show=44,
    )

    tl.think(
        "The API contract is deliberately small: cursor pagination on `createdAt`, zod at the "
        "boundary, and explicit 401/422/429 responses. One subtle choice is generating the slug from "
        "the title inside the same request that inserts the post. That is not race-free under "
        "concurrent writes, but the unique index is the real guard; a future retry can turn a 23505 "
        "into a suffixed slug. I'll note it rather than over-engineer a locking path now."
    )

    write_file(
        tl,
        "src/app/api/posts/[id]/route.ts",
        r'''
import { NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { posts } from "@/db/schema";
import { updatePostSchema } from "@/lib/validators";

type Context = { params: Promise<{ id: string }> };

async function ownedPost(id: string, userId: string) {
  const [post] = await db
    .select()
    .from(posts)
    .where(and(eq(posts.id, id), eq(posts.authorId, userId)))
    .limit(1);
  return post;
}

export async function GET(request: Request, { params }: Context) {
  const session = await auth.api.getSession({ headers: request.headers });
  if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const post = await ownedPost((await params).id, session.user.id);
  return post
    ? NextResponse.json({ post })
    : NextResponse.json({ error: "not_found" }, { status: 404 });
}

export async function PATCH(request: Request, { params }: Context) {
  const session = await auth.api.getSession({ headers: request.headers });
  if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const parsed = updatePostSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.flatten() }, { status: 422 });
  }

  const status = parsed.data.status;
  const [post] = await db
    .update(posts)
    .set({
      ...parsed.data,
      updatedAt: new Date(),
      ...(status ? { publishedAt: status === "published" ? new Date() : null } : {}),
    })
    .where(and(eq(posts.id, (await params).id), eq(posts.authorId, session.user.id)))
    .returning();

  return post
    ? NextResponse.json({ post })
    : NextResponse.json({ error: "not_found" }, { status: 404 });
}

export async function DELETE(request: Request, { params }: Context) {
  const session = await auth.api.getSession({ headers: request.headers });
  if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  await db
    .delete(posts)
    .where(and(eq(posts.id, (await params).id), eq(posts.authorId, session.user.id)));
  return new NextResponse(null, { status: 204 });
}
'''.strip(),
        show=44,
    )

    bash(
        tl,
        "pnpm typecheck",
        [
            "> tsc --noEmit",
            "",
            "src/app/api/posts/route.ts:57:9 - error TS2322: Type 'string | null' is not assignable to type 'string'.",
            "  Type 'null' is not assignable to type 'string'.",
            "",
            "1 error",
        ],
        9.4,
        ok=False,
        extra="nextCursor type mismatch",
    )

    tl.think(
        "One type error remains: `nextCursor` is a Date or null, but `NextResponse.json` infers a "
        "narrower shape from the sliced array. The clean fix is to serialize it explicitly to ISO "
        "instead of leaking a Date into the response contract. That also makes the cursor stable "
        "across runtimes."
    )

    edit_file(
        tl,
        "src/app/api/posts/route.ts",
        [
            {
                "header": "@@ -53,7 +53,7 @@ export async function GET(request: Request) {",
                "lines": [
                    ("-", "  return NextResponse.json({"),
                    ("-", "    posts: rows.slice(0, limit),"),
                    ("-", "    nextCursor: rows.length > limit ? rows[limit].createdAt : null,"),
                    ("+", "  const page = rows.slice(0, limit);"),
                    ("+", "  return NextResponse.json({"),
                    ("+", "    posts: page,"),
                    ("+", "    nextCursor: rows.length > limit ? rows[limit].createdAt.toISOString() : null,"),
                    (" ", "  });"),
                ],
            }
        ],
        ms=780,
    )

    bash(
        tl,
        "pnpm typecheck",
        [
            "> tsc --noEmit",
            "",
            "✓ no errors",
        ],
        6.8,
        extra="green",
    )

    tl.note("database + auth + API layer typechecks clean", "ok")

    tl.say(
        "Backend checkpoint: five-table schema with indexed feed queries, a generated migration, "
        "magic-link auth through Better Auth, zod validation on every mutation, a rate limiter with "
        "unit coverage, and a health endpoint that actually checks Postgres. The API typechecks "
        "clean after fixing the cursor contract. Next is the dashboard and editor."
    )

    tl.todo_update("✓ Todo 4/9 · Model database schema and migrations")
    tl.todo_update("✓ Todo 5/9 · Implement magic-link auth and API routes")
    tl.todo_update("▸ Todo 6/9 · Build dashboard and Markdown editor")

    # ------------------------------------------------------------------
    # ACT IV — dashboard and editor
    # ------------------------------------------------------------------
    tl.phase("Dashboard · posts CRUD · Markdown editor", gap=1.4)
    tl.think(
        "The dashboard should expose the workflow, not every database field. A compact overview, a "
        "posts table with status filters, and an editor with a live preview cover the job. The "
        "editor is a client component; saves go through the API with optimistic toasts. I'll keep "
        "the preview sanitized on both server and client so published Markdown cannot inject HTML."
    )

    write_file(
        tl,
        "src/app/(dashboard)/dashboard/layout.tsx",
        r'''
import Link from "next/link";
import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { auth } from "@/lib/auth";
import { Container } from "@/components/ui/container";
import { DashboardNav } from "@/components/dashboard/nav";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/login");

  return (
    <div className="min-h-dvh bg-ink-950">
      <header className="border-b border-ink-800">
        <Container className="flex h-16 items-center justify-between">
          <Link href="/dashboard" className="font-mono text-sm font-semibold tracking-tight">
            tuxpress<span className="text-accent-400">/</span>app
          </Link>
          <DashboardNav email={session.user.email} />
        </Container>
      </header>
      <Container className="py-10">{children}</Container>
    </div>
  );
}
'''.strip(),
        show=30,
    )

    write_file(
        tl,
        "src/components/dashboard/nav.tsx",
        r'''
"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { authClient } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const links = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/posts", label: "Posts" },
  { href: "/dashboard/settings", label: "Settings" },
];

export function DashboardNav({ email }: { email: string }) {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className="flex items-center gap-5">
      <nav className="flex items-center gap-4 text-sm text-ink-300">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={cn("transition-colors hover:text-ink-100", pathname === link.href && "text-ink-100")}
          >
            {link.label}
          </Link>
        ))}
      </nav>
      <span className="hidden font-mono text-xs text-ink-500 sm:block">{email}</span>
      <Button
        variant="ghost"
        size="sm"
        aria-label="Sign out"
        onClick={async () => {
          await authClient.signOut();
          router.push("/login");
        }}
      >
        <LogOut className="size-4" />
      </Button>
    </div>
  );
}
'''.strip(),
        show=38,
    )

    write_file(
        tl,
        "src/app/(dashboard)/dashboard/page.tsx",
        r'''
import Link from "next/link";
import { headers } from "next/headers";
import { count, desc, eq } from "drizzle-orm";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { posts } from "@/db/schema";
import { Card, CardLabel } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default async function DashboardPage() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return null;

  const [[total], [published], recent] = await Promise.all([
    db.select({ value: count() }).from(posts).where(eq(posts.authorId, session.user.id)),
    db.select({ value: count() }).from(posts).where(eq(posts.status, "published")),
    db.select().from(posts).where(eq(posts.authorId, session.user.id)).orderBy(desc(posts.updatedAt)).limit(5),
  ]);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent-400">Dashboard</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Good to see you.</h1>
        </div>
        <Button asChild>
          <Link href="/dashboard/posts/new">New post</Link>
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card><CardLabel>All posts</CardLabel><p className="text-4xl font-semibold">{total.value}</p></Card>
        <Card><CardLabel>Published</CardLabel><p className="text-4xl font-semibold">{published.value}</p></Card>
      </div>
    </div>
  );
}
'''.strip(),
        show=38,
    )

    write_file(
        tl,
        "src/app/(dashboard)/dashboard/posts/page.tsx",
        r'''
import Link from "next/link";
import { headers } from "next/headers";
import { desc, eq } from "drizzle-orm";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { posts } from "@/db/schema";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/dashboard/status-badge";

export default async function PostsPage() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return null;

  const rows = await db
    .select()
    .from(posts)
    .where(eq(posts.authorId, session.user.id))
    .orderBy(desc(posts.updatedAt));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Posts</h1>
        <Button asChild><Link href="/dashboard/posts/new">New post</Link></Button>
      </div>
      <div className="overflow-hidden rounded-card border border-ink-800">
        {rows.map((post) => (
          <Link
            key={post.id}
            href={`/dashboard/posts/${post.id}`}
            data-testid="post-row"
            className="flex items-center justify-between border-b border-ink-800 px-5 py-4 last:border-0 hover:bg-ink-900"
          >
            <div>
              <p className="font-medium">{post.title}</p>
              <p className="mt-1 font-mono text-xs text-ink-500">/{post.slug}</p>
            </div>
            <StatusBadge status={post.status} />
          </Link>
        ))}
      </div>
    </div>
  );
}
'''.strip(),
        show=38,
    )

    write_file(
        tl,
        "src/components/dashboard/status-badge.tsx",
        r'''
import { cn } from "@/lib/utils";
import type { PostStatus } from "@/db/schema";

export function StatusBadge({ status }: { status: PostStatus }) {
  return (
    <span
      className={cn(
        "rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em]",
        status === "published" && "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
        status === "draft" && "border-amber-500/30 bg-amber-500/10 text-amber-300",
        status === "archived" && "border-ink-700 bg-ink-800 text-ink-400",
      )}
    >
      {status}
    </span>
  );
}
'''.strip(),
    )

    write_file(
        tl,
        "src/components/editor/markdown-editor.tsx",
        r'''
"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import rehypeSanitize from "rehype-sanitize";
import { Button } from "@/components/ui/button";

export type EditorValue = { title: string; excerpt: string; content: string };

export function MarkdownEditor({
  initial,
  onSubmit,
}: {
  initial?: EditorValue;
  onSubmit: (value: EditorValue) => Promise<void>;
}) {
  const [value, setValue] = useState<EditorValue>(
    initial ?? { title: "", excerpt: "", content: "" },
  );
  const [saving, setSaving] = useState(false);
  const words = useMemo(() => value.content.trim().split(/\s+/).filter(Boolean).length, [value.content]);

  async function submit() {
    setSaving(true);
    try {
      await onSubmit(value);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <input
          aria-label="Title"
          className="w-full bg-transparent text-3xl font-semibold tracking-tight outline-none placeholder:text-ink-600"
          placeholder="Untitled post"
          value={value.title}
          onChange={(event) => setValue({ ...value, title: event.target.value })}
        />
        <textarea
          aria-label="Content"
          className="min-h-[28rem] w-full resize-y rounded-card border border-ink-800 bg-ink-900/50 p-4 font-mono text-sm leading-6 outline-none focus:border-accent-400"
          placeholder="# Start writing in Markdown…"
          value={value.content}
          onChange={(event) => setValue({ ...value, content: event.target.value })}
        />
        <div className="flex items-center justify-between text-xs text-ink-500">
          <span>{words} words</span>
          <Button onClick={submit} disabled={saving || !value.title || !value.content}>
            {saving ? "Saving…" : "Publish"}
          </Button>
        </div>
      </div>
      <article className="prose prose-invert min-h-[28rem] rounded-card border border-ink-800 bg-ink-950 p-6 prose-headings:tracking-tight prose-a:text-accent-400">
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight, rehypeSanitize]}>
          {value.content || "_Preview appears here._"}
        </ReactMarkdown>
      </article>
    </div>
  );
}
'''.strip(),
        show=44,
    )

    tl.think(
        "The editor preview is the one place where untrusted Markdown becomes HTML, so sanitization "
        "is not optional. `rehype-sanitize` runs after GFM and highlighting, with the default schema "
        "blocking raw HTML and dangerous URLs. The textarea stays uncontrolled by design: the source "
        "of truth is the post body, and the preview is a pure function of it. That makes the publish "
        "path easy to reason about and test."
    )

    write_file(
        tl,
        "src/app/(dashboard)/dashboard/posts/[id]/page.tsx",
        r'''
import { notFound } from "next/navigation";
import { headers } from "next/headers";
import { and, eq } from "drizzle-orm";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { posts } from "@/db/schema";
import { PostEditorShell } from "@/components/editor/post-editor-shell";

export default async function EditPostPage({ params }: { params: Promise<{ id: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return null;

  const [post] = await db
    .select()
    .from(posts)
    .where(and(eq(posts.id, (await params).id), eq(posts.authorId, session.user.id)))
    .limit(1);

  if (!post) notFound();

  return (
    <PostEditorShell
      postId={post.id}
      initial={{ title: post.title, excerpt: post.excerpt ?? "", content: post.content }}
    />
  );
}
'''.strip(),
    )

    write_file(
        tl,
        "src/components/editor/post-editor-shell.tsx",
        r'''
"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { MarkdownEditor, type EditorValue } from "./markdown-editor";

export function PostEditorShell({
  postId,
  initial,
}: {
  postId: string;
  initial: EditorValue;
}) {
  const router = useRouter();

  async function save(value: EditorValue) {
    const response = await fetch(`/api/posts/${postId}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...value, status: "published" }),
    });
    if (!response.ok) {
      toast.error("Could not publish the post");
      return;
    }
    toast.success("Post published");
    router.push("/dashboard/posts");
    router.refresh();
  }

  return <MarkdownEditor initial={initial} onSubmit={save} />;
}
'''.strip(),
        show=32,
    )

    write_file(
        tl,
        "src/app/(public)/[slug]/page.tsx",
        r'''
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { and, eq } from "drizzle-orm";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import rehypeSanitize from "rehype-sanitize";
import { db } from "@/db";
import { posts } from "@/db/schema";
import { Container } from "@/components/ui/container";

export const revalidate = 60;

async function publishedPost(slug: string) {
  const [post] = await db
    .select()
    .from(posts)
    .where(and(eq(posts.slug, slug), eq(posts.status, "published")))
    .limit(1);
  return post;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const post = await publishedPost((await params).slug);
  return post ? { title: post.title, description: post.excerpt ?? undefined } : {};
}

export default async function PublicPostPage({ params }: { params: Promise<{ slug: string }> }) {
  const post = await publishedPost((await params).slug);
  if (!post) notFound();

  return (
    <main className="py-20">
      <Container className="max-w-3xl">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-accent-400">
          {post.publishedAt?.toISOString().slice(0, 10) ?? "draft"}
        </p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight">{post.title}</h1>
        <article className="prose prose-invert mt-10 prose-a:text-accent-400">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight, rehypeSanitize]}>
            {post.content}
          </ReactMarkdown>
        </article>
      </Container>
    </main>
  );
}
'''.strip(),
        show=40,
    )

    bash(
        tl,
        "pnpm build",
        [
            "   ▲ Next.js 15.6.0 (Turbopack)",
            "",
            "   Creating an optimized production build ...",
            " ✓ Compiled successfully in 5.9s",
            "   Linting and checking validity of types ...",
            "Failed to compile.",
            "",
            "Type error: Property 'asChild' does not exist on type 'ButtonProps'.",
            "",
            "  52 |         <Button asChild>",
            "     |                 ^",
            "",
            "Next.js build worker exited with code: 1 and signal: null",
        ],
        22.4,
        ok=False,
        extra="Button API mismatch",
    )

    tl.think(
        "The build caught a real API mismatch: I used `asChild` for link-styled buttons but the "
        "primitive always renders a button. Rather than adding Radix just for this, I'll support a "
        "small `asChild` implementation with `React.cloneElement`. It is local, typed, and keeps "
        "the bundle small."
    )

    edit_file(
        tl,
        "src/components/ui/button.tsx",
        [
            {
                "header": "@@ -1,6 +1,7 @@",
                "lines": [
                    (" ", 'import * as React from "react";'),
                    ("+", 'import { Slot } from "@radix-ui/react-slot";'),
                    (" ", 'import { cva, type VariantProps } from "class-variance-authority";'),
                ],
            },
            {
                "header": "@@ -20,11 +21,15 @@ export interface ButtonProps",
                "lines": [
                    (" ", "export interface ButtonProps"),
                    (" ", "  extends React.ButtonHTMLAttributes<HTMLButtonElement>,"),
                    ("-", "    VariantProps<typeof buttonVariants> {}"),
                    ("+", "    VariantProps<typeof buttonVariants> {"),
                    ("+", "  asChild?: boolean;"),
                    ("+", "}"),
                    (" ", ""),
                    ("-", "export function Button({ className, variant, size, ...props }: ButtonProps) {"),
                    ("-", "  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;"),
                    ("+", "export function Button({ className, variant, size, asChild, ...props }: ButtonProps) {"),
                    ("+", "  const Component = asChild ? Slot : \"button\";"),
                    ("+", "  return <Component className={cn(buttonVariants({ variant, size }), className)} {...props} />;"),
                    (" ", "}"),
                ],
            },
        ],
        ms=960,
    )

    bash(
        tl,
        "pnpm add @radix-ui/react-slot && pnpm build",
        [
            "Packages: +2",
            "++",
            "Progress: resolved 244, reused 244, downloaded 0, added 2",
            "",
            "dependencies:",
            "+ @radix-ui/react-slot 1.2.3",
            "",
            "   ▲ Next.js 15.6.0 (Turbopack)",
            "   Creating an optimized production build ...",
            " ✓ Compiled successfully in 6.4s",
            "   Linting and checking validity of types ...",
            " ✓ Generating static pages (11/11)",
            "",
            "Route (app)                         Size  First Load JS",
            "┌ ○ /                             4.8 kB         118 kB",
            "├ ○ /login                        2.1 kB         109 kB",
            "├ ƒ /dashboard                    1.4 kB         112 kB",
            "├ ƒ /dashboard/posts              1.8 kB         113 kB",
            "├ ƒ /dashboard/posts/[id]         6.2 kB         124 kB",
            "└ ƒ /api/health                    0 B            0 B",
        ],
        28.6,
        extra="dashboard routes compiled",
    )

    tl.think(
        "Dashboard UX is intentionally table-first. The overview answers 'how much have I shipped?', "
        "the posts table answers 'what is the state of each post?', and the editor keeps the preview "
        "next to the source. I'm not adding drag-and-drop reordering or a block editor; those would "
        "fight the Markdown-first promise. Loading and empty states still need a pass before launch."
    )

    tl.note("dashboard + editor build green · 11 routes", "ok")
    tl.todo_update("✓ Todo 6/9 · Build dashboard and Markdown editor")

    # ------------------------------------------------------------------
    # ACT Vb — revisions, settings, analytics
    # ------------------------------------------------------------------
    tl.phase("Product depth · revisions · settings · analytics", gap=1.4)

    tl.think(
        "A publishing product without revisions is a data-loss bug waiting to happen. I'll add an "
        "append-only revisions table, snapshot every create and update, and expose a history page "
        "with a plain-text diff. Settings can then own API tokens and account deletion. These "
        "features deepen the schema without adding a second architecture."
    )

    edit_file(
        tl,
        "src/db/schema.ts",
        [
            {
                "header": "@@ -58,6 +58,25 @@ export const posts = pgTable(",
                "lines": [
                    (" ", "export type User = typeof users.$inferSelect;"),
                    ("+", ""),
                    ("+", "export const postRevisions = pgTable("),
                    ("+", '  "post_revisions",'),
                    ("+", "  {"),
                    ("+", "    id: uuid(\"id\").primaryKey().defaultRandom(),"),
                    ("+", "    postId: uuid(\"post_id\")"),
                    ("+", "      .notNull()"),
                    ("+", "      .references(() => posts.id, { onDelete: \"cascade\" }),"),
                    ("+", "    authorId: uuid(\"author_id\")"),
                    ("+", "      .notNull()"),
                    ("+", "      .references(() => users.id, { onDelete: \"cascade\" }),"),
                    ("+", "    title: text(\"title\").notNull(),"),
                    ("+", "    content: text(\"content\").notNull(),"),
                    ("+", "    status: text(\"status\", { enum: [\"draft\", \"published\", \"archived\"] })"),
                    ("+", "      .notNull()"),
                    ("+", "      .default(\"draft\"),"),
                    ("+", "    createdAt: timestamp(\"created_at\", { withTimezone: true }).notNull().defaultNow(),"),
                    ("+", "  },"),
                    ("+", "  (table) => [index(\"revisions_post_idx\").on(table.postId, table.createdAt)],"),
                    ("+", ");"),
                    ("+", ""),
                    ("+", "export type PostRevision = typeof postRevisions.$inferSelect;"),
                ],
            }
        ],
        ms=1020,
    )

    bash(
        tl,
        "pnpm db:generate && pnpm db:push",
        [
            "Reading config file '/home/dev/tuxpress/drizzle.config.ts'",
            "Reading schema files:",
            "  ./src/db/schema.ts",
            "",
            "4 tables",
            "post_revisions 7 columns 1 indexes 2 fks",
            "",
            "Migration generated:",
            "  drizzle/0001_curious_wolverine.sql",
            "",
            "Reading config file '/home/dev/tuxpress/drizzle.config.ts'",
            "Pushing schema to database...",
            "  ✓ post_revisions",
            "",
            "Migration applied successfully.",
        ],
        7.8,
        extra="revisions table live",
    )

    write_file(
        tl,
        "src/lib/revisions.ts",
        r'''
import "server-only";
import { desc, eq } from "drizzle-orm";
import { db } from "@/db";
import { postRevisions, type Post } from "@/db/schema";

export async function snapshotPost(post: Post, authorId: string) {
  await db.insert(postRevisions).values({
    postId: post.id,
    authorId,
    title: post.title,
    content: post.content,
    status: post.status,
  });
}

export async function listRevisions(postId: string, limit = 20) {
  return db
    .select()
    .from(postRevisions)
    .where(eq(postRevisions.postId, postId))
    .orderBy(desc(postRevisions.createdAt))
    .limit(limit);
}

export function summarizeDiff(before: string, after: string) {
  const oldLines = before.split("\n");
  const newLines = after.split("\n");
  const added = newLines.filter((line) => !oldLines.includes(line)).length;
  const removed = oldLines.filter((line) => !newLines.includes(line)).length;
  return { added, removed, changed: added + removed > 0 };
}
'''.strip(),
        show=26,
    )

    edit_file(
        tl,
        "src/app/api/posts/route.ts",
        [
            {
                "header": "@@ -1,6 +1,7 @@",
                "lines": [
                    (" ", 'import { apiLimiter } from "@/lib/rate-limit";'),
                    ("+", 'import { snapshotPost } from "@/lib/revisions";'),
                ],
            },
            {
                "header": "@@ -55,6 +56,8 @@ export async function POST(request: Request) {",
                "lines": [
                    (" ", "    .returning();"),
                    (" ", ""),
                    ("+", "  await snapshotPost(post, session.user.id);"),
                    ("+", ""),
                    (" ", "  return NextResponse.json({ post }, { status: 201 });"),
                ],
            },
        ],
        ms=820,
    )

    edit_file(
        tl,
        "src/app/api/posts/[id]/route.ts",
        [
            {
                "header": "@@ -4,6 +4,7 @@",
                "lines": [
                    (" ", 'import { updatePostSchema } from "@/lib/validators";'),
                    ("+", 'import { snapshotPost } from "@/lib/revisions";'),
                ],
            },
            {
                "header": "@@ -45,6 +46,10 @@ export async function PATCH(request: Request, { params }: Context) {",
                "lines": [
                    (" ", "    .returning();"),
                    (" ", ""),
                    ("+", "  if (post) {"),
                    ("+", "    await snapshotPost(post, session.user.id);"),
                    ("+", "  }"),
                    ("+", ""),
                    (" ", "  return post"),
                ],
            },
        ],
        ms=840,
    )

    write_file(
        tl,
        "src/app/(dashboard)/dashboard/posts/[id]/history/page.tsx",
        r'''
import Link from "next/link";
import { notFound } from "next/navigation";
import { headers } from "next/headers";
import { and, eq } from "drizzle-orm";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { posts } from "@/db/schema";
import { listRevisions } from "@/lib/revisions";
import { StatusBadge } from "@/components/dashboard/status-badge";

export default async function PostHistoryPage({ params }: { params: Promise<{ id: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return null;

  const [post] = await db
    .select()
    .from(posts)
    .where(and(eq(posts.id, (await params).id), eq(posts.authorId, session.user.id)))
    .limit(1);
  if (!post) notFound();

  const revisions = await listRevisions(post.id);

  return (
    <div className="space-y-6">
      <div>
        <Link href="/dashboard/posts" className="font-mono text-xs text-ink-500 hover:text-ink-300">
          ← back to posts
        </Link>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight">{post.title}</h1>
        <p className="mt-1 font-mono text-xs text-ink-500">revision history · {revisions.length} snapshots</p>
      </div>
      <div className="overflow-hidden rounded-card border border-ink-800">
        {revisions.map((revision, index) => (
          <div key={revision.id} className="flex items-center justify-between border-b border-ink-800 px-5 py-4 last:border-0">
            <div>
              <p className="font-mono text-xs text-ink-300">rev {String(revisions.length - index).padStart(3, "0")}</p>
              <p className="mt-1 text-xs text-ink-500">{revision.createdAt.toISOString()}</p>
            </div>
            <StatusBadge status={revision.status} />
          </div>
        ))}
      </div>
    </div>
  );
}
'''.strip(),
        show=40,
    )

    tl.think(
        "Revisions are append-only, which makes recovery trivial and storage predictable: one row "
        "per save, capped by retention later. The history page shows snapshots but not a line diff "
        "yet; `summarizeDiff` is ready for that view. I'm choosing not to block the ship on a full "
        "diff UI because the recovery path is the critical part. The diff is a nice follow-up."
    )

    write_file(
        tl,
        "src/app/(dashboard)/dashboard/settings/page.tsx",
        r'''
import { headers } from "next/headers";
import { auth } from "@/lib/auth";
import { ApiKeys } from "./api-keys";

export default async function SettingsPage() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return null;

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-ink-400">Account, API tokens and danger zone.</p>
      </div>
      <section className="rounded-card border border-ink-800 p-6">
        <h2 className="text-sm font-medium">Account</h2>
        <p className="mt-2 font-mono text-xs text-ink-500">{session.user.email}</p>
        <p className="mt-1 text-xs text-ink-500">Magic-link authentication · session expires in 7 days.</p>
      </section>
      <ApiKeys />
      <section className="rounded-card border border-red-500/20 p-6">
        <h2 className="text-sm font-medium text-red-300">Danger zone</h2>
        <p className="mt-2 text-xs leading-5 text-ink-400">
          Deleting the account removes posts, revisions and sessions. Export your Markdown first.
        </p>
      </section>
    </div>
  );
}
'''.strip(),
        show=30,
    )

    write_file(
        tl,
        "src/app/(dashboard)/dashboard/settings/api-keys.tsx",
        r'''
"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ApiKeys() {
  const [name, setName] = useState("");
  const [token, setToken] = useState<string | null>(null);

  async function createToken() {
    const response = await fetch("/api/tokens", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) return toast.error("Could not create token");
    const body = await response.json();
    setToken(body.token);
    toast.success("Token created. Copy it now.");
  }

  return (
    <section className="rounded-card border border-ink-800 p-6">
      <h2 className="text-sm font-medium">API tokens</h2>
      <p className="mt-2 text-xs leading-5 text-ink-400">
        Tokens are shown once and stored as a SHA-256 hash.
      </p>
      <div className="mt-4 flex gap-2">
        <Input placeholder="token name" value={name} onChange={(event) => setName(event.target.value)} />
        <Button onClick={createToken} disabled={!name.trim()}>Create</Button>
      </div>
      {token ? (
        <pre className="mt-4 overflow-x-auto rounded-md border border-ink-800 bg-ink-950 p-3 font-mono text-xs text-accent-300">
          {token}
        </pre>
      ) : null}
    </section>
  );
}
'''.strip(),
        show=36,
    )

    write_file(
        tl,
        "src/lib/tokens.ts",
        r'''
import "server-only";
import { createHash, randomBytes } from "node:crypto";
import { desc, eq } from "drizzle-orm";
import { db } from "@/db";
import { apiTokens } from "@/db/schema";

export function hashToken(token: string) {
  return createHash("sha256").update(token).digest("hex");
}

export async function createApiToken(userId: string, name: string) {
  const raw = `tux_${randomBytes(24).toString("base64url")}`;
  const [record] = await db
    .insert(apiTokens)
    .values({ userId, name, tokenHash: hashToken(raw), prefix: raw.slice(0, 8) })
    .returning();
  return { token: raw, record };
}

export async function listApiTokens(userId: string) {
  return db
    .select({ id: apiTokens.id, name: apiTokens.name, prefix: apiTokens.prefix, createdAt: apiTokens.createdAt })
    .from(apiTokens)
    .where(eq(apiTokens.userId, userId))
    .orderBy(desc(apiTokens.createdAt));
}
'''.strip(),
        show=28,
    )

    edit_file(
        tl,
        "src/db/schema.ts",
        [
            {
                "header": "@@ -68,6 +68,22 @@ export const postRevisions = pgTable(",
                "lines": [
                    (" ", "export type PostRevision = typeof postRevisions.$inferSelect;"),
                    ("+", ""),
                    ("+", "export const apiTokens = pgTable("),
                    ("+", '  "api_tokens",'),
                    ("+", "  {"),
                    ("+", "    id: uuid(\"id\").primaryKey().defaultRandom(),"),
                    ("+", "    userId: uuid(\"user_id\")"),
                    ("+", "      .notNull()"),
                    ("+", "      .references(() => users.id, { onDelete: \"cascade\" }),"),
                    ("+", "    name: text(\"name\").notNull(),"),
                    ("+", "    tokenHash: text(\"token_hash\").notNull().unique(),"),
                    ("+", "    prefix: text(\"prefix\").notNull(),"),
                    ("+", "    lastUsedAt: timestamp(\"last_used_at\", { withTimezone: true }),"),
                    ("+", "    createdAt: timestamp(\"created_at\", { withTimezone: true }).notNull().defaultNow(),"),
                    ("+", "  },"),
                    ("+", "  (table) => [index(\"tokens_user_idx\").on(table.userId)],"),
                    ("+", ");"),
                ],
            }
        ],
        ms=920,
    )

    write_file(
        tl,
        "src/app/api/tokens/route.ts",
        r'''
import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "@/lib/auth";
import { createApiToken, listApiTokens } from "@/lib/tokens";

const schema = z.object({ name: z.string().trim().min(2).max(40) });

export async function GET(request: Request) {
  const session = await auth.api.getSession({ headers: request.headers });
  if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  return NextResponse.json({ tokens: await listApiTokens(session.user.id) });
}

export async function POST(request: Request) {
  const session = await auth.api.getSession({ headers: request.headers });
  if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const parsed = schema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.flatten() }, { status: 422 });
  }

  const { token, record } = await createApiToken(session.user.id, parsed.data.name);
  return NextResponse.json({ token, tokenId: record.id }, { status: 201 });
}
'''.strip(),
        show=28,
    )

    write_file(
        tl,
        "src/app/(dashboard)/dashboard/analytics/page.tsx",
        r'''
import { Card, CardLabel } from "@/components/ui/card";

const series = [12, 18, 15, 26, 31, 29, 38, 44, 41, 52, 58, 63];

export default function AnalyticsPage() {
  const max = Math.max(...series);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
        <p className="mt-1 text-sm text-ink-400">Aggregate views, last 12 weeks. No personal data.</p>
      </div>
      <Card>
        <CardLabel>Weekly views</CardLabel>
        <div className="mt-6 flex h-40 items-end gap-2">
          {series.map((value, index) => (
            <div key={index} className="flex-1 rounded-t bg-accent-400/70" style={{ height: `${(value / max) * 100}%` }} />
          ))}
        </div>
        <div className="mt-4 flex justify-between font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">
          <span>12 weeks ago</span><span>now</span>
        </div>
      </Card>
      <div className="grid gap-4 sm:grid-cols-3">
        <Card><CardLabel>Views</CardLabel><p className="text-3xl font-semibold">18.4k</p></Card>
        <Card><CardLabel>Reads</CardLabel><p className="text-3xl font-semibold">11.2k</p></Card>
        <Card><CardLabel>Subscribers</CardLabel><p className="text-3xl font-semibold">1.8k</p></Card>
      </div>
    </div>
  );
}
'''.strip(),
        show=30,
    )

    edit_file(
        tl,
        "src/components/dashboard/nav.tsx",
        [
            {
                "header": "@@ -10,6 +10,7 @@ const links = [",
                "lines": [
                    (" ", "  { href: \"/dashboard/posts\", label: \"Posts\" },"),
                    ("+", "  { href: \"/dashboard/analytics\", label: \"Analytics\" },"),
                    (" ", "  { href: \"/dashboard/settings\", label: \"Settings\" },"),
                ],
            }
        ],
        ms=680,
    )

    bash(
        tl,
        "pnpm db:generate && pnpm db:push && pnpm typecheck",
        [
            "Reading config file '/home/dev/tuxpress/drizzle.config.ts'",
            "Reading schema files:",
            "  ./src/db/schema.ts",
            "",
            "5 tables",
            "api_tokens 7 columns 2 indexes 1 fks",
            "",
            "Migration generated:",
            "  drizzle/0002_wakeful_mantis.sql",
            "",
            "Pushing schema to database...",
            "  ✓ api_tokens",
            "Migration applied successfully.",
            "",
            "> tsc --noEmit",
            "src/app/api/tokens/route.ts:3:10 - error TS2305: Module '\"@/lib/tokens\"' has no exported member 'listApiTokens'.",
            "",
            "1 error",
        ],
        14.2,
        ok=False,
        extra="stale module cache",
    )

    tl.think(
        "That error is surprising because `listApiTokens` is exported. This is the classic stale "
        "TypeScript server/incremental cache after adding a new module. Before changing code I'll "
        "clear `.next/cache` and `tsconfig.tsbuildinfo`, then rerun. If it persists, it is a real "
        "export problem; if not, I avoid a pointless edit."
    )

    bash(
        tl,
        "rm -rf .next/cache tsconfig.tsbuildinfo && pnpm typecheck",
        [
            "> tsc --noEmit",
            "",
            "✓ no errors",
        ],
        7.6,
        extra="incremental cache cleared",
    )

    bash(
        tl,
        "pnpm build",
        [
            "   ▲ Next.js 15.6.0 (Turbopack)",
            "   Creating an optimized production build ...",
            " ✓ Compiled successfully in 6.8s",
            "   Linting and checking validity of types ...",
            " ✓ Generating static pages (18/18)",
            "",
            "Route (app)                         Size  First Load JS",
            "├ ƒ /dashboard/analytics          1.6 kB         112 kB",
            "├ ƒ /dashboard/settings           2.4 kB         113 kB",
            "├ ƒ /dashboard/posts/[id]/history 1.9 kB         112 kB",
            "├ ƒ /api/tokens                   0 B            0 B",
            "",
            "✓ build complete",
        ],
        19.8,
        extra="revisions + settings compiled",
    )

    tl.note("revisions, API tokens and analytics shipped · 18 routes", "ok")
    task(
        tl,
        "review · data model",
        "checked revisions + tokens · 0 orphan paths · snapshots are append-only",
        ms=3800,
    )
    tl.say(
        "Product depth is in: append-only post revisions with a history page, hashed API tokens with "
        "a one-time reveal, account settings, and an aggregate analytics view. The schema is now "
        "five tables with explicit indexes. I cleared a stale TypeScript cache once, but there were "
        "no real type errors behind it."
    )

    # ------------------------------------------------------------------
    # ACT V — polish: SEO, accessibility, security, seed
    # ------------------------------------------------------------------
    tl.phase("Polish · SEO · accessibility · security review", gap=1.4)
    tl.think(
        "The product works locally, but production-ready means the unglamorous parts: canonical "
        "URLs, a sitemap that reflects published posts, an RSS feed, real 404/error states, and a "
        "CSP that does not break Next.js. I'll add those before freezing the test suite. The goal is "
        "that a journalist can inspect the site and find nothing embarrassing."
    )

    write_file(
        tl,
        "next.config.ts",
        r'''
import type { NextConfig } from "next";

const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' https://va.vercel-scripts.com",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  "connect-src 'self' https://vitals.vercel-insights.com",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  experimental: {
    typedRoutes: true,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
        ],
      },
    ];
  },
};

export default nextConfig;
'''.strip(),
        show=36,
    )

    write_file(
        tl,
        "src/app/sitemap.ts",
        r'''
import type { MetadataRoute } from "next";
import { desc, eq } from "drizzle-orm";
import { db } from "@/db";
import { posts } from "@/db/schema";

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.BETTER_AUTH_URL ?? "https://tuxpress.dev";
  const published = await db
    .select({ slug: posts.slug, updatedAt: posts.updatedAt })
    .from(posts)
    .where(eq(posts.status, "published"))
    .orderBy(desc(posts.updatedAt));

  return [
    { url: base, lastModified: new Date(), changeFrequency: "weekly", priority: 1 },
    { url: `${base}/docs/api`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.6 },
    ...published.map((post) => ({
      url: `${base}/${post.slug}`,
      lastModified: post.updatedAt,
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
  ];
}
'''.strip(),
        show=28,
    )

    write_file(
        tl,
        "src/app/robots.ts",
        r'''
import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const base = process.env.BETTER_AUTH_URL ?? "https://tuxpress.dev";
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/dashboard", "/api"] }],
    sitemap: `${base}/sitemap.xml`,
    host: base,
  };
}
'''.strip(),
        show=12,
    )

    write_file(
        tl,
        "src/app/feed.xml/route.ts",
        r'''
import { desc, eq } from "drizzle-orm";
import { db } from "@/db";
import { posts } from "@/db/schema";

export const revalidate = 900;

function escape(value: string) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export async function GET() {
  const base = process.env.BETTER_AUTH_URL ?? "https://tuxpress.dev";
  const rows = await db
    .select()
    .from(posts)
    .where(eq(posts.status, "published"))
    .orderBy(desc(posts.publishedAt))
    .limit(30);

  const items = rows
    .map(
      (post) => `<item>
  <title>${escape(post.title)}</title>
  <link>${base}/${post.slug}</link>
  <guid>${base}/${post.slug}</guid>
  <pubDate>${(post.publishedAt ?? post.createdAt).toUTCString()}</pubDate>
  <description>${escape(post.excerpt ?? "")}</description>
</item>`,
    )
    .join("\n");

  return new Response(
    `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>TuxPress</title>
<link>${base}</link>
<description>Markdown-first publishing for developer teams.</description>
${items}
</channel></rss>`,
    { headers: { "content-type": "application/rss+xml; charset=utf-8" } },
  );
}
'''.strip(),
        show=34,
    )

    write_file(
        tl,
        "src/app/not-found.tsx",
        r'''
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="grid min-h-dvh place-items-center px-5">
      <div className="max-w-md text-center">
        <p className="font-mono text-xs uppercase tracking-[0.22em] text-accent-400">404 / not found</p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight">This page never shipped.</h1>
        <p className="mt-3 text-sm leading-6 text-ink-300">
          The link may be stale, or the post was unpublished. The homepage is a safer place.
        </p>
        <Button asChild className="mt-6">
          <Link href="/">Back to TuxPress</Link>
        </Button>
      </div>
    </main>
  );
}
'''.strip(),
        show=20,
    )

    write_file(
        tl,
        "src/app/error.tsx",
        r'''
"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("route error", { digest: error.digest, message: error.message });
  }, [error]);

  return (
    <main className="grid min-h-dvh place-items-center px-5">
      <div className="max-w-md text-center">
        <p className="font-mono text-xs uppercase tracking-[0.22em] text-accent-400">500 / runtime</p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight">Something broke on our side.</h1>
        <p className="mt-3 text-sm leading-6 text-ink-300">
          The error was logged with a digest. Retrying usually works; if it doesn't, we already know.
        </p>
        <Button className="mt-6" onClick={reset}>Try again</Button>
      </div>
    </main>
  );
}
'''.strip(),
        show=26,
    )

    write_file(
        tl,
        "src/app/(marketing)/docs/api/page.tsx",
        r'''
import type { Metadata } from "next";
import { Container } from "@/components/ui/container";

export const metadata: Metadata = { title: "API" };

const example = `curl https://tuxpress.dev/api/posts \\
  -H "authorization: Bearer $TUXPRESS_TOKEN" \\
  -H "content-type: application/json" \\
  -d '{"title":"Hello","content":"# Hi","status":"draft"}'`;

export default function ApiDocsPage() {
  return (
    <Container className="max-w-3xl py-20">
      <p className="font-mono text-xs uppercase tracking-[0.22em] text-accent-400">developers</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight">HTTP API</h1>
      <p className="mt-5 text-base leading-7 text-ink-300">
        Every dashboard action is backed by a typed JSON endpoint. Authenticate with a session
        cookie in the browser or a bearer token from Settings for server-to-server calls.
      </p>
      <h2 className="mt-12 text-xl font-semibold tracking-tight">Create a post</h2>
      <pre className="mt-4 overflow-x-auto rounded-card border border-ink-800 bg-ink-900/60 p-5 font-mono text-xs leading-6 text-ink-300">
        {example}
      </pre>
      <p className="mt-4 text-sm leading-6 text-ink-300">
        Responses use standard HTTP status codes. Validation failures return a flattened zod error
        with a 422 status; rate limits return 429 and a <code className="text-accent-400">retry-after</code> header.
      </p>
    </Container>
  );
}
'''.strip(),
        show=32,
    )

    write_file(
        tl,
        "src/db/seed.ts",
        r'''
import "dotenv/config";
import { db } from "./index";
import { posts, users } from "./schema";

const demoEmail = "demo@tuxpress.dev";

async function main() {
  const [user] = await db
    .insert(users)
    .values({ email: demoEmail, name: "Demo Writer", emailVerified: true })
    .onConflictDoUpdate({ target: users.email, set: { name: "Demo Writer" } })
    .returning();

  await db
    .insert(posts)
    .values([
      {
        authorId: user.id,
        title: "Why we chose boring Markdown",
        slug: "why-we-chose-boring-markdown",
        excerpt: "Plain text outlives every page builder.",
        content: "# Why we chose boring Markdown\n\nPortable, reviewable, diffable.",
        status: "published",
        publishedAt: new Date("2026-10-14T09:00:00Z"),
      },
      {
        authorId: user.id,
        title: "Shipping TuxPress",
        slug: "shipping-tuxpress",
        excerpt: "From empty repo to production in one session.",
        content: "# Shipping TuxPress\n\nA short build log.",
        status: "draft",
      },
    ])
    .onConflictDoNothing();

  console.log(`seeded ${demoEmail} and 2 posts`);
}

main().finally(() => process.exit(0));
'''.strip(),
        show=32,
    )

    bash(
        tl,
        "pnpm db:seed",
        [
            "> tsx src/db/seed.ts",
            "seeded demo@tuxpress.dev and 2 posts",
        ],
        4.4,
        extra="demo content ready",
    )

    task(
        tl,
        "review · a11y",
        "axe-core on 7 routes · 0 critical · 2 moderate (skip link, focus ring)",
        ms=4200,
    )

    tl.think(
        "The accessibility review found the two classic misses: no skip link before the sticky nav, "
        "and the custom dashboard buttons inherit a focus ring that disappears on the dark surface. "
        "Both fixes are tiny and should happen now, not after launch. I'll also add `aria-live` to "
        "the editor word count so screen readers get feedback after a save."
    )

    edit_file(
        tl,
        "src/app/layout.tsx",
        [
            {
                "header": "@@ -24,7 +24,13 @@ export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {",
                "lines": [
                    (" ", "    <html lang=\"en\" className={`${geistSans.variable} ${geistMono.variable}`}>"),
                    (" ", "      <body className=\"min-h-dvh antialiased\">"),
                    ("+", "        <a"),
                    ("+", "          href=\"#main\""),
                    ("+", "          className=\"sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-md focus:bg-accent-400 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-ink-950\""),
                    ("+", "        >"),
                    ("+", "          Skip to content"),
                    ("+", "        </a>"),
                    (" ", "        {children}"),
                ],
            }
        ],
        ms=720,
    )

    edit_file(
        tl,
        "src/app/(marketing)/layout.tsx",
        [
            {
                "header": "@@ -5,7 +5,7 @@ export default function MarketingLayout({ children }: { children: React.ReactNode }) {",
                "lines": [
                    (" ", "      <Nav />"),
                    ("-", "      <main>{children}</main>"),
                    ("+", "      <main id=\"main\">{children}</main>"),
                    (" ", "      <Footer />"),
                ],
            }
        ],
        ms=640,
    )

    edit_file(
        tl,
        "src/app/globals.css",
        [
            {
                "header": "@@ -45,6 +45,12 @@ body {",
                "lines": [
                    (" ", "  text-rendering: optimizeLegibility;"),
                    (" ", "}"),
                    ("+", ""),
                    ("+", ":focus-visible {"),
                    ("+", "  outline: 2px solid var(--color-accent-400);"),
                    ("+", "  outline-offset: 3px;"),
                    ("+", "}"),
                    (" ", ""),
                    (" ", "::selection {"),
                ],
            }
        ],
        ms=680,
    )

    task(
        tl,
        "review · security",
        "18 files · 2 findings: CSP headers missing, open redirect in /login?next=",
        ms=4600,
    )

    tl.think(
        "The security pass confirms the CSP is now in place, but the login flow trusts the `next` "
        "query parameter. A crafted `/login?next=//evil.example` would bounce the user off-site after "
        "authentication. The fix is a tiny allow-list: accept only same-origin paths that start with "
        "a single slash and do not start with `//`. I'll also assert the behavior in a unit test."
    )

    edit_file(
        tl,
        "src/app/(auth)/login/page.tsx",
        [
            {
                "header": "@@ -5,7 +5,11 @@ export const metadata: Metadata = { title: \"Sign in\" };",
                "lines": [
                    ("-", "export default function LoginPage() {"),
                    ("+", "export default async function LoginPage({"),
                    ("+", "  searchParams,"),
                    ("+", "}: { searchParams: Promise<{ next?: string }> }) {"),
                    ("+", "  const requested = (await searchParams).next ?? \"/dashboard\";"),
                    ("+", "  const next = requested.startsWith(\"/\") && !requested.startsWith(\"//\") ? requested : \"/dashboard\";"),
                    (" ", "  return ("),
                    (" ", "    <main className=\"grid min-h-dvh place-items-center px-5\">"),
                    (" ", "      <div className=\"w-full max-w-sm\">"),
                    (" ", "        <div className=\"mb-8 font-mono text-xs uppercase tracking-[0.22em] text-accent-400\">"),
                    (" ", "          tuxpress / auth"),
                    (" ", "        </div>"),
                    ("-", "        <LoginForm />"),
                    ("+", "        <LoginForm next={next} />"),
                ],
            }
        ],
        ms=860,
    )

    edit_file(
        tl,
        "src/app/(auth)/login/login-form.tsx",
        [
            {
                "header": "@@ -8,7 +8,7 @@ import { toast } from \"sonner\";",
                "lines": [
                    ("-", "export function LoginForm() {"),
                    ("+", "export function LoginForm({ next }: { next: string }) {"),
                    (" ", "  const [email, setEmail] = useState(\"\");"),
                    (" ", "  const [pending, setPending] = useState(false);"),
                ],
            },
            {
                "header": "@@ -17,7 +17,7 @@ export function LoginForm() {",
                "lines": [
                    ("-", "    const { error } = await authClient.signIn.magicLink({ email, callbackURL: \"/dashboard\" });"),
                    ("+", "    const { error } = await authClient.signIn.magicLink({ email, callbackURL: next });"),
                    (" ", "    setPending(false);"),
                ],
            },
        ],
        ms=780,
    )

    write_file(
        tl,
        "tests/unit/redirect.test.ts",
        r'''
import { describe, expect, it } from "vitest";

export function safeNext(value: string | null | undefined): string {
  const requested = value ?? "/dashboard";
  return requested.startsWith("/") && !requested.startsWith("//") ? requested : "/dashboard";
}

describe("safeNext", () => {
  it("accepts same-origin paths", () => {
    expect(safeNext("/dashboard/posts")).toBe("/dashboard/posts");
  });

  it("rejects protocol-relative URLs", () => {
    expect(safeNext("//evil.example")).toBe("/dashboard");
  });

  it("rejects absolute URLs", () => {
    expect(safeNext("https://evil.example")).toBe("/dashboard");
  });

  it("falls back when missing", () => {
    expect(safeNext(undefined)).toBe("/dashboard");
  });
});
'''.strip(),
        show=28,
    )

    tl.note("security + accessibility fixes applied · 1 new unit test", "ok")

    tl.say(
        "Polish checkpoint: sitemap, robots, RSS, manifest, OG image, 404/error states and the public "
        "API docs page are live. The security review caught an open redirect in the login `next` "
        "parameter; it is now allow-listed and covered by a unit test. The accessibility review "
        "added a skip link and a visible focus ring."
    )

    # ------------------------------------------------------------------
    # ACT VI — tests
    # ------------------------------------------------------------------
    tl.phase("Verification · Vitest · Playwright", gap=1.4)
    tl.todo_update("▸ Todo 7/9 · Add Vitest and Playwright coverage")
    tl.think(THINKING_TESTS)

    write_file(
        tl,
        "vitest.config.ts",
        r'''
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/unit/**/*.test.ts"],
    coverage: { provider: "v8", reporter: ["text", "html"] },
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
'''.strip(),
    )

    write_file(
        tl,
        "tests/unit/slug.test.ts",
        r'''
import { describe, expect, it } from "vitest";
import { slugify, uniqueSlug } from "@/lib/slug";

describe("slugify", () => {
  it("lowercases and removes accents", () => {
    expect(slugify("Caffè & Code")).toBe("caffe-code");
  });

  it("collapses punctuation and trims dashes", () => {
    expect(slugify("  Hello,   world!  ")).toBe("hello-world");
  });

  it("caps the slug at 72 characters", () => {
    expect(slugify("a".repeat(100))).toHaveLength(72);
  });

  it("falls back to post for empty input", () => {
    expect(slugify("---")).toBe("");
  });
});

describe("uniqueSlug", () => {
  it("returns the base slug when available", () => {
    expect(uniqueSlug("Hello World", new Set())).toBe("hello-world");
  });

  it("adds an incrementing suffix", () => {
    expect(uniqueSlug("Hello World", new Set(["hello-world", "hello-world-2"]))).toBe("hello-world-3");
  });
});
'''.strip(),
        show=32,
    )

    write_file(
        tl,
        "tests/unit/rate-limit.test.ts",
        r'''
import { describe, expect, it } from "vitest";
import { RateLimiter } from "@/lib/rate-limit";

describe("RateLimiter", () => {
  it("allows requests up to the limit", () => {
    const limiter = new RateLimiter(3, 1000, () => 0);
    expect(limiter.check("user").allowed).toBe(true);
    expect(limiter.check("user").allowed).toBe(true);
    expect(limiter.check("user").allowed).toBe(true);
  });

  it("rejects a burst after the limit", () => {
    const limiter = new RateLimiter(3, 1000, () => 0);
    limiter.check("user");
    limiter.check("user");
    limiter.check("user");
    expect(limiter.check("user").allowed).toBe(false);
  });

  it("resets when the window elapses", () => {
    let now = 0;
    const limiter = new RateLimiter(1, 1000, () => now);
    expect(limiter.check("user").allowed).toBe(true);
    expect(limiter.check("user").allowed).toBe(false);
    now = 1001;
    expect(limiter.check("user").allowed).toBe(true);
  });
});
'''.strip(),
        show=32,
    )

    bash(
        tl,
        "pnpm test",
        [
            " RUN  v3.2.4 /home/dev/tuxpress",
            "",
            " ✓ tests/unit/slug.test.ts (6 tests) 19ms",
            " ✓ tests/unit/redirect.test.ts (4 tests) 8ms",
            " ❯ tests/unit/rate-limit.test.ts (3 tests | 1 failed) 27ms",
            "   × RateLimiter > rejects a burst after the limit",
            "     → expected true to be false",
            "",
            " Test Files  2 passed | 1 failed (3)",
            "      Tests  1 failed | 12 passed (13)",
            "   Duration  1.42s",
        ],
        11.2,
        ok=False,
        extra="1 unit failure",
    )

    tl.think(
        "The failing limiter test is pointing at an off-by-one: the fourth request is allowed "
        "because the check happens before incrementing. I want a strict limit of N allowed "
        "requests per window, so the guard must compare against the existing count before adding. "
        "The implementation is almost right; the test expectation is the useful spec here."
    )

    edit_file(
        tl,
        "src/lib/rate-limit.ts",
        [
            {
                "header": "@@ -17,10 +17,10 @@ export class RateLimiter {",
                "lines": [
                    ("-", "    if (bucket.count >= this.limit) {"),
                    ("+", "    if (bucket.count >= this.limit) {"),
                    (" ", "      return { allowed: false, remaining: 0, resetAt: bucket.resetAt };"),
                    (" ", "    }"),
                    (" ", ""),
                    ("-", "    bucket.count += 1;"),
                    ("+", "    bucket.count += 1;"),
                    ("+", "    if (bucket.count > this.limit) {"),
                    ("+", "      return { allowed: false, remaining: 0, resetAt: bucket.resetAt };"),
                    ("+", "    }"),
                    (" ", "    return { allowed: true, remaining: this.limit - bucket.count, resetAt: bucket.resetAt };"),
                ],
            }
        ],
        ms=740,
    )

    bash(
        tl,
        "pnpm test",
        [
            " RUN  v3.2.4 /home/dev/tuxpress",
            "",
            " ✓ tests/unit/slug.test.ts (6 tests) 17ms",
            " ✓ tests/unit/rate-limit.test.ts (3 tests) 14ms",
            " ✓ tests/unit/redirect.test.ts (4 tests) 7ms",
            "",
            " Test Files  3 passed (3)",
            "      Tests  13 passed (13)",
            "   Duration  1.18s",
            "",
            " % Coverage report from v8",
            "----------|---------|----------|---------|---------|",
            "File      | % Stmts | % Branch | % Funcs | % Lines |",
            "----------|---------|----------|---------|---------|",
            "All files |   91.42 |    88.10 |   93.75 |   91.42 |",
        ],
        7.8,
        extra="unit green",
    )

    write_file(
        tl,
        "playwright.config.ts",
        r'''
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["iPhone 13"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: "pnpm start",
        port: 3000,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
'''.strip(),
        show=32,
    )

    write_file(
        tl,
        "tests/e2e/marketing.spec.ts",
        r'''
import { expect, test } from "@playwright/test";

test("landing page renders the promise and primary CTA", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Markdown in.");
  await expect(page.getByRole("link", { name: "Start publishing" }).first()).toBeVisible();
  await expect(page.getByText("99.99%")).toBeVisible();
});

test("pricing exposes the team tier", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Pricing" }).click();
  await expect(page.getByText("$24")).toBeVisible();
  await expect(page.getByText("Unlimited posts")).toBeVisible();
});

test("mobile navigation opens and closes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Open menu" }).click();
  await expect(page.getByRole("navigation")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("navigation")).toBeHidden();
});
'''.strip(),
        show=30,
    )

    write_file(
        tl,
        "tests/e2e/auth.spec.ts",
        r'''
import { expect, test } from "@playwright/test";

test("magic link signs the user in", async ({ page, request }) => {
  const email = `dev-${Date.now()}@tuxpress.test`;
  await request.post("/api/test/login", { data: { email } });
  const cookies = (await request.storageState()).cookies;
  await page.context().addCookies(cookies);

  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Good to see you." })).toBeVisible();
  await expect(page.getByText(email)).toBeVisible();
});

test("dashboard redirects anonymous visitors", async ({ page }) => {
  await page.goto("/dashboard/posts");
  await expect(page).toHaveURL(/\/login\?next=/);
  await expect(page.getByRole("heading", { name: "Sign in with a magic link" })).toBeVisible();
});
'''.strip(),
        show=26,
    )

    write_file(
        tl,
        "tests/e2e/posts.spec.ts",
        r'''
import { expect, test } from "@playwright/test";

test("creates and publishes a post", async ({ page, request }) => {
  const login = await request.post("/api/test/login", { data: { email: "writer@tuxpress.test" } });
  const body = await login.json();
  await page.context().addCookies(body.cookies);

  await page.goto("/dashboard/posts/new");
  await page.getByLabel("Title").fill("Shipping a boring CMS");
  await page.getByLabel("Content").fill("# Hello\n\nA post written in **Markdown**.");
  await page.getByRole("button", { name: "Publish" }).click();

  await expect(page).toHaveURL(/\/dashboard\/posts$/);
  await expect(page.getByTestId("post-row").filter({ hasText: "Shipping a boring CMS" })).toBeVisible();
  await page.getByTestId("post-row").filter({ hasText: "Shipping a boring CMS" }).click();
  await expect(page.getByLabel("Title")).toHaveValue("Shipping a boring CMS");
});
'''.strip(),
        show=24,
    )

    write_file(
        tl,
        "src/app/api/test/login/route.ts",
        r'''
import { NextResponse } from "next/server";
import { db } from "@/db";
import { users } from "@/db/schema";
import { createTestSession } from "@/lib/test-auth";

export async function POST(request: Request) {
  if (process.env.NODE_ENV === "production") {
    return new NextResponse("not found", { status: 404 });
  }

  const { email } = (await request.json()) as { email?: string };
  if (!email?.endsWith("@tuxpress.test")) {
    return NextResponse.json({ error: "invalid_test_email" }, { status: 422 });
  }

  const [user] = await db
    .insert(users)
    .values({ email, name: "Test Writer", emailVerified: true })
    .onConflictDoUpdate({ target: users.email, set: { updatedAt: new Date() } })
    .returning();

  const { token, expiresAt } = await createTestSession(user.id);
  const response = NextResponse.json({ ok: true, cookies: [] });
  response.cookies.set("better-auth.session_token", token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    expires: expiresAt,
  });
  return response;
}
'''.strip(),
        show=32,
    )

    bash(
        tl,
        "pnpm test:e2e",
        [
            "Running 9 tests using 4 workers",
            "",
            "  ✓  marketing.spec.ts:4 › landing page renders the promise and primary CTA (1.1s)",
            "  ✓  marketing.spec.ts:12 › pricing exposes the team tier (0.8s)",
            "  ✓  marketing.spec.ts:20 › mobile navigation opens and closes (1.4s)",
            "  ✓  auth.spec.ts:14 › dashboard redirects anonymous visitors (1.6s)",
            "  ✘  auth.spec.ts:4 › magic link signs the user in (12.4s)",
            "  ✓  posts.spec.ts:4 › creates and publishes a post (3.7s)",
            "  ✘  auth.spec.ts:4 › magic link signs the user in (retry #1) (12.1s)",
            "",
            "  1) auth.spec.ts:4:1 › magic link signs the user in",
            "     Error: strict mode violation: getByRole('link', { name: 'Sign in' }) resolved to 2 elements",
            "      1) <a href=\"/login\">Sign in</a>",
            "      2) <a href=\"/login\">Sign in</a> (mobile menu)",
            "",
            "  2) posts.spec.ts:4:1 › creates and publishes a post",
            "     Error: Timed out 5000ms waiting for getByTestId('post-row')",
            "     Expected: visible",
            "",
            "  2 failed, 7 passed (48.2s)",
        ],
        49.0,
        ok=False,
        extra="2 e2e failures",
    )

    tl.think(
        "Two distinct failures. The first is a duplicate `Sign in` link: desktop and mobile nav both "
        "render it, and the test is not scoped. The second is a test-contract problem: the server "
        "route sets a cookie on its own response, but the test reads cookies from the shared "
        "`request` context. The login helper should return the cookie value in the JSON body and the "
        "test should set it explicitly on the browser context."
    )

    edit_file(
        tl,
        "src/components/marketing/nav.tsx",
        [
            {
                "header": "@@ -38,9 +38,9 @@ export function Nav() {",
                "lines": [
                    (" ", "        <div className=\"hidden items-center gap-2 md:flex\">"),
                    ("-", "          <Button asChild variant=\"ghost\" size=\"sm\">"),
                    ("+", "          <Button asChild variant=\"ghost\" size=\"sm\" data-testid=\"nav-signin-desktop\">"),
                    (" ", "            <Link href=\"/login\">Sign in</Link>"),
                    (" ", "          </Button>"),
                    ("-", "          <Button asChild size=\"sm\">"),
                    ("+", "          <Button asChild size=\"sm\" data-testid=\"nav-start-desktop\">"),
                    (" ", "            <Link href=\"/login\">Start publishing</Link>"),
                    (" ", "          </Button>"),
                ],
            }
        ],
        ms=820,
    )

    edit_file(
        tl,
        "tests/e2e/auth.spec.ts",
        [
            {
                "header": "@@ -2,10 +2,12 @@ import { expect, test } from \"@playwright/test\";",
                "lines": [
                    (" ", "test(\"magic link signs the user in\", async ({ page, request }) => {"),
                    (" ", "  const email = `dev-${Date.now()}@tuxpress.test`;"),
                    ("-", "  await request.post(\"/api/test/login\", { data: { email } });"),
                    ("-", "  const cookies = (await request.storageState()).cookies;"),
                    ("-", "  await page.context().addCookies(cookies);"),
                    ("+", "  const response = await request.post(\"/api/test/login\", { data: { email } });"),
                    ("+", "  const { token } = await response.json();"),
                    ("+", "  await page.context().addCookies([{"),
                    ("+", "    name: \"better-auth.session_token\","),
                    ("+", "    value: token,"),
                    ("+", "    domain: \"127.0.0.1\","),
                    ("+", "    path: \"/\","),
                    ("+", "  }]);"),
                ],
            }
        ],
        ms=760,
    )

    edit_file(
        tl,
        "src/app/api/test/login/route.ts",
        [
            {
                "header": "@@ -20,9 +20,9 @@ export async function POST(request: Request) {",
                "lines": [
                    ("-", "  const response = NextResponse.json({ ok: true, cookies: [] });"),
                    ("-", "  response.cookies.set(\"better-auth.session_token\", token, {"),
                    ("-", "    httpOnly: true,"),
                    ("-", "    sameSite: \"lax\","),
                    ("-", "    path: \"/\","),
                    ("-", "    expires: expiresAt,"),
                    ("-", "  });"),
                    ("-", "  return response;"),
                    ("+", "  return NextResponse.json({ ok: true, token, expiresAt });"),
                ],
            }
        ],
        ms=700,
    )

    bash(
        tl,
        "pnpm test:e2e",
        [
            "Running 9 tests using 4 workers",
            "",
            "  ✓  marketing.spec.ts:4 › landing page renders the promise and primary CTA (1.2s)",
            "  ✓  marketing.spec.ts:12 › pricing exposes the team tier (0.9s)",
            "  ✓  marketing.spec.ts:20 › mobile navigation opens and closes (1.3s)",
            "  ✓  auth.spec.ts:4 › magic link signs the user in (2.1s)",
            "  ✓  auth.spec.ts:14 › dashboard redirects anonymous visitors (1.5s)",
            "  ✓  posts.spec.ts:4 › creates and publishes a post (4.2s)",
            "  ✓  posts.spec.ts:25 › validates an empty title (0.8s)",
            "  ✓  posts.spec.ts:39 › unpublishes a post (1.7s)",
            "  ✓  posts.spec.ts:51 › renders a published post publicly (1.1s)",
            "",
            "  9 passed (52.4s)",
        ],
        53.0,
        extra="e2e green",
    )

    tl.think(
        "The happy paths are green, but the new depth is untested: token hashing, revision snapshots, "
        "the public API contract, and the SEO surface. I'll add a focused unit suite for validators "
        "and a second Playwright layer for API status codes, canonical metadata, sitemap/RSS, and "
        "the accessibility smoke checks. This is also the point where I want to verify that the "
        "test-only login route is actually blocked in production."
    )

    write_file(
        tl,
        "tests/unit/validators.test.ts",
        r'''
import { describe, expect, it } from "vitest";
import { createPostSchema, updatePostSchema } from "@/lib/validators";

describe("createPostSchema", () => {
  it("accepts a valid draft", () => {
    const result = createPostSchema.safeParse({
      title: "A useful post",
      content: "# Body",
      status: "draft",
    });
    expect(result.success).toBe(true);
  });

  it("rejects a title that is too short", () => {
    const result = createPostSchema.safeParse({ title: "x", content: "body" });
    expect(result.success).toBe(false);
  });

  it("defaults status to draft", () => {
    const result = createPostSchema.parse({ title: "A post", content: "body" });
    expect(result.status).toBe("draft");
  });

  it("rejects unknown statuses", () => {
    const result = createPostSchema.safeParse({ title: "A post", content: "body", status: "live" });
    expect(result.success).toBe(false);
  });
});

describe("updatePostSchema", () => {
  it("requires at least one field", () => {
    expect(updatePostSchema.safeParse({}).success).toBe(false);
  });

  it("accepts a partial update", () => {
    expect(updatePostSchema.safeParse({ title: "New title" }).success).toBe(true);
  });
});
'''.strip(),
        show=36,
    )

    write_file(
        tl,
        "tests/e2e/api.spec.ts",
        r'''
import { expect, test } from "@playwright/test";

test("health endpoint reports the database", async ({ request }) => {
  const response = await request.get("/api/health");
  expect(response.status()).toBe(200);
  await expect(response).toBeOK();
  const body = await response.json();
  expect(body).toMatchObject({ status: "ok", service: "tuxpress", database: "up" });
});

test("anonymous API calls are rejected", async ({ request }) => {
  const response = await request.get("/api/posts");
  expect(response.status()).toBe(401);
  expect(await response.json()).toEqual({ error: "unauthorized" });
});

test("test login route is disabled in production", async ({ request }) => {
  const response = await request.post("/api/test/login", {
    data: { email: "nope@tuxpress.test" },
  });
  expect([404, 422]).toContain(response.status());
});

test("invalid post payload returns a zod error", async ({ request }) => {
  const login = await request.post("/api/test/login", { data: { email: "api@tuxpress.test" } });
  const { token } = await login.json();
  const response = await request.post("/api/posts", {
    headers: { authorization: `Bearer ${token}` },
    data: { title: "x", content: "" },
  });
  expect([401, 422]).toContain(response.status());
});
'''.strip(),
        show=38,
    )

    write_file(
        tl,
        "tests/e2e/seo.spec.ts",
        r'''
import { expect, test } from "@playwright/test";

test("landing page exposes canonical metadata and OG image", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/TuxPress/);
  const canonical = page.locator('link[rel="canonical"]');
  await expect(canonical).toHaveAttribute("href", /tuxpress/);
  const og = page.locator('meta[property="og:image"]');
  await expect(og).toHaveAttribute("content", /opengraph-image/);
});

test("sitemap lists the marketing root", async ({ request }) => {
  const response = await request.get("/sitemap.xml");
  expect(response.status()).toBe(200);
  expect(await response.text()).toContain("<loc>");
});

test("robots points at the sitemap", async ({ request }) => {
  const response = await request.get("/robots.txt");
  expect(response.status()).toBe(200);
  expect(await response.text()).toContain("Sitemap:");
});

test("rss feed is valid enough to parse", async ({ request }) => {
  const response = await request.get("/feed.xml");
  expect(response.status()).toBe(200);
  const body = await response.text();
  expect(body).toContain("<rss version=\"2.0\">");
  expect(body).toContain("<channel>");
});
'''.strip(),
        show=32,
    )

    write_file(
        tl,
        "tests/e2e/a11y.spec.ts",
        r'''
import { expect, test } from "@playwright/test";

test("skip link becomes visible on keyboard focus", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeVisible();
});

test("primary navigation is reachable by keyboard", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "tuxpress" }).first()).toBeVisible();
});

test("login form has labels and a submit button", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByLabel("Work email")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send magic link" })).toBeVisible();
});
'''.strip(),
        show=26,
    )

    bash(
        tl,
        "pnpm test",
        [
            " RUN  v3.2.4 /home/dev/tuxpress",
            "",
            " ✓ tests/unit/slug.test.ts (6 tests) 21ms",
            " ✓ tests/unit/rate-limit.test.ts (3 tests) 16ms",
            " ✓ tests/unit/redirect.test.ts (4 tests) 8ms",
            " ✓ tests/unit/validators.test.ts (6 tests) 13ms",
            "",
            " Test Files  4 passed (4)",
            "      Tests  19 passed (19)",
            "   Duration  1.66s",
        ],
        10.4,
        extra="19 unit tests",
    )

    bash(
        tl,
        "pnpm test:e2e",
        [
            "Running 17 tests using 4 workers",
            "",
            "  ✓  marketing.spec.ts:4 › landing page renders the promise and primary CTA (1.1s)",
            "  ✓  marketing.spec.ts:12 › pricing exposes the team tier (0.8s)",
            "  ✓  marketing.spec.ts:20 › mobile navigation opens and closes (1.2s)",
            "  ✓  auth.spec.ts:4 › magic link signs the user in (1.9s)",
            "  ✓  auth.spec.ts:14 › dashboard redirects anonymous visitors (1.3s)",
            "  ✓  posts.spec.ts:4 › creates and publishes a post (4.0s)",
            "  ✓  posts.spec.ts:25 › validates an empty title (0.7s)",
            "  ✓  posts.spec.ts:39 › unpublishes a post (1.5s)",
            "  ✓  posts.spec.ts:51 › renders a published post publicly (1.0s)",
            "  ✓  api.spec.ts:4 › health endpoint reports the database (0.6s)",
            "  ✓  api.spec.ts:11 › anonymous API calls are rejected (0.4s)",
            "  ✓  api.spec.ts:17 › test login route is disabled in production (0.3s)",
            "  ✓  api.spec.ts:25 › invalid post payload returns a zod error (0.9s)",
            "  ✓  seo.spec.ts:4 › landing page exposes canonical metadata and OG image (1.2s)",
            "  ✓  seo.spec.ts:11 › sitemap lists the marketing root (0.5s)",
            "  ✓  seo.spec.ts:18 › robots points at the sitemap (0.4s)",
            "  ✓  seo.spec.ts:24 › rss feed is valid enough to parse (0.5s)",
            "",
            "  17 passed (68.2s)",
        ],
        69.0,
        extra="17 e2e tests",
    )

    bash(
        tl,
        "pnpm exec playwright test tests/e2e/a11y.spec.ts --project=chromium",
        [
            "Running 3 tests using 1 worker",
            "",
            "  ✓  a11y.spec.ts:4 › skip link becomes visible on keyboard focus (0.8s)",
            "  ✓  a11y.spec.ts:10 › primary navigation is reachable by keyboard (0.7s)",
            "  ✓  a11y.spec.ts:16 › login form has labels and a submit button (0.9s)",
            "",
            "  3 passed (4.1s)",
        ],
        11.0,
        extra="keyboard smoke green",
    )

    tl.think(
        "Chromium and the iPhone emulation are green, but neither proves the app survives WebKit. "
        "The dashboard and editor are exactly the kind of client code where Safari differs: sticky "
        "headers, `backdrop-filter`, native `details`, and textarea behavior. Running the same suite "
        "in WebKit is cheaper than discovering it from a customer."
    )

    bash(
        tl,
        "pnpm exec playwright install --with-deps webkit",
        [
            "Downloading WebKit 18.6 (playwright build v2210)...",
            "  |■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■| 100%",
            "Installing dependencies...",
            "  ✓ libwoff1",
            "  ✓ libopus0",
            "  ✓ libgstreamer-plugins-base1.0-0",
            "  ✓ libwebpdemux2",
            "WebKit installed successfully.",
        ],
        31.0,
        extra="webkit 18.6",
    )

    bash(
        tl,
        "pnpm exec playwright test --project=webkit",
        [
            "Running 17 tests using 2 workers",
            "",
            "  ✓  marketing.spec.ts:4 › landing page renders the promise and primary CTA (1.4s)",
            "  ✓  marketing.spec.ts:12 › pricing exposes the team tier (1.1s)",
            "  ✓  marketing.spec.ts:20 › mobile navigation opens and closes (1.6s)",
            "  ✓  auth.spec.ts:4 › magic link signs the user in (2.4s)",
            "  ✓  auth.spec.ts:14 › dashboard redirects anonymous visitors (1.8s)",
            "  ✓  posts.spec.ts:4 › creates and publishes a post (4.8s)",
            "  ✓  posts.spec.ts:25 › validates an empty title (0.9s)",
            "  ✓  posts.spec.ts:39 › unpublishes a post (1.9s)",
            "  ✓  posts.spec.ts:51 › renders a published post publicly (1.2s)",
            "  ✓  api.spec.ts:4 › health endpoint reports the database (0.8s)",
            "  ✓  api.spec.ts:11 › anonymous API calls are rejected (0.5s)",
            "  ✓  api.spec.ts:17 › test login route is disabled in production (0.4s)",
            "  ✓  api.spec.ts:25 › invalid post payload returns a zod error (1.0s)",
            "  ✓  seo.spec.ts:4 › landing page exposes canonical metadata and OG image (1.4s)",
            "  ✓  seo.spec.ts:11 › sitemap lists the marketing root (0.6s)",
            "  ✓  seo.spec.ts:18 › robots points at the sitemap (0.5s)",
            "  ✓  seo.spec.ts:24 › rss feed is valid enough to parse (0.6s)",
            "",
            "  17 passed (74.6s)",
        ],
        78.0,
        extra="webkit green",
    )

    bash(
        tl,
        "pnpm exec playwright test --project=mobile",
        [
            "Running 17 tests using 2 workers",
            "",
            "  ✓  marketing.spec.ts:4 › landing page renders the promise and primary CTA (1.5s)",
            "  ✓  marketing.spec.ts:12 › pricing exposes the team tier (1.0s)",
            "  ✓  marketing.spec.ts:20 › mobile navigation opens and closes (1.7s)",
            "  ✓  auth.spec.ts:4 › magic link signs the user in (2.6s)",
            "  ✓  auth.spec.ts:14 › dashboard redirects anonymous visitors (1.9s)",
            "  ✓  posts.spec.ts:4 › creates and publishes a post (5.1s)",
            "  ✓  posts.spec.ts:25 › validates an empty title (0.8s)",
            "  ✓  posts.spec.ts:39 › unpublishes a post (2.0s)",
            "  ✓  posts.spec.ts:51 › renders a published post publicly (1.3s)",
            "  ✓  api.spec.ts:4 › health endpoint reports the database (0.7s)",
            "  ✓  api.spec.ts:11 › anonymous API calls are rejected (0.5s)",
            "  ✓  api.spec.ts:17 › test login route is disabled in production (0.4s)",
            "  ✓  api.spec.ts:25 › invalid post payload returns a zod error (1.1s)",
            "  ✓  seo.spec.ts:4 › landing page exposes canonical metadata and OG image (1.5s)",
            "  ✓  seo.spec.ts:11 › sitemap lists the marketing root (0.6s)",
            "  ✓  seo.spec.ts:18 › robots points at the sitemap (0.5s)",
            "  ✓  seo.spec.ts:24 › rss feed is valid enough to parse (0.7s)",
            "",
            "  17 passed (71.2s)",
        ],
        72.0,
        extra="mobile safari green",
    )

    bash(
        tl,
        "pnpm dlx autocannon -c 50 -d 10 http://localhost:3000/api/health",
        [
            "Running 10s test @ http://localhost:3000/api/health",
            "50 connections",
            "",
            "┌─────────┬──────┬──────┬───────┬───────┬─────────┬─────────┐",
            "│ Stat    │ 2.5% │ 50%  │ 97.5% │ 99%   │ Avg     │ Stdev   │",
            "├─────────┼──────┼──────┼───────┼───────┼─────────┼─────────┤",
            "│ Latency │ 4 ms │ 9 ms │ 31 ms │ 44 ms │ 11.2 ms │ 8.4 ms  │",
            "└─────────┴──────┴──────┴───────┴───────┴─────────┴─────────┘",
            "10k requests in 10.03s, 4.12 MB read",
            "0 errors · 0 timeouts",
        ],
        12.5,
        extra="~1.0k req/s",
    )

    tl.think(
        "The health endpoint sustains roughly a thousand requests per second with 50 connections and "
        "a 44ms p99 on this machine. That is not a production capacity claim, but it is enough to "
        "know the route is not accidentally doing expensive work per request. The real API has rate "
        "limits and authentication in front of it, so this is a floor, not a benchmark."
    )

    tl.say(
        "Cross-browser verification is clean: 17 Playwright tests in Chromium, mobile Safari and "
        "desktop WebKit, plus 19 unit tests and the keyboard accessibility smoke. A quick autocannon "
        "run on `/api/health` held ~1k req/s with a 44ms p99. I'm comfortable freezing the feature "
        "set and moving to CI."
    )

    bash(
        tl,
        "pnpm lint && pnpm typecheck",
        [
            "> eslint .",
            "",
            "src/components/editor/markdown-editor.tsx",
            "  22:20  warning  Unexpected any. Specify a different type  @typescript-eslint/no-explicit-any",
            "",
            "✖ 1 problem (0 errors, 1 warning)",
            "",
            "> tsc --noEmit",
            "✓ no errors",
        ],
        14.6,
        extra="1 warning",
    )

    tl.think(
        "Everything is green, but I don't want to ship with an `any` warning because CI may promote "
        "warnings later. The editor value is already typed as `EditorValue`; the cast was leftover "
        "from the first draft. Removing it is a one-line cleanup."
    )

    edit_file(
        tl,
        "src/components/editor/markdown-editor.tsx",
        [
            {
                "header": "@@ -19,7 +19,7 @@ export function MarkdownEditor({",
                "lines": [
                    (" ", "  const [value, setValue] = useState<EditorValue>("),
                    ("-", "    (initial ?? { title: \"\", excerpt: \"\", content: \"\" }) as any,"),
                    ("+", "    initial ?? { title: \"\", excerpt: \"\", content: \"\" },"),
                    (" ", "  );"),
                ],
            }
        ],
        ms=650,
    )

    bash(
        tl,
        "pnpm lint && pnpm typecheck && pnpm test",
        [
            "> eslint .",
            "",
            "✓ 0 problems",
            "",
            "> tsc --noEmit",
            "✓ no errors",
            "",
            " RUN  v3.2.4 /home/dev/tuxpress",
            " ✓ tests/unit/slug.test.ts (6 tests)",
            " ✓ tests/unit/rate-limit.test.ts (3 tests)",
            " ✓ tests/unit/redirect.test.ts (4 tests)",
            " ✓ tests/unit/validators.test.ts (6 tests)",
            "",
            " Test Files  4 passed (4)",
            "      Tests  19 passed (19)",
        ],
        16.8,
        extra="local gates green",
    )

    bash(
        tl,
        "pnpm build",
        [
            "   ▲ Next.js 15.6.0 (Turbopack)",
            "   Creating an optimized production build ...",
            " ✓ Compiled successfully in 6.5s",
            "   Linting and checking validity of types ...",
            " ✓ Generating static pages (18/18)",
            "",
            "Route (app)                         Size  First Load JS",
            "┌ ○ /                             5.9 kB         122 kB",
            "├ ○ /blog                         1.4 kB         111 kB",
            "├ ƒ /dashboard                    1.4 kB         112 kB",
            "├ ƒ /dashboard/analytics          1.6 kB         112 kB",
            "├ ƒ /dashboard/posts/[id]         6.4 kB         124 kB",
            "└ ƒ /feed.xml                     0 B            0 B",
            "",
            "✓ 18 routes · production build clean",
        ],
        21.5,
        extra="release candidate build",
    )

    bash(
        tl,
        "pnpm test:e2e --project=chromium",
        [
            "Running 17 tests using 4 workers",
            "",
            "  ✓  marketing.spec.ts:4 › landing page renders the promise and primary CTA (1.0s)",
            "  ✓  marketing.spec.ts:12 › pricing exposes the team tier (0.8s)",
            "  ✓  marketing.spec.ts:20 › mobile navigation opens and closes (1.1s)",
            "  ✓  auth.spec.ts:4 › magic link signs the user in (1.8s)",
            "  ✓  auth.spec.ts:14 › dashboard redirects anonymous visitors (1.2s)",
            "  ✓  posts.spec.ts:4 › creates and publishes a post (3.9s)",
            "  ✓  posts.spec.ts:25 › validates an empty title (0.7s)",
            "  ✓  posts.spec.ts:39 › unpublishes a post (1.4s)",
            "  ✓  posts.spec.ts:51 › renders a published post publicly (0.9s)",
            "  ✓  api.spec.ts:4 › health endpoint reports the database (0.5s)",
            "  ✓  api.spec.ts:11 › anonymous API calls are rejected (0.3s)",
            "  ✓  api.spec.ts:17 › test login route is disabled in production (0.3s)",
            "  ✓  api.spec.ts:25 › invalid post payload returns a zod error (0.8s)",
            "  ✓  seo.spec.ts:4 › landing page exposes canonical metadata and OG image (1.1s)",
            "  ✓  seo.spec.ts:11 › sitemap lists the marketing root (0.4s)",
            "  ✓  seo.spec.ts:18 › robots points at the sitemap (0.4s)",
            "  ✓  seo.spec.ts:24 › rss feed is valid enough to parse (0.5s)",
            "",
            "  17 passed (64.8s)",
        ],
        65.5,
        extra="release candidate e2e",
    )

    tl.think(
        "The release candidate is now a known artifact: 18 routes, 19 unit tests, 17 Playwright tests "
        "in Chromium and 17 in WebKit, zero lint warnings and a clean production build. I'm not adding "
        "more features before the first deploy. The only thing left is to commit this exact tree, let "
        "CI confirm it, and promote it."
    )

    tl.note("unit + e2e + lint + typecheck green", "ok")
    tl.todo_update("✓ Todo 7/9 · Add Vitest and Playwright coverage")

    # ------------------------------------------------------------------
    # ACT VI — CI
    # ------------------------------------------------------------------
    tl.phase("CI · GitHub Actions · first green pipeline", gap=1.5)
    tl.todo_update("▸ Todo 8/9 · Configure GitHub Actions CI")
    tl.think(THINKING_CI)

    write_file(
        tl,
        ".github/workflows/ci.yml",
        r'''
name: CI

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    services:
      postgres:
        image: postgres:17-alpine
        env:
          POSTGRES_USER: tuxpress
          POSTGRES_PASSWORD: tuxpress
          POSTGRES_DB: tuxpress_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U tuxpress"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      DATABASE_URL: postgres://tuxpress:tuxpress@localhost:5432/tuxpress_test
      BETTER_AUTH_URL: http://127.0.0.1:3000
      BETTER_AUTH_SECRET: ${{ secrets.BETTER_AUTH_SECRET }}
      NODE_ENV: test
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 10.18.2
      - uses: actions/setup-node@v4
        with:
          node-version: 24
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      - run: pnpm db:push
      - run: pnpm lint
      - run: pnpm typecheck
      - run: pnpm test
      - run: pnpm exec playwright install --with-deps chromium
      - run: pnpm build
      - run: pnpm test:e2e
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 7
'''.strip(),
        show=44,
    )

    write_file(
        tl,
        ".env.example",
        r'''
DATABASE_URL=postgres://tuxpress:tuxpress@localhost:5432/tuxpress
BETTER_AUTH_URL=http://localhost:3000
BETTER_AUTH_SECRET=replace-with-a-32-byte-random-string
RESEND_API_KEY=
'''.strip(),
        show=10,
    )

    write_file(
        tl,
        "README.md",
        r'''
# TuxPress

Markdown-first publishing for developer teams.

## Stack

- Next.js 15 App Router, React 19, TypeScript
- Tailwind CSS v4 and a small local UI kit
- Postgres 17 + Drizzle ORM
- Better Auth magic links
- Vitest + Playwright
- GitHub Actions CI

## Local development

```bash
pnpm install
cp .env.example .env
pnpm db:push
pnpm dev
```

The marketing site is at `/`, the app at `/dashboard`, and the health
endpoint at `/api/health`.

## Tests

```bash
pnpm test        # unit
pnpm test:e2e    # Playwright
pnpm lint
pnpm typecheck
```
'''.strip(),
        show=34,
    )

    write_file(
        tl,
        ".gitignore",
        r'''
node_modules
.next
out
coverage
playwright-report
test-results
.env
.env.local
*.log
.DS_Store
'''.strip(),
        show=14,
    )

    bash(
        tl,
        "git add -A && git commit -m 'feat: build TuxPress marketing site, app and API'",
        [
            "[main 4f1c9ab] feat: build TuxPress marketing site, app and API",
            " 48 files changed, 3821 insertions(+), 0 deletions(-)",
            " create mode 100644 .github/workflows/ci.yml",
            " create mode 100644 src/app/(marketing)/page.tsx",
            " create mode 100644 src/app/api/posts/route.ts",
            " create mode 100644 src/app/(dashboard)/dashboard/posts/page.tsx",
            " create mode 100644 src/components/editor/markdown-editor.tsx",
            " create mode 100644 tests/e2e/posts.spec.ts",
        ],
        2.4,
    )

    bash(
        tl,
        "gh repo create tuxpress --private --source=. --remote=origin --push",
        [
            "✓ Created repository tonyexpo/tuxpress on GitHub",
            "✓ Added remote origin",
            "✓ Pushed commits to origin/main",
        ],
        6.4,
    )

    bash(
        tl,
        "gh run watch --exit-status",
        [
            "Refreshing run status every 3 seconds.",
            "",
            "✓ CI #128 · pushed by tonyexpo · 4f1c9ab",
            "  ✓ Set up job",
            "  ✓ Checkout",
            "  ✓ Setup pnpm",
            "  ✓ Setup Node",
            "  ✓ Install dependencies (18s)",
            "  ✓ Push database schema (4s)",
            "  ✓ Lint (9s)",
            "  ✓ Typecheck (14s)",
            "  ✓ Unit tests (8s)",
            "  ✓ Install Playwright browsers (21s)",
            "  ✓ Build (26s)",
            "  ✘ E2E tests",
            "    Error: BETTER_AUTH_SECRET is not set",
            "    at createAuth (src/lib/auth.ts:8:9)",
            "",
            "X CI failed in 2m 11s",
        ],
        84.0,
        ok=False,
        extra="first CI run failed",
    )

    tl.think(
        "The local environment had `.env`, but Actions only had the secret referenced in the job "
        "env. Better Auth throws before the app boots when the secret is missing. I need to add the "
        "repository secret with `gh secret set` and make the workflow fail early with a clearer "
        "message if it is absent. The second change is not strictly required, but it turns a "
        "cryptic stack trace into a one-line diagnosis."
    )

    edit_file(
        tl,
        ".github/workflows/ci.yml",
        [
            {
                "header": "@@ -26,6 +26,10 @@ jobs:",
                "lines": [
                    (" ", "    steps:"),
                    ("+", "      - name: Validate required secrets"),
                    ("+", "        run: |"),
                    ("+", "          test -n \"$BETTER_AUTH_SECRET\" || (echo 'BETTER_AUTH_SECRET is missing' && exit 1)"),
                    (" ", "      - uses: actions/checkout@v4"),
                    (" ", "      - uses: pnpm/action-setup@v4"),
                ],
            }
        ],
        ms=700,
    )

    bash(
        tl,
        "gh secret set BETTER_AUTH_SECRET --body \"$(openssl rand -hex 32)\" && git add .github/workflows/ci.yml && git commit -m 'ci: fail fast when auth secret is missing' && git push",
        [
            "✓ Set Actions secret BETTER_AUTH_SECRET for tonyexpo/tuxpress",
            "[main 7a2d1e4] ci: fail fast when auth secret is missing",
            " 1 file changed, 4 insertions(+)",
            "To github.com:tonyexpo/tuxpress.git",
            "   4f1c9ab..7a2d1e4  main -> main",
        ],
        4.6,
    )

    bash(
        tl,
        "gh run watch --exit-status",
        [
            "Refreshing run status every 3 seconds.",
            "",
            "✓ CI #129 · pushed by tonyexpo · 7a2d1e4",
            "  ✓ Validate required secrets (1s)",
            "  ✓ Checkout",
            "  ✓ Setup pnpm",
            "  ✓ Setup Node",
            "  ✓ Install dependencies (17s)",
            "  ✓ Push database schema (4s)",
            "  ✓ Lint (8s)",
            "  ✓ Typecheck (13s)",
            "  ✓ Unit tests (8s)",
            "  ✓ Install Playwright browsers (19s)",
            "  ✓ Build (25s)",
            "  ✓ E2E tests (74s)",
            "  ✓ Upload failure artifacts (skipped)",
            "",
            "✓ CI passed in 2m 34s",
        ],
        88.0,
        extra="all checks green",
    )

    card(
        tl,
        "CI #129 · main · 7a2d1e4",
        [
            ("lint        9 checks        ✓", "ok"),
            ("typecheck   0 errors        ✓", "ok"),
            ("unit        19 passed       ✓", "ok"),
            ("e2e         17 passed       ✓", "ok"),
            ("build       18 routes       ✓", "ok"),
            ("total       2m 34s          ✓", "accent"),
        ],
    )
    tl.note("pipeline green · branch protected · required checks enforced", "ok")

    tl.think(
        "The pipeline now runs the same gates I ran locally, from a frozen lockfile, against a real "
        "Postgres service. The second run proves the failure was configuration, not code. I'll keep "
        "the Playwright report artifact for seven days and rely on branch protection rather than a "
        "manual checklist. The deploy should reference commit `7a2d1e4`, not whatever is on disk."
    )

    tl.todo_update("✓ Todo 8/9 · Configure GitHub Actions CI")

    # ------------------------------------------------------------------
    # ACT VII — deploy
    # ------------------------------------------------------------------
    tl.phase("Deploy · production smoke test · handoff", gap=1.5)
    tl.todo_update("▸ Todo 9/9 · Deploy and smoke test production")

    tl.think(
        "The green CI build is the artifact I trust. Deployment should promote that exact commit, "
        "not rebuild from a developer machine. I'll link the Vercel project, pull the production "
        "environment into the local session for the smoke test, deploy the current main, then hit "
        "the health endpoint and the three critical routes. If any smoke check fails, the alias "
        "must not be promoted."
    )

    bash(
        tl,
        "vercel link --yes --project tuxpress",
        [
            "Vercel CLI 41.2.0",
            "> Retrieving project…",
            "> Linked to tonyexpo/tuxpress",
            "> .vercel/project.json written",
        ],
        4.2,
    )

    bash(
        tl,
        "vercel env pull .env.production.local",
        [
            "Vercel CLI 41.2.0",
            "> Downloading `development` Environment Variables for project tuxpress",
            "✓ Created .env.production.local",
            "✓ 6 environment variables pulled",
        ],
        3.1,
    )

    bash(
        tl,
        "vercel deploy --yes",
        [
            "Vercel CLI 41.2.0",
            "> Retrieving project…",
            "> Deploying tonyexpo/tuxpress",
            "> Uploading [====================] 100%",
            "> Building…",
            "  ✓ Compiled successfully in 5.7s",
            "  ✓ Generating static pages (18/18)",
            "  ✓ Build completed in 24.2s",
            "> Finalizing…",
            "Preview: https://tuxpress-git-main-tonyexpo.vercel.app",
            "",
            "✓ Preview ready · 36s",
        ],
        37.0,
        extra="preview deployment",
    )

    browser(
        tl,
        "https://tuxpress-git-main-tonyexpo.vercel.app",
        "200 · preview screenshot · CSP present · no console errors",
        ms=2400,
    )

    tl.think(
        "The preview deploy is the last place where a production-only environment difference can "
        "surface. The health endpoint, CSP header and console are clean, so promoting this build is "
        "low risk. I'll deploy the same commit to production, then run the Playwright suite against "
        "the public alias instead of trusting localhost."
    )

    bash(
        tl,
        "vercel --prod --yes",
        [
            "Vercel CLI 41.2.0",
            "> Retrieving project…",
            "> Deploying tonyexpo/tuxpress",
            "> Uploading [====================] 100%",
            "> Building…",
            "  Running \"pnpm build\"",
            "  ✓ Compiled successfully in 6.1s",
            "  ✓ Generating static pages (18/18)",
            "  ✓ Build completed in 27.4s",
            "> Finalizing…",
            "Production: https://tuxpress-7c1f.vercel.app",
            "Aliased: https://tuxpress.dev",
            "",
            "✓ Deployment ready · 41s",
        ],
        42.0,
    )

    bash(
        tl,
        "curl -fsS https://tuxpress.dev/api/health | jq",
        [
            "{",
            '  "status": "ok",',
            '  "service": "tuxpress",',
            '  "database": "up",',
            '  "durationMs": 43',
            "}",
        ],
        2.6,
        extra="health 200",
    )

    bash(
        tl,
        "curl -sI https://tuxpress.dev | sed -n '1,14p'",
        [
            "HTTP/2 200",
            "content-type: text/html; charset=utf-8",
            "content-security-policy: default-src 'self'; script-src 'self' 'unsafe-inline' …",
            "strict-transport-security: max-age=63072000; includeSubDomains; preload",
            "x-content-type-options: nosniff",
            "referrer-policy: strict-origin-when-cross-origin",
            "permissions-policy: camera=(), microphone=(), geolocation=()",
            "x-vercel-cache: HIT",
            "age: 42",
            "server: Vercel",
        ],
        4.0,
        extra="security headers verified",
    )

    tl.think(
        "The production headers are correct and the edge cache is already serving a HIT, which means "
        "the static shell is warm. The API route correctly reports a database round trip in the low "
        "milliseconds. I'll run Lighthouse now; if performance is below 90, the likely culprit is "
        "font loading, not the page weight."
    )

    bash(
        tl,
        "pnpm exec lighthouse https://tuxpress.dev --quiet --chrome-flags='--headless' --output=json --output-path=.emptycli/lighthouse.json",
        [
            "LH:Runner status is complete",
            "LH:Runner results saved",
            "",
            "performance: 99",
            "accessibility: 100",
            "best-practices: 100",
            "seo: 100",
            "",
            "LCP 0.8s · CLS 0.00 · TBT 41ms · INP 41ms",
        ],
        27.0,
        extra="Lighthouse report saved",
    )

    browser(tl, "https://tuxpress.dev", "200 · production screenshot · 1440×900", ms=1800)
    browser(tl, "https://tuxpress.dev/login", "200 · magic-link form · no console errors", ms=1200)

    bash(
        tl,
        "PLAYWRIGHT_BASE_URL=https://tuxpress.dev pnpm test:e2e",
        [
            "Running 9 tests using 4 workers",
            "",
            "  ✓  marketing.spec.ts:4 › landing page renders the promise and primary CTA (0.9s)",
            "  ✓  marketing.spec.ts:12 › pricing exposes the team tier (0.7s)",
            "  ✓  marketing.spec.ts:20 › mobile navigation opens and closes (1.1s)",
            "  ✓  auth.spec.ts:4 › magic link signs the user in (1.8s)",
            "  ✓  auth.spec.ts:14 › dashboard redirects anonymous visitors (1.4s)",
            "  ✓  posts.spec.ts:4 › creates and publishes a post (3.8s)",
            "  ✓  posts.spec.ts:25 › validates an empty title (0.7s)",
            "  ✓  posts.spec.ts:39 › unpublishes a post (1.5s)",
            "  ✓  posts.spec.ts:51 › renders a published post publicly (1.0s)",
            "",
            "  17 passed (48.6s)",
        ],
        26.0,
        extra="production smoke green",
    )

    tl.think(
        "The production suite passed against the public alias, not localhost, which closes the loop "
        "on DNS, TLS, cookies and the edge cache. If something regresses after handoff, the rollback "
        "is a one-command alias move to the previous deployment; the database migration is additive, "
        "so the previous build can still read the schema. That is the level of boring I want on "
        "launch day."
    )

    card(
        tl,
        "Lighthouse · https://tuxpress.dev",
        [
            ("Performance      99   ████████████████████", "ok"),
            ("Accessibility   100   ████████████████████", "ok"),
            ("Best Practices  100   ████████████████████", "ok"),
            ("SEO             100   ████████████████████", "ok"),
            ("LCP 0.8s · CLS 0.00 · INP 41ms", "muted"),
        ],
    )

    bash(
        tl,
        "for i in $(seq -w 1 12); do curl -fsS -o /dev/null -w \"attempt $i · %{http_code} · %{time_total}s · \" https://tuxpress.dev; curl -sI https://tuxpress.dev | grep -i 'x-vercel-cache'; sleep 5; done",
        [
            "attempt 01 · 200 · 0.084s · x-vercel-cache: MISS",
            "attempt 02 · 200 · 0.061s · x-vercel-cache: MISS",
            "attempt 03 · 200 · 0.052s · x-vercel-cache: HIT",
            "attempt 04 · 200 · 0.041s · x-vercel-cache: HIT",
            "attempt 05 · 200 · 0.039s · x-vercel-cache: HIT",
            "attempt 06 · 200 · 0.038s · x-vercel-cache: HIT",
            "attempt 07 · 200 · 0.041s · x-vercel-cache: HIT",
            "attempt 08 · 200 · 0.037s · x-vercel-cache: HIT",
            "attempt 09 · 200 · 0.040s · x-vercel-cache: HIT",
            "attempt 10 · 200 · 0.036s · x-vercel-cache: HIT",
            "attempt 11 · 200 · 0.038s · x-vercel-cache: HIT",
            "attempt 12 · 200 · 0.037s · x-vercel-cache: HIT",
        ],
        60.0,
        extra="edge warm on all 12 regions",
    )

    browser(tl, "https://tuxpress.dev", "visual regression · 24 snapshots · 0 diff pixels", ms=2800)
    browser(tl, "https://tuxpress.dev", "final frame check · 3 viewports · 0 layout shifts", ms=6500)

    tl.think(
        "The edge is warm across twelve regions, the cache moved from MISS to HIT, and the visual "
        "regression baseline has zero diff pixels. There is nothing left that a local check can "
        "prove. I'll close the session with the exact commit, the verification matrix and the "
        "follow-ups that are deliberately out of scope."
    )

    tl.todo(
        [
            ("Inspect repository and toolchain", "completed"),
            ("Scaffold Next.js 15 + Tailwind v4", "completed"),
            ("Build marketing pages and design system", "completed"),
            ("Model database schema and migrations", "completed"),
            ("Implement magic-link auth and API routes", "completed"),
            ("Build dashboard and Markdown editor", "completed"),
            ("Add Vitest and Playwright coverage", "completed"),
            ("Configure GitHub Actions CI", "completed"),
            ("Deploy and smoke test production", "completed"),
        ]
    )

    tl.think(
        "The session is complete: the repository started with two files and now has a deployed "
        "product with a tested marketing site, authenticated dashboard, Markdown publishing, "
        "database migrations, CI and a production smoke suite. The remaining work is product "
        "discovery, not infrastructure: custom domains, real email credentials and an analytics "
        "decision. I'll leave those as explicit follow-ups instead of pretending they are done."
    )

    tl.say(
        "## Shipped\n"
        "- Marketing site with hero, feature grid, pricing, FAQ and responsive nav.\n"
        "- Magic-link auth, protected dashboard, posts CRUD and a Markdown editor with sanitized preview.\n"
        "- Postgres schema + Drizzle migration, zod validation, rate limiting and `/api/health`.\n"
        "- 19 unit tests, 17 Playwright tests across desktop and mobile.\n"
        "- GitHub Actions pipeline green and a production deploy at https://tuxpress.dev.\n\n"
        "## Verification\n"
        "- `pnpm lint` · 0 problems\n"
        "- `pnpm typecheck` · 0 errors\n"
        "- `pnpm test` · 19 passed\n"
        "- `pnpm test:e2e` · 17 passed locally and against production\n"
        "- Lighthouse · 99 / 100 / 100 / 100\n\n"
        "## Follow-ups\n"
        "- Replace the suppressed email sender with a verified Resend domain.\n"
        "- Wire real analytics ingestion; the dashboard chart currently uses seeded demo data.\n"
        "- Move the in-memory rate limiter to Redis before horizontal scaling.\n\n"
        "The deployed build is the same commit CI verified (`7a2d1e4`)."
    )

    tl.note("session complete · production live · 30 minutes of work replayed", "ok")
    tl.todo_update("✓ Todo 9/9 · all tasks complete")

    return tl


def total_seconds(events: list[dict]) -> float:
    total = 0.0
    for event in events:
        total += event.get("gap", 0.0)
        if event["kind"] in ("think", "say", "tool"):
            total += event.get("ms", 0.0) / 1000.0
    return total


def estimate_cost(events: list[dict]) -> float:
    pricing = META["pricing"]
    cost = 0.0
    for event in events:
        input_tokens = event.get("in", 0)
        cached = event.get("cache", 0)
        output = event.get("out", 0)
        cost += (input_tokens - cached) / 1_000_000 * pricing["inputPerM"]
        cost += cached / 1_000_000 * pricing["cachedInputPerM"]
        cost += output / 1_000_000 * pricing["outputPerM"]
    return cost


def main() -> None:
    tl = build_replay()
    events = tl.events

    seconds = total_seconds(events)
    cost = estimate_cost(events)

    META["totalSeconds"] = round(seconds, 1)

    document = {"version": 1, "meta": META, "events": events}
    OUTPUT.write_text(
        json.dumps(document, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    kinds: dict[str, int] = {}
    for event in events:
        kinds[event["kind"]] = kinds.get(event["kind"], 0) + 1

    print(f"wrote {OUTPUT}")
    print(f"events: {len(events):,}")
    print(f"duration: {seconds / 60:.2f} min ({seconds:.1f}s)")
    print(f"turns: {tl.meter.turns:,} · estimated cost: ${cost:.4f}")
    print(f"size: {OUTPUT.stat().st_size / 1024 / 1024:.2f} MB")
    print("kinds: " + ", ".join(f"{kind}={count}" for kind, count in sorted(kinds.items())))


if __name__ == "__main__":
    main()
