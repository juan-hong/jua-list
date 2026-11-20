"""jua-list MCP 서버 (stdio, 외부 패키지 없음). 도구 설명은 영어 고정, 결과 문구는 화면 언어."""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jua  # noqa: E402
import jua_core as core  # noqa: E402
from jua_i18n import _  # noqa: E402

FILE = {"type": "string", "description": "List name, number or path. Default: the first list"}
REF = {"type": "string", "description": "Item id, number (#n), or part of its text"}
STATUS = {"type": "string", "enum": list(core.MARK),
          "description": "todo, doing, review (waiting for the person), blocked (question/stuck), done"}


def obj(props, req=()):
    return {"type": "object", "properties": props, "required": list(req)}


TOOLS = [
    ("jua_lists", "Show registered jua-list lists with open, assigned-to-Claude, review and blocked counts.", obj({}),
     lambda a: jua.op_lists()),
    ("jua_list", "Show a list's items by section. Use the #number or id shown here as ref in other tools.",
     obj({"file": FILE, "status": STATUS, "claude_only": {"type": "boolean"}, "hide_done": {"type": "boolean"},
          "all_files": {"type": "boolean", "description": "All lists at once"}}),
     lambda a: jua.op_list(a.get("file"), a.get("status"), a.get("claude_only", False),
                           a.get("hide_done", False), a.get("all_files", False))),
    ("jua_add", "Add an item. Without section it goes to the end of the first section. claude=true marks it as assigned to Claude.",
     obj({"text": {"type": "string"}, "file": FILE, "section": {"type": "string"},
          "claude": {"type": "boolean"}, "create_section": {"type": "boolean", "description": "Create the section if missing"}},
         ["text"]),
     lambda a: jua.op_add(a["text"], a.get("file"), a.get("section"), a.get("claude", False),
                          a.get("create_section", False))),
    ("jua_update", "Update an item: text, status, claude (assigned), result (one line; empty string clears it). Only given fields change.",
     obj({"ref": REF, "file": FILE, "text": {"type": "string"}, "status": STATUS,
          "claude": {"type": "boolean"}, "result": {"type": "string"}}, ["ref"]),
     lambda a: update(a)),
    ("jua_block", "When an assigned task cannot be done or needs a human decision: mark it blocked and leave a question.",
     obj({"ref": REF, "question": {"type": "string"}, "file": FILE}, ["ref", "question"]),
     lambda a: jua.op_block(a["ref"], a["question"], a.get("file"))),
    ("jua_delete", "Delete an item (and its result line). Only when the user asks to delete.",
     obj({"ref": REF, "file": FILE}, ["ref"]),
     lambda a: jua.op_rm(a["ref"], a.get("file"))),
    ("jua_move", "Move an item: to the end of to_section, or by delta (-1 up, +1 down).",
     obj({"ref": REF, "file": FILE, "to_section": {"type": "string"}, "delta": {"type": "integer"}}, ["ref"]),
     lambda a: jua.op_move(a["ref"], a.get("file"), a.get("to_section"), a.get("delta", 0))),
    ("jua_new_list", "Create a new list .md file and register it in the widget. cwd is the folder where Claude works on assigned tasks.",
     obj({"path": {"type": "string"}, "title": {"type": "string"},
          "sections": {"type": "string", "description": "Comma separated"}, "name": {"type": "string"},
          "cwd": {"type": "string"}}, ["path"]),
     lambda a: jua.op_new(a["path"], a.get("title"), a.get("sections"), a.get("name"), a.get("cwd"))),
    ("jua_register", "Register an existing .md file in the widget.",
     obj({"path": {"type": "string"}, "name": {"type": "string"}, "cwd": {"type": "string"}}, ["path"]),
     lambda a: jua.op_register(a["path"], a.get("name"), a.get("cwd"))),
    ("jua_unregister", "Unregister a list (the file is kept).", obj({"file": FILE}, ["file"]),
     lambda a: jua.op_unregister(a["file"])),
    ("jua_entry", "Change a registered list's tab name or work folder.",
     obj({"file": FILE, "name": {"type": "string"}, "cwd": {"type": "string"}}, ["file"]),
     lambda a: jua.op_set_entry(a["file"], a.get("name"), a.get("cwd"))),
    ("jua_config", "Show or change widget settings. Without key shows all. e.g. alpha (0-255), font_size (8-16), hide_done, "
                   "lang (auto/ko/en), x/y/w/h (window), pin, tab, claude.max_turns, claude.timeout_min, claude.model.",
     obj({"key": {"type": "string"}, "value": {"description": "JSON value. Omit to read"}}),
     lambda a: jua.op_config(a.get("key"), None if a.get("value") is None else json.dumps(a["value"]))),
]


def update(a):
    d, t = jua._doc_item(a.get("file"), a["ref"])
    if "text" in a:
        t = d.edit(t, a["text"])
    if "claude" in a:
        t = d.set_claude(t, bool(a["claude"]))
    if "status" in a:
        if a["status"] not in core.MARK:
            raise core.JuaError("invalid status")
        t = d.set_status(t, a["status"])
    if "result" in a:
        t = d.set_result(t, a["result"])
    return _("고침: ") + core.fmt_item(t)


HANDLERS = {n: fn for n, _, _, fn in TOOLS}


def reply(mid, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": mid}
    if error:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.buffer.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def handle(req):
    m, mid, p = req.get("method"), req.get("id"), req.get("params") or {}
    if m == "initialize":
        return reply(mid, {"protocolVersion": p.get("protocolVersion", "2025-06-18"),
                           "capabilities": {"tools": {}},
                           "serverInfo": {"name": "jua-list", "version": "1.0.0"},
                           "instructions": "jua-list is the user's desktop todo widget. Look at items with jua_list first, "
                                           "then refer to them by #number or id. Items tagged @claude are tasks the user assigned to Claude. "
                                           "When you finish one, set status to review and leave a one-line result. "
                                           "Only the user marks items done. Reply in the user's language."})
    if m == "tools/list":
        return reply(mid, {"tools": [{"name": n, "description": d, "inputSchema": s} for n, d, s, _ in TOOLS]})
    if m == "tools/call":
        fn = HANDLERS.get(p.get("name"))
        if not fn:
            return reply(mid, error={"code": -32602, "message": f"unknown tool: {p.get('name')}"})
        try:
            text, err = fn(p.get("arguments") or {}), False
        except core.JuaError as e:
            text, err = _("오류: {0}").format(e), True
        except Exception as e:
            core.log("mcp " + traceback.format_exc())
            text, err = f"internal error: {e}", True
        return reply(mid, {"content": [{"type": "text", "text": text}], "isError": err})
    if m == "ping":
        return reply(mid, {})
    if mid is not None:
        reply(mid, error={"code": -32601, "message": f"method not supported: {m}"})


def main():
    for raw in sys.stdin.buffer:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw.decode("utf-8"))
        except ValueError:
            continue
        # 배치 요청도 받음
        for r in req if isinstance(req, list) else [req]:
            handle(r)


if __name__ == "__main__":
    main()
