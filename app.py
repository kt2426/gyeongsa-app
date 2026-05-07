"""경조사 관리 시스템 - 단일 파일 Streamlit 앱 (경사/애사 통합)"""
import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import date
import plotly.express as px

# ---------- 설정 ----------
st.set_page_config(page_title="애경사 관리", page_icon="📒", layout="wide")

KYUNGSA_TYPES = ["결혼", "회갑", "칠순", "팔순", "고희연", "돌", "백일", "개업", "개원", "취임", "생일", "본인경사", "기타"]
AESA_TYPES = ["본인상", "부친상", "모친상", "배우자상", "자녀상", "형제상", "조부상", "조모상", "장인상", "장모상", "시부상", "시모상", "기타상"]
RELATIONS = ["가족", "친척", "직장", "거래처", "동창", "지인", "기타"]
DELIVERY_METHODS = ["직접", "송금", "대봉", "우편환", "화환", "난"]
CATEGORIES = ["경사", "애사"]


def types_for(category):
    return KYUNGSA_TYPES if category == "경사" else AESA_TYPES


# ---------- Supabase 연결 ----------
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = init_supabase()


# ---------- 데이터 가져오기 ----------
def fetch_events(filters=None):
    query = supabase.table("event").select("*, person(name, relation)").order("event_date", desc=True)
    if filters:
        if filters.get("category") and filters["category"] != "전체":
            query = query.eq("category", filters["category"])
        if filters.get("year_from"):
            query = query.gte("event_date", f"{filters['year_from']}-01-01")
        if filters.get("year_to"):
            query = query.lte("event_date", f"{filters['year_to']}-12-31")
        if filters.get("event_type") and filters["event_type"] != "전체":
            query = query.eq("event_type", filters["event_type"])
        if filters.get("min_amount"):
            query = query.gte("amount", filters["min_amount"])
    res = query.execute()
    return res.data


def fetch_persons():
    res = supabase.table("person").select("*").order("name").execute()
    return res.data


def find_or_create_person(name, relation=None):
    res = supabase.table("person").select("*").eq("name", name).execute()
    if res.data:
        return res.data[0]["id"]
    payload = {"name": name}
    if relation:
        payload["relation"] = relation
    res = supabase.table("person").insert(payload).execute()
    return res.data[0]["id"]


def insert_event(data):
    return supabase.table("event").insert(data).execute()


def update_event(event_id, data):
    return supabase.table("event").update(data).eq("id", event_id).execute()


def delete_event(event_id):
    return supabase.table("event").delete().eq("id", event_id).execute()


def to_dataframe(events):
    if not events:
        return pd.DataFrame()
    rows = []
    for e in events:
        rows.append({
            "id": e["id"],
            "구분": e.get("category") or "",
            "날짜": e["event_date"],
            "행사": e.get("event_type") or "",
            "주인공": e.get("subject") or "",
            "관계": (e.get("person") or {}).get("relation") if e.get("person") else "",
            "금액": e.get("amount") or 0,
            "장소": e.get("place") or "",
            "전달": e.get("delivery_method") or "",
            "메모": e.get("memo") or "",
        })
    return pd.DataFrame(rows)


# ---------- UI ----------
st.title("📒 애경사 관리")
st.caption("2005년부터 누적 기록 (경사 + 애사 통합)")

tab_home, tab_add, tab_search, tab_stats = st.tabs(["대시보드", "입력", "검색·수정", "통계"])


# ===== 대시보드 =====
with tab_home:
    events = fetch_events()
    df = to_dataframe(events)
    if df.empty:
        st.info("아직 기록이 없습니다. '입력' 탭에서 추가하세요.")
    else:
        df["날짜"] = pd.to_datetime(df["날짜"])
        this_year = date.today().year
        df_year = df[df["날짜"].dt.year == this_year]

        # 전체 카드
        st.markdown("##### 📊 전체")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(f"{this_year}년 합계", f"{int(df_year['금액'].sum()):,}원")
        col2.metric(f"{this_year}년 건수", f"{len(df_year)}건")
        col3.metric("전체 누적", f"{int(df['금액'].sum()):,}원")
        col4.metric("전체 건수", f"{len(df)}건")

        # 경사/애사 분리 카드
        st.markdown("##### 🎉 경사 / 🕯️ 애사 분리")
        c1, c2 = st.columns(2)
        df_k = df[df["구분"] == "경사"]
        df_a = df[df["구분"] == "애사"]
        with c1:
            st.metric("🎉 경사 누적", f"{int(df_k['금액'].sum()):,}원", f"{len(df_k)}건")
        with c2:
            st.metric("🕯️ 애사 누적", f"{int(df_a['금액'].sum()):,}원", f"{len(df_a)}건")

        st.subheader("최근 입력 10건")
        st.dataframe(df.head(10).drop(columns=["id"]), use_container_width=True, hide_index=True)


