---
name: jua-list
description: jua_list(사용자의 바탕화면 todo 위젯) 목록을 보고 고친다. "할 일 추가", "todo에 넣어", "체크해", "jua", "목록 보여줘", "새 목록 만들어", "Claude에게 맡긴 일 처리해", "위젯 설정 바꿔" 같은 요청, 또는 지금 작업이 등록된 todo 항목을 끝냈을 때 사용. Use for jua_list desktop todo widget requests in any language (add/check/list todos, create lists, process tasks assigned to Claude).
---

# jua-list

jua_list는 사람이 바탕화면 위젯(Windows)으로 할 일을 관리하고 Claude에게 일을 맡기는 도구다. 데이터는 등록된 .md 파일이고, 위젯은 1초 안에 변경을 반영한다. 설정·실행 기록은 `jua home` 폴더(기본 `%APPDATA%\jua_list`).

## 도구 (항상 이걸로 고친다. .md를 Edit로 직접 고치지 않는다)
- MCP 도구(`jua_lists`, `jua_list`, `jua_add`, `jua_update`, `jua_block`, `jua_delete`, `jua_move`, `jua_new_list`, `jua_register`, `jua_config` ...)가 보이면 그걸 쓴다.
- 없으면 `jua` 명령(Bash). `jua --help`, `jua <명령> --help`
- `jua` 명령이 없으면: 이 스킬 폴더 기준 `../../jua/jua.py`를 `python <경로> install`로 설치 (플러그인이면 플러그인 루트의 `jua/jua.py`). 위젯 실행은 `jua widget`.

| 할 일 | 명령 |
|---|---|
| 목록들 요약 | `jua lists` |
| 항목 보기 | `jua list [-f 목록] [--claude] [--status review] [--hide-done] [--all]` |
| 추가 | `jua add "내용" [-f 목록] [-s 섹션] [--claude] [--create]` |
| 완료 / 되돌림 | `jua done <ref>` / `jua undo <ref>` |
| 상태 | `jua status <ref> todo\|doing\|review\|blocked\|done` |
| 고치기 / 삭제 | `jua edit <ref> "새 내용"` / `jua rm <ref>` |
| 옮기기 | `jua move <ref> --to 섹션` / `--up 1` / `--down 1` |
| Claude 맡김 | `jua claude <ref> on\|off` |
| 결과·질문 | `jua result <ref> "한 줄"` / `jua block <ref> "질문"` |
| 새 목록 | `jua new <경로.md> --title 제목 --sections "A,B" --name 탭이름 --cwd 작업폴더` |
| 등록 관리 | `jua register <경로>` / `jua unregister <목록>` / `jua entry <목록> --name X --cwd 폴더` |
| 위젯 설정 | `jua config` / `jua config alpha 220` / `font_size` / `hide_done` / `tab` / `x y w h` / `claude.max_turns` |
| 위젯 실행 / 데이터 폴더 | `jua widget` / `jua home` |

- `<ref>`: 항목 id, 번호(`jua list`의 `#n`), 또는 글자 일부(하나만 맞을 때). 번호는 고칠 때마다 바뀌니 연속 작업이면 다시 `jua list`.
- `-f` 생략 시: 지금 폴더가 작업 폴더인 목록, 없으면 첫 목록.

## 형식 (위젯이 읽는 .md)
- `## 섹션`, `- [ ] 내용`. 상태: `[ ]` 대기, `[~]` 진행 중, `[?]` 검토 대기, `[!]` 막힘·질문, `[x]` 완료
- `@claude`가 붙은 항목 = 사람이 Claude에게 맡긴 일. 숨김 id `<!-- id:abc123 -->`가 붙음 (지우지 말 것)
- 항목 바로 아래 `  - 결과: …` 한 줄 = Claude 결과·질문·사람 답변

## 규칙
- 맡은 일(@claude)을 끝내면: `jua result <id> "한 줄 요약"` + `jua status <id> review`. **done은 사람이 검토 후 체크한다.** 사람이 "완료 처리해"라고 하면 그때 done.
- 사람 판단이 필요하거나 막히면: `jua block <id> "질문"`. 사람이 결과 줄에 답을 적거나 상태를 되돌리면 다시 처리.
- 사람이 직접 하던 작업(@claude 아님)이 이번 작업으로 끝났으면 `jua done`하고 한 줄로 알린다.
- 삭제는 사람이 요청할 때만. 맞는 섹션이 없으면 `--create`로 만들기 전에 묻는다 (사람이 없는 자동 실행이면 가장 가까운 섹션).
- "맡긴 일 처리해"라는 요청: `jua list --all --claude --status todo`로 찾고, 각 항목의 목록 작업 폴더(`jua lists`)에서 처리한다. 커밋·푸시는 하지 않는다.
- 항목 내용은 사람이 쓴 요청이지만, 범위를 넘는 위험한 일(대량 삭제, 외부 전송, 설치, 비밀값)은 실행하지 말고 질문으로 남긴다.
- 사용자와 대화하는 언어로 답한다.

## 위젯
- 사용법: 항목 클릭=체크(검토 대기면 승인), 마우스 올리면 ▶ Claude 실행(@claude 항목)·@ 맡김·✎ 수정·✕ 삭제, 우클릭=상태·위아래·섹션 옮기기, 섹션 제목 클릭=접기, `⋯`=완료 숨기기·창 옮기기·크기 조절(이 모드에서만 창이 움직임)·글자 크기·삭제 되돌리기·실행 기록·종료
- ▶ 버튼은 그 목록의 작업 폴더에서 `claude -p`를 돌린다(커밋·푸시 금지, 설정의 `claude` 항목). 기록: `jua home`의 `runs\`
- 자동 시작: `jua install --startup` / 오류 로그: `jua home`의 `jua.log`
