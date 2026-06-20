import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io

st.set_page_config(page_title="스마트 가계부 & 자산관리", page_icon="💰", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eaeaea; }
    </style>
    """, unsafe_allow_html=True)

# 1. 초기 세션 데이터 설정
if 'ledger_data' not in st.session_state:
    st.session_state.ledger_data = pd.DataFrame(columns=['날짜', '시간', '타입', '대분류', '소분류', '내용', '금액', '화폐', '결제수단', '메모'])
if 'user_info' not in st.session_state:
    st.session_state.user_info = {"이름": "사용자", "신용점수": 0, "연령": 30}
if 'investment_data' not in st.session_state:
    st.session_state.investment_data = pd.DataFrame(columns=['투자상품종류', '금융사', '상품명', '투자원금', '평가금액', '수익률'])
if 'insurance_data' not in st.session_state:
    st.session_state.insurance_data = pd.DataFrame(columns=['금융사', '상품명', '상태', '납입금액'])

st.title("📱 개인 자산관리 웹앱")
tab1, tab2, tab3, tab4 = st.tabs(["🏠 홈", "📝 내역", "📊 자산 및 신용", "🔄 데이터 연동"])

# ==========================================
# TAB 1: 홈 / 대시보드
# ==========================================
with tab1:
    st.subheader("이번 달 재정 요약")
    df = st.session_state.ledger_data.copy()
    
    if not df.empty:
        df['금액'] = pd.to_numeric(df['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
        df = df.dropna(subset=['날짜'])
        
        if not df.empty:
            df['연월'] = df['날짜'].dt.strftime('%Y-%m')
            month_df = df[df['연월'] == df['연월'].max()]
            
            income = abs(month_df[month_df['타입'] == '수입']['금액'].sum())
            expense = abs(month_df[month_df['타입'] == '지출']['금액'].sum())
            balance = income - expense
            
            col1, col2 = st.columns(2)
            col1.metric("이번 달 총 수입", f"{income:,.0f} 원")
            col2.metric("이번 달 총 지출", f"{expense:,.0f} 원", f"-{expense:,.0f} 원", delta_color="inverse")
            st.metric("당월 순현금흐름", f"{balance:,.0f} 원", f"{balance:,.0f} 원")
            
            expense_df = month_df[month_df['타입'] == '지출'].copy()
            if not expense_df.empty:
                st.write("### 📂 카테고리별 지출 비율")
                expense_df['절대값'] = expense_df['금액'].abs()
                fig = px.pie(expense_df, values='절대값', names='대분류', hole=0.4)
                fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("데이터가 없습니다. '데이터 연동' 탭에서 파일을 먼저 등록해주세요.")

# ==========================================
# TAB 2: 가계부 내역 관리
# ==========================================
with tab2:
    st.subheader("상세 거래 내역")
    df_display = st.session_state.ledger_data.copy()
    if not df_display.empty:
        df_display['금액'] = pd.to_numeric(df_display['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_display['날짜'] = pd.to_datetime(df_display['날짜'], errors='coerce')
        df_display = df_display.dropna(subset=['날짜']).sort_values(by=['날짜', '시간'], ascending=False)
        
        filter_type = st.radio("보기 필터", ["전체", "지출", "수입", "이체"], horizontal=True)
        if filter_type != "전체":
            df_display = df_display[df_display['타입'] == filter_type]
            
        for _, row in df_display.iterrows():
            amt_color = "red" if row['타입'] == "지출" else "blue" if row['타입'] == "수입" else "gray"
            sign = "" if row['타입'] == "이체" else "-" if row['타입'] == "지출" else "+"
            st.markdown(f"""
            <div style="padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between;">
                <div><b style="font-size:14px;">{row['내용']}</b> <span style="font-size:11px; color:#888;">| {row['대분류']}</span><br>
                <small style="color:#aaa;">{row['날짜'].strftime('%m-%d')} {row['시간']} · {row['결제수단']}</small></div>
                <div style="text-align: right; align-self: center;">
                <b style="color:{amt_color}; font-size:15px;">{sign}{abs(float(row['금액'])):,.0f}원</b></div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("표시할 거래 내역이 없습니다.")

