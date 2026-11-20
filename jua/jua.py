"""jua_list CLI. Claude·사람이 목록을 다룸. 예: jua list, jua add "할 일" -s 섹션 --claude"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jua_core as core  # noqa: E402
from jua_core import JuaError  # noqa: E402


# ---------- 동작 (MCP도 이걸 씀. 전부 문자열 반환) ----------
def op_lists():
    cfg = core.load_cfg()
    out = []
    for k, e in enumerate(core.entries(cfg), 1):
        d = core.Doc(e["path"], e["name"], e["cwd"])
        d.load()
        its = d.items()
        cnt = {s: sum(t["status"] == s for t in its) for s in core.MARK}
        mine = sum(t["claude"] and t["status"] != "done" for t in its)
        out.append(f"{k}. {e['name']}  남음 {len(its) - cnt['done']}/{len(its)}, Claude 맡김 {mine}, "
                   f"검토 대기 {cnt['review']}, 막힘 {cnt['blocked']}\n   파일: {e['path']}\n   작업 폴더: {e['cwd']}"
                   + (f"\n   오류: {d.error}" if d.error else ""))
    return "\n".join(out) or "등록된 목록 없음"


def op_list(file=None, status=None, claude=False, hide_done=False, all_files=False):
    cfg = core.load_cfg()
    if all_files:
        docs = []
        for e in core.entries(cfg):
            d = core.Doc(e["path"], e["name"], e["cwd"])
            d.load()
            docs.append(core.fmt_doc(d, status, claude, hide_done))
        return "\n\n".join(docs) or "등록된 목록 없음"
    return core.fmt_doc(core.open_doc(cfg, file), status, claude, hide_done)


def _doc_item(file, ref):
    d = core.open_doc(core.load_cfg(), file)
    return d, d.resolve(ref)


def op_add(text, file=None, section=None, claude=False, create=False):
    d = core.open_doc(core.load_cfg(), file)
    t = d.add(text, section, claude, create)
    return "추가함: " + core.fmt_item(t)


def op_status(ref, status, file=None):
    if status not in core.MARK:
        raise JuaError(f"상태는 {', '.join(core.MARK)} 중 하나")
    d, t = _doc_item(file, ref)
    return f"{core.STATUS_KO[status]}(으)로 바꿈: " + core.fmt_item(d.set_status(t, status))


def op_edit(ref, text, file=None):
    d, t = _doc_item(file, ref)
    return "고침: " + core.fmt_item(d.edit(t, text))


def op_rm(ref, file=None):
    d, t = _doc_item(file, ref)
    d.delete(t)
    return f"지움: #{t['n']} {t['text']}"


def op_move(ref, file=None, to=None, delta=0):
    d, t = _doc_item(file, ref)
    return "옮김: " + core.fmt_item(d.move(t, to, delta))


def op_claude(ref, on=True, file=None):
    d, t = _doc_item(file, ref)
    return ("Claude에게 맡김: " if on else "맡김 해제: ") + core.fmt_item(d.set_claude(t, on))


def op_result(ref, text, file=None):
    d, t = _doc_item(file, ref)
    return "결과 남김: " + core.fmt_item(d.set_result(t, text))


def op_block(ref, question, file=None):
    d, t = _doc_item(file, ref)
    t = d.set_status(t, "blocked")
    return "질문 남김: " + core.fmt_item(d.set_result(t, f"질문: {question}"))


def op_register(path, name=None, cwd=None):
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise JuaError(f"파일 없음: {path} (새로 만들려면 jua new)")

    def fn(cfg):
        for e in core.entries(cfg):
            if e["path"].lower() == path.lower():
                raise JuaError(f"이미 등록됨: {e['name']}")
        item = {"path": path}
        if name:
            item["name"] = name
        if cwd:
            item["cwd"] = os.path.abspath(cwd)
        cfg["files"].append(item if len(item) > 1 else path)
    core.update_cfg(fn)
    return f"등록함: {path}"


def op_unregister(file):
    cfg = core.load_cfg()
    e = core.find_entry(cfg, file)

    def fn(c):
        c["files"] = [x for x in c["files"]
                      if os.path.abspath(os.path.expandvars(x if isinstance(x, str) else x.get("path", ""))).lower()
                      != e["path"].lower()]
    core.update_cfg(fn)
    return f"등록 해제함(파일은 그대로): {e['name']}"


def op_set_entry(file, name=None, cwd=None):
    cfg = core.load_cfg()
    e = core.find_entry(cfg, file)

    def fn(c):
        for k, x in enumerate(c["files"]):
            p = x if isinstance(x, str) else x.get("path", "")
            if os.path.abspath(os.path.expandvars(p)).lower() == e["path"].lower():
                x = {"path": p} if isinstance(x, str) else x
                if name:
                    x["name"] = name
                if cwd:
                    x["cwd"] = os.path.abspath(cwd)
                c["files"][k] = x
    core.update_cfg(fn)
    return f"바꿈: {name or e['name']} (작업 폴더 {os.path.abspath(cwd) if cwd else e['cwd']})"


def op_new(path, title=None, sections=None, name=None, cwd=None, register=True):
    secs = [s.strip() for s in (sections or "할 일").split(",") if s.strip()]
    p = core.new_list(path, title or os.path.splitext(os.path.basename(path))[0], secs)
    msg = f"만듦: {p}"
    if register:
        msg += "\n" + op_register(p, name, cwd)
    return msg


def op_config(key=None, value=None):
    cfg = core.load_cfg()
    if key is None:
        show = {k: v for k, v in cfg.items() if k != "files"}
        return json.dumps(show, ensure_ascii=False, indent=2)
    parts = key.split(".")
    if parts[0] == "files":
        raise JuaError("files는 jua register / unregister / entry로 바꿈")
    if value is None:
        cur = cfg
        for p in parts:
            if not isinstance(cur, dict) or p not in cur:
                raise JuaError(f"설정 '{key}' 없음")
            cur = cur[p]
        return json.dumps(cur, ensure_ascii=False)
    try:
        val = json.loads(value)
    except ValueError:
        val = value

    def fn(c):
        cur = c
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = val
    core.update_cfg(fn)
    return f"{key} = {json.dumps(val, ensure_ascii=False)}"


def op_install(mcp=False, startup=False):
    """jua 명령을 PATH(~/.local/bin)에 깔음. mcp=True면 Claude Code·데스크톱에 MCP 등록. 폴더 옮기면 다시 실행."""
    bindir = os.path.join(os.path.expanduser("~"), ".local", "bin")
    os.makedirs(bindir, exist_ok=True)
    me = os.path.abspath(__file__)
    py = sys.executable.replace("pythonw.exe", "python.exe")
    with open(os.path.join(bindir, "jua.cmd"), "w", encoding="utf-8") as f:
        f.write(f'@"{py}" "{me}" %*\r\n')
    with open(os.path.join(bindir, "jua"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f'#!/bin/sh\nexec "{py.replace(os.sep, "/")}" "{me.replace(os.sep, "/")}" "$@"\n')
    out = [f"설치함: {bindir}\\jua.cmd, {bindir}\\jua"]
    if bindir.lower() not in os.environ.get("PATH", "").lower():
        out.append(f"주의: {bindir}가 PATH에 없음. PATH에 추가해야 jua 명령이 됨")
    if mcp:
        out += install_mcp(py, os.path.join(os.path.dirname(me), "jua_mcp.py"))
    if startup:
        out.append(install_startup())
    return "\n".join(out)


def _pythonw():
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    return pyw if os.path.exists(pyw) else sys.executable


def op_widget():
    import subprocess
    w = os.path.join(os.path.dirname(os.path.abspath(__file__)), "widget.py")
    subprocess.Popen([_pythonw(), w], cwd=os.path.dirname(w), creationflags=0x00000008 | 0x00000200)
    return "위젯 실행함 (이미 떠 있으면 그대로)"


def install_startup():
    import subprocess
    w = os.path.join(os.path.dirname(os.path.abspath(__file__)), "widget.py")
    startup = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    lnk = os.path.join(startup, "jua_list.lnk")
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:J_LNK);"
          "$s.TargetPath=$env:J_PYW;$s.Arguments='\"'+$env:J_W+'\"';$s.WorkingDirectory=$env:J_DIR;$s.Save()")
    env = dict(os.environ, J_LNK=lnk, J_PYW=_pythonw(), J_W=w, J_DIR=os.path.dirname(w))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, capture_output=True)
    return f"시작 프로그램 등록함: {lnk}" if r.returncode == 0 else "시작 프로그램 등록 실패"


def install_mcp(py, server):
    import shutil
    import subprocess
    out = []
    exe = shutil.which("claude")
    if exe:
        subprocess.run([exe, "mcp", "remove", "jua_list", "--scope", "user"], capture_output=True)
        r = subprocess.run([exe, "mcp", "add", "--scope", "user", "jua_list", "--", py, server],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        out.append("Claude Code MCP 등록함" if r.returncode == 0 else f"Claude Code MCP 등록 실패: {r.stderr.strip()}")
    else:
        out.append("claude 명령 없음. Claude Code MCP 등록 건너뜀")
    import glob
    # MSIX 설치면 패키지 안 LocalCache가 진짜 위치
    cands = glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages", "Claude_*",
                                   "LocalCache", "Roaming", "Claude"))
    cands.append(os.path.join(os.environ.get("APPDATA", ""), "Claude"))
    home = next((c for c in cands if os.path.isdir(c)), None)
    if not home:
        out.append("Claude 데스크톱 앱 설정 폴더 없음. 건너뜀")
    else:
        path = os.path.join(home, "claude_desktop_config.json")
        data = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8-sig") as f:
                    data = json.load(f)
            except ValueError:
                # 깨진 설정 덮어쓰면 안 됨
                out.append(f"데스크톱 설정 형식 오류. 건너뜀: {path}")
                return out
        data.setdefault("mcpServers", {})["jua_list"] = {"command": py, "args": [server]}
        core.atomic_write(path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        out.append(f"데스크톱 앱 MCP 등록함 (앱 다시 시작해야 반영): {path}")
    return out


# ---------- CLI ----------
def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    fp = argparse.ArgumentParser(add_help=False)
    fp.add_argument("-f", "--file", help="목록 이름·번호·경로 (생략하면 지금 폴더 목록, 없으면 첫 목록)")
    ap = argparse.ArgumentParser(prog="jua", description="jua_list: Claude와 같이 쓰는 todo 목록")
    sp = ap.add_subparsers(dest="cmd", required=True)

    sp.add_parser("lists", help="등록된 목록과 개수")
    p = sp.add_parser("list", parents=[fp], help="항목 보기")
    p.add_argument("--status", choices=list(core.MARK))
    p.add_argument("--claude", action="store_true", help="Claude 맡긴 것만")
    p.add_argument("--hide-done", action="store_true")
    p.add_argument("--all", action="store_true", help="모든 목록")
    p = sp.add_parser("add", parents=[fp], help="항목 추가")
    p.add_argument("text")
    p.add_argument("-s", "--section")
    p.add_argument("--claude", action="store_true", help="Claude에게 맡김")
    p.add_argument("--create", action="store_true", help="섹션 없으면 만듦")
    for name, hlp in [("done", "완료"), ("undo", "대기로 되돌림"), ("rm", "삭제")]:
        sp.add_parser(name, parents=[fp], help=hlp).add_argument("ref", help="id, 번호, 글자 일부")
    p = sp.add_parser("status", parents=[fp], help="상태 바꿈")
    p.add_argument("ref")
    p.add_argument("status", choices=list(core.MARK))
    p = sp.add_parser("edit", parents=[fp], help="내용 고침")
    p.add_argument("ref")
    p.add_argument("text")
    p = sp.add_parser("move", parents=[fp], help="옮김")
    p.add_argument("ref")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--to", help="다른 섹션 끝으로")
    g.add_argument("--up", type=int)
    g.add_argument("--down", type=int)
    p = sp.add_parser("claude", parents=[fp], help="Claude에게 맡김(on)/해제(off)")
    p.add_argument("ref")
    p.add_argument("onoff", choices=["on", "off"], nargs="?", default="on")
    p = sp.add_parser("result", parents=[fp], help="결과 한 줄 남김 (빈 문자열이면 지움)")
    p.add_argument("ref")
    p.add_argument("text")
    p = sp.add_parser("block", parents=[fp], help="막힘으로 바꾸고 질문 남김")
    p.add_argument("ref")
    p.add_argument("question")
    p = sp.add_parser("new", help="새 목록 파일 만들고 등록")
    p.add_argument("path")
    p.add_argument("--title")
    p.add_argument("--sections", help="쉼표로 구분")
    p.add_argument("--name")
    p.add_argument("--cwd", help="Claude 작업 폴더")
    p.add_argument("--no-register", action="store_true")
    p = sp.add_parser("register", help="기존 .md 등록")
    p.add_argument("path")
    p.add_argument("--name")
    p.add_argument("--cwd")
    sp.add_parser("unregister", help="등록 해제").add_argument("file")
    p = sp.add_parser("entry", help="목록 이름·작업 폴더 바꿈")
    p.add_argument("file")
    p.add_argument("--name")
    p.add_argument("--cwd")
    p = sp.add_parser("config", help="설정 보기·바꿈 (예: jua config alpha 220)")
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p = sp.add_parser("install", help="jua 명령을 PATH에 설치")
    p.add_argument("--mcp", action="store_true", help="Claude Code·데스크톱 앱에 MCP 서버도 등록")
    p.add_argument("--startup", action="store_true", help="로그인 시 위젯 자동 실행")
    sp.add_parser("widget", help="위젯 실행")
    sp.add_parser("home", help="데이터 폴더(설정·실행 기록) 위치")

    a = ap.parse_args(argv)
    f = getattr(a, "file", None)
    try:
        c = a.cmd
        if c == "lists":
            r = op_lists()
        elif c == "list":
            r = op_list(f, a.status, a.claude, a.hide_done, a.all)
        elif c == "add":
            r = op_add(a.text, f, a.section, a.claude, a.create)
        elif c == "done":
            r = op_status(a.ref, "done", f)
        elif c == "undo":
            r = op_status(a.ref, "todo", f)
        elif c == "status":
            r = op_status(a.ref, a.status, f)
        elif c == "rm":
            r = op_rm(a.ref, f)
        elif c == "edit":
            r = op_edit(a.ref, a.text, f)
        elif c == "move":
            r = op_move(a.ref, f, a.to, (a.down or 0) - (a.up or 0))
        elif c == "claude":
            r = op_claude(a.ref, a.onoff == "on", f)
        elif c == "result":
            r = op_result(a.ref, a.text, f)
        elif c == "block":
            r = op_block(a.ref, a.question, f)
        elif c == "new":
            r = op_new(a.path, a.title, a.sections, a.name, a.cwd, not a.no_register)
        elif c == "register":
            r = op_register(a.path, a.name, a.cwd)
        elif c == "unregister":
            r = op_unregister(a.file)
        elif c == "entry":
            r = op_set_entry(a.file, a.name, a.cwd)
        elif c == "config":
            r = op_config(a.key, a.value)
        elif c == "install":
            r = op_install(a.mcp, a.startup)
        elif c == "widget":
            r = op_widget()
        elif c == "home":
            r = core.HOME
        print(r)
        return 0
    except JuaError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
