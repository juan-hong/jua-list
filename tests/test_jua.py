"""jua_list 테스트. 실행: python -m unittest discover -s tests"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout

TMP = tempfile.mkdtemp(prefix="jua_test_")
os.environ["JUA_HOME"] = os.path.join(TMP, "home")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "jua"))

import jua  # noqa: E402
import jua_core as core  # noqa: E402
import jua_mcp  # noqa: E402


def cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = jua.main(list(args))
    return code, out.getvalue() + err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(dir=TMP)
        self.md = os.path.join(self.dir, "t.md")
        if os.path.exists(core.CFG_PATH):
            os.remove(core.CFG_PATH)
        core.save_cfg(dict(core.DEFAULT_CFG, files=[]))
        code, out = cli("new", self.md, "--title", "T", "--sections", "A,B", "--name", "t", "--cwd", self.dir)
        self.assertEqual(code, 0, out)

    def text(self):
        with open(self.md, encoding="utf-8") as f:
            return f.read()

    def doc(self):
        return core.open_doc(core.load_cfg(), "t")


class TestDoc(Base):
    def test_add_and_sections(self):
        cli("add", "하나", "-f", "t", "-s", "A")
        cli("add", "둘", "-f", "t", "-s", "B", "--claude")
        cli("add", "셋", "-f", "t", "-s", "A")
        secs = {s["title"]: [t["text"] for t in s["items"]] for s in self.doc().sections()}
        self.assertEqual(secs["A"], ["하나", "셋"])
        self.assertEqual(secs["B"], ["둘"])
        two = self.doc().resolve("둘")
        self.assertTrue(two["claude"])
        self.assertRegex(two["id"], r"^[0-9a-f]{6}$")

    def test_missing_section(self):
        code, out = cli("add", "x", "-f", "t", "-s", "없음")
        self.assertEqual(code, 1)
        self.assertIn("없음", out)
        code, _ = cli("add", "x", "-f", "t", "-s", "새섹션", "--create")
        self.assertEqual(code, 0)
        self.assertIn("## 새섹션\n- [ ] x", self.text())

    def test_status_cycle(self):
        cli("add", "일", "-f", "t", "-s", "A")
        for st, mark in [("doing", "~"), ("review", "?"), ("blocked", "!"), ("done", "x"), ("todo", " ")]:
            code, out = cli("status", "일", st, "-f", "t")
            self.assertEqual(code, 0, out)
            self.assertIn(f"- [{mark}] 일", self.text())

    def test_edit_keeps_tag_and_id(self):
        cli("add", "@claude 원래", "-f", "t", "-s", "A")
        iid = self.doc().resolve("원래")["id"]
        cli("edit", iid, "바뀜", "-f", "t")
        t = self.doc().resolve(iid)
        self.assertEqual((t["text"], t["claude"]), ("바뀜", True))
        # 나중에 태그 붙이면 id 생김
        cli("add", "보통", "-f", "t", "-s", "A")
        cli("edit", "보통", "보통 @claude", "-f", "t")
        self.assertTrue(self.doc().resolve("보통")["id"])

    def test_result_and_delete_with_result(self):
        cli("add", "일", "-f", "t", "-s", "A")
        cli("add", "다음", "-f", "t", "-s", "A")
        cli("result", "일", "결과 문장", "-f", "t")
        self.assertIn("- [ ] 일\n  - 결과: 결과 문장\n- [ ] 다음", self.text())
        cli("result", "일", "고친 결과", "-f", "t")
        self.assertEqual(self.text().count("결과:"), 1)
        d = self.doc()
        idx, removed = d.delete(d.resolve("일"))
        self.assertEqual(len(removed), 2)
        self.assertNotIn("결과", self.text())
        d.restore(idx, removed)
        self.assertIn("- [ ] 일\n  - 결과: 고친 결과", self.text())

    def test_block(self):
        cli("add", "질문할 일", "-f", "t", "-s", "A")
        cli("block", "질문할", "어떻게?", "-f", "t")
        t = self.doc().resolve("질문할")
        self.assertEqual((t["status"], t["result"]), ("blocked", "질문: 어떻게?"))

    def test_move(self):
        for x in ["a1", "a2", "a3"]:
            cli("add", x, "-f", "t", "-s", "A")
        cli("result", "a1", "r", "-f", "t")
        cli("move", "a1", "--down", "1", "-f", "t")
        self.assertEqual([t["text"] for t in self.doc().sections()[2]["items"]], ["a2", "a1", "a3"])
        self.assertEqual(self.doc().resolve("a1")["result"], "r")
        cli("move", "a3", "--up", "2", "-f", "t")
        self.assertEqual([t["text"] for t in self.doc().sections()[2]["items"]], ["a3", "a2", "a1"])
        cli("move", "a1", "--to", "B", "-f", "t")
        b = self.doc().sections()[3]
        self.assertEqual((b["title"], [t["text"] for t in b["items"]]), ("B", ["a1"]))

    def test_resolve_ambiguous(self):
        cli("add", "같은 글", "-f", "t", "-s", "A")
        cli("add", "같은 글", "-f", "t", "-s", "B")
        code, out = cli("done", "같은", "-f", "t")
        self.assertEqual(code, 1)
        self.assertIn("2개", out)
        self.assertEqual(cli("done", "2", "-f", "t")[0], 0)
        self.assertIn("## B\n- [x] 같은 글", self.text())

    def test_stale_duplicate_picks_nearest(self):
        cli("add", "dup", "-f", "t", "-s", "A")
        cli("add", "dup", "-f", "t", "-s", "B")
        d = self.doc()
        second = d.items()[1]
        # 다른 데서 위에 줄 추가 (줄 번호 밀림)
        cli("add", "위에 끼움", "-f", "t", "-s", "A")
        d.set_status(second, "done")
        self.assertIn("## A\n- [ ] dup", self.text())
        self.assertIn("## B\n- [x] dup", self.text())

    def test_preserves_other_lines_crlf_bom(self):
        with open(self.md, "wb") as f:
            f.write(b"\xef\xbb\xbf# T\r\n\r\n## A\r\n- [ ] x\r\n\xeb\xa9\x94\xeb\xaa\xa8 \xec\xa4\x84\r\n```\r\n- [ ] code\r\n```\r\n")
        cli("done", "x", "-f", "t")
        with open(self.md, "rb") as f:
            raw = f.read()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"- [x] x\r\n", raw)
        self.assertIn("메모 줄".encode(), raw)
        self.assertEqual(len(self.doc().items()), 1)  # 코드 블록 안은 무시

    def test_non_utf8_is_readonly(self):
        with open(self.md, "wb") as f:
            f.write("## A\n- [ ] 한글\n".encode("cp949"))
        d = self.doc()
        self.assertTrue(d.readonly)
        with self.assertRaises(core.JuaError):
            d.set_status(d.items()[0], "done")
        with open(self.md, "rb") as f:
            self.assertEqual(f.read(), "## A\n- [ ] 한글\n".encode("cp949"))

    def test_backup_written(self):
        cli("add", "x", "-f", "t", "-s", "A")
        self.assertTrue(os.path.exists(self.md + ".bak"))


class TestConfig(Base):
    def test_corrupt_config_not_overwritten(self):
        with open(core.CFG_PATH, "w", encoding="utf-8") as f:
            f.write("{ broken")
        with self.assertRaises(core.JuaError):
            core.load_cfg()
        with self.assertRaises(core.JuaError):
            core.update_cfg(lambda c: c.update(alpha=1))
        with open(core.CFG_PATH, encoding="utf-8") as f:
            self.assertEqual(f.read(), "{ broken")

    def test_config_set_get(self):
        self.assertEqual(cli("config", "alpha", "200")[0], 0)
        self.assertEqual(cli("config", "claude.max_turns", "5")[0], 0)
        cfg = core.load_cfg()
        self.assertEqual((cfg["alpha"], cfg["claude"]["max_turns"], cfg["claude"]["timeout_min"]), (200, 5, 30))
        self.assertEqual(cli("config", "files", "[]")[0], 1)

    def test_register_unregister_entry(self):
        other = os.path.join(self.dir, "o.md")
        open(other, "w").close()
        self.assertEqual(cli("register", other, "--name", "oo")[0], 0)
        self.assertEqual(cli("register", other)[0], 1)  # 중복
        self.assertEqual(cli("entry", "oo", "--cwd", TMP)[0], 0)
        e = core.find_entry(core.load_cfg(), "oo")
        self.assertEqual(e["cwd"], os.path.abspath(TMP))
        self.assertEqual(cli("unregister", "oo")[0], 0)
        self.assertTrue(os.path.exists(other))
        self.assertEqual(cli("list", "-f", "oo")[0], 1)

    def test_concurrent_writers(self):
        procs = [subprocess.Popen([sys.executable, os.path.join(ROOT, "jua", "jua.py"), "add", f"c{i}",
                                   "-f", "t", "-s", "A"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                 for i in range(15)]
        procs += [subprocess.Popen([sys.executable, os.path.join(ROOT, "jua", "jua.py"), "config", "alpha",
                                    str(100 + i)], stdout=subprocess.DEVNULL) for i in range(5)]
        for p in procs:
            p.wait(60)
        self.assertEqual(sum(t["text"].startswith("c") for t in self.doc().items()), 15)
        self.assertEqual(len(core.entries(core.load_cfg())), 1)


class TestMcp(Base):
    def call(self, *reqs):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "jua", "jua_mcp.py")],
                           input="\n".join(json.dumps(r) for r in reqs).encode(), capture_output=True, timeout=60)
        return [json.loads(x) for x in p.stdout.decode("utf-8").splitlines()]

    def test_protocol(self):
        r = self.call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                      {"jsonrpc": "2.0", "method": "notifications/initialized"},
                      {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                      {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                       "params": {"name": "jua_add", "arguments": {"text": "엠씨피", "file": "t", "section": "A",
                                                                     "claude": True}}},
                      {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                       "params": {"name": "jua_update", "arguments": {"ref": "엠씨피", "file": "t",
                                                                        "status": "review", "result": "ok"}}},
                      {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                       "params": {"name": "jua_list", "arguments": {"file": "없음"}}},
                      {"jsonrpc": "2.0", "id": 6, "method": "nope"})
        self.assertEqual([x["id"] for x in r], [1, 2, 3, 4, 5, 6])
        self.assertEqual(r[0]["result"]["serverInfo"]["name"], "jua_list")
        self.assertGreaterEqual(len(r[1]["result"]["tools"]), 12)
        self.assertFalse(r[2]["result"]["isError"])
        self.assertFalse(r[3]["result"]["isError"])
        self.assertTrue(r[4]["result"]["isError"])
        self.assertIn("error", r[5])
        t = self.doc().resolve("엠씨피")
        self.assertEqual((t["status"], t["result"], t["claude"]), ("review", "ok", True))


class FakeProc:
    def __init__(self, code):
        self.returncode, self.pid = code, 0


class TestRun(Base):
    def run_case(self, code, reason=None, claude_sets=None):
        cli("add", "@claude 일", "-f", "t", "-s", "A")
        d = self.doc()
        t = d.set_status(d.resolve("일"), "doing")
        if claude_sets:
            d.set_status(t, claude_sets)
        logp = os.path.join(TMP, f"run{time.time()}.log")
        with open(logp, "wb") as f:
            f.write("출력".encode("cp949"))
        run = {"proc": FakeProc(code), "out": open(logp, "ab"), "log": logp, "start": time.time(), "id": t["id"],
               "path": self.md, "cwd": self.dir, "text": "일"}
        core.finish_run(run, self.doc(), reason)
        with open(logp, encoding="utf-8") as f:
            self.assertIn("출력", f.read())  # cp949 -> utf-8
        return self.doc().resolve(t["id"])

    def test_success_goes_review(self):
        t = self.run_case(0)
        self.assertEqual(t["status"], "review")
        self.assertIn("끝남", t["result"])

    def test_failure_goes_blocked(self):
        t = self.run_case(1)
        self.assertEqual(t["status"], "blocked")
        self.assertIn("실패", t["result"])

    def test_timeout_reason(self):
        self.assertIn("시간 초과", self.run_case(None, "시간 초과")["result"])

    def test_claude_status_kept(self):
        self.assertEqual(self.run_case(0, claude_sets="blocked")["status"], "blocked")

    def test_prompt_has_rules(self):
        cli("add", "@claude 프롬프트", "-f", "t", "-s", "A")
        d = self.doc()
        p = core.build_prompt(d, d.resolve("프롬프트"))
        self.assertIn("git commit", p)
        self.assertIn("jua result", p)
        self.assertIn(self.dir, p)

    def test_start_run_missing_cwd(self):
        cli("add", "@claude 폴더", "-f", "t", "-s", "A")
        cli("entry", "t", "--cwd", os.path.join(TMP, "없는폴더"))
        d = self.doc()
        with self.assertRaises(core.JuaError):
            core.start_run(core.load_cfg(), d, d.resolve("폴더"))


if __name__ == "__main__":
    unittest.main()
