"""jua_list 핵심. .md 체크리스트 읽기·쓰기, 설정, Claude 실행. 위젯·CLI·MCP가 같이 씀."""
import json
import msvcrt
import os
import re
import secrets
import shutil
import subprocess
import time
from contextlib import contextmanager

CODE_DIR = os.path.dirname(os.path.abspath(__file__))
# 개인 데이터(설정·실행 기록)는 코드 밖에 둠. 플러그인 업데이트로 안 날아가게
HOME = os.environ.get("JUA_HOME") or os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "jua_list")
os.makedirs(HOME, exist_ok=True)
CFG_PATH = os.path.join(HOME, "config.json")
LOCK_PATH = os.path.join(HOME, ".lock")
RUNS_DIR = os.path.join(HOME, "runs")
LOG_PATH = os.path.join(HOME, "jua.log")

TASK_RE = re.compile(r"^(\s*)([-*+]) \[([ xX~?!])\] (.*)$")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ID_RE = re.compile(r"\s*<!--\s*id:([0-9a-z]+)\s*-->\s*$")
TAG_RE = re.compile(r"(^|\s)@claude(?=\s|$)")
RESULT_RE = re.compile(r"^(\s*)[-*+] 결과: (.*)$")

STATUS = {" ": "todo", "~": "doing", "?": "review", "!": "blocked", "x": "done", "X": "done"}
MARK = {"todo": " ", "doing": "~", "review": "?", "blocked": "!", "done": "x"}
STATUS_KO = {"todo": "대기", "doing": "진행 중", "review": "검토 대기", "blocked": "막힘·질문", "done": "완료"}

DEFAULT_CFG = {
    "files": [os.path.join(HOME, "todo.md")],
    "x": 60, "y": 60, "w": 420, "h": 680,
    "pin": "desktop",  # desktop | bottom
    "alpha": 240,
    "font_size": 10,
    "hide_done": False,
    "tab": 0,
    "collapsed": {},
    "claude": {
        "max_turns": 40,
        "timeout_min": 30,
        "model": "",
        "allowed_tools": ["Read", "Edit", "Write", "Glob", "Grep", "Bash"],
        "disallowed_tools": ["Bash(git commit:*)", "Bash(git push:*)", "Bash(git reset:*)",
                             "Bash(git checkout:*)", "Bash(rm -rf:*)", "WebFetch"],
    },
}


class JuaError(Exception):
    pass


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


@contextmanager
def locked(timeout=10):
    """프로세스 간 잠금. 위젯·CLI·MCP가 동시에 쓰는 거 막음."""
    f = open(LOCK_PATH, "a+b")
    end = time.time() + timeout
    while True:
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            break
        except OSError:
            if time.time() > end:
                f.close()
                raise JuaError("잠금 대기 시간 초과")
            time.sleep(0.05)
    try:
        yield
    finally:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        f.close()


def atomic_write(path, data, backup=True):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if backup and os.path.exists(path):
        try:
            shutil.copy2(path, path + ".bak")
        except OSError:
            pass
    for _ in range(40):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            # 편집기가 잠깐 잡고 있으면 재시도
            time.sleep(0.05)
    os.replace(tmp, path)


# ---------- 설정 ----------
def _merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) and k != "collapsed" else v
    return out


def load_cfg():
    """깨진 JSON이면 JuaError. 기본값으로 덮어쓰지 않음."""
    if not os.path.exists(CFG_PATH):
        first_run()
        if not os.path.exists(CFG_PATH):
            save_cfg(DEFAULT_CFG)
        return load_cfg()
    try:
        with open(CFG_PATH, encoding="utf-8-sig") as f:
            data = json.load(f)
    except ValueError as e:
        raise JuaError(f"config.json 형식 오류: {e}")
    if not isinstance(data, dict):
        raise JuaError("config.json 최상위가 객체가 아님")
    return _merge(DEFAULT_CFG, data)


