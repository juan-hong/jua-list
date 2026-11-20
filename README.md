# jua-list

**A Windows desktop todo widget you share with Claude.**

Tasks live in plain Markdown checklists. The widget sits on the desktop layer, so it stays visible even after `Win+D`. Claude reads and edits the same lists through a CLI and an MCP server. Tag a task `@claude` and press ▶: Claude Code works on it in that list's work folder, leaves a one-line result, and marks it **review**. You check it off when you're happy.

[한국어 안내](#한국어)

```
## Website
- [x] Fix login bug
- [?] @claude Fix typos in README <!-- id:3fa2c1 -->
  - Result: fixed 4 typos in README.md
- [ ] Decide release date
```

## Features

- **Desktop widget**: pinned to the desktop layer, rounded dark UI, tabs for several lists, collapsible sections, progress bars. Korean and English UI (follows the Windows display language).
- **Edit in place**: click to check off; hover for ✎ edit and ✕ delete; right-click for status, order and section; undo delete.
- **Hand tasks to Claude**: `@claude` tag → ▶ → `claude -p` runs in the list's work folder → result line + **review** → you check it off.
- **Claude manages the lists too**: the `jua` CLI and an MCP server (12 tools) add, edit, move and delete items, create lists, and change widget settings.
- **Safe writes**: atomic saves, `.bak` backups, cross-process locking; non-UTF-8 files open read-only.
- **Just files**: data stays in `.md`. Edit it in Notepad, Obsidian or VS Code at the same time; the widget updates within a second.

Status marks: `[ ]` todo · `[~]` doing · `[?]` review · `[!]` blocked/question · `[x]` done

## Requirements

- Windows 10 or 11
- Python 3.10+ with tkinter (included in the python.org installer). No third-party packages.
- [Claude Code](https://claude.com/claude-code) CLI (`claude`) to hand tasks to Claude

## Install

### As a Claude Code plugin (skill + MCP server)

```
/plugin marketplace add juan-hong/jua-list
/plugin install jua-list@jua-list
```

Then install the `jua` command and the widget. Ask Claude "install jua-list", or run:

```powershell
python "$env:USERPROFILE\.claude\plugins\marketplaces\jua-list\jua\jua.py" install --startup
jua widget
```

### From the repository

```powershell
git clone https://github.com/juan-hong/jua-list
cd jua-list
powershell -ExecutionPolicy Bypass -File jua\install.ps1
```

`install.ps1` installs the `jua` command into `~\.local\bin`, registers the MCP server in Claude Code and the Claude desktop app, adds the widget to Startup, and starts it. To use only the skill, copy `skills\jua-list` into `~\.claude\skills\`.

On first run, a sample list is created at `%APPDATA%\jua-list\todo.md`.

## Usage

### Widget

| Action | How |
|---|---|
| Check off / approve review | Click the item |
| Edit, delete, assign, run | Hover the item → ✎ ✕ @ ▶ |
| Status, move up/down, move to section | Right-click the item |
| Add | `+ Add` at the end of a section, or the input at the bottom (start with `@claude` to assign) |
| Collapse section | Click the section title |
| Move / resize window | `⋯` → Move / resize window (the window only moves in this mode) |
| Hide done, text size, run logs, quit | `⋯` menu |

### CLI

```powershell
jua lists                                   # all lists
jua list --claude                           # tasks assigned to Claude
jua add "Write tests" -s Backend --claude   # add and assign
jua done 3                                  # mark #3 done
jua move "Write tests" --to Frontend
jua new D:\proj\todo.md --sections "Bugs,Features" --cwd D:\proj   # new list with a work folder
jua config alpha 220                        # widget opacity
jua config lang en                          # UI language: auto | ko | en
jua --help
```

`<ref>` is an item id, a number from `jua list`, or part of its text.

### Handing a task to Claude

1. Add `@claude` to the task. Give each list a work folder (`--cwd`).
2. Press ▶. `claude -p` runs in that folder. Logs go to `%APPDATA%\jua-list\runs\`.
3. When it finishes you see `[?]` review with a one-line result. Check it off once you have reviewed it. If Claude has a question, the task shows `[!]`.

Defaults (change with `jua config claude.<key>`): 40 turns, 30 minutes, file edits auto-approved, and `git commit/push/reset/checkout`, `rm -rf` and WebFetch blocked.

> ⚠ ▶ lets Claude Code edit files and run commands in the list's work folder. Use it only with lists and folders you trust, and review the result. Text that another program writes into a list file can become an instruction to Claude.

## Settings

`%APPDATA%\jua-list\config.json` (`jua home` shows the folder; set `JUA_HOME` to move it)

| Key | Meaning |
|---|---|
| `files` | Lists: a path string or `{"path", "name", "cwd"}` |
| `x` `y` `w` `h` | Window position and size (physical pixels) |
| `pin` | `desktop` (desktop layer) / `bottom` (normal window kept at the bottom) |
| `lang` | `auto` / `ko` / `en` (environment variable `JUA_LANG` overrides) |
| `alpha` `font_size` `hide_done` | Opacity 0–255, text size 8–16, hide done items |
| `claude.max_turns` `claude.timeout_min` `claude.model` | Limits for ▶ runs |
| `claude.allowed_tools` `claude.disallowed_tools` | Tool allow/deny lists for ▶ runs |

## Development

```powershell
python -m unittest discover -s tests
```

Layout: `jua/jua_core.py` (files, settings, runs) · `jua/jua.py` (CLI) · `jua/jua_mcp.py` (MCP server, no dependencies) · `jua/widget.py` (tkinter widget) · `jua/jua_i18n.py` (Korean/English) · `skills/jua-list` (Claude skill) · `.claude-plugin` (plugin and marketplace)

## License

MIT

---

## 한국어

**사람과 Claude가 같이 쓰는 Windows 바탕화면 todo 위젯**

할 일은 평범한 Markdown 체크리스트로 저장되고, 바탕화면에 붙은 위젯으로 보고 고칩니다. Claude는 CLI·MCP로 같은 목록을 읽고 고칩니다. 항목에 `@claude`를 붙이고 ▶를 누르면 Claude Code가 그 목록의 작업 폴더에서 일을 처리하고, 결과 한 줄을 남긴 뒤 **검토 대기**로 바꿉니다. 확인하고 체크하면 완료입니다.

- 요구 사항: Windows 10/11, Python 3.10+(tkinter 포함, 외부 패키지 없음), ▶ 실행에는 Claude Code CLI
- 플러그인 설치: `/plugin marketplace add juan-hong/jua-list` → `/plugin install jua-list@jua-list` → `python <플러그인>\jua\jua.py install --startup` → `jua widget`
- 직접 설치: 저장소를 받고 `jua\install.ps1` 실행
- 상태: `[ ]` 대기 · `[~]` 진행 중 · `[?]` 검토 대기 · `[!]` 막힘·질문 · `[x]` 완료
- 화면 언어는 Windows 표시 언어를 따릅니다. `jua config lang ko`로 고정할 수 있습니다.
- 설정·실행 기록: `%APPDATA%\jua-list` (`JUA_HOME`으로 변경)

> ⚠ ▶ 실행은 Claude Code가 작업 폴더에서 파일을 고치고 명령을 실행하게 합니다. 믿을 수 있는 목록과 폴더에서만 쓰고, 결과는 직접 검토하세요.
