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
            page = 'https://popga.co.kr/popup/%d' % pid
            notice = re.sub(r'\s+', '', html.unescape(s.replace('\\"', '"')))
            rlink = link.group(1) if link else ''
            if re.search('사전예약없이|예약없이|예약불필요', flat) or re.search('별도의사전예약없이|예약없이자유롭게', notice):
                reserve, rlink = '예약 없이 입장', ''
            elif re.search('예약필수|사전예약필수|예약제|사전예약자에한|예약자에한해', flat):
                reserve = '예약 필수'
            elif rlink:
                reserve = '사전예약 있음 · 확인'
            elif re.search('팝가단독예약|"isPopgaReservation":true', notice):
                reserve, rlink = '사전예약 있음 · 팝가에서 예약', page
            elif re.search('사전예약|네이버예약|예약', flat):
                reserve, rlink = '예약 안내 있음 · 확인', page  # 예약 주소가 따로 없으면 안내가 실린 팝가 화면으로
            else:
                reserve = '예약 안내 없음 · 현장 방문'
            return {
                'reserve': reserve, 'reserveLink': rlink,
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
    extras = []
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
        kw = it.pop('yeyak', '')
        if kw:
            found = [r for r in yeyak_all() if kw.replace(' ', '') in html.unescape(r.get('SVCNM') or '').replace(' ', '')]
            found.sort(key=lambda r: (r.get('SVCSTATNM') != '접수중', r.get('SVCOPNBGNDT') or ''))
            links = []
            for r in found[:4]:
                name = re.sub(r'\s+', ' ', html.unescape(r.get('SVCNM') or '')).strip()
                short = name.split(']')[-1].strip() or name
                links.append({'label': '%s · %s' % (r.get('SVCSTATNM') or '', short[:24]), 'url': r.get('SVCURL') or ''})
            if links:
                it['reserveLinks'] = links
                it['reserveLink'] = links[0]['url']
                if all(r.get('SVCSTATNM') != '접수중' for r in found):
                    it['reserve'] = '예약 필수 · 지금은 마감(취소분만)'
            else:
                problems.append('공공예약에서 못 찾음: %s (%s)' % (it['title'], kw))
        if it.pop('ongoing', False) and not it.get('end'):
            # 끝나는 날이 정해지지 않은 상시 운영 — 갱신할 때마다 30일 뒤까지로 둠
            it['end'] = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        extras.append(it)
    # 팝가 순위 둘에 직접 고른 것(전시·서울시 블로그) 하나씩 섞어 한쪽으로 쏠리지 않게
    popga_items, items = items, []
    while popga_items or extras:
        items += popga_items[:2]
        popga_items = popga_items[2:]
        if extras:
            items.append(extras.pop(0))

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
            'rank', 'type', 'title', 'place', 'addr', 'region', 'lat', 'lon', 'start', 'end', 'why', 'reserve', 'reserveLink', 'reserveLinks', 'image', 'source', 'sourceName')})

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





# ───────── 서울시 공공서비스예약(yeyak.seoul.go.kr) — 지금 예약되는 문화체험·교육 프로그램 ─────────
# 서울 열린데이터광장 공식 API를 씀 (예약 사이트 목록 화면은 robots.txt 로 수집을 막아 둠).
# 인증키: 환경변수 SEOUL_KEY 또는 이 폴더의 .seoul_key (git 에 올리지 않음). 없으면 견본 키라 서비스마다 5건만 나옴.
SEOUL_SERVICES = ['ListPublicReservationCulture', 'ListPublicReservationEducation']
GYEONGGI = ('고양시', '과천시', '남양주시', '하남시', '포천시', '양평군', '광주시', '구리시', '성남시', '의정부시')


def seoul_key():
    k = os.environ.get('SEOUL_KEY', '').strip()
    f = os.path.join(HERE, '.seoul_key')
    if not k and os.path.exists(f):
        k = open(f, encoding='utf-8-sig').read().strip()
    return k or 'sample'


