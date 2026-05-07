"""DB에 임포트된 결과 검증"""
from supabase import create_client

SUPABASE_URL = "https://kpibajjiymxeahrisrls.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtwaWJhamppeW14ZWFocmlzcmxzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5NTc0MTQsImV4cCI6MjA5MzUzMzQxNH0.y_dHLE55er-nmDIKBB5SPX9j-15veHhuJh3PPdrtdoo"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# 페이지네이션으로 전체 가져오기
def fetch_all(category):
    all_data = []
    offset = 0
    page = 1000
    while True:
        res = sb.table("event").select("amount, event_date, event_type").eq("category", category).range(offset, offset + page - 1).execute()
        if not res.data:
            break
        all_data.extend(res.data)
        if len(res.data) < page:
            break
        offset += page
    return all_data

aesa = fetch_all("애사")
kyungsa = fetch_all("경사")

print(f"=== 임포트 검증 ===")
print(f"애사: {len(aesa)}건, 합계 {sum(e['amount'] for e in aesa):,}원")
print(f"경사: {len(kyungsa)}건, 합계 {sum(e['amount'] for e in kyungsa):,}원")
print()

# 연도별 분포
from collections import defaultdict
yearly_aesa = defaultdict(lambda: {'count': 0, 'sum': 0})
for e in aesa:
    y = e['event_date'][:4]
    yearly_aesa[y]['count'] += 1
    yearly_aesa[y]['sum'] += e['amount']

print(f"=== 애사 연도별 분포 (임포트된 데이터) ===")
for y in sorted(yearly_aesa.keys()):
    d = yearly_aesa[y]
    print(f"  {y}년: {d['count']:3d}건, {d['sum']:>12,}원")

# 행사 종류별
type_dist = defaultdict(int)
for e in aesa:
    type_dist[e['event_type']] += 1
print(f"\n=== 애사 종류별 분포 ===")
for t, c in sorted(type_dist.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c}건")
