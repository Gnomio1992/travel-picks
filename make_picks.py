# 여행 찾기 앱의 '요즘 핫한 팝업·전시' 목록(picks.json) 만들기
# 사용: python -I make_picks.py   (input.json → picks.json)
#  - input.json 의 popga: 팝가(popga.co.kr) 팝업 번호와 고른 이유 → 상세 페이지에서 장소·좌표·기간·사진을 읽음
#  - input.json 의 extra: 전시 등 직접 적은 항목 (lat/lon 이 없으면 place 로 카카오 검색해 채움)
#  - 카카오 키는 비공개 저장소 사본(C:\Users\fpsxm\travel_finder\lib\keys.dart)에서 읽음 — 이 저장소에는 키를 두지 않음
import datetime, html, json, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 Safari/537.36'}
KEYS = r'C:\Users\fpsxm\travel_finder\lib\keys.dart'


def get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')


def popga(pid):
    s = get('https://popga.co.kr/popup/%d' % pid)
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, flags=re.S):
        try:
            d = json.loads(block)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get('@type') == 'Event':
            loc = d.get('location') or {}
            geo = loc.get('geo') or {}
            img = d.get('image') or []
            if isinstance(img, str):
                img = [img]
            link = re.search(r'preReservationLink\\?":\\?"(https?://[^"\\]+)', s)
            kw = re.search(r'<meta[^>]+name="keywords"[^>]+content="([^"]*)"', s)
            text = (d.get('description') or '') + ' ' + (html.unescape(kw.group(1)) if kw else '')
            flat = text.replace(' ', '')
            if re.search('예약필수|사전예약필수|예약제|사전예약자에한|예약자에한해', flat):
                reserve = '예약 필수'
            elif link:
                reserve = '사전예약 있음 · 확인'
            elif re.search('사전예약|네이버예약|예약', flat):
                reserve = '예약 안내 있음 · 확인'
            else:
                reserve = '예약 안내 없음 · 현장 방문'
            return {
                'reserve': reserve, 'reserveLink': link.group(1) if link else '',
                'title': d.get('name', '').strip(),
                'place': (loc.get('name') or '').strip(),
                'addr': ((loc.get('address') or {}).get('streetAddress') or '').strip(),
                'lat': geo.get('latitude'), 'lon': geo.get('longitude'),
                'start': d.get('startDate', ''), 'end': d.get('endDate', ''),
                'image': img[0] if img else '',
                'source': 'https://popga.co.kr/popup/%d' % pid, 'sourceName': '팝가',
            }
    raise RuntimeError('팝가 %d: 행사 정보를 찾지 못함' % pid)


def kakao_key():
    src = open(KEYS, encoding='utf-8').read()
    return re.search(r"_buildKakao = '([^']+)'", src).group(1)


def geocode(query, key):
    u = 'https://dapi.kakao.com/v2/local/search/keyword.json?' + urllib.parse.urlencode({'query': query, 'size': 1})
    docs = json.loads(get(u, {'Authorization': 'KakaoAK ' + key})).get('documents') or []
    if not docs:
        return None
    d = docs[0]
    return float(d['y']), float(d['x']), d.get('road_address_name') or d.get('address_name') or ''


def main():
    inp = json.load(open(os.path.join(HERE, 'input.json'), encoding='utf-8'))
    today = datetime.date.today().isoformat()
    items, problems = [], []
    for row in inp.get('popga', []):
        try:
            it = popga(int(row['id']))
        except Exception as e:  # 한 건 실패해도 나머지는 만든다
            problems.append('팝가 %s: %s' % (row.get('id'), e))
            continue
        it.update(type=row.get('type', '팝업'), why=row.get('why', ''))
        if row.get('reserve'):  # 직접 확인해 적은 값이 우선
            it['reserve'] = row['reserve']
        items.append(it)
    key = None
    for row in inp.get('extra', []):
        it = dict(row)
        if it.get('lat') is None or it.get('lon') is None:
            key = key or kakao_key()
            g = geocode(it.get('geocode') or it['place'], key)
            if not g:
                problems.append('좌표 못 찾음: %s' % it['title'])
                continue
            it['lat'], it['lon'] = g[0], g[1]
            it.setdefault('addr', g[2])
        it.pop('geocode', None)
        items.append(it)

    out = []
    for it in items:
        addr = it.get('addr', '')
        region = '서울' if addr.startswith('서울') else '경기' if addr.startswith('경기') else ''
        if not region:
            problems.append('서울·경기 밖이라 뺌: %s (%s)' % (it['title'], addr))
            continue
        if not it.get('start'):
            it['start'] = today  # 시작일을 모르는 진행 중 행사
        if not it.get('start') or not it.get('end'):
            problems.append('기간 없음이라 뺌: %s' % it['title'])
            continue
        if it['end'] < today:
            problems.append('이미 끝나서 뺌: %s (~%s)' % (it['title'], it['end']))
            continue
        it['region'] = region
        it['rank'] = len(out) + 1
        out.append({k: it.get(k, '') for k in (
            'rank', 'type', 'title', 'place', 'addr', 'region', 'lat', 'lon', 'start', 'end', 'why', 'reserve', 'reserveLink', 'image', 'source', 'sourceName')})

    doc = {'updated': today, 'by': 'Claude가 웹을 훑어 고름', 'items': out}
    with open(os.path.join(HERE, 'picks.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')
    sys.stdout.reconfigure(encoding='utf-8')
    print('picks.json: %d건 (기준일 %s)' % (len(out), today))
    for o in out:
        print(' %2d %s | %s | %s ~ %s | %s | %s' % (o['rank'], o['type'], o['title'], o['start'], o['end'], o['place'], o['reserve'] or '예약 확인 필요'))
    for p in problems:
        print(' ! ' + p)


if __name__ == '__main__':
    main()
