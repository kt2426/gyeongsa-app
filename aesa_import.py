"""애사 시트 데이터를 Supabase event 테이블에 임포트 (category='애사')"""
import pandas as pd
import re
from datetime import datetime
from supabase import create_client

# ---- 설정 ----
EXCEL = r'G:\김규태\1. 개인기록2022.xls'
SUPABASE_URL = "https://kpibajjiymxeahrisrls.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtwaWJhamppeW14ZWFocmlzcmxzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5NTc0MTQsImV4cCI6MjA5MzUzMzQxNH0.y_dHLE55er-nmDIKBB5SPX9j-15veHhuJh3PPdrtdoo"

PATTERNS = [
    ('배우자상', '배우자상'), ('자녀상', '자녀상'),
    ('형제상', '형제상'), ('조부상', '조부상'), ('조모상', '조모상'),
    ('본인상', '본인상'), ('본인사망', '본인상'),
    ('부친상', '부친상'), ('부치상', '부친상'),
    ('모친상', '모친상'), ('모치상', '모친상'),
    ('시부상', '시부상'), ('시모상', '시모상'),
    ('장인상', '장인상'), ('빙부상', '장인상'), ('빙장상', '장인상'),
    ('장모상', '장모상'), ('빙모상', '장모상'),
    ('부군상', '배우자상'), ('남편상', '배우자상'), ('부인상', '배우자상'),
    ('사모님', '배우자상'),
    ('형님상', '형제상'), ('누님상', '형제상'), ('누나상', '형제상'),
    ('매형상', '형제상'), ('누나 매형', '형제상'), ('누님 매형', '형제상'),
    ('형님본인사망', '형제상'),
    ('아버지', '부친상'), ('아버님', '부친상'),
    ('어머니', '모친상'), ('어머님', '모친상'),
    ('할머니', '조모상'), ('외할머니', '조모상'),
    ('할아버지', '조부상'), ('외할아버지', '조부상'),
    ('아주머니', '기타상'), ('아저씨', '기타상'),
    ('고모부', '기타상'), ('이모부', '기타상'), ('큰이모', '기타상'),
    ('작은이모', '기타상'), ('큰엄마', '기타상'), ('작은엄마', '기타상'),
    ('큰아버지', '기타상'), ('작은아버지', '기타상'), ('삼촌', '기타상'),
    ('여자친구', '기타상'), ('남자친구', '기타상'),
]

TITLES = ['이사', '부장', '지점장', '소장', '사장', '회장', '대표', '과장', '차장',
          '실장', '팀장', '본부장', '전무', '상무', '주임', '대리', '원장', '국장',
          '처장', '청장', '선배', '후배', '선생', '선생님']

SELF_RELATIVE_KEYWORDS = ['고모부', '이모부', '큰이모', '작은이모', '큰엄마', '작은엄마',
                          '큰아버지', '작은아버지', '삼촌', '여자친구', '남자친구']


def extract(item_str):
    if not isinstance(item_str, str):
        return None, None, '항목 없음'
    s = item_str.strip()
    matched_type, matched_keyword = None, None
    for keyword, normalized in PATTERNS:
        if keyword in s:
            matched_type = normalized
            matched_keyword = keyword
            break
    if not matched_type:
        return None, None, '종류추출실패'

    # 본인 친척 케이스 → 가족명="본인"
    if matched_keyword in SELF_RELATIVE_KEYWORDS and not s.split(matched_keyword)[0].strip():
        return '본인', matched_type, 'OK'

    name_part = s.split(matched_keyword)[0]
    name_clean = name_part
    for t in TITLES:
        name_clean = name_clean.replace(t, '')
    name_clean = name_clean.strip()
    name_clean = re.sub(r'(씨|님)$', '', name_clean).strip()
    name_clean = re.sub(r'\s+', ' ', name_clean).strip()
    name_clean = re.sub(r'\([^)]*\)', '', name_clean).strip()

    if not name_clean:
        # 이름이 없으면 본인 친척으로 간주
        return '본인', matched_type, 'OK'
    return name_clean, matched_type, 'OK'


def parse_date(d):
    if pd.isna(d):
        return None
    if isinstance(d, datetime):
        return d.strftime('%Y-%m-%d')
    s = str(d).strip().replace('.', '-')
    parts = s.split(' ')[0].split('-')
    if len(parts) == 3:
        try:
            y, m, dd = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{y:04d}-{m:02d}-{dd:02d}"
        except ValueError:
            return None
    return None


