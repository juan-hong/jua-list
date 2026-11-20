"""jua-list 데이터 위치와 화면 언어(ko/en). 한국어 원문을 키로 영어 번역을 찾음."""
import ctypes
import json
import os

_BASE = os.environ.get("APPDATA") or os.path.expanduser("~")
HOME = os.environ.get("JUA_HOME") or os.path.join(_BASE, "jua-list")
if not os.environ.get("JUA_HOME"):
    _old = os.path.join(_BASE, "jua_list")
    # 예전 이름 폴더면 옮김
    if os.path.isdir(_old) and not os.path.exists(HOME):
        try:
            os.rename(_old, HOME)
        except OSError:
            pass
os.makedirs(HOME, exist_ok=True)


def _detect():
    v = (os.environ.get("JUA_LANG") or "").lower()
    if v in ("ko", "en"):
        return v
    try:
        with open(os.path.join(HOME, "config.json"), encoding="utf-8-sig") as f:
            v = str(json.load(f).get("lang", "auto")).lower()
        if v in ("ko", "en"):
            return v
    except (OSError, ValueError, AttributeError):
        pass
    try:
        # Windows 표시 언어. 0x12 = 한국어
        return "ko" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x12 else "en"
    except Exception:
        return "en"


LANG = _detect()


def _(s):
    return s if LANG == "ko" else EN.get(s, s)


