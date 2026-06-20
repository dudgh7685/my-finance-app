import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io

# 1. 웹앱 기본 설정 (모바일 최적화 및 와이드 레이아웃)
st.set_page_config(
    page_title="스마트 가계부 & 자산관리",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 자체 스타일링 (모바일 하단 네비게이션 스타일 모방 및 깔끔한 카드 디자인)
st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eaeaea; }
    div[data-testid="stNotification"] { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 2. 초기 세션 데이터(초기값) 설정 (파일 업로드 전 보여줄 샘플 및 기준 데이터)
if 'ledger_data' not in st.session_state:
    # 빈 데이터프레임 구조 생성
    st.session_state.ledger_data = pd.DataFrame(columns=[
        '날짜', '시간', '타입', '대분류', '소분류', '내용', '금액', '화폐', '결제수단', '메모'
    ])
if 'user_info' not in st.session_state:
    st.session_state.user_info = {"이름": "사용자", "신용점수": 919, "연령": 30}
if 'investment_data' not in st.session_state:
    st.session_state.investment_data = pd.DataFrame(columns=['투자상품종류', '금융사', '상품명', '투자원금', '평가금액', '수익률'])
if 'insurance_data' not in st.session_state:
    st.session_state.insurance_data = pd.DataFrame(columns=['금융사', '상품명', '상태', '납입금액'])

# 3. 상단 타이틀
st.title("📱 개인 자산관리 웹앱")
st.caption("모바일 브라우저에 최적화된 가계부 및 자산 대시보드입니다.")

# 4. 하단 탭 구조 선언 (홈, 내역, 자산관리, 데이터연동)
tab1, tab2, tab3, tab4 = st.tabs(["🏠 홈", "📝 내역", "📊 자산 및 신용", "🔄 데이터 연동"])

# ==========================================
# TAB 1: 홈 / 대시보드
# ==========================================
with tab1:
    st.subheader("이번 달 재정 요약")
    
    df = st.session_state.ledger_data
    
    if not df.empty:
        # 금액 데이터 숫자 변환
        df['금액'] = pd.to_numeric(df['금액']).fillna(0)
        df['날짜'] = pd.to_datetime(df['날짜'])
        
        # 이번 달 데이터 필터링
        current_month = datetime.now().strftime('%Y-%m')
        df['연월'] = df['날짜'].dt.strftime('%Y-%m')
        month_df = df[df['연월'] == df['연월'].max()] # 데이터 내 가장 최근 달 기준
        
        # 수입 / 지출 합계 계산
        income = abs(month_df[month_df['타입'] == '수입']['금액'].sum())
        expense = abs(month_df[month_df['타입'] == '지출']['금액'].sum())
        balance = income - expense
        
        # 대시보드 상단 메트릭 배치
        col1, col2 = st.columns(2)
        col1.metric(label="이번 달 총 수입", value=f"{income:,.0f} 원")
        col2.metric(label="이번 달 총 지출", value=f"{expense:,.0f} 원", delta=f"-{expense:,.0f} 원", delta_color="inverse")
        st.metric(label="당월 순현금흐름", value=f"{balance:,.0f} 원", delta=f"{balance:,.0f} 원")
        
        # 지출 시각화 (Pie 차트)
        expense_df = month_df[month_df['타입'] == '지출']
        if not expense_df.empty:
            st.write("### 📂 카테고리별 지출 비율")
            # 금액을 양수로 표현하기 위해 가공
            expense_df['절대값금액'] = expense_df['금액'].abs()
            fig = px.pie(expense_df, values='절대값금액', names='대분류', hole=0.4,
                         color_discrete_sequence=px.colors.sequential.RdBu)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("이번 달 지출 내역이 없습니다.")
    else:
        st.warning("데이터가 없습니다. '데이터 연동' 탭에서 엑셀/CSV 파일을 먼저 등록해주세요.")

# ==========================================
# TAB 2: 가계부 내역 관리
# ==========================================
with tab2:
    st.subheader("상세 거래 내역")
    
    # 내역 직접 추가 Form (팝업/모달 대용 인터페이스)
    with st.expander("➕ 수동 지출/수입 추가하기", expanded=False):
        with st.form("add_transaction_form", clear_on_submit=True):
            f_date = st.date_input("날짜", datetime.now())
            f_time = st.time_input("시간", datetime.now().time()).strftime('%H:%M:%S')
            f_type = st.selectbox("타입", ["지출", "수입", "이체"])
            f_main_cat = st.selectbox("대분류", ["식비", "주거", "교통", "생활", "저축", "미분류"])
            f_sub_cat = st.text_input("소분류", "미분류")
            f_content = st.text_input("내용", placeholder="지출처 명칭")
            f_amount = st.number_input("금액", min_value=0, step=1000)
            f_asset = st.text_input("결제 수단", placeholder="카카오뱅크, 신용카드 등")
            f_memo = st.text_input("메모")
            
            submit_btn = st.form_submit_form_button("내역 저장하기")
            if submit_btn:
                # 지출인 경우 금액을 음수로 저장하는 규칙 처리
                final_amount = -f_amount if f_type == "지출" else f_amount
                new_row = {
                    '날짜': f_date.strftime('%Y-%m-%d'), '시간': f_time, '타입': f_type,
                    '대분류': f_main_cat, '소분류': f_sub_cat, '내용': f_content,
                    '금액': final_amount, '화폐': 'KRW', '결제수단': f_asset, '메모': f_memo
                }
                st.session_state.ledger_data = pd.concat([st.session_state.ledger_data, pd.DataFrame([new_row])], ignore_index=True)
                st.success("내역이 성공적으로 추가되었습니다!")
                st.rerun()

    # 내역 리스트 필터링 및 노출
    if not st.session_state.ledger_data.empty:
        df_display = st.session_state.ledger_data.copy()
        df_display['날짜'] = pd.to_datetime(df_display['날짜'])
        df_display = df_display.sort_values(by=['날짜', '시간'], ascending=False)
        
        # 빠른 필터 인터페이스 (칩 스타일 대용 무선 버튼)
        filter_type = st.radio("보기 필터", ["전체", "지출", "수입", "이체"], horizontal=True)
        if filter_type != "전체":
            df_display = df_display[df_display['타입'] == filter_type]
            
        # 모바일 가독성을 위한 포맷팅 뷰 전환
        for index, row in df_display.iterrows():
            amt_color = "red" if row['타입'] == "지출" else "blue" if row['타입'] == "수입" else "gray"
            sign = "" if row['타입'] == "이체" else "-" if row['타입'] == "지출" else "+"
            
            with st.container():
                st.markdown(f"""
                <div style="padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between;">
                    <div>
                        <b style="font-size:14px;">{row['내용']}</b> <span style="font-size:11px; color:#888;">| {row['대분류']}</span><br>
                        <small style="color:#aaa;">{row['날짜'].strftime('%m-%d')} {row['시간']} · {row['결제수단']}</small>
                    </div>
                    <div style="text-align: right; align-self: center;">
                        <b style="color:{amt_color}; font-size:15px;">{sign}{abs(float(row['금액'])):,.0f}원</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("표시할 거래 내역이 없습니다.")

# ==========================================
# TAB 3: 자산 및 신용 관리
# ==========================================
with tab3:
    st.subheader("나의 신용 및 금융 자산")
    
    # 1. 신용 점수 표시
    u_info = st.session_state.user_info
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 12px; color: white; margin-bottom: 20px;">
        <span style="font-size:14px; opacity:0.8;">KCB 신용점수</span>
        <h2 style="margin: 5px 0 0 0; color:white;">{u_info['신용점수']} 점</h2>
        <small style="opacity:0.9;">상위 {100 - int(u_info['신용점수']/10):}% 이내 우수 신용 등급 상태</small>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. 투자 자산 현황 아코디언
    with st.expander("📈 투자 자산 현황 (실시간 변동률 반영)", expanded=True):
        inv_df = st.session_state.investment_data
        if not inv_df.empty:
            # 금액 데이터 포맷팅하여 테이블 노출
            display_inv = inv_df.copy()
            
            # 총 투자 요약 연산
            total_origin = pd.to_numeric(display_inv['투자원금']).sum()
            total_eval = pd.to_numeric(display_inv['평가금액']).sum()
            total_return = ((total_eval - total_origin) / total_origin * 100) if total_origin > 0 else 0
            
            st.metric(label="총 투자 평가액", value=f"{total_eval:,.0f} 원", delta=f"{total_return:+.2f}%")
            
            # 테이블 스타일 최적화 리스트업
            for _, row in display_inv.iterrows():
                st.markdown(f"""
                <div style="background-color:#fafafa; padding:12px; border-radius:8px; margin-bottom:8px; border-left:4px solid #4e73df;">
                    <small style="color:#888;">{row['투자상품종류']} | {row['금융사']}</small><br>
                    <b>{row['상품명']}</b><br>
                    <span style="font-size:13px;">원금: {float(row['투자원금']):,.0f}원 → 평가액: <b>{float(row['평가금액']):,.0f}원</b></span>
                    <span style="color:{"red" if float(row['수익률'])>=0 else "blue"}; font-size:13px; float:right;"><b>{float(row['수익률']):+.2f}%</b></span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("등록된 투자 상품이 없습니다. '데이터 연동' 탭에서 파일을 업로드해 주세요.")
            
    # 3. 보험 계약 현황 아코디언
    with st.expander("🛡️ 보장성 보험 가입 현황", expanded=False):
        ins_df = st.session_state.insurance_data
        if not ins_df.empty:
            st.dataframe(ins_df, use_container_width=True, hide_index=True)
        else:
            st.info("등록된 보험 내역이 없습니다.")

# ==========================================
# TAB 4: 데이터 연동 (자동 정리 기능)
# ==========================================
with tab4:
    st.subheader("엑셀 / CSV 파일 등록 자동 정리")
    st.write("뱅크샐러드나 기존 가계부에서 추출한 기간 명시형 CSV 파일을 업로드하면 시스템이 자동으로 중복을 제거하고 데이터를 파싱합니다.")
    
    uploaded_file = st.file_uploader("파일 선택 (가계부 내역 혹은 뱅샐현황 CSV 파일)", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        filename = uploaded_file.name
        st.success(f"📂 파일이 성공적으로 감지되었습니다: {filename}")
        
        try:
            # 업로드 데이터 바이트 변환 처리
            file_bytes = uploaded_file.getvalue()
            
            # 1. 가계부 내역 파일 파싱 규칙 처리
            if "내역" in filename or "가계부" in filename:
                new_df = pd.read_csv(io.StringIO(file_bytes.decode('utf-8')))
                
                # 필요 필수 컬럼 존재 확인 검증
                required_cols = ['날짜', '시간', '타입', '금액']
                if all(col in new_df.columns for col in required_cols):
                    # 기존 데이터가 있다면 병합 후 중복 제거(디두플리케이션)
                    if not st.session_state.ledger_data.empty:
                        combined = pd.concat([st.session_state.ledger_data, new_df], ignore_index=True)
                        # 완전히 동일한 시간 및 내용, 금액의 Row 제거 처리
                        combined.drop_duplicates(subset=['날짜', '시간', '내용', '금액'], keep='first', inplace=True)
                        st.session_state.ledger_data = combined
                    else:
                        st.session_state.ledger_data = new_df
                        
                    st.balloons()
                    st.success(f"🎯 가계부 내역 동기화 완료! 총 {len(st.session_state.ledger_data)}개의 거래 이력이 안전하게 보관 중입니다.")
                else:
                    st.error("가계부 표준 규격 컬럼(날짜, 시간, 타입, 금액 등)이 확인되지 않습니다. 파일 구조를 확인해주세요.")
            
            # 2. 뱅샐현황 파일 파싱 규칙 처리
            elif "현황" in filename or "뱅샐" in filename:
                raw_text = file_bytes.decode('utf-8')
                lines = raw_text.split('\n')
                
                # 세부 섹션별 데이터를 가두기 위한 임시 저장소
                invest_rows = []
                ins_rows = []
                
                for line in lines:
                    parts = [p.strip() for p in line.split(',')]
                    # 신용 점수 라인 파싱 규칙
                    if len(parts) >= 5 and "정성훈" in parts:
                        st.session_state.user_info["신용점수"] = int(parts[3])
                    # 투자 자산 라인 파싱 규칙
                    if len(parts) >= 8 and parts[0] in ["주식", "펀드", "채권", "투자"]:
                        invest_rows.append({
                            '투자상품종류': parts[0], '금융사': parts[1], '상품명': parts[2],
                            '투자원금': parts[4], '평가금액': parts[5], '수익률': parts[6]
                        })
                    # 보험 현황 라인 파싱 규칙
                    if len(parts) >= 6 and "보험" in parts[1]:
                        ins_rows.append({
                            '금융사': parts[1], '상품명': parts[2], '상태': parts[4], '납입금액': parts[5]
                        })
                
                # 추출된 임시 자산 리스트 세션 적재
                if invest_rows:
                    st.session_state.investment_data = pd.DataFrame(invest_rows)
                if ins_rows:
                    st.session_state.insurance_data = pd.DataFrame(ins_rows)
                    
                st.balloons()
                st.success("🏦 고객 정보 및 금융 투자/보험 자산 현황 동기화가 안전하게 완료되었습니다!")
                
        except Exception as e:
            st.error(f"파일을 읽는 과정에서 인코딩 혹은 규격 오류가 발생했습니다: {e}")