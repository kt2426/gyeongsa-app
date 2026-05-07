"""애사 시트 587건을 분석해서 자동 추출 결과를 미리 확인 (DB에 안 넣음)"""
import pandas as pd
import re
from datetime import datetime

EXCEL = r'G:\김규태\1. 개인기록2022.xls'

# 애사 종류 패턴 (긴 것부터 매칭)
AESA_TYPES = [
    '배우자상', '자녀상', '형제상', '조부상', '조모상', '본인상',
    '부친상', '모친상', '시부상', '시모상', '장인상', '장모상', '기타상'
]

def extract(item_str):
    """항목명에서 가족 대표명 + 애사 종류 추출"""
    if not isinstance(item_str, str):
        return None, None, '항목 없음'
    s = item_str.strip()

    # 패턴 → (정규화된 종류, 매칭 키워드)
    PATTERNS = [
        # 직접 매칭
        ('배우자상', '배우자상'), ('자녀상', '자녀상'),
        ('형제상', '형제상'), ('조부상', '조부상'), ('조모상', '조모상'),
        ('본인상', '본인상'), ('본인사망', '본인상'),
        ('부친상', '부친상'), ('부치상', '부친상'),  # 오타
        ('모친상', '모친상'), ('모치상', '모친상'),
        ('시부상', '시부상'), ('시모상', '시모상'),
        ('장인상', '장인상'), ('빙부상', '장인상'), ('빙장상', '장인상'),
        ('장모상', '장모상'), ('빙모상', '장모상'),
        # 배우자
        ('부군상', '배우자상'), ('남편상', '배우자상'), ('부인상', '배우자상'),
        ('사모님', '배우자상'),
        # 형제·자매
        ('형님상', '형제상'), ('누님상', '형제상'), ('누나상', '형제상'),
        ('매형상', '형제상'), ('누나 매형', '형제상'), ('누님 매형', '형제상'),
        ('형님본인사망', '형제상'),
        # 친척 → 기타상
        ('고모부', '기타상'), ('이모부', '기타상'), ('큰이모', '기타상'),
        ('작은이모', '기타상'), ('큰엄마', '기타상'), ('작은엄마', '기타상'),
        ('큰아버지', '기타상'), ('작은아버지', '기타상'), ('삼촌', '기타상'),
        ('여자친구', '기타상'), ('남자친구', '기타상'),
        # 부모 (관련어)
        ('아버지', '부친상'), ('아버님', '부친상'),
        ('어머니', '모친상'), ('어머님', '모친상'),
        # 조부모
        ('할머니', '조모상'), ('외할머니', '조모상'),
        ('할아버지', '조부상'), ('외할아버지', '조부상'),
        # 기타: '아주머니', '여자친구' 등은 기타상
        ('아주머니', '기타상'), ('아저씨', '기타상'),
    ]

    matched_type = None
    matched_keyword = None
    for keyword, normalized in PATTERNS:
        if keyword in s:
            matched_type = normalized
            matched_keyword = keyword
            break

    if not matched_type:
        return None, None, '종류추출실패'

    # 가족 대표명 추출: 매칭된 키워드 앞부분에서
    name_part = s.split(matched_keyword)[0]
    # "이사", "부장", "지점장", "소장", "사장", "회장" 같은 직책 제거
    titles = ['이사', '부장', '지점장', '소장', '사장', '회장', '대표', '과장', '차장', '실장', '팀장', '본부장', '전무', '상무', '주임', '대리', '원장', '국장', '처장', '청장']
    name_clean = name_part
    for t in titles:
        name_clean = name_clean.replace(t, '')
    name_clean = name_clean.strip()
    # "○○씨", "○○님" 제거
    name_clean = re.sub(r'(씨|님)$', '', name_clean).strip()
    # 공백 정리
    name_clean = re.sub(r'\s+', ' ', name_clean).strip()

    if not name_clean:
        return None, matched_type, '이름추출실패'

    # 한글만 (괄호 안 영문/숫자 등 제거)
    name_clean = re.sub(r'\([^)]*\)', '', name_clean).strip()

    return name_clean, matched_type, 'OK'


def parse_date(d):
    if pd.isna(d):
        return None
    if isinstance(d, datetime):
        return d.date()
    s = str(d).strip()
    # "2005.12.29", "2006.01.9", "2006-01-12 00:00:00"
    s = s.replace('.', '-')
    parts = s.split(' ')[0].split('-')
    if len(parts) == 3:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{y:04d}-{m:02d}-{d:02d}"
        except ValueError:
            return None
    return None


# 데이터 로드
df = pd.read_excel(EXCEL, sheet_name='애사', header=0)
df.columns = ['날짜', '항목', '장소', '금액', '기타']

# 빈 행 / 합계 행 / 헤더 행 제거
df = df.dropna(subset=['항목'])
df = df[~df['항목'].astype(str).str.contains('합계', na=False)]
df = df[df['항목'].astype(str).str.strip() != '항목']

# 분석
ok = []
fail = []
for idx, row in df.iterrows():
    name, atype, status = extract(row['항목'])
    parsed_date = parse_date(row['날짜'])
    amount = row['금액']
    place = row['장소'] if pd.notna(row['장소']) else None
    memo = row['기타'] if pd.notna(row['기타']) else None

    record = {
        'row': idx,
        '날짜': parsed_date,
        '원본항목': row['항목'],
        '추출가족명': name,
        '추출종류': atype,
        '금액': amount,
        '장소': place,
        '메모': memo,
        '상태': status,
    }
    if status == 'OK' and parsed_date and pd.notna(amount):
        ok.append(record)
    else:
        fail.append(record)

print(f"=== 분석 결과 ===")
print(f"전체: {len(df)}건")
print(f"성공: {len(ok)}건")
print(f"실패: {len(fail)}건")
print()
print("=== 성공 샘플 (앞 15건) ===")
for r in ok[:15]:
    print(f"  {r['날짜']} | {r['원본항목'][:25]:25s} → {r['추출가족명']:8s} / {r['추출종류']:6s} / {int(r['금액']):,}원")
print()
print(f"=== 성공 샘플 (뒤 5건) ===")
for r in ok[-5:]:
    print(f"  {r['날짜']} | {r['원본항목'][:25]:25s} → {r['추출가족명']:8s} / {r['추출종류']:6s} / {int(r['금액']):,}원")
print()
print(f"=== 실패 건 ({len(fail)}건) ===")
for r in fail[:30]:
    print(f"  row {r['row']:3d} | 날짜:{r['날짜']} | {r['원본항목']!s:30s} | 금액:{r['금액']} | 사유:{r['상태']}")
if len(fail) > 30:
    print(f"  ... 외 {len(fail)-30}건")
