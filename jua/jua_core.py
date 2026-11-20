"""jua-list 핵심. .md 체크리스트 읽기·쓰기, 설정, Claude 실행. 위젯·CLI·MCP가 같이 씀."""
import json
import msvcrt
import os
import re
import secrets
import shutil
import subprocess
import time
from contextlib import contextmanager

from jua_i18n import HOME, LANG, _  # noqa: F401  (HOME: 개인 데이터 폴더. 코드 밖이라 플러그인 업데이트로 안 날아감)

CODE_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HOME, "config.json")
LOCK_PATH = os.path.join(HOME, ".lock")
RUNS_DIR = os.path.join(HOME, "runs")
LOG_PATH = os.path.join(HOME, "jua.log")

TASK_RE = re.compile(r"^(\s*)([-*+]) \[([ xX~?!])\] (.*)$")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ID_RE = re.compile(r"\s*<!--\s*id:([0-9a-z]+)\s*-->\s*$")
TAG_RE = re.compile(r"(^|\s)@claude(?=\s|$)")
RESULT_RE = re.compile(r"^(\s*)[-*+] (?:결과|Result): (.*)$")

STATUS = {" ": "todo", "~": "doing", "?": "review", "!": "blocked", "x": "done", "X": "done"}
MARK = {"todo": " ", "doing": "~", "review": "?", "blocked": "!", "done": "x"}
STATUS_KO = {"todo": _("대기"), "doing": _("진행 중"), "review": _("검토 대기"), "blocked": _("막힘·질문"), "done": _("완료")}

