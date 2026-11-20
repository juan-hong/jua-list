"""jua_list MCP 서버 (stdio, 외부 패키지 없음). Claude 데스크톱·Claude Code에서 목록을 다룸."""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jua  # noqa: E402
import jua_core as core  # noqa: E402

FILE = {"type": "string", "description": "목록 이름·번호·경로. 생략하면 첫 목록"}
REF = {"type": "string", "description": "항목 id, 번호(#n), 또는 글자 일부"}
STATUS = {"type": "string", "enum": list(core.MARK),
          "description": "todo 대기, doing 진행 중, review 검토 대기, blocked 막힘·질문, done 완료"}


def obj(props, req=()):
    return {"type": "object", "properties": props, "required": list(req)}


TOOLS = [
    ("jua_lists", "등록된 jua_list 목록들과 남은 개수·Claude 맡김·검토 대기 수를 봄.", obj({}),
     lambda a: jua.op_lists()),
    ("jua_list", "목록의 항목을 섹션별로 봄. 각 항목 앞 #번호와 id로 다른 도구에서 지정.",
     obj({"file": FILE, "status": STATUS, "claude_only": {"type": "boolean"}, "hide_done": {"type": "boolean"},
          "all_files": {"type": "boolean", "description": "모든 목록 한꺼번에"}}),
     lambda a: jua.op_list(a.get("file"), a.get("status"), a.get("claude_only", False),
                           a.get("hide_done", False), a.get("all_files", False))),
    ("jua_add", "항목 추가. section 생략 시 첫 섹션 끝. claude=true면 Claude에게 맡긴 일로 표시.",
     obj({"text": {"type": "string"}, "file": FILE, "section": {"type": "string"},
          "claude": {"type": "boolean"}, "create_section": {"type": "boolean", "description": "섹션 없으면 만듦"}},
         ["text"]),
     lambda a: jua.op_add(a["text"], a.get("file"), a.get("section"), a.get("claude", False),
                          a.get("create_section", False))),
    ("jua_update", "항목 고침: 내용(text), 상태(status), Claude 맡김(claude), 결과 한 줄(result, 빈 문자열이면 지움). 준 것만 바뀜.",
     obj({"ref": REF, "file": FILE, "text": {"type": "string"}, "status": STATUS,
          "claude": {"type": "boolean"}, "result": {"type": "string"}}, ["ref"]),
     lambda a: update(a)),
    ("jua_block", "맡은 일을 못 하거나 사람 판단이 필요할 때: 막힘으로 바꾸고 질문을 남김.",
     obj({"ref": REF, "question": {"type": "string"}, "file": FILE}, ["ref", "question"]),
     lambda a: jua.op_block(a["ref"], a["question"], a.get("file"))),
    ("jua_delete", "항목 삭제(결과 줄 포함). 사용자가 지우라고 할 때만.",
     obj({"ref": REF, "file": FILE}, ["ref"]),
     lambda a: jua.op_rm(a["ref"], a.get("file"))),
    ("jua_move", "항목 옮김: to_section으로 다른 섹션 끝, 또는 delta(-1 위, +1 아래).",
     obj({"ref": REF, "file": FILE, "to_section": {"type": "string"}, "delta": {"type": "integer"}}, ["ref"]),
     lambda a: jua.op_move(a["ref"], a.get("file"), a.get("to_section"), a.get("delta", 0))),
    ("jua_new_list", "새 목록 .md 파일을 만들고 위젯에 등록. cwd는 Claude가 맡은 일을 할 작업 폴더.",
     obj({"path": {"type": "string"}, "title": {"type": "string"},
          "sections": {"type": "string", "description": "쉼표로 구분"}, "name": {"type": "string"},
          "cwd": {"type": "string"}}, ["path"]),
     lambda a: jua.op_new(a["path"], a.get("title"), a.get("sections"), a.get("name"), a.get("cwd"))),
    ("jua_register", "이미 있는 .md 파일을 위젯에 등록.",
     obj({"path": {"type": "string"}, "name": {"type": "string"}, "cwd": {"type": "string"}}, ["path"]),
     lambda a: jua.op_register(a["path"], a.get("name"), a.get("cwd"))),
    ("jua_unregister", "목록 등록 해제 (파일은 안 지움).", obj({"file": FILE}, ["file"]),
     lambda a: jua.op_unregister(a["file"])),
    ("jua_entry", "등록된 목록의 탭 이름·작업 폴더 바꿈.",
     obj({"file": FILE, "name": {"type": "string"}, "cwd": {"type": "string"}}, ["file"]),
     lambda a: jua.op_set_entry(a["file"], a.get("name"), a.get("cwd"))),
    ("jua_config", "위젯 설정 보기·바꿈. key 없으면 전체. 예: alpha(0~255), font_size(8~16), hide_done, "
                   "x/y/w/h(창 위치·크기), pin, claude.max_turns, claude.timeout_min, claude.model.",
     obj({"key": {"type": "string"}, "value": {"description": "JSON 값. 없으면 읽기만"}}),
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
            raise core.JuaError("잘못된 상태")
        t = d.set_status(t, a["status"])
    if "result" in a:
        t = d.set_result(t, a["result"])
    return "고침: " + core.fmt_item(t)


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
                           "serverInfo": {"name": "jua_list", "version": "1.0.0"},
                           "instructions": "jua_list는 사용자의 바탕화면 todo 위젯이다. 항목은 jua_list로 먼저 보고 "
                                           "#번호나 id로 지정한다. @claude 항목은 사용자가 Claude에게 맡긴 일이다. "
                                           "맡은 일을 끝내면 status는 review로 두고 result에 한 줄 요약을 남긴다. "
                                           "done(완료 확정)은 사용자가 한다."})
    if m == "tools/list":
        return reply(mid, {"tools": [{"name": n, "description": d, "inputSchema": s} for n, d, s, _ in TOOLS]})
    if m == "tools/call":
        fn = HANDLERS.get(p.get("name"))
        if not fn:
            return reply(mid, error={"code": -32602, "message": f"없는 도구: {p.get('name')}"})
        try:
            text, err = fn(p.get("arguments") or {}), False
        except core.JuaError as e:
            text, err = f"오류: {e}", True
        except Exception as e:
            core.log("mcp " + traceback.format_exc())
            text, err = f"내부 오류: {e}", True
        return reply(mid, {"content": [{"type": "text", "text": text}], "isError": err})
    if m == "ping":
        return reply(mid, {})
    if mid is not None:
        reply(mid, error={"code": -32601, "message": f"지원 안 함: {m}"})


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
