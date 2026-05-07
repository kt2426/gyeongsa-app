"""'성기누나' → '김성기누나' 이름 변경"""
from supabase import create_client

SUPABASE_URL = "https://kpibajjiymxeahrisrls.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtwaWJhamppeW14ZWFocmlzcmxzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5NTc0MTQsImV4cCI6MjA5MzUzMzQxNH0.y_dHLE55er-nmDIKBB5SPX9j-15veHhuJh3PPdrtdoo"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

OLD = "성기누나"
NEW = "김성기누나"

# 1) 기존 상태 확인
old_p = sb.table("person").select("*").eq("name", OLD).execute().data
new_p = sb.table("person").select("*").eq("name", NEW).execute().data
print(f"'{OLD}': {len(old_p)}건 / '{NEW}': {len(new_p)}건")
for p in old_p:
    print(f"  → {OLD}: id={p['id']}, relation={p.get('relation')}")

if not old_p:
    print("'성기누나' 행이 없습니다. 종료.")
    raise SystemExit

old_id = old_p[0]['id']

# 2) 새 이름이 이미 있는지에 따라 분기
if new_p:
    # 김성기누나가 이미 있다면 합치기
    new_id = new_p[0]['id']
    print(f"'{NEW}' 이미 존재 (id={new_id}). 합치기 진행")
    events = sb.table("event").select("id, subject").eq("person_id", old_id).execute().data
    for e in events:
        sub = e['subject'] or ""
        if sub.startswith(OLD):
            sub = NEW + sub[len(OLD):]
        sb.table("event").update({"person_id": new_id, "subject": sub}).eq("id", e['id']).execute()
        print(f"  event {e['id']}: '{e['subject']}' → '{sub}', person {old_id}→{new_id}")
    sb.table("person").delete().eq("id", old_id).execute()
    print(f"person id={old_id} 삭제")
else:
    # 단순 rename (person.name 변경 + 관련 event subject도 변경)
    print(f"'{NEW}' 신규 → 단순 rename")
    sb.table("person").update({"name": NEW}).eq("id", old_id).execute()
    print(f"  person id={old_id} 이름 '{OLD}' → '{NEW}'")
    # 관련 event들의 subject 업데이트
    events = sb.table("event").select("id, subject").eq("person_id", old_id).execute().data
    for e in events:
        sub = e['subject'] or ""
        if sub.startswith(OLD):
            new_sub = NEW + sub[len(OLD):]
            sb.table("event").update({"subject": new_sub}).eq("id", e['id']).execute()
            print(f"  event {e['id']}: subject '{sub}' → '{new_sub}'")

# 3) 검증
print("\n=== 검증 ===")
final = sb.table("person").select("id").eq("name", NEW).execute().data
if final:
    fid = final[0]['id']
    evs = sb.table("event").select("event_date, subject, amount").eq("person_id", fid).order("event_date").execute().data
    print(f"'{NEW}'(id={fid}) 연결 event {len(evs)}건:")
    for e in evs:
        print(f"  {e['event_date']} | {e['subject']} | {e['amount']:,}원")
remaining_old = sb.table("person").select("id").eq("name", OLD).execute().data
print(f"'{OLD}' 잔여 person: {len(remaining_old)}건 (0이어야 정상)")