def yeyak_rows(service, key):
    rows, start, step = [], 1, (5 if key == 'sample' else 1000)
    while True:
        u = 'http://openapi.seoul.go.kr:8088/%s/json/%s/%d/%d/' % (key, service, start, start + step - 1)
        d = json.loads(get(u))
        body = d.get(service)
        if not body:
            raise RuntimeError('%s: %s' % (service, json.dumps(d, ensure_ascii=False)[:200]))
        got = body.get('row') or []
        rows += got
        total = int(body.get('list_total_count') or 0)
        if key == 'sample' or not got or start + step > total:
            return rows, total
        start += step


_YEYAK_ALL = None


def yeyak_all():
    # 서울시 공공예약 전체 행 (한 번만 받아 둠) — 직접 고른 항목의 예약 주소를 찾는 데도 씀
    global _YEYAK_ALL
    if _YEYAK_ALL is None:
        _YEYAK_ALL = []
        key = seoul_key()
        for service in SEOUL_SERVICES:
            try:
                _YEYAK_ALL += yeyak_rows(service, key)[0]
            except Exception:
                pass
    return _YEYAK_ALL


def build_yeyak():
    key = seoul_key()
    today = datetime.date.today()
    horizon = (today + datetime.timedelta(days=30)).isoformat()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    out, seen, notes = [], set(), []
    for service in SEOUL_SERVICES:
        try:
            rows, total = yeyak_rows(service, key)
        except Exception as e:
            notes.append('%s 실패: %s' % (service, e))
            continue
        notes.append('%s: 전체 %d건 중 %d건 받음' % (service, total, len(rows)))
        for r in rows:
            use_s, use_e = (r.get('SVCOPNBGNDT') or '')[:10], (r.get('SVCOPNENDDT') or '')[:10]
            rc_s, rc_e = (r.get('RCPTBGNDT') or '')[:16], (r.get('RCPTENDDT') or '')[:16]
            if not use_s or not use_e or use_e < today.isoformat() or use_s > horizon:
                continue
            if r.get('SVCSTATNM') not in ('접수중', '안내중') or (rc_e and rc_e < now):
                continue  # 접수가 끝났거나 일시정지된 것은 뺌
            area = (r.get('AREANM') or '').strip()
            region = '서울' if area.endswith('구') else ('경기' if area in GYEONGGI else '')
            if not region or r.get('MINCLASSNM') in ('서울형키즈카페', '단체봉사'):
                continue
            try:
                lat, lon = float(r.get('Y') or 0), float(r.get('X') or 0)
            except ValueError:
                lat = lon = 0.0
            if not (33 < lat < 39 and 124 < lon < 132):
                continue
            title = re.sub(r'\s+', ' ', html.unescape(html.unescape(r.get('SVCNM') or ''))).strip()
            place = html.unescape(r.get('PLACENM') or '').strip()
            k = (re.sub(r'\d+', '#', title), place)  # 회차·달만 다른 같은 프로그램은 가장 이른 것 하나만
            if k in seen:
                continue
            seen.add(k)
            out.append({
                'id': r.get('SVCID'), 'title': title, 'big': r.get('MAXCLASSNM') or '',
                'cat': r.get('MINCLASSNM') or '', 'status': r.get('SVCSTATNM') or '',
                'pay': (r.get('PAYATNM') or '').strip(), 'place': place, 'area': area, 'region': region,
                'target': (r.get('USETGTINFO') or '').strip(), 'url': r.get('SVCURL') or '',
                'lat': lat, 'lon': lon, 'start': use_s, 'end': use_e, 'rcptStart': rc_s, 'rcptEnd': rc_e,
                'image': r.get('IMGURL') or '',
            })
    out.sort(key=lambda o: (o['rcptEnd'] or '9999', o['start']))
    doc = {'updated': today.isoformat(), 'source': '서울 열린데이터광장 · 서울시 공공서비스예약',
           'sample': key == 'sample', 'items': out}
    with open(os.path.join(HERE, 'yeyak.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    print('yeyak.json: %d건%s' % (len(out), ' (견본 키 — 인증키를 넣으면 전체가 나옴)' if key == 'sample' else ''))
    for n in notes:
        print(' - ' + n)


if __name__ == '__main__':
    main()
    build_yeyak()