EN = {
    # 상태·기본
    "대기": "To do", "진행 중": "Doing", "검토 대기": "Review", "막힘·질문": "Blocked", "완료": "Done",
    "할 일": "To do", "없음": "none", "(해당 항목 없음)": "(no matching items)", "(섹션 없음)": "(no section)",
    "(파일 끝)": "(end of file)", "작업 중": "Working",
    # core 오류·메시지
    "config.json 최상위가 객체가 아님": "config.json top level is not an object",
    "등록된 목록 없음. `jua register <경로>` 또는 `jua new <경로>`":
        "No lists registered. Use `jua register <path>` or `jua new <path>`",
    "claude 명령을 못 찾음 (Claude Code CLI 필요)": "claude command not found (Claude Code CLI required)",
    "항목을 못 찾음. 그새 다른 데서 바뀜. 다시 읽고 하세요": "Item not found. It changed elsewhere; reload and retry",
    "빈 내용": "Empty text",
    "# 시작 {0}  종료 코드 {1}{2}\n# 목록 {3}  id {4}\n# 작업 폴더 {5}\n# 할 일 {6}\n\n":
        "# start {0}  exit code {1}{2}\n# list {3}  id {4}\n# work folder {5}\n# task {6}\n\n",
    "목록 '{0}' 없음. 등록된 목록: ": "No list '{0}'. Registered lists: ",
    "UTF-8 아님. 읽기 전용": "Not UTF-8. Read-only",
    "{0}  - 결과: {1}": "{0}  - Result: {1}",
    "이미 있는 파일: {0}": "File already exists: {0}",
    "{0} 못 읽음: {1}": "Cannot read {0}: {1}",
    "작업 폴더 없음: {0}": "Work folder not found: {0}",
    "실패({0}). 기록: {1}": "Failed ({0}). Log: {1}",
    "잠금 대기 시간 초과": "Timed out waiting for lock",
    "config.json 형식 오류: {0}": "config.json format error: {0}",
    "읽기 전용 파일: {0}": "Read-only file: {0}",
    "#{0} 항목 없음 (1~{1})": "No item #{0} (1-{1})",
    "'{0}' 항목 없음": "No item '{0}'",
    "'{0}' 항목이 {1}개. 번호로 지정: ": "{1} items match '{0}'. Use a number: ",
    "끝남. 기록: {0}": "Finished. Log: {0}",
    "종료 코드 {0}": "exit code {0}",
    "섹션 '{0}' 없음. 있는 섹션: {1}": "No section '{0}'. Sections: {1}",
    "섹션 '{0}' 없음": "No section '{0}'",
    "시간 초과": "timed out", "사용자가 멈춤": "stopped by user",
    # CLI 출력
    "위젯 실행함 (이미 떠 있으면 그대로)": "Widget started (no-op if already running)",
    "등록된 목록 없음": "No lists registered",
    "추가함: ": "Added: ", "고침: ": "Updated: ", "옮김: ": "Moved: ", "결과 남김: ": "Result saved: ",
    "질문 남김: ": "Question saved: ", "Claude에게 맡김: ": "Assigned to Claude: ", "맡김 해제: ": "Unassigned: ",
    "{0}(으)로 바꿈: ": "Set to {0}: ",
    "지움: #{0} {1}": "Deleted: #{0} {1}",
    "등록함: {0}": "Registered: {0}",
    "등록 해제함(파일은 그대로): {0}": "Unregistered (file kept): {0}",
    "바꿈: {0} (작업 폴더 {1})": "Updated: {0} (work folder {1})",
    "만듦: {0}": "Created: {0}",
    "files는 jua register / unregister / entry로 바꿈": "Change files with jua register / unregister / entry",
    "claude 명령 없음. Claude Code MCP 등록 건너뜀": "claude command not found. Skipped Claude Code MCP registration",
    "Claude 데스크톱 앱 설정 폴더 없음. 건너뜀": "Claude desktop app config folder not found. Skipped",
    "시작 프로그램 등록 실패": "Failed to add to Startup",
    "설치함: {0}\\jua.cmd, {1}\\jua": "Installed: {0}\\jua.cmd, {1}\\jua",
    "시작 프로그램 등록함: {0}": "Added to Startup: {0}",
    "Claude Code MCP 등록함": "Registered MCP server in Claude Code",
    "Claude Code MCP 등록 실패: {0}": "Claude Code MCP registration failed: {0}",
    "데스크톱 앱 MCP 등록함 (앱 다시 시작해야 반영): {0}":
        "Registered MCP server in Claude desktop app (restart the app to apply): {0}",
    "데스크톱 설정 형식 오류. 건너뜀: {0}": "Desktop config is malformed. Skipped: {0}",
    "상태는 {0} 중 하나": "Status must be one of {0}",
    "파일 없음: {0} (새로 만들려면 jua new)": "File not found: {0} (use jua new to create)",
    "주의: {0}가 PATH에 없음. PATH에 추가해야 jua 명령이 됨": "Note: {0} is not on PATH. Add it to use the jua command",
    "질문: {0}": "Question: {0}",
    "오류: {0}": "Error: {0}",
    "작업 폴더: {0}": "Work folder: {0}",
    "파일: {0}": "File: {0}",
    "이미 등록됨: {0}": "Already registered: {0}",
    "설정 '{0}' 없음": "No setting '{0}'",
    "{0}. {1}  남음 {2}/{3}, Claude 맡김 {4}, 검토 대기 {5}, 막힘 {6}":
        "{0}. {1}  open {2}/{3}, assigned to Claude {4}, review {5}, blocked {6}",
    # CLI 도움말
    "목록 이름·번호·경로 (생략하면 지금 폴더 목록, 없으면 첫 목록)":
        "list name, number or path (default: the list for the current folder, else the first list)",
    "jua-list: Claude와 같이 쓰는 todo 목록": "jua-list: a todo list you share with Claude",
    "등록된 목록과 개수": "registered lists and counts", "항목 보기": "show items",
    "Claude 맡긴 것만": "only items assigned to Claude", "모든 목록": "all lists", "항목 추가": "add an item",
    "Claude에게 맡김": "assign to Claude", "섹션 없으면 만듦": "create the section if missing",
    "대기로 되돌림": "mark as to do", "삭제": "Delete", "상태 바꿈": "set status", "내용 고침": "edit text",
    "옮김": "move", "다른 섹션 끝으로": "to the end of another section",
    "Claude에게 맡김(on)/해제(off)": "assign to Claude (on) / unassign (off)",
    "결과 한 줄 남김 (빈 문자열이면 지움)": "save a one-line result (empty string clears it)",
    "막힘으로 바꾸고 질문 남김": "mark blocked and leave a question",
    "새 목록 파일 만들고 등록": "create and register a new list file", "쉼표로 구분": "comma separated",
    "Claude 작업 폴더": "Claude's work folder", "기존 .md 등록": "register an existing .md",
    "목록 이름·작업 폴더 바꿈": "change a list's name or work folder",
    "설정 보기·바꿈 (예: jua config alpha 220)": "show or change settings (e.g. jua config alpha 220)",
    "jua 명령을 PATH에 설치": "install the jua command on PATH",
    "Claude Code·데스크톱 앱에 MCP 서버도 등록": "also register the MCP server in Claude Code and the desktop app",
    "로그인 시 위젯 자동 실행": "start the widget at sign-in", "위젯 실행": "start the widget",
    "데이터 폴더(설정·실행 기록) 위치": "data folder (settings, run logs)", "id, 번호, 글자 일부": "id, number or part of the text",
    "등록 해제": "unregister",
    # 위젯
    "할 일 추가 후 Enter  (앞에 @claude 붙이면 Claude에게 맡김)": "Add a task, press Enter  (start with @claude to assign it)",
    "창이 닫힘. 다시 띄움": "Window closed. Restarting",
    "끌어서 옮기기 · ◢ 끌어서 크기 조절": "Drag to move · drag ◢ to resize",
    "등록된 목록 없음. jua new <경로> 또는 ⋯ → 설정 파일 열기": "No lists. Run jua new <path> or ⋯ → Open settings",
    "할 일이 없음. 아래 칸에서 추가": "Nothing here. Add a task below",
    "+ 추가": "+ Add",
    "Claude가 작업 중. ⋯ 버튼 대신 ■로 멈출 수 있음": "Claude is working on this. Press ■ to stop it",
    "작업 중인 항목은 먼저 ■로 멈추세요": "Stop the running task with ■ first",
    "지움. ⋯ → 삭제 되돌리기": "Deleted. ⋯ → Undo delete",
    "완료된 항목. 먼저 체크를 푸세요": "This task is done. Uncheck it first",
    "상태 바꾸기": "Set status", "위로": "Move up", "아래로": "Move down", "섹션 옮기기": "Move to section",
    "수정": "Edit", "창 옮기기·크기 조절": "Move / resize window", "글자 크게": "Larger text", "글자 작게": "Smaller text",
    "Claude 실행 기록 폴더": "Claude run logs", "설정 파일 열기": "Open settings", "다시 읽기": "Reload", "종료": "Quit",
    "시작 계속 실패. 종료": "Failed to start repeatedly. Exiting",
    "바탕화면 창 못 찾음. bottom 모드로 대체": "Desktop window not found. Falling back to bottom mode",
    "Claude 맡김 해제": "Unassign from Claude", "@ Claude에게 맡기기": "@ Assign to Claude",
    "결과 줄 지우기": "Clear result line", "완료 항목 보이기": "Show done items", "완료 항목 숨기기": "Hide done items",
    "삭제 되돌리기": "Undo delete", "md 파일 열기": "Open .md file", "Claude 시작: {0}": "Claude started: {0}",
    "■ Claude 멈추기": "■ Stop Claude", "▶ Claude 실행": "▶ Run Claude",
    "Claude 작업 {0}개 진행 중. 위젯을 꺼도 작업은 계속되지만 상태 정리는 안 됨":
        "{0} Claude task(s) running. They keep running after you quit, but their status won't be updated",
    "● Claude 작업 {0}": "● Claude {0}",
}
