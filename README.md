# travel-picks

여행 찾기 앱이 읽는 '요즘 핫한 팝업·전시' 목록. 서울·경기 행사 이름·기간·장소·출처만 담음 (개인정보 없음).

- `picks.json` — 앱이 읽는 목록 (Claude가 주 2회 웹을 훑어 고름)
- `input.json` — 고른 항목과 이유
- `make_picks.py` — input.json → picks.json (팝가 상세에서 장소·좌표·기간을 읽고, 전시는 장소 이름으로 좌표를 찾음)