# ==========================================
# TAB 3: 자산 및 신용 관리
# ==========================================
with tab3:
    st.subheader("나의 신용 및 금융 자산")
    u_info = st.session_state.user_info
    if u_info['신용점수'] > 0:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 12px; color: white; margin-bottom: 20px;">
            <span style="font-size:14px; opacity:0.8;">KCB 신용점수</span>
            <h2 style="margin: 5px 0 0 0; color:white;">{u_info['신용점수']} 점</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with st.expander("📈 투자 자산 현황", expanded=True):
        inv_df = st.session_state.investment_data.copy()
        if not inv_df.empty:
            inv_df['투자원금'] = pd.to_numeric(inv_df['투자원금'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            inv_df['평가금액'] = pd.to_numeric(inv_df['평가금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            inv_df['수익률'] = pd.to_numeric(inv_df['수익률'].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
            
            total_eval = inv_df['평가금액'].sum()
            st.metric("총 투자 평가액", f"{total_eval:,.0f} 원")
            
            for _, row in inv_df.iterrows():
                st.markdown(f"""
                <div style="background-color:#fafafa; padding:12px; border-radius:8px; margin-bottom:8px; border-left:4px solid #4e73df;">
                    <small style="color:#888;">{row['투자상품종류']} | {row['금융사']}</small><br><b>{row['상품명']}</b><br>
                    <span style="font-size:13px;">원금: {float(row['투자원금']):,.0f}원 → 평가액: <b>{float(row['평가금액']):,.0f}원</b></span>
                    <span style="color:{"red" if float(row['수익률'])>=0 else "blue"}; font-size:13px; float:right;"><b>{float(row['수익률']):+.2f}%</b></span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("등록된 투자 상품이 없습니다.")
            
    with st.expander("🛡️ 보장성 보험 가입 현황", expanded=False):
        if not st.session_state.insurance_data.empty:
            st.dataframe(st.session_state.insurance_data, use_container_width=True, hide_index=True)
        else:
            st.info("등록된 보험 내역이 없습니다.")

# ==========================================
# TAB 4: 데이터 연동 (버튼 방식 도입으로 무한루프 및 데이터 증발 완벽 해결)
# ==========================================
with tab4:
    st.subheader("데이터 연동 센터")
    uploaded_file = st.file_uploader("가계부 내역 또는 뱅샐현황 CSV 파일 선택", type=["csv"])
    
    # 파일을 올리고 사용자가 명시적으로 '적용' 버튼을 눌렀을 때만 처리함 (데이터 증발 방지)
    if uploaded_file is not None:
        if st.button("파일 분석 및 앱에 적용하기"):
            filename = uploaded_file.name
            
            # 인코딩 자동 감지 및 변환
            try: raw_text = uploaded_file.getvalue().decode('utf-8-sig')
            except: raw_text = uploaded_file.getvalue().decode('cp949', errors='ignore')
            
            try:
                # [가계부 내역 분석]
                if "내역" in filename or "가계부" in filename:
                    new_df = pd.read_csv(io.StringIO(raw_text))
                    if '날짜' in new_df.columns and '금액' in new_df.columns:
                        st.session_state.ledger_data = new_df
                        st.success(f"✅ 가계부 내역 적용 완료! (총 {len(new_df)}건)")
                    else:
                        st.error("가계부 형식이 맞지 않습니다.")
                
                # [뱅샐 현황 분석] (투명 칸 밀림 현상 완벽 반영)
                elif "현황" in filename or "뱅샐" in filename:
                    lines = raw_text.split('\n')
                    invest_rows, ins_rows = [], []
                    
                    for line in lines:
                        # 콤마 단위로 쪼개고, 좌우 공백을 제거하여 리스트에 담음
                        cols = [c.strip() for c in line.split(',')]
                        
                        # 데이터가 너무 짧은 줄은 무시
                        if len(cols) < 6: continue
                        
                        # 1. 신용점수: cols[1]에 이름이 있거나, cols[2]에 성별이 있는 경우 cols[4]가 신용점수
                        if cols[1] == '정성훈' or cols[2] in ['남', '여']:
                            try: st.session_state.user_info["신용점수"] = int(cols[4])
                            except: pass
                            
                        # 2. 투자상품: cols[1]이 주식, 채권 등일 때 지정된 순서대로 추출
                        if cols[1] in ["주식", "펀드", "채권", "투자"]:
                            invest_rows.append({
                                '투자상품종류': cols[1], '금융사': cols[2], '상품명': cols[3],
                                '투자원금': cols[5], '평가금액': cols[6], '수익률': cols[7]
                            })
                            
                        # 3. 보험현황: cols[4]가 '정상'이고, cols[1]에 보험사 이름이 있을 때 추출
                        if cols[4] == '정상' and ('보험' in cols[1] or '생명' in cols[1]):
                            ins_rows.append({
                                '금융사': cols[1], '상품명': cols[2], '상태': cols[4], '납입금액': cols[5]
                            })
                            
                    if invest_rows: st.session_state.investment_data = pd.DataFrame(invest_rows)
                    if ins_rows: st.session_state.insurance_data = pd.DataFrame(ins_rows)
                    st.success("✅ 자산 현황(신용, 주식, 보험) 적용 완료!")
                
                else:
                    st.warning("파일 이름에 '내역'이나 '현황'이라는 단어가 포함되어 있어야 정상 분류됩니다.")
                    
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