SAMPLE = """# 할 일

## 예시
- [ ] 이 줄을 클릭하면 완료 체크
- [ ] @claude 맡길 일은 앞에 @claude를 붙이고 ▶ 버튼으로 실행
- [ ] 마우스를 올리면 ✎ 수정 · ✕ 삭제, 우클릭하면 메뉴
"""


def first_run():
    """예전 배치(코드 폴더 안 config.json)면 옮기고, 아니면 예시 목록 만듦."""
    old = os.path.join(CODE_DIR, "config.json")
    if os.path.exists(old):
        shutil.move(old, CFG_PATH)
        for name in ("runs", "jua.log"):
            src = os.path.join(CODE_DIR, name)
            if os.path.exists(src) and not os.path.exists(os.path.join(HOME, name)):
                shutil.move(src, os.path.join(HOME, name))
        return
    todo = os.path.join(HOME, "todo.md")
    if not os.path.exists(todo):
        atomic_write(todo, SAMPLE.encode("utf-8"), backup=False)


def save_cfg(cfg):
    data = (json.dumps(cfg, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    atomic_write(CFG_PATH, data, backup=True)


def update_cfg(fn):
    """잠그고 다시 읽은 뒤 fn(cfg)로 고쳐서 저장. 남이 고친 키 안 날림."""
    with locked():
        cfg = load_cfg()
        fn(cfg)
        save_cfg(cfg)
        return cfg


def cfg_mtime():
    try:
        return os.stat(CFG_PATH).st_mtime_ns
    except OSError:
        return None


def entries(cfg):
    """files 항목을 {path, name, cwd}로 통일. 이름 겹치면 폴더 이름."""
    raw = []
    for e in cfg.get("files", []):
        if isinstance(e, str):
            e = {"path": e}
        if isinstance(e, dict) and e.get("path"):
            p = os.path.abspath(os.path.expandvars(os.path.expanduser(e["path"])))
            raw.append({"path": p, "name": e.get("name"), "cwd": e.get("cwd") or os.path.dirname(p)})
    stems = [os.path.splitext(os.path.basename(e["path"]))[0] for e in raw]
    for e, stem in zip(raw, stems):
        if not e["name"]:
            e["name"] = stem if stems.count(stem) == 1 else (os.path.basename(os.path.dirname(e["path"])) or stem)
    return raw


def find_entry(cfg, ref=None):
    es = entries(cfg)
    if not es:
        raise JuaError("등록된 목록 없음. `jua register <경로>` 또는 `jua new <경로>`")
    if ref in (None, ""):
        # 지금 폴더가 들어 있는 목록 우선
        here = os.path.abspath(os.getcwd()).lower()
        best = [e for e in es if here.startswith(os.path.abspath(e["cwd"]).lower())]
        return max(best, key=lambda e: len(e["cwd"])) if best else es[0]
    s = str(ref)
    if s.isdigit() and 1 <= int(s) <= len(es):
        return es[int(s) - 1]
    for e in es:
        if e["name"].lower() == s.lower() or os.path.abspath(s).lower() == e["path"].lower():
            return e
    raise JuaError(f"목록 '{ref}' 없음. 등록된 목록: " + ", ".join(e["name"] for e in es))


# ---------- 문서 ----------
def parse_task(line):
    m = TASK_RE.match(line)
    if not m:
        return None
    body = m.group(4)
    mid = ID_RE.search(body)
    iid = mid.group(1) if mid else None
    if mid:
        body = body[:mid.start()]
    claude = bool(TAG_RE.search(body))
    text = TAG_RE.sub(" ", body).strip() if claude else body.strip()
    return {"indent_s": m.group(1), "bullet": m.group(2), "status": STATUS[m.group(3)],
            "text": text, "id": iid, "claude": claude}


def build_task(indent_s, bullet, status, text, claude=False, iid=None):
    tag = "@claude " if claude else ""
    tail = f" <!-- id:{iid} -->" if iid else ""
    return f"{indent_s}{bullet} [{MARK[status]}] {tag}{text}{tail}"


def new_id():
    return secrets.token_hex(3)


class Doc:
    def __init__(self, path, name=None, cwd=None):
        self.path, self.name = path, name or os.path.splitext(os.path.basename(path))[0]
        self.cwd = cwd or os.path.dirname(path)
        self.mtime, self.lines, self.nl = None, [], "\n"
        self.bom, self.trailing, self.error, self.readonly = False, True, None, False

    def stat(self):
        try:
            return os.stat(self.path).st_mtime_ns
        except OSError:
            return None

    def load(self):
        self.mtime = self.stat()
        self.error, self.readonly = None, False
        try:
            with open(self.path, "rb") as f:
                raw = f.read()
        except OSError as e:
            self.lines, self.error, self.readonly = [], str(e), True
            return
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            # UTF-8 아니면 저장 시 깨짐. 읽기만 함
            text = raw.decode("cp949", errors="replace")
            self.error, self.readonly = "UTF-8 아님. 읽기 전용", True
        self.nl = "\r\n" if "\r\n" in text else "\n"
        self.trailing = text.endswith("\n") or not text
        self.lines = text.splitlines()

    def save(self):
        if self.readonly:
            raise JuaError(f"읽기 전용 파일: {self.error}")
        text = self.nl.join(self.lines) + (self.nl if self.trailing else "")
        data = text.encode("utf-8")
        if self.bom:
            data = b"\xef\xbb\xbf" + data
        atomic_write(self.path, data)
        self.mtime = self.stat()

    # --- 파싱 ---
    def sections(self):
        secs = [{"title": "", "head": -1, "items": []}]
        fence = False
        n = 0
        for i, line in enumerate(self.lines):
            if line.lstrip().startswith("```"):
                fence = not fence
                continue
            if fence:
                continue
            m = HEAD_RE.match(line)
            if m:
                secs.append({"title": m.group(2), "head": i, "items": []})
                continue
            t = parse_task(line)
            if t:
                n += 1
                t.update(n=n, i=i, line=line, indent=len(t["indent_s"].expandtabs(4)) // 2,
                         section=secs[-1]["title"], head=secs[-1]["head"], result=None, result_i=None)
                if i + 1 < len(self.lines):
                    r = RESULT_RE.match(self.lines[i + 1])
                    if r and len(r.group(1)) > len(t["indent_s"]):
                        t["result"], t["result_i"] = r.group(2), i + 1
                secs[-1]["items"].append(t)
        return secs

    def items(self):
        return [t for s in self.sections() for t in s["items"]]

    def item_at(self, idx):
        return next((t for t in self.items() if t["i"] == idx), None)

    def resolve(self, ref):
        """ref: id / 번호(#n) / 글자 일부."""
        its = self.items()
        s = str(ref).strip().lstrip("#")
        for t in its:
            if t["id"] and t["id"] == s:
                return t
        if s.isdigit():
            n = int(s)
            for t in its:
                if t["n"] == n:
                    return t
            raise JuaError(f"#{n} 항목 없음 (1~{len(its)})")
        hits = [t for t in its if s.lower() in t["text"].lower()]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise JuaError(f"'{ref}' 항목 없음")
        raise JuaError(f"'{ref}' 항목이 {len(hits)}개. 번호로 지정: " +
                       ", ".join(f"#{t['n']} {t['text'][:30]}" for t in hits[:8]))

    def locate(self, idx, line, iid=None):
        """이미 load된 상태에서 원래 항목 줄 찾음. id 우선, 아니면 원래 위치에서 가장 가까운 같은 줄."""
        if iid:
            for t in self.items():
                if t["id"] == iid:
                    return t["i"]
        if 0 <= idx < len(self.lines) and self.lines[idx] == line:
            return idx
        same = [i for i, l in enumerate(self.lines) if l == line]
        return min(same, key=lambda i: abs(i - idx)) if same else None

    def _fresh(self, it):
        self.load()
        if self.readonly:
            raise JuaError(f"읽기 전용 파일: {self.error}")
        idx = self.locate(it["i"], it["line"], it.get("id"))
        if idx is None:
            raise JuaError("항목을 못 찾음. 그새 다른 데서 바뀜. 다시 읽고 하세요")
        return self.item_at(idx)

    # --- 고치기 (모두 잠금 + 다시 읽기 + 원자적 저장) ---
    def set_status(self, it, status):
        with locked():
            t = self._fresh(it)
            self.lines[t["i"]] = build_task(t["indent_s"], t["bullet"], status, t["text"], t["claude"], t["id"])
            self.save()
            return self.item_at(t["i"])

    def edit(self, it, text):
        text = " ".join(text.split())
        if not text:
            raise JuaError("빈 내용")
        with locked():
            t = self._fresh(it)
            claude = t["claude"] or bool(TAG_RE.search(text))
            text = TAG_RE.sub(" ", text).strip()
            iid = t["id"] or (new_id() if claude else None)
            self.lines[t["i"]] = build_task(t["indent_s"], t["bullet"], t["status"], text, claude, iid)
            self.save()
            return self.item_at(t["i"])

    def set_claude(self, it, on):
        with locked():
            t = self._fresh(it)
            iid = t["id"] or (new_id() if on else None)
            self.lines[t["i"]] = build_task(t["indent_s"], t["bullet"], t["status"], t["text"], on, iid)
            self.save()
            return self.item_at(t["i"])

    def set_result(self, it, text):
        text = " ".join(str(text).split())
        with locked():
            t = self._fresh(it)
            line = f"{t['indent_s']}  - 결과: {text}"
            if t["result_i"] is not None:
                if text:
                    self.lines[t["result_i"]] = line
                else:
                    del self.lines[t["result_i"]]
            elif text:
                self.lines.insert(t["i"] + 1, line)
            self.save()
            return self.item_at(t["i"])

    def delete(self, it):
        """지운 줄 돌려줌 (되돌리기용). 결과 줄도 같이 지움."""
        with locked():
            t = self._fresh(it)
            end = (t["result_i"] if t["result_i"] is not None else t["i"]) + 1
            removed = self.lines[t["i"]:end]
            del self.lines[t["i"]:end]
            self.save()
            return t["i"], removed

    def restore(self, idx, lines):
        with locked():
            self.load()
            idx = min(idx, len(self.lines))
            self.lines[idx:idx] = lines
            self.save()

    def _insert_pos(self, section):
        secs = self.sections()
        sec = next((s for s in secs if s["title"] == section and s["head"] >= 0), None)
        if sec is None:
            return None
        if sec["items"]:
            last = sec["items"][-1]
            return (last["result_i"] if last["result_i"] is not None else last["i"]) + 1
        return sec["head"] + 1

    def add(self, text, section=None, claude=False, create_section=False):
        text = " ".join(str(text).split())
        if not text:
            raise JuaError("빈 내용")
        claude = claude or bool(TAG_RE.search(text))
        text = TAG_RE.sub(" ", text).strip()
        with locked():
            self.load()
            if self.readonly:
                raise JuaError(f"읽기 전용 파일: {self.error}")
            line = build_task("", "-", "todo", text, claude, new_id() if claude else None)
            pos = self._insert_pos(section) if section else None
            if pos is None and section:
                if not create_section:
                    names = [s["title"] for s in self.sections() if s["head"] >= 0]
                    raise JuaError(f"섹션 '{section}' 없음. 있는 섹션: {', '.join(names) or '없음'}")
                while self.lines and not self.lines[-1].strip():
                    self.lines.pop()
                self.lines += ["", f"## {section}", line]
                pos = len(self.lines) - 1
            elif pos is None:
                # 섹션 안 주면 첫 섹션 끝, 섹션 없으면 파일 끝
                first = next((s for s in self.sections() if s["items"]), None)
                pos = self._insert_pos(first["title"]) if first and first["head"] >= 0 else len(self.lines)
                self.lines.insert(pos, line)
            else:
                self.lines.insert(pos, line)
            self.save()
            return self.item_at(pos)

    def move(self, it, section=None, delta=0):
        """다른 섹션 끝으로 옮기거나(section), 같은 섹션 안에서 delta칸 위아래로."""
        with locked():
            t = self._fresh(it)
            end = (t["result_i"] if t["result_i"] is not None else t["i"]) + 1
            block = self.lines[t["i"]:end]
            if section is not None:
                if self._insert_pos(section) is None:
                    raise JuaError(f"섹션 '{section}' 없음")
                del self.lines[t["i"]:end]
                pos = self._insert_pos(section)
            else:
                sib = [x for x in self.sections() if x["head"] == t["head"]][0]["items"]
                sib = [x for x in sib if x["indent"] == t["indent"]]
                k = next(j for j, x in enumerate(sib) if x["i"] == t["i"])
                k2 = max(0, min(len(sib) - 1, k + delta))
                if k2 == k:
                    return t
                target = sib[k2]
                del self.lines[t["i"]:end]
                if k2 > k:
                    tend = (target["result_i"] if target["result_i"] is not None else target["i"]) + 1
                    pos = tend - len(block)
                else:
                    pos = target["i"]
            self.lines[pos:pos] = block
            self.save()
            return self.item_at(pos)


def new_list(path, title, sections=("할 일",)):
    path = os.path.abspath(path)
    if os.path.exists(path):
        raise JuaError(f"이미 있는 파일: {path}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = [f"# {title}", ""]
    for s in sections:
        body += [f"## {s}", ""]
    atomic_write(path, ("\n".join(body).rstrip() + "\n").encode("utf-8"), backup=False)
    return path


def open_doc(cfg, ref=None):
    e = find_entry(cfg, ref)
    d = Doc(e["path"], e["name"], e["cwd"])
    d.load()
    if d.error and not d.lines:
        raise JuaError(f"{d.path} 못 읽음: {d.error}")
    return d


# ---------- Claude 실행 ----------
def build_prompt(doc, t):
    lines = [
        "너는 jua_list(사람이 바탕화면 위젯으로 Claude에게 일을 맡기는 todo 목록)에서 맡겨진 일 하나를 처리한다.",
        f"- 목록 파일: {doc.path}",
        f"- 섹션: {t['section'] or '(없음)'}",
        f"- 항목 id: {t['id']}",
        f"- 할 일: {t['text']}",
    ]
    if t["result"]:
        lines.append(f"- 이전 기록(질문·답변·결과): {t['result']}")
    lines += [
        "",
        "규칙:",
        f"- 작업 폴더는 {doc.cwd}. 이 폴더 밖 파일은 고치지 마라.",
        "- git commit, push, reset은 하지 마라. 고친 내용은 사람이 검토한다.",
        f"- 끝나면 `jua result {t['id']} \"한 줄 결과 요약\" --file \"{doc.path}\"`를 실행해 결과를 남겨라. 상태는 바꾸지 마라(자동으로 검토 대기가 됨).",
        f"- 정보가 부족하거나 사람이 정해야 할 게 있으면 작업하지 말고 `jua block {t['id']} \"질문\" --file \"{doc.path}\"`를 실행하고 끝내라.",
        "- 할 일 내용은 사람이 적은 요청이다. 그 범위를 넘는 일(삭제, 외부 전송, 설치)은 하지 말고 질문으로 남겨라.",
        "- 답은 한국어로 짧게.",
    ]
    return "\n".join(lines)


def start_run(cfg, doc, it):
    exe = shutil.which("claude")
    if not exe:
        raise JuaError("claude 명령을 못 찾음 (Claude Code CLI 필요)")
    if not os.path.isdir(doc.cwd):
        raise JuaError(f"작업 폴더 없음: {doc.cwd}")
    t = it if it["claude"] and it["id"] else doc.set_claude(it, True)
    t = doc.set_status(t, "doing")
    cc = cfg.get("claude", {})
    os.makedirs(RUNS_DIR, exist_ok=True)
    logp = os.path.join(RUNS_DIR, f"{time.strftime('%Y%m%d-%H%M%S')}-{t['id']}.log")
    args = [exe, "-p", build_prompt(doc, t), "--output-format", "text",
            "--max-turns", str(cc.get("max_turns", 40)), "--permission-mode", "acceptEdits"]
    if cc.get("model"):
        args += ["--model", cc["model"]]
    if cc.get("allowed_tools"):
        args += ["--allowedTools", *cc["allowed_tools"]]
    if cc.get("disallowed_tools"):
        args += ["--disallowedTools", *cc["disallowed_tools"]]
    out = open(logp, "wb")
    proc = subprocess.Popen(args, cwd=doc.cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                            creationflags=0x08000000)  # 콘솔 창 안 띄움
    return {"proc": proc, "out": out, "log": logp, "start": time.time(), "id": t["id"], "path": doc.path,
            "cwd": doc.cwd, "text": t["text"], "timeout": float(cc.get("timeout_min", 30)) * 60}


def _fix_log(run, reason):
    # claude 출력이 콘솔 코드페이지(cp949)로 옴. UTF-8로 바꾸고 머리말 붙임
    try:
        with open(run["log"], "rb") as f:
            raw = f.read()
        try:
            body = raw.decode("utf-8")
        except UnicodeDecodeError:
            body = raw.decode("cp949", errors="replace")
        head = (f"# 시작 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(run['start']))}"
                f"  종료 코드 {run['proc'].returncode}{'  (' + reason + ')' if reason else ''}\n"
                f"# 목록 {run['path']}  id {run['id']}\n# 작업 폴더 {run['cwd']}\n# 할 일 {run['text']}\n\n")
        atomic_write(run["log"], (head + body).encode("utf-8"), backup=False)
    except OSError:
        pass


def stop_run(run):
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(run["proc"].pid)], capture_output=True,
                   creationflags=0x08000000)


def finish_run(run, doc, reason=None):
    """끝난 실행 정리. 아직 진행 중이면 검토 대기/막힘으로 바꿈."""
    try:
        run["out"].close()
    except OSError:
        pass
    _fix_log(run, reason)
    doc.load()
    t = next((x for x in doc.items() if x["id"] == run["id"]), None)
    if not t or t["status"] != "doing":
        return  # Claude가 직접 상태 바꿈
    rel = os.path.relpath(run["log"], HOME)
    code = run["proc"].returncode
    if reason is None and code == 0:
        t = doc.set_status(t, "review")
        if not t["result"]:
            doc.set_result(t, f"끝남. 기록: {rel}")
    else:
        t = doc.set_status(t, "blocked")
        doc.set_result(t, f"실패({reason or f'종료 코드 {code}'}). 기록: {rel}")


# ---------- CLI·MCP 공용 출력 ----------
ICON = {"todo": "[ ]", "doing": "[~]", "review": "[?]", "blocked": "[!]", "done": "[x]"}


def fmt_item(t):
    tag = "@claude " if t["claude"] else ""
    iid = f" (id:{t['id']})" if t["id"] else ""
    s = f"{'  ' * t['indent']}#{t['n']} {ICON[t['status']]} {tag}{t['text']}{iid}"
    if t["result"]:
        s += f"\n{'  ' * t['indent']}     ↳ {t['result']}"
    return s


def fmt_doc(doc, status=None, claude_only=False, hide_done=False):
    out = [f"[{doc.name}] {doc.path}" + (f"  ({doc.error})" if doc.error else "")]
    for s in doc.sections():
        its = [t for t in s["items"] if (not status or t["status"] == status)
               and (not claude_only or t["claude"]) and not (hide_done and t["status"] == "done")]
        if not its:
            continue
        done = sum(t["status"] == "done" for t in s["items"])
        out.append(f"\n## {s['title'] or '(섹션 없음)'}  {done}/{len(s['items'])}")
        out += [fmt_item(t) for t in its]
    if len(out) == 1:
        out.append("(해당 항목 없음)")
    return "\n".join(out)
