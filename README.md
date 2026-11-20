# jua_list

**사람과 Claude가 같이 쓰는 바탕화면 todo 위젯 (Windows)**

할 일은 평범한 Markdown 체크리스트(`- [ ]`)로 저장되고, 바탕화면에 붙은 위젯으로 보고 고칩니다.
Claude는 CLI·MCP로 같은 목록을 읽고 고치며, 항목에 `@claude`를 붙이고 ▶를 누르면 Claude Code가 그 일을 처리한 뒤 사람의 검토를 기다립니다.

[English below](#english)

```
## 웹사이트
- [x] 로그인 버그 고치기
- [?] @claude README 오타 고치기 <!-- id:3fa2c1 -->
  - 결과: README.md 오타 4곳 수정
- [ ] 배포 일정 정하기
```

## 기능

- **바탕화면 위젯**: 바탕화면 층에 붙어 `Win+D`에도 보임. 둥근 다크 UI, 여러 목록 탭, 섹션 접기, 진행 막대
- **바로 고치기**: 클릭으로 체크, 마우스를 올리면 ✎ 수정·✕ 삭제, 우클릭으로 상태·순서·섹션 이동, 삭제 되돌리기
- **Claude에게 일 맡기기**: `@claude` 태그 → ▶ 버튼 → 목록의 작업 폴더에서 `claude -p` 실행 → 결과 한 줄과 함께 **검토 대기** → 사람이 체크하면 완료
- **Claude가 직접 관리**: `jua` CLI와 MCP 서버(도구 12개)로 추가·삭제·수정·이동·새 목록·위젯 설정까지
- **안전한 저장**: 원자적 쓰기, `.bak` 백업, 프로세스 간 잠금, UTF-8이 아닌 파일은 읽기 전용
- **평범한 파일**: 데이터는 `.md` 그대로. 메모장·Obsidian·VS Code에서 같이 고쳐도 1초 안에 반영

상태 표시: `[ ]` 대기 · `[~]` 진행 중 · `[?]` 검토 대기 · `[!]` 막힘·질문 · `[x]` 완료

## 요구 사항

- Windows 10/11
- Python 3.10+ (tkinter 포함, python.org 설치본이면 기본 포함). 외부 패키지 없음
- Claude에게 일을 맡기려면 [Claude Code](https://claude.com/claude-code) CLI(`claude`)

## 설치

### Claude Code 플러그인으로 (스킬 + MCP)

```
/plugin marketplace add juan-hong/jua-list
/plugin install jua-list@jua-list
```

그다음 위젯과 `jua` 명령은 Claude에게 "jua_list 설치해줘"라고 하거나, 직접 실행합니다.

```powershell
python "$env:USERPROFILE\.claude\plugins\marketplaces\jua-list\jua\jua.py" install --startup
jua widget
```

### 저장소에서 직접

```powershell
git clone https://github.com/juan-hong/jua-list
cd jua-list
powershell -ExecutionPolicy Bypass -File jua\install.ps1
```

`install.ps1`이 하는 일: `jua` 명령을 `~\.local\bin`에 설치, Claude Code·Claude 데스크톱 앱에 MCP 서버 등록, 로그인 시 위젯 자동 실행 등록, 위젯 실행.
스킬만 따로 쓰려면 `skills\jua-list`를 `~\.claude\skills\`에 복사하세요.

처음 실행하면 `%APPDATA%\jua_list\todo.md` 예시 목록이 만들어집니다.

## 사용법

### 위젯

| 동작 | 방법 |
|---|---|
| 체크 / 검토 승인 | 항목 클릭 |
| 수정·삭제·Claude 맡김·실행 | 항목에 마우스 → ✎ ✕ @ ▶ |
| 상태·위아래·섹션 이동 | 항목 우클릭 |
| 추가 | 섹션 끝 `+ 추가`, 또는 아래 입력칸 (앞에 `@claude` 붙이면 맡김) |
| 섹션 접기 | 섹션 제목 클릭 |
| 창 옮기기·크기 | `⋯` → 창 옮기기·크기 조절 (이 모드에서만 움직임) |
| 완료 숨기기·글자 크기·실행 기록·종료 | `⋯` 메뉴 |

### CLI

```powershell
jua lists                                   # 목록들 요약
jua list --claude                           # Claude에게 맡긴 항목
jua add "할 일" -s 섹션 --claude             # 추가 (맡김)
jua done 3                                  # #3 완료
jua move "할 일" --to 다른섹션
jua new D:\proj\todo.md --sections "버그,기능" --cwd D:\proj   # 새 목록 + 작업 폴더
jua config alpha 220                        # 위젯 투명도
jua --help
```

`<ref>`는 항목 id, `jua list`의 번호, 또는 글자 일부입니다.

### Claude에게 맡기기

1. 항목에 `@claude`를 붙입니다. 목록마다 작업 폴더(`--cwd`)를 정해 두세요.
2. ▶를 누르면 그 폴더에서 `claude -p`가 실행됩니다. 기록은 `%APPDATA%\jua_list\runs\`에 남습니다.
3. 끝나면 `[?]` 검토 대기와 결과 한 줄이 보입니다. 확인하고 체크하면 완료입니다. Claude가 질문을 남기면 `[!]`로 표시됩니다.

기본 제한(`jua config claude`로 바꿈): 최대 40턴, 30분, 파일 수정 자동 허용, `git commit/push/reset/checkout`·`rm -rf`·WebFetch 금지.

> ⚠ ▶ 실행은 Claude Code가 작업 폴더에서 파일을 고치고 명령을 실행하게 합니다. 믿을 수 있는 목록과 폴더에서만 쓰고, 결과는 직접 검토하세요. 다른 프로그램이 목록 파일에 쓴 내용도 Claude 지시가 될 수 있습니다.

## 설정

`%APPDATA%\jua_list\config.json` (`jua home`으로 위치 확인, 환경 변수 `JUA_HOME`으로 변경)

| 키 | 뜻 |
|---|---|
| `files` | 목록: 경로 문자열 또는 `{"path", "name", "cwd"}` |
| `x` `y` `w` `h` | 창 위치·크기 (물리 픽셀) |
| `pin` | `desktop`(바탕화면 층) / `bottom`(맨 아래 일반 창) |
| `alpha` `font_size` `hide_done` | 투명도 0~255, 글자 크기 8~16, 완료 숨기기 |
| `claude.max_turns` `claude.timeout_min` `claude.model` | ▶ 실행 제한 |
| `claude.allowed_tools` `claude.disallowed_tools` | ▶ 실행 도구 허용·금지 목록 |

## 개발

```powershell
python -m unittest discover -s tests
```

구조: `jua/jua_core.py`(파일·설정·실행 핵심) · `jua/jua.py`(CLI) · `jua/jua_mcp.py`(MCP, 외부 패키지 없음) · `jua/widget.py`(tkinter 위젯) · `skills/jua-list`(Claude 스킬) · `.claude-plugin`(플러그인·마켓플레이스)

## 라이선스

MIT

---

## English

**A Windows desktop todo widget you share with Claude.**

Tasks live in plain Markdown checklists. The widget sits on the desktop layer (visible even after `Win+D`). Claude reads and edits the same lists through a CLI and an MCP server. Tag a task `@claude`, press ▶, and Claude Code works on it in that list's working folder, leaves a one-line result, and marks it **review**. You check it off when you're happy.

- Requirements: Windows 10/11, Python 3.10+ with tkinter (no third-party packages), Claude Code CLI for ▶.
- Install as a plugin: `/plugin marketplace add juan-hong/jua-list` then `/plugin install jua-list@jua-list`, then run `python <plugin>/jua/jua.py install --startup` and `jua widget`.
- Or clone and run `jua\install.ps1`.
- Statuses: `[ ]` todo · `[~]` doing · `[?]` review · `[!]` blocked/question · `[x]` done.
- Data and settings: `%APPDATA%\jua_list` (override with `JUA_HOME`).
- UI and messages are in Korean for now. PRs welcome.

> ⚠ ▶ lets Claude Code edit files and run commands in the list's working folder. Use it only with lists and folders you trust, and review the result.
