# Privacy policy — jua-list

Last updated: 2026-11-20

jua-list (the desktop widget, the `jua` command, the MCP server and the Claude skill in this repository) runs entirely on your computer.

## What it reads and stores

- **Your todo lists**: the Markdown files you register. jua-list reads and edits them in place, and keeps one `.bak` backup next to each file.
- **Settings**: window position, display options, the list of registered files and run limits, in `config.json` inside the data folder (default `%APPDATA%\jua-list`, or `JUA_HOME`).
- **Run logs**: when you press ▶, the output of the Claude Code run is saved under `runs\` in the data folder.
- An error log (`jua.log`) in the data folder.

Your lists can contain anything you type, including personal information. They stay in the files you chose.

## What it sends

jua-list itself sends nothing over the network and has no server, analytics or telemetry.

- When you use Claude (in Claude Code, the Claude desktop app, or by pressing ▶), the text of the lists and tasks that Claude reads is sent to Anthropic as part of that conversation, under Anthropic's own terms and privacy policy.
- Installing from GitHub downloads the code from GitHub.

## Retention and deletion

Nothing is retained by the author. To delete everything: run `jua\install.ps1 -Uninstall` (removes the Startup shortcut), `claude mcp remove jua-list -s user`, and delete the data folder (`jua home` shows it), `~\.local\bin\jua` and `~\.local\bin\jua.cmd`. Your list files are yours to keep or delete.

## Contact

Open an issue at https://github.com/juan-hong/jua-list/issues.
