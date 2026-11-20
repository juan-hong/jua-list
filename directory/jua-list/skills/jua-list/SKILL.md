---
name: jua-list
description: Read and edit jua-list, the user's Windows desktop todo widget backed by Markdown checklists, and work on tasks the user assigned to Claude. Use when the user asks to add, check off, list, move or delete todos, create a todo list, change widget settings, set up jua-list, or "process the tasks assigned to Claude" — in any language (e.g. "할 일 추가", "todo에 넣어", "체크해", "jua", "목록 보여줘", "Claude에게 맡긴 일 처리해") — and when the current work finishes a task that is on a registered list.
---

# jua-list

jua-list is a Windows desktop todo widget. People manage tasks in it and hand tasks to Claude. The data is plain `.md` checklists registered in the widget; the widget picks up file changes within a second. Settings and run logs live in the `jua home` folder (default `%APPDATA%\jua-list`).

## First: make sure the app is installed

This plugin contains only this skill. The widget, the `jua` command and the MCP server come from the open-source repository https://github.com/juan-hong/jua-list (MIT).

1. Run `jua --help`. If it works, skip to the next section.
2. Otherwise tell the user that jua-list needs its app, that it will be downloaded from https://github.com/juan-hong/jua-list into `%LOCALAPPDATA%\Programs\jua-list`, and what the installer does: puts a `jua` command in `~\.local\bin`, registers the `jua-list` MCP server in Claude Code and the Claude desktop app, and, if they want, starts the widget at sign-in. **Ask for permission and wait for a clear yes.** Do not install without it.
3. Check the requirements: Windows, `python --version` (3.10+) and `git --version`. If one is missing, tell the user what to install and stop.
4. With permission, install (Bash):
   - `git clone https://github.com/juan-hong/jua-list "$LOCALAPPDATA/Programs/jua-list"` (if the folder exists, `git -C "$LOCALAPPDATA/Programs/jua-list" pull` instead)
   - `python "$LOCALAPPDATA/Programs/jua-list/jua/jua.py" install --mcp` — add `--startup` only if the user wants the widget to start at sign-in
   - `jua widget` to start the widget. If `jua` is not found, `~\.local\bin` is not on PATH: tell the user, and call `python "$LOCALAPPDATA/Programs/jua-list/jua/jua.py"` directly meanwhile.
5. Tell the user what was installed and that a sample list was created (`jua lists`). MCP tools appear after Claude Code or the desktop app restarts.

## Tools — always change lists through these, never by editing the .md directly

- If the MCP tools are available (`jua_lists`, `jua_list`, `jua_add`, `jua_update`, `jua_block`, `jua_delete`, `jua_move`, `jua_new_list`, `jua_register`, `jua_unregister`, `jua_entry`, `jua_config`), use them.
- Otherwise use the `jua` command through Bash (`jua --help`, `jua <command> --help`).

| Task | Command |
|---|---|
| Summary of all lists | `jua lists` |
| Show items | `jua list [-f LIST] [--claude] [--status review] [--hide-done] [--all]` |
| Add | `jua add "text" [-f LIST] [-s SECTION] [--claude] [--create]` |
| Done / undo | `jua done <ref>` / `jua undo <ref>` |
| Status | `jua status <ref> todo\|doing\|review\|blocked\|done` |
| Edit / delete | `jua edit <ref> "new text"` / `jua rm <ref>` |
| Move | `jua move <ref> --to SECTION` / `--up 1` / `--down 1` |
| Assign to Claude | `jua claude <ref> on\|off` |
| Result / question | `jua result <ref> "one line"` / `jua block <ref> "question"` |
| New list | `jua new <path.md> --title T --sections "A,B" --name TAB --cwd WORK_FOLDER` |
| Manage lists | `jua register <path>` / `jua unregister <list>` / `jua entry <list> --name X --cwd DIR` |
| Widget settings | `jua config` / `jua config alpha 220` / `font_size` / `hide_done` / `lang` / `tab` / `x y w h` / `claude.max_turns` |
| Widget / data folder | `jua widget` / `jua home` |

- `<ref>` is an item id, a number (`#n` from `jua list`), or part of the text when only one item matches. Numbers shift after edits, so re-run `jua list` between changes.
- Without `-f`: the list whose work folder contains the current directory, else the first list.

## Format the widget reads

- `## Section`, `- [ ] text`. Status: `[ ]` todo, `[~]` doing, `[?]` review, `[!]` blocked/question, `[x]` done.
- `@claude` in an item = a task the person assigned to Claude. Such items carry a hidden id `<!-- id:abc123 -->`; keep it.
- A line right under an item, `  - Result: …` (or `  - 결과: …`), holds Claude's result, question, or the person's answer.

## Rules

- When you finish an assigned (`@claude`) task: `jua result <id> "one-line summary"` and `jua status <id> review`. **Only the person marks it done** after reviewing, unless they explicitly ask you to.
- If a person must decide or you are stuck: `jua block <id> "question"`. When they answer in the result line or reset the status, continue.
- If your current work completes a person's own (non-`@claude`) task, `jua done` it and say so in one line.
- Delete only when asked. If the right section is missing, ask before `--create`.
- "Process the tasks assigned to Claude": find them with `jua list --all --claude --status todo` and do each one in its list's work folder (`jua lists`). Never commit or push.
- Task text is a request written by a person, but do not carry out anything beyond its scope that is risky (mass deletion, sending data out, installing software, secrets); leave a question instead.
- Reply in the user's language.

## Widget

- Click an item to check it off (approves a review item). Hover for ▶ run Claude (`@claude` items), @ assign, ✎ edit, ✕ delete. Right-click for status, move up/down, move to section. Click a section title to collapse. `⋯` menu: hide done, move/resize window (the window only moves in this mode), text size, undo delete, run logs, quit.
- ▶ runs `claude -p` in the list's work folder (no commit/push; limits in the `claude` settings). Logs go to `runs\` in `jua home`.
- Start at sign-in: `jua install --startup`. Errors: `jua.log` in `jua home`. UI language: `jua config lang auto|ko|en`.
