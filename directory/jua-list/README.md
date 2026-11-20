# jua-list (skill)

This plugin teaches Claude to use **jua-list**, a Windows desktop todo widget you share with Claude.

- Your tasks live in plain Markdown checklists, shown in a widget pinned to the desktop.
- Claude reads and edits the same lists: add, check off, move, delete, create lists, change widget settings.
- Tag a task `@claude` and press ▶ in the widget: Claude Code does it in that list's work folder, leaves a one-line result, and marks it for your review.

The widget, the `jua` command and the MCP server are a separate, open-source app (MIT): https://github.com/juan-hong/jua-list. This plugin contains only the skill and never installs or runs anything by itself. Install the app first by following https://github.com/juan-hong/jua-list#install; until then, the skill tells you it's missing.

Privacy policy: https://github.com/juan-hong/jua-list/blob/main/PRIVACY.md

Requirements: Windows 10/11, Python 3.10+ with tkinter, Git, and Claude Code.

Try: "Add 'write release notes' to my jua-list", "Show what I assigned to Claude", "Create a todo list for D:\proj with sections Bugs and Features".

License: MIT
