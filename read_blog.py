# 서울시 공식 블로그(haechiseoul) '즐겨봐요 문화관광' 새 글의 본문에서 날짜·장소·예약 줄을 뽑아 보여 줌
# 사용: python -I read_blog.py [글 수=30]  → 화면에 요약 출력 (Claude가 읽고 input.json 의 extra 에 갈 곳을 적음)
import html, re, sys, urllib.request
import xml.etree.ElementTree as E

UA = {'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36'}
KEY = re.compile(r'기간|일시|일정|날짜|장소|위치|주소|운영|시간|예약|예매|신청|요금|입장|관람|무료|휴관|문의|\d{1,2}\s*월\s*\d{1,2}\s*일|\d{1,2}\.\s?\d{1,2}\.')


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode('utf-8', 'replace')


def body(log_no):
    s = get('https://m.blog.naver.com/haechiseoul/%s' % log_no)
    m = re.search(r'<div class="se-main-container">(.*)', s, flags=re.S)
    s = m.group(1) if m else s
    s = re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S)
    s = re.sub(r'<(br|/p|/div|/li|/h\d)[^>]*>', '\n', s)
    s = html.unescape(re.sub(r'<[^>]+>', '', s)).replace('​', '')
    lines = [re.sub(r'\s+', ' ', l).strip() for l in s.split('\n')]
    out, seen = [], set()
    for l in lines:
        if len(l) < 4 or l in seen or l.startswith('#'):
            continue
        seen.add(l)
        out.append(l)
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    sys.stdout.reconfigure(encoding='utf-8')
    root = E.fromstring(get('https://rss.blog.naver.com/haechiseoul.xml'))
    items = [i for i in root.findall('.//item') if '문화관광' in (i.findtext('category') or '')][:n]
    for i in items:
        link = (i.findtext('guid') or i.findtext('link') or '').split('?')[0]
        log_no = link.rstrip('/').split('/')[-1]
        print('\n=== %s | %s\n    %s' % ((i.findtext('pubDate') or '')[:16], i.findtext('title'), link))
        try:
            lines = body(log_no)
        except Exception as e:
            print('    (본문 못 읽음: %s)' % e)
            continue
        picked = [l for l in lines if KEY.search(l) and len(l) <= 160][:int(sys.argv[2]) if len(sys.argv) > 2 else 14]
        for l in picked:
            print('    - ' + l)


if __name__ == '__main__':
    main()