DEFAULT_CFG = {
    "files": [os.path.join(HOME, "todo.md")],
    "x": 60, "y": 60, "w": 420, "h": 680,
    "pin": "desktop",  # desktop | bottom
    "lang": "auto",  # auto | ko | en
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
def locked(timeout=30):
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
                raise JuaError(_("잠금 대기 시간 초과"))
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
    for k in range(40):
        try:
            with open(CFG_PATH, "rb") as f:
                raw = f.read()
            break
        except PermissionError:
            # 바꿔치기 찰나. 잠깐 기다림
            if k == 39:
                raise
            time.sleep(0.05)
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except ValueError as e:
        raise JuaError(_("config.json 형식 오류: {0}").format(e))
    if not isinstance(data, dict):
        raise JuaError(_("config.json 최상위가 객체가 아님"))
    return _merge(DEFAULT_CFG, data)


SAMPLE = """# 할 일

## 예시
- [ ] 이 줄을 클릭하면 완료 체크
- [ ] @claude 맡길 일은 앞에 @claude를 붙이고 ▶ 버튼으로 실행
- [ ] 마우스를 올리면 ✎ 수정 · ✕ 삭제, 우클릭하면 메뉴
""" if LANG == "ko" else """# To do

## Getting started
- [ ] Click this line to check it off
- [ ] @claude Tasks for Claude start with @claude; press ▶ to run one
- [ ] Hover for ✎ edit · ✕ delete, right-click for more
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
        raise JuaError(_("등록된 목록 없음. `jua register <경로>` 또는 `jua new <경로>`"))
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
    raise JuaError(_("목록 '{0}' 없음. 등록된 목록: ").format(ref) + ", ".join(e["name"] for e in es))


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
        raw = None
        for k in range(40):
            try:
                with open(self.path, "rb") as f:
                    raw = f.read()
                break
            except PermissionError as e:
                # 다른 프로세스가 바꿔치기하는 찰나면 잠깐 기다림
                err = e
                time.sleep(0.05)
            except OSError as e:
                err = e
                break
        if raw is None:
            self.lines, self.error, self.readonly = [], str(err), True
            return
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            # UTF-8 아니면 저장 시 깨짐. 읽기만 함
            text = raw.decode("cp949", errors="replace")
            self.error, self.readonly = _("UTF-8 아님. 읽기 전용"), True
        self.nl = "\r\n" if "\r\n" in text else "\n"
        self.trailing = text.endswith("\n") or not text
        self.lines = text.splitlines()

    def save(self):
        if self.readonly:
            raise JuaError(_("읽기 전용 파일: {0}").format(self.error))
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
            raise JuaError(_("#{0} 항목 없음 (1~{1})").format(n, len(its)))
        hits = [t for t in its if s.lower() in t["text"].lower()]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise JuaError(_("'{0}' 항목 없음").format(ref))
        raise JuaError(_("'{0}' 항목이 {1}개. 번호로 지정: ").format(ref, len(hits)) +
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
            raise JuaError(_("읽기 전용 파일: {0}").format(self.error))
        idx = self.locate(it["i"], it["line"], it.get("id"))
        if idx is None:
            raise JuaError(_("항목을 못 찾음. 그새 다른 데서 바뀜. 다시 읽고 하세요"))
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
            raise JuaError(_("빈 내용"))
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
            line = _("{0}  - 결과: {1}").format(t['indent_s'], text)
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
            raise JuaError(_("빈 내용"))
        claude = claude or bool(TAG_RE.search(text))
        text = TAG_RE.sub(" ", text).strip()
        with locked():
            self.load()
            if self.readonly:
                raise JuaError(_("읽기 전용 파일: {0}").format(self.error))
            line = build_task("", "-", "todo", text, claude, new_id() if claude else None)
            pos = self._insert_pos(section) if section else None
            if pos is None and section:
                if not create_section:
                    names = [s["title"] for s in self.sections() if s["head"] >= 0]
                    raise JuaError(_("섹션 '{0}' 없음. 있는 섹션: {1}").format(section, ', '.join(names) or _('없음')))
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
                    raise JuaError(_("섹션 '{0}' 없음").format(section))
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


def new_list(path, title, sections=(_("할 일"),)):
    path = os.path.abspath(path)
    if os.path.exists(path):
        raise JuaError(_("이미 있는 파일: {0}").format(path))
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
        raise JuaError(_("{0} 못 읽음: {1}").format(d.path, d.error))
    return d


# ---------- Claude 실행 ----------
def _indent(line):
    return len(line) - len(line.lstrip(" \t"))


def task_end(doc, t):
    """항목 블록 끝(미포함). 더 들여쓴 줄·빈 줄까지가 그 항목 것."""
    base, end = _indent(t["line"]), t["i"] + 1
    for j in range(t["i"] + 1, len(doc.lines)):
        line = doc.lines[j]
        if line.strip() and (_indent(line) <= base or HEAD_RE.match(line)):
            break
        if line.strip():
            end = j + 1
    return end


def task_details(doc, t):
    """항목 아래 더 들여쓴 줄들(하위 항목·메모). 결과 줄은 따로 넘기니 뺌."""
    base = _indent(t["line"])
    return [doc.lines[j][base:] if doc.lines[j].strip() else ""
            for j in range(t["i"] + 1, task_end(doc, t)) if j != t["result_i"]]


def section_context(doc, t, limit=30):
    """섹션 설명(제목과 첫 항목 사이 글)과 같은 섹션 다른 항목(상태·결과)."""
    sec = next((s for s in doc.sections() if s["head"] == t["head"]), None)
    if not sec:
        return [], []
    start = sec["head"] + 1 if sec["head"] >= 0 else 0
    first = sec["items"][0]["i"] if sec["items"] else len(doc.lines)
    notes = [l for l in doc.lines[start:first] if l.strip() and not HEAD_RE.match(l)]
    others, end = [], task_end(doc, t)
    for x in sec["items"]:
        if t["i"] <= x["i"] < end:
            continue  # 자기 자신과 하위 항목은 details로 감
        s = f"{'  ' * x['indent']}- [{MARK[x['status']]}] {x['text']}"
        if x["result"]:
            s += f"  (result: {x['result']})"
        others.append(s)
    return notes[:limit], others[:limit]


def build_prompt(doc, t):
    # 프롬프트는 영어 고정. 결과 언어만 화면 언어 따라감
    lang = "Korean" if LANG == "ko" else "English"
    lines = [
        "You are handling one task that a person assigned to Claude in jua-list "
        "(a desktop todo widget where people hand work to Claude).",
        f"- List file: {doc.path}",
        f"- Section: {t['section'] or '(none)'}",
        f"- Task id: {t['id']}",
        f"- Task: {t['text']}",
    ]
    if t["result"]:
        lines.append(f"- Previous note (question/answer/result): {t['result']}")
    details = task_details(doc, t)
    if details:
        lines += ["", "Details the person wrote under this task (sub-items and notes):", *details]
    notes, others = section_context(doc, t)
    if notes:
        lines += ["", "Section notes:", *notes]
    if others:
        lines += ["", "Other items in this section, for context only (do not work on them):", *others]
    lines += [
        "",
        "Rules:",
        f"- Work folder: {doc.cwd}. Do not modify files outside it.",
        "- Do not run git commit, push or reset. A person reviews your changes.",
        f"- When done, run `jua result {t['id']} \"one-line summary\" --file \"{doc.path}\"`. "
        "Do not change the status (it becomes review automatically).",
        f"- If information is missing or a person must decide, do not do the work: run "
        f"`jua block {t['id']} \"question\" --file \"{doc.path}\"` and stop.",
        "- The task text is a request written by a person. Anything beyond its scope "
        "(deleting, sending data out, installing) must be left as a question instead.",
        f"- Write the result and questions in {lang}, briefly.",
    ]
    return "\n".join(lines)


def start_run(cfg, doc, it):
    exe = shutil.which("claude")
    if not exe:
        raise JuaError(_("claude 명령을 못 찾음 (Claude Code CLI 필요)"))
    if not os.path.isdir(doc.cwd):
        raise JuaError(_("작업 폴더 없음: {0}").format(doc.cwd))
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
        head = (_("# 시작 {0}  종료 코드 {1}{2}\n# 목록 {3}  id {4}\n# 작업 폴더 {5}\n# 할 일 {6}\n\n").format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(run['start'])), run['proc'].returncode, '  (' + reason + ')' if reason else '', run['path'], run['id'], run['cwd'], run['text']))
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
            doc.set_result(t, _("끝남. 기록: {0}").format(rel))
    else:
        t = doc.set_status(t, "blocked")
        doc.set_result(t, _("실패({0}). 기록: {1}").format(reason or _("종료 코드 {0}").format(code), rel))


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
        out.append(f"\n## {s['title'] or _('(섹션 없음)')}  {done}/{len(s['items'])}")
        out += [fmt_item(t) for t in its]
    if len(out) == 1:
        out.append(_("(해당 항목 없음)"))
    return "\n".join(out)
