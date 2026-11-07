"""Streamlit front end for collecting KCI journal metadata."""
from __future__ import annotations
import io
import os
import pandas as pd
import streamlit as st
from kci_client import KCIError, collect

st.set_page_config(page_title="KCI 논문 수집기", page_icon="📚", layout="wide")
st.title("📚 KCI 논문 수집기")
st.caption("학술지 검색 · 발행연도 필터 · 국문 초록 · CSV / Excel 다운로드")
st.info("시험 운영 버전: KCI 검색은 유사한 학술지를 함께 반환할 수 있어요. 원래 입력한 학술지와 **정확하게 일치하는 데이터만** 다운로드 대상이 됩니다.")

try:
    saved_key = st.secrets.get("KCI_API_KEY", "")
except (FileNotFoundError, KeyError):
    saved_key = ""
saved_key = saved_key or os.getenv("KCI_API_KEY", "")

with st.sidebar:
    st.header("인증 및 수집 설정")
    if saved_key:
        st.success("서버 인증키가 설정되어 있습니다.")
        key = saved_key
    else:
        st.warning("서버 인증키가 설정되지 않았습니다.")
        key = st.text_input("KCI API 인증키", type="password", help="화면에서만 사용하는 키이며 CSV/Excel에 포함하지 않습니다.")
    page_limit = st.number_input("최대 조회 페이지", min_value=1, max_value=200, value=10, step=1,
                                 help="페이지당 최대 100건. 처음에는 4페이지로 시험해 보세요.")
    pause = st.slider("요청 간격(초)", min_value=0.3, max_value=3.0, value=0.7, step=0.1)
    st.caption("동시 대량 수집 대신 소규모 테스트를 먼저 권장합니다. KCI 이용 정책을 준수하세요.")

with st.form("search_form"):
    journal = st.text_input("학술지명", value="한국컴퓨터정보학회논문지", help="가능하면 KCI에 표시된 공식 학술지명을 입력하세요.")
    c1, c2 = st.columns(2)
    with c1:
        start_year = st.number_input("시작 연도", min_value=1990, max_value=2030, value=2024, step=1)
    with c2:
        end_year = st.number_input("종료 연도", min_value=1990, max_value=2030, value=2024, step=1)
    korean_only = st.checkbox("국문 초록이 있는 논문만 다운로드", value=True)
    submitted = st.form_submit_button("🔍 논문 수집 시작", type="primary", disabled=not bool(key))

if submitted:
    if not journal.strip():
        st.error("학술지명을 입력해 주세요.")
    elif start_year > end_year:
        st.error("시작 연도는 종료 연도보다 늦을 수 없습니다.")
    else:
        bar = st.progress(0, text="KCI API에 요청하는 중...")
        status = st.empty()
        def on_progress(done: int, estimated: int, count: int):
            bar.progress(min(1., done / max(1, estimated)), text=f"{done}/{estimated}페이지 조회 · 응답 {count}건")
        try:
            result = collect(key=key, journal=journal, start_year=int(start_year),
                             end_year=int(end_year), page_limit=int(page_limit),
                             pause=float(pause), progress=on_progress)
            st.session_state["collection"] = result
            st.session_state["collection_params"] = {
                "journal": journal.strip(), "start_year": int(start_year),
                "end_year": int(end_year), "korean_only": korean_only,
            }
            status.success("API 조회를 마쳤습니다.")
        except KCIError as exc:
            st.session_state.pop("collection", None)
            st.session_state.pop("collection_params", None)
            status.error(str(exc))
        finally:
            bar.empty()

if "collection" in st.session_state:
    result = st.session_state["collection"]
    used = st.session_state["collection_params"]
    source = pd.DataFrame(result.rows)
    wanted = used["journal"]
    if source.empty:
        st.warning("검색된 논문이 없습니다.")
    else:
        source["journal_match"] = source["journal"].str.strip().eq(wanted)
        source["has_korean_abstract"] = source["abstract_ko"].str.strip().ne("")
        source["in_year_range"] = pd.to_numeric(source["year"], errors="coerce").between(used["start_year"], used["end_year"])
        matched = source[source["journal_match"] & source["in_year_range"]].copy()
        selected = matched[matched["has_korean_abstract"]].copy() if used["korean_only"] else matched.copy()

        st.subheader("수집 결과")
        cols = st.columns(4)
        cols[0].metric("API 전체 검색 건수", f"{result.total_reported:,}")
        cols[1].metric("조회된 고유 논문", f"{len(source):,}")
        cols[2].metric("학술지명 일치", f"{len(matched):,}")
        cols[3].metric("최종 다운로드 대상", f"{len(selected):,}")
        st.caption(f"조회한 페이지: {result.pages_fetched} · 전체 검색 결과 조회 완료: {'예' if result.complete else '아니요'}")
        for msg in result.messages:
            st.warning(msg)
        if not result.complete:
            st.warning("부분 수집 결과입니다. 다운로드하더라도 모든 논문이 포함되었다고 간주하지 마세요.")
        if len(matched) == 0:
            st.error("입력한 학술지명과 정확히 일치하는 논문이 발견되지 않았습니다. 학술지명이나 검색조건을 바꿔 주세요.")
        elif len(matched) < len(source):
            st.warning("검색 결과에 다른 학술지가 포함되어 있습니다. 일치하는 학술지의 논문만 선별했습니다. 다만 검색 누락 가능성까지 없어진 것은 아닙니다.")
        if result.complete:
            st.caption("전체 API 검색 페이지를 조회했더라도 KCI 검색이 해당 학술지의 모든 논문을 반환한다는 보장은 없습니다.")

        with st.expander("API에서 실제 반환된 학술지별 건수"):
            st.dataframe(source["journal"].value_counts().rename_axis("학술지").reset_index(name="건수"), hide_index=True, use_container_width=True)
        st.subheader("논문 미리보기")
        display_cols = ["article_id", "journal", "year", "title", "field", "abstract_ko"]
        st.dataframe(selected[display_cols], hide_index=True, use_container_width=True, height=360)
        if not selected.empty:
            # No credential is ever written into the exported dataframe.
            export_cols = ["article_id", "journal", "publisher", "year", "month", "field",
                           "regularity", "title", "abstract_ko", "abstract_en", "doi", "url"]
            exported = selected[export_cols]
            csv_bytes = exported.to_csv(index=False).encode("utf-8-sig")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                exported.to_excel(writer, index=False, sheet_name="articles")
                pd.DataFrame([{
                    "requested_journal": wanted, "start_year": used["start_year"],
                    "end_year": used["end_year"], "api_reported_total": result.total_reported,
                    "collected_unique": len(source), "exact_journal_matches": len(matched),
                    "download_rows": len(exported), "all_pages_fetched": result.complete,
                    "note": "API 검색의 완전성은 보장되지 않습니다.",
                }]).to_excel(writer, index=False, sheet_name="collection_info")
            col_csv, col_xlsx = st.columns(2)
            col_csv.download_button("⬇️ CSV 다운로드", csv_bytes, file_name="kci_articles.csv", mime="text/csv", use_container_width=True)
            col_xlsx.download_button("⬇️ Excel 다운로드", buffer.getvalue(), file_name="kci_articles.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

st.divider()
st.caption("본 도구는 KCI 공식 서비스가 아닌 독립적인 연구용 프로그램입니다. API 이용 조건과 데이터 저작권 및 재배포 정책을 확인한 후 사용하세요.")
