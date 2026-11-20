"""jua-list CLI. Claude·사람이 목록을 다룸. 예: jua list, jua add "할 일" -s 섹션 --claude"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jua_core as core  # noqa: E402
from jua_core import JuaError  # noqa: E402
from jua_i18n import _  # noqa: E402


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
        out.append(_("{0}. {1}  남음 {2}/{3}, Claude 맡김 {4}, 검토 대기 {5}, 막힘 {6}").format(
            k, e["name"], len(its) - cnt["done"], len(its), mine, cnt["review"], cnt["blocked"])
                   + "\n   " + _("파일: {0}").format(e["path"])
                   + "\n   " + _("작업 폴더: {0}").format(e["cwd"])
                   + ("\n   " + _("오류: {0}").format(d.error) if d.error else ""))
    return "\n".join(out) or _("등록된 목록 없음")


def op_list(file=None, status=None, claude=False, hide_done=False, all_files=False):
    cfg = core.load_cfg()
    if all_files:
        docs = []
        for e in core.entries(cfg):
            d = core.Doc(e["path"], e["name"], e["cwd"])
            d.load()
            docs.append(core.fmt_doc(d, status, claude, hide_done))
        return "\n\n".join(docs) or _("등록된 목록 없음")
    return core.fmt_doc(core.open_doc(cfg, file), status, claude, hide_done)


def _doc_item(file, ref):
    d = core.open_doc(core.load_cfg(), file)
    return d, d.resolve(ref)


def op_add(text, file=None, section=None, claude=False, create=False):
    d = core.open_doc(core.load_cfg(), file)
    t = d.add(text, section, claude, create)
    return _("추가함: ") + core.fmt_item(t)


def op_status(ref, status, file=None):
    if status not in core.MARK:
        raise JuaError(_("상태는 {0} 중 하나").format(', '.join(core.MARK)))
    d, t = _doc_item(file, ref)
    return _("{0}(으)로 바꿈: ").format(core.STATUS_KO[status]) + core.fmt_item(d.set_status(t, status))


def op_edit(ref, text, file=None):
    d, t = _doc_item(file, ref)
    return _("고침: ") + core.fmt_item(d.edit(t, text))


def op_rm(ref, file=None):
    d, t = _doc_item(file, ref)
    d.delete(t)
    return _("지움: #{0} {1}").format(t['n'], t['text'])


def op_move(ref, file=None, to=None, delta=0):
    d, t = _doc_item(file, ref)
    return _("옮김: ") + core.fmt_item(d.move(t, to, delta))


def op_claude(ref, on=True, file=None):
    d, t = _doc_item(file, ref)
    return (_("Claude에게 맡김: ") if on else _("맡김 해제: ")) + core.fmt_item(d.set_claude(t, on))


def op_result(ref, text, file=None):
    d, t = _doc_item(file, ref)
    return _("결과 남김: ") + core.fmt_item(d.set_result(t, text))


def op_block(ref, question, file=None):
    d, t = _doc_item(file, ref)
    t = d.set_status(t, "blocked")
    return _("질문 남김: ") + core.fmt_item(d.set_result(t, _("질문: {0}").format(question)))


def op_register(path, name=None, cwd=None):
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise JuaError(_("파일 없음: {0} (새로 만들려면 jua new)").format(path))

    def fn(cfg):
        for e in core.entries(cfg):
            if e["path"].lower() == path.lower():
                raise JuaError(_("이미 등록됨: {0}").format(e['name']))
        item = {"path": path}
        if name:
            item["name"] = name
        if cwd:
            item["cwd"] = os.path.abspath(cwd)
        cfg["files"].append(item if len(item) > 1 else path)
    core.update_cfg(fn)
    return _("등록함: {0}").format(path)


def op_unregister(file):
    cfg = core.load_cfg()
    e = core.find_entry(cfg, file)

    def fn(c):
        c["files"] = [x for x in c["files"]
                      if os.path.abspath(os.path.expandvars(x if isinstance(x, str) else x.get("path", ""))).lower()
                      != e["path"].lower()]
    core.update_cfg(fn)
    return _("등록 해제함(파일은 그대로): {0}").format(e['name'])


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
    return _("바꿈: {0} (작업 폴더 {1})").format(name or e['name'], os.path.abspath(cwd) if cwd else e['cwd'])


def op_new(path, title=None, sections=None, name=None, cwd=None, register=True):
    secs = [s.strip() for s in (sections or _("할 일")).split(",") if s.strip()]
    p = core.new_list(path, title or os.path.splitext(os.path.basename(path))[0], secs)
    msg = _("만듦: {0}").format(p)
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
        raise JuaError(_("files는 jua register / unregister / entry로 바꿈"))
    if value is None:
        cur = cfg
        for p in parts:
            if not isinstance(cur, dict) or p not in cur:
                raise JuaError(_("설정 '{0}' 없음").format(key))
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
    out = [_("설치함: {0}\\jua.cmd, {1}\\jua").format(bindir, bindir)]
    if bindir.lower() not in os.environ.get("PATH", "").lower():
        out.append(_("주의: {0}가 PATH에 없음. PATH에 추가해야 jua 명령이 됨").format(bindir))
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
    return _("위젯 실행함 (이미 떠 있으면 그대로)")


def install_startup():
    import subprocess
    w = os.path.join(os.path.dirname(os.path.abspath(__file__)), "widget.py")
    startup = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    lnk = os.path.join(startup, "jua-list.lnk")
    for old in ("jua_list.lnk", "Todo Widget.lnk"):
        # 예전 이름 바로가기 정리
        try:
            os.remove(os.path.join(startup, old))
        except OSError:
            pass
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:J_LNK);"
          "$s.TargetPath=$env:J_PYW;$s.Arguments='\"'+$env:J_W+'\"';$s.WorkingDirectory=$env:J_DIR;$s.Save()")
    env = dict(os.environ, J_LNK=lnk, J_PYW=_pythonw(), J_W=w, J_DIR=os.path.dirname(w))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, capture_output=True)
    return _("시작 프로그램 등록함: {0}").format(lnk) if r.returncode == 0 else _("시작 프로그램 등록 실패")


def install_mcp(py, server):
    import shutil
    import subprocess
    out = []
    exe = shutil.which("claude")
    if exe:
        for name in ("jua-list", "jua_list"):  # jua_list는 예전 이름
            subprocess.run([exe, "mcp", "remove", name, "--scope", "user"], capture_output=True)
        r = subprocess.run([exe, "mcp", "add", "--scope", "user", "jua-list", "--", py, server],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        out.append(_("Claude Code MCP 등록함") if r.returncode == 0 else _("Claude Code MCP 등록 실패: {0}").format(r.stderr.strip()))
    else:
        out.append(_("claude 명령 없음. Claude Code MCP 등록 건너뜀"))
    import glob
    # MSIX 설치면 패키지 안 LocalCache가 진짜 위치
    cands = glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages", "Claude_*",
                                   "LocalCache", "Roaming", "Claude"))
    cands.append(os.path.join(os.environ.get("APPDATA", ""), "Claude"))
    home = next((c for c in cands if os.path.isdir(c)), None)
    if not home:
        out.append(_("Claude 데스크톱 앱 설정 폴더 없음. 건너뜀"))
    else:
        path = os.path.join(home, "claude_desktop_config.json")
        data = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8-sig") as f:
                    data = json.load(f)
            except ValueError:
                # 깨진 설정 덮어쓰면 안 됨
                out.append(_("데스크톱 설정 형식 오류. 건너뜀: {0}").format(path))
                return out
        data.setdefault("mcpServers", {}).pop("jua_list", None)
        data["mcpServers"]["jua-list"] = {"command": py, "args": [server]}
        core.atomic_write(path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        out.append(_("데스크톱 앱 MCP 등록함 (앱 다시 시작해야 반영): {0}").format(path))
    return out


# ---------- CLI ----------
def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    fp = argparse.ArgumentParser(add_help=False)
    fp.add_argument("-f", "--file", help=_("목록 이름·번호·경로 (생략하면 지금 폴더 목록, 없으면 첫 목록)"))
    ap = argparse.ArgumentParser(prog="jua", description=_("jua-list: Claude와 같이 쓰는 todo 목록"))
    sp = ap.add_subparsers(dest="cmd", required=True)

    sp.add_parser("lists", help=_("등록된 목록과 개수"))
    p = sp.add_parser("list", parents=[fp], help=_("항목 보기"))
    p.add_argument("--status", choices=list(core.MARK))
    p.add_argument("--claude", action="store_true", help=_("Claude 맡긴 것만"))
    p.add_argument("--hide-done", action="store_true")
    p.add_argument("--all", action="store_true", help=_("모든 목록"))
    p = sp.add_parser("add", parents=[fp], help=_("항목 추가"))
    p.add_argument("text")
    p.add_argument("-s", "--section")
    p.add_argument("--claude", action="store_true", help=_("Claude에게 맡김"))
    p.add_argument("--create", action="store_true", help=_("섹션 없으면 만듦"))
    for name, hlp in [("done", _("완료")), ("undo", _("대기로 되돌림")), ("rm", _("삭제"))]:
        sp.add_parser(name, parents=[fp], help=hlp).add_argument("ref", help=_("id, 번호, 글자 일부"))
    p = sp.add_parser("status", parents=[fp], help=_("상태 바꿈"))
    p.add_argument("ref")
    p.add_argument("status", choices=list(core.MARK))
    p = sp.add_parser("edit", parents=[fp], help=_("내용 고침"))
    p.add_argument("ref")
    p.add_argument("text")
    p = sp.add_parser("move", parents=[fp], help=_("옮김"))
    p.add_argument("ref")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--to", help=_("다른 섹션 끝으로"))
    g.add_argument("--up", type=int)
    g.add_argument("--down", type=int)
    p = sp.add_parser("claude", parents=[fp], help=_("Claude에게 맡김(on)/해제(off)"))
    p.add_argument("ref")
    p.add_argument("onoff", choices=["on", "off"], nargs="?", default="on")
    p = sp.add_parser("result", parents=[fp], help=_("결과 한 줄 남김 (빈 문자열이면 지움)"))
    p.add_argument("ref")
    p.add_argument("text")
    p = sp.add_parser("block", parents=[fp], help=_("막힘으로 바꾸고 질문 남김"))
    p.add_argument("ref")
    p.add_argument("question")
    p = sp.add_parser("new", help=_("새 목록 파일 만들고 등록"))
    p.add_argument("path")
    p.add_argument("--title")
    p.add_argument("--sections", help=_("쉼표로 구분"))
    p.add_argument("--name")
    p.add_argument("--cwd", help=_("Claude 작업 폴더"))
    p.add_argument("--no-register", action="store_true")
    p = sp.add_parser("register", help=_("기존 .md 등록"))
    p.add_argument("path")
    p.add_argument("--name")
    p.add_argument("--cwd")
    sp.add_parser("unregister", help=_("등록 해제")).add_argument("file")
    p = sp.add_parser("entry", help=_("목록 이름·작업 폴더 바꿈"))
    p.add_argument("file")
    p.add_argument("--name")
    p.add_argument("--cwd")
    p = sp.add_parser("config", help=_("설정 보기·바꿈 (예: jua config alpha 220)"))
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p = sp.add_parser("install", help=_("jua 명령을 PATH에 설치"))
    p.add_argument("--mcp", action="store_true", help=_("Claude Code·데스크톱 앱에 MCP 서버도 등록"))
    p.add_argument("--startup", action="store_true", help=_("로그인 시 위젯 자동 실행"))
    sp.add_parser("widget", help=_("위젯 실행"))
    sp.add_parser("home", help=_("데이터 폴더(설정·실행 기록) 위치"))

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
        print(_("오류: {0}").format(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