# ===== 입력 =====
with tab_add:
    st.subheader("새 애경사 입력")

    # 카테고리는 폼 밖에 두어 변경시 행사종류가 즉시 반영
    cat_col1, cat_col2 = st.columns([1, 3])
    with cat_col1:
        category = st.radio("구분", CATEGORIES, horizontal=True, key="add_category")

    persons = fetch_persons()
    person_names = [p["name"] for p in persons]

    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            event_date = st.date_input("행사 날짜", value=date.today())
            event_type = st.selectbox("행사 종류", types_for(category))
            person_name = st.text_input("가족 대표 이름 (예: 박찬권)", help=f"기존 등록자: {len(person_names)}명. 같은 이름은 한 가족으로 묶입니다.")
            subject = st.text_input("주인공", help='예: "박찬권 딸". 비우면 가족 이름 사용.')
            relation = st.selectbox("관계", ["선택 안함"] + RELATIONS)
        with c2:
            amount = st.number_input("금액 (원)", min_value=0, value=100000, step=10000)
            place = st.text_input("장소")
            delivery_method = st.selectbox("전달 방법", ["선택 안함"] + DELIVERY_METHODS)
            proxy_name = st.text_input("대납자 (대봉 시)")
            companions = st.text_input("동반자 (콤마로 구분)")

        memo = st.text_area("메모")
        submit = st.form_submit_button(f"💾 {category} 저장", use_container_width=True, type="primary")

        if submit:
            if not person_name.strip():
                st.error("가족 대표 이름을 입력해주세요.")
            elif amount <= 0:
                st.error("금액을 입력해주세요.")
            else:
                rel = relation if relation != "선택 안함" else None
                pid = find_or_create_person(person_name.strip(), rel)
                payload = {
                    "person_id": pid,
                    "category": category,
                    "event_date": event_date.isoformat(),
                    "event_type": event_type,
                    "subject": subject.strip() or person_name.strip(),
                    "amount": int(amount),
                    "place": place.strip() or None,
                    "delivery_method": delivery_method if delivery_method != "선택 안함" else None,
                    "proxy_name": proxy_name.strip() or None,
                    "companions": companions.strip() or None,
                    "memo": memo.strip() or None,
                }
                insert_event(payload)
                st.success(f"저장 완료 ({category}): {event_date} {subject or person_name} {amount:,}원")
                st.rerun()