# ---- 데이터 로드 ----
df = pd.read_excel(EXCEL, sheet_name='애사', header=0)
df.columns = ['날짜', '항목', '장소', '금액', '기타']
df = df.dropna(subset=['항목'])
df = df[~df['항목'].astype(str).str.contains('합계', na=False)]
df = df[df['항목'].astype(str).str.strip() != '항목']
df = df.reset_index(drop=True)

# ---- 날짜 미상 행: 인접 행으로 추정 ----
parsed_dates = [parse_date(d) for d in df['날짜']]
for i in range(len(parsed_dates)):
    if parsed_dates[i] is None:
        # 앞쪽에서 가장 가까운 유효 날짜 찾기
        prev_d = next((parsed_dates[j] for j in range(i-1, -1, -1) if parsed_dates[j]), None)
        next_d = next((parsed_dates[j] for j in range(i+1, len(parsed_dates)) if parsed_dates[j]), None)
        parsed_dates[i] = prev_d or next_d

# ---- 임포트용 레코드 생성 ----
to_insert = []
skipped = []
for idx, row in df.iterrows():
    name, atype, status = extract(row['항목'])
    parsed = parsed_dates[idx]
    amount = row['금액']

    if status != 'OK' or not parsed or pd.isna(amount):
        skipped.append({
            'row': idx,
            '날짜': parsed,
            '원본': row['항목'],
            '금액': amount,
            '사유': status if status != 'OK' else ('날짜없음' if not parsed else '금액없음'),
        })
        continue

    place = row['장소'] if pd.notna(row['장소']) else None
    memo_orig = row['기타'] if pd.notna(row['기타']) else None
    memo_parts = []
    if memo_orig:
        memo_parts.append(str(memo_orig))
    memo_parts.append(f"[원본: {row['항목']}]")
    if parse_date(row['날짜']) is None:
        memo_parts.append("[날짜미상-인접행 추정]")
    if name == '본인':
        memo_parts.append(f"[본인의 {row['항목'].strip()}]")
    memo = ' / '.join(memo_parts) if memo_parts else None

    to_insert.append({
        '_name': name,
        'category': '애사',
        'event_date': parsed,
        'event_type': atype,
        'subject': str(row['항목']).strip(),
        'amount': int(amount),
        'place': str(place).strip() if place else None,
        'delivery_method': None,
        'proxy_name': None,
        'companions': None,
        'memo': memo,
    })

print(f"=== 임포트 대상 ===")
print(f"전체 데이터: {len(df)}건")
print(f"임포트 예정: {len(to_insert)}건")
print(f"스킵: {len(skipped)}건")
if skipped:
    print(f"\n스킵된 행:")
    for s in skipped:
        print(f"  row {s['row']}: {s['원본']} (사유: {s['사유']})")

# ---- DB 연결 ----
print(f"\n=== DB 연결 시도 ===")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)
print("OK")

# ---- person 캐시 (가족명 → person_id) ----
print(f"\n=== person 테이블 캐시 로드 ===")
existing_persons = sb.table("person").select("id, name").execute().data
person_cache = {p['name']: p['id'] for p in existing_persons}
print(f"기존 person 수: {len(person_cache)}")


def get_or_create_person(name):
    if name in person_cache:
        return person_cache[name]
    res = sb.table("person").insert({"name": name}).execute()
    pid = res.data[0]['id']
    person_cache[name] = pid
    return pid


# ---- 중복 방지: 이미 이 subject + event_date + amount가 있으면 스킵 ----
print(f"\n=== 기존 애사 데이터 조회 (중복 방지) ===")
existing = sb.table("event").select("event_date, subject, amount").eq("category", "애사").execute().data
existing_keys = set((e['event_date'], e['subject'], e['amount']) for e in existing)
print(f"기존 애사 건수: {len(existing)}")

# ---- 임포트 실행 ----
print(f"\n=== 임포트 시작 ===")
inserted = 0
duplicates = 0
errors = []

for i, rec in enumerate(to_insert, 1):
    key = (rec['event_date'], rec['subject'], rec['amount'])
    if key in existing_keys:
        duplicates += 1
        continue

    try:
        pid = get_or_create_person(rec['_name'])
        payload = {k: v for k, v in rec.items() if not k.startswith('_')}
        payload['person_id'] = pid
        sb.table("event").insert(payload).execute()
        inserted += 1
        if i % 50 == 0:
            print(f"  진행: {i}/{len(to_insert)}")
    except Exception as e:
        errors.append({'rec': rec, 'error': str(e)})

print(f"\n=== 임포트 완료 ===")
print(f"신규 입력: {inserted}건")
print(f"중복 스킵: {duplicates}건")
print(f"오류: {len(errors)}건")
if errors:
    for e in errors[:10]:
        print(f"  - {e['rec']['event_date']} {e['rec']['subject']}: {e['error']}")
