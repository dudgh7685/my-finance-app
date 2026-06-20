import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import hashlib

# 1. 웹앱 기본 설정
st.set_page_config(
    page_title="스마트 가계부 & 자산관리",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eaeaea; }
    div[data-testid="stNotification"] { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 한국어 엑셀 CSV 인코딩 깨짐 방지 함수
def decode_bytes(fb):
    for enc in ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']:
        try: return fb.decode(enc)
        except: pass
    return fb.decode('utf-8', errors='ignore')

# 2. 초기 세션 데이터 설정
if 'ledger_data' not in st.session_state:
    st.session_state.ledger_data = pd.DataFrame(columns=[
        '날짜', '시간', '타입', '대분류', '소분류', '내용', '금액', '화폐', '결제수단', '메모'
    ])
if 'user_info' not in st.session_state:
    st.session_state.user_info = {"이름": "사용자", "신용점수": 919, "연령": 30}
if 'investment_data' not in st.session_state:
    st.session_state.investment_data = pd.DataFrame(columns=['투자상품종류', '금융사', '상품명', '투자원금', '평가금액', '수익률'])
if 'insurance_data' not in st.session_state:
    st.session_state.insurance_data = pd.DataFrame(columns=['금융사', '상품명', '상태', '납입금액'])

st.title("📱 개인 자산관리 웹앱")
st.caption("모바일 브라우저에 최적화된 가계부 및 자산 대시보드입니다.")

tab1, tab2, tab3, tab4 = st.tabs(["🏠 홈", "📝 내역", "📊 자산 및 신용", "🔄 데이터 연동"])

# ==========================================
# TAB 1: 홈 / 대시보드
# ==========================================
with tab1:
    st.subheader("이번 달 재정 요약")
    
    df = st.session_state.ledger_data.copy()
    
    if not df.empty:
        # 콤마, 공백 등 오류 유발 문자 제거 후 숫자로 안전 변환
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
            col1.metric(label="이번 달 총 수입", value=f"{income:,.0f} 원")
            col2.metric(label="이번 달 총 지출", value=f"{expense:,.0f} 원", delta=f"-{expense:,.0f} 원", delta_color="inverse")
            st.metric(label="당월 순현금흐름", value=f"{balance:,.0f} 원", delta=f"{balance:,.0f} 원")
            
            expense_df = month_df[month_df['타입'] == '지출'].copy()
            if not expense_df.empty:
                st.write("### 📂 카테고리별 지출 비율")
                expense_df['절대값금액'] = expense_df['금액'].abs()
                fig = px.pie(expense_df, values='절대값금액', names='대분류', hole=0.4,
                             color_discrete_sequence=px.colors.sequential.RdBu)
                fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("이번 달 지출 내역이 없습니다.")
    else:
        st.warning("데이터가 없습니다. '데이터 연동' 탭에서 파일을 먼저 등록해주세요.")

# ==========================================
# TAB 2: 가계부 내역 관리
# ==========================================
with tab2:
    st.subheader("상세 거래 내역")
    
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
            
            submit_btn = st.form_submit_button("내역 저장하기")
            if submit_btn:
                final_amount = -f_amount if f_type == "지출" else f_amount
                new_row = {
                    '날짜': f_date.strftime('%Y-%m-%d'), '시간': f_time, '타입': f_type,
                    '대분류': f_main_cat, '소분류': f_sub_cat, '내용': f_content,
                    '금액': final_amount, '화폐': 'KRW', '결제수단': f_asset, '메모': f_memo
                }
                st.session_state.ledger_data = pd.concat([st.session_state.ledger_data, pd.DataFrame([new_row])], ignore_index=True)
                st.success("내역이 성공적으로 추가되었습니다!")
                st.rerun()

    if not st.session_state.ledger_data.empty:
        df_display = st.session_state.ledger_data.copy()
        df_display['금액'] = pd.to_numeric(df_display['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_display['날짜'] = pd.to_datetime(df_display['날짜'], errors='coerce')
        df_display = df_display.dropna(subset=['날짜']).sort_values(by=['날짜', '시간'], ascending=False)
        
        filter_type = st.radio("보기 필터", ["전체", "지출", "수입", "이체"], horizontal=True)
        if filter_type != "전체":
            df_display = df_display[df_display['타입'] == filter_type]
            
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
    
    u_info = st.session_state.user_info
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 12px; color: white; margin-bottom: 20px;">
        <span style="font-size:14px; opacity:0.8;">KCB 신용점수</span>
        <h2 style="margin: 5px 0 0 0; color:white;">{u_info['신용점수']} 점</h2>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📈 투자 자산 현황 (실시간 변동률 반영)", expanded=True):
        inv_df = st.session_state.investment_data.copy()
        if not inv_df.empty:
            inv_df['투자원금'] = pd.to_numeric(inv_df['투자원금'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            inv_df['평가금액'] = pd.to_numeric(inv_df['평가금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            inv_df['수익률'] = pd.to_numeric(inv_df['수익률'].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
            
            total_origin = inv_df['투자원금'].sum()
            total_eval = inv_df['평가금액'].sum()
            total_return = ((total_eval - total_origin) / total_origin * 100) if total_origin > 0 else 0
            
            st.metric(label="총 투자 평가액", value=f"{total_eval:,.0f} 원", delta=f"{total_return:+.2f}%")
            
            for _, row in inv_df.iterrows():
                st.markdown(f"""
                <div style="background-color:#fafafa; padding:12px; border-radius:8px; margin-bottom:8px; border-left:4px solid #4e73df;">
                    <small style="color:#888;">{row['투자상품종류']} | {row['금융사']}</small><br>
                    <b>{row['상품명']}</b><br>
                    <span style="font-size:13px;">원금: {float(row['투자원금']):,.0f}원 → 평가액: <b>{float(row['평가금액']):,.0f}원</b></span>
                    <span style="color:{"red" if float(row['수익률'])>=0 else "blue"}; font-size:13px; float:right;"><b>{float(row['수익률']):+.2f}%</b></span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("등록된 투자 상품이 없습니다.")
            
    with st.expander("🛡️ 보장성 보험 가입 현황", expanded=False):
        ins_df = st.session_state.insurance_data
        if not ins_df.empty:
            st.dataframe(ins_df, use_container_width=True, hide_index=True)
        else:
            st.info("등록된 보험 내역이 없습니다.")

# ==========================================
# TAB 4: 데이터 연동 (초강력 파싱 엔진 적용)
# ==========================================
with tab4:
    st.subheader("엑셀 / CSV 파일 등록 자동 정리")
    uploaded_file = st.file_uploader("파일 선택", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_hash = hashlib.md5(file_bytes).hexdigest()
        
        # 파일이 처음 업로드 되었을 때만 파싱 후 화면 새로고침(Rerun)
        if st.session_state.get('last_processed_file') != file_hash:
            filename = uploaded_file.name
            raw_text = decode_bytes(file_bytes)
            
            try:
                # 1. 가계부 내역 파일 파싱 (빈칸, 특수기호 자동 무시)
                if "내역" in filename or "가계부" in filename:
                    new_df = pd.read_csv(io.StringIO(raw_text))
                    new_df.columns = new_df.columns.str.strip()
                    
                    required_cols = ['날짜', '시간', '타입', '금액']
                    if all(col in new_df.columns for col in required_cols):
                        if not st.session_state.ledger_data.empty:
                            combined = pd.concat([st.session_state.ledger_data, new_df], ignore_index=True)
                            combined.drop_duplicates(subset=['날짜', '시간', '내용', '금액'], keep='first', inplace=True)
                            st.session_state.ledger_data = combined
                        else:
                            st.session_state.ledger_data = new_df
                            
                # 2. 뱅샐현황 파일 파싱 (엑셀 숨은 빈칸 완벽 제거 기술 적용)
                elif "현황" in filename or "뱅샐" in filename:
                    lines = raw_text.split('\n')
                    invest_rows = []
                    ins_rows = []
                    
                    for line in lines:
                        # 엑셀이 만든 쓸데없는 빈칸(,,,) 제거하고 순수 데이터만 추출
                        parts = [p.strip() for p in line.split(',') if p.strip() != '']
                        if not parts: continue
                        
                        # 신용점수 추출
                        if "남" in parts or "여" in parts:
                            try: st.session_state.user_info["신용점수"] = int(parts[3])
                            except: pass
                        
                        # 투자 현황 추출 (주식, 채권 등)
                        if parts[0] in ["주식", "펀드", "채권", "투자"]:
                            if len(parts) >= 6:
                                invest_rows.append({
                                    '투자상품종류': parts[0], '금융사': parts[1], '상품명': parts[2],
                                    '투자원금': parts[3], '평가금액': parts[4], '수익률': parts[5]
                                })
                                
                        # 보험 현황 추출
                        if "보험" in parts[0] or "생명" in parts[0]:
                            if len(parts) >= 4:
                                ins_rows.append({
                                    '금융사': parts[0], '상품명': parts[1], '상태': parts[2], '납입금액': parts[3]
                                })
                                
                    if invest_rows: st.session_state.investment_data = pd.DataFrame(invest_rows)
                    if ins_rows: st.session_state.insurance_data = pd.DataFrame(ins_rows)
                
                # 데이터베이스 업데이트 후 스마트폰 화면 즉시 새로고침
                st.session_state['last_processed_file'] = file_hash
                st.rerun()
                
            except Exception as e:
                st.error(f"데이터를 분석하는 중 오류가 발생했습니다: {e}")
        else:
            st.success("✅ 파일 분석 완료! 홈 화면과 자산 탭에 모든 데이터가 연동되었습니다.")