# ===== 검색·수정 =====
with tab_search:
    st.subheader("검색 / 수정 / 삭제")

    with st.expander("필터", expanded=True):
        c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 2, 2])
        with c1:
            f_cat = st.radio("구분", ["전체", "경사", "애사"], key="search_cat")
        with c2:
            keyword = st.text_input("키워드 (주인공/장소/메모)", "")
        with c3:
            year_range = st.slider("연도 범위", 2005, date.today().year + 1, (2005, date.today().year + 1))
        with c4:
            type_options = ["전체"]
            if f_cat in ("전체", "경사"):
                type_options += KYUNGSA_TYPES
            if f_cat in ("전체", "애사"):
                type_options += AESA_TYPES
            f_type = st.selectbox("행사 종류", type_options)
        with c5:
            min_amt = st.number_input("최소 금액", min_value=0, value=0, step=50000)

    events = fetch_events({
        "category": f_cat,
        "year_from": year_range[0],
        "year_to": year_range[1],
        "event_type": f_type,
        "min_amount": min_amt if min_amt > 0 else None,
    })
    df = to_dataframe(events)

    # 키워드 필터 (클라이언트 측)
    if keyword and not df.empty:
        kw = keyword.lower()
        mask = (
            df["주인공"].str.lower().str.contains(kw, na=False) |
            df["장소"].str.lower().str.contains(kw, na=False) |
            df["메모"].str.lower().str.contains(kw, na=False)
        )
        df = df[mask]

    if df.empty:
        st.info("조건에 맞는 기록이 없습니다.")
    else:
        st.write(f"**{len(df)}건** 조회됨 / 합계: **{int(df['금액'].sum()):,}원**")
        st.dataframe(df.drop(columns=["id"]), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("##### 행 수정/삭제")
        ids = df["id"].tolist()
        labels = [f"[{r['구분']}] {r['날짜']} | {r['주인공']} | {r['금액']:,}원" for _, r in df.iterrows()]
        sel_idx = st.selectbox("수정·삭제할 행 선택", range(len(ids)), format_func=lambda i: labels[i] if ids else "없음")

        if ids:
            ev = next(e for e in events if e["id"] == ids[sel_idx])
            ev_cat = ev.get("category") or "경사"

            with st.form("edit_form"):
                c0, _ = st.columns([1, 3])
                with c0:
                    e_cat = st.radio("구분", CATEGORIES, horizontal=True,
                                     index=CATEGORIES.index(ev_cat) if ev_cat in CATEGORIES else 0)

                c1, c2 = st.columns(2)
                with c1:
                    e_date = st.date_input("날짜", value=date.fromisoformat(ev["event_date"]))
                    type_list = types_for(e_cat)
                    cur_type = ev["event_type"]
                    e_type = st.selectbox("행사", type_list,
                                          index=type_list.index(cur_type) if cur_type in type_list else 0)
                    e_subject = st.text_input("주인공", ev.get("subject") or "")
                    e_place = st.text_input("장소", ev.get("place") or "")
                with c2:
                    e_amount = st.number_input("금액", min_value=0, value=int(ev["amount"]), step=10000)
                    dm_idx = DELIVERY_METHODS.index(ev["delivery_method"]) + 1 if ev.get("delivery_method") in DELIVERY_METHODS else 0
                    e_delivery = st.selectbox("전달방법", ["선택 안함"] + DELIVERY_METHODS, index=dm_idx)
                    e_proxy = st.text_input("대납자", ev.get("proxy_name") or "")
                    e_companions = st.text_input("동반자", ev.get("companions") or "")
                e_memo = st.text_area("메모", ev.get("memo") or "")

                cc1, cc2 = st.columns(2)
                with cc1:
                    save = st.form_submit_button("💾 수정 저장", use_container_width=True, type="primary")
                with cc2:
                    delete = st.form_submit_button("🗑️ 삭제", use_container_width=True)

                if save:
                    update_event(ev["id"], {
                        "category": e_cat,
                        "event_date": e_date.isoformat(),
                        "event_type": e_type,
                        "subject": e_subject.strip() or None,
                        "place": e_place.strip() or None,
                        "amount": int(e_amount),
                        "delivery_method": e_delivery if e_delivery != "선택 안함" else None,
                        "proxy_name": e_proxy.strip() or None,
                        "companions": e_companions.strip() or None,
                        "memo": e_memo.strip() or None,
                    })
                    st.success("수정 완료")
                    st.rerun()
                if delete:
                    delete_event(ev["id"])
                    st.success("삭제 완료")
                    st.rerun()


# ===== 통계 =====
with tab_stats:
    s_cat = st.radio("통계 범위", ["전체(애경사)", "경사", "애사"], horizontal=True, key="stats_cat")
    cat_filter = None if s_cat == "전체(애경사)" else s_cat
    events = fetch_events({"category": cat_filter} if cat_filter else None)
    df = to_dataframe(events)

    if df.empty:
        st.info("데이터가 없습니다.")
    else:
        df["날짜"] = pd.to_datetime(df["날짜"])
        df["연도"] = df["날짜"].dt.year
        df["월"] = df["날짜"].dt.month

        # 경사/애사 비교 (전체 선택 시)
        if s_cat == "전체(애경사)":
            st.subheader("연도별 경사 vs 애사 비교")
            yearly_cat = df.groupby(["연도", "구분"])["금액"].sum().reset_index()
            fig0 = px.bar(yearly_cat, x="연도", y="금액", color="구분",
                          barmode="group", title="연도별 합계 (경사/애사)",
                          color_discrete_map={"경사": "#FF6B9D", "애사": "#5B7CB8"})
            st.plotly_chart(fig0, use_container_width=True)

        st.subheader(f"{s_cat} 연도별 지출")
        yearly = df.groupby("연도")["금액"].agg(["sum", "count"]).reset_index()
        yearly.columns = ["연도", "합계", "건수"]
        fig1 = px.bar(yearly, x="연도", y="합계", text="합계", title=f"{s_cat} - 연도별 합계 (원)")
        fig1.update_traces(texttemplate="%{text:,}", textposition="outside")
        st.plotly_chart(fig1, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("행사 종류별 비율")
            type_df = df.groupby("행사")["금액"].sum().reset_index()
            fig2 = px.pie(type_df, names="행사", values="금액")
            st.plotly_chart(fig2, use_container_width=True)
        with c2:
            st.subheader("월별 분포 (전체 기간)")
            monthly = df.groupby("월")["금액"].agg(["count", "sum"]).reset_index()
            monthly.columns = ["월", "건수", "합계"]
            fig3 = px.bar(monthly, x="월", y="건수", title="월별 건수")
            st.plotly_chart(fig3, use_container_width=True)

        st.subheader("가족별 누적 지출 TOP 20")
        person_sum = df.groupby("주인공")["금액"].agg(["sum", "count"]).reset_index()
        person_sum.columns = ["주인공", "누적금액", "횟수"]
        person_sum = person_sum.sort_values("누적금액", ascending=False).head(20)
        person_sum["누적금액"] = person_sum["누적금액"].apply(lambda x: f"{int(x):,}원")
        st.dataframe(person_sum, use_container_width=True, hide_index=True)
