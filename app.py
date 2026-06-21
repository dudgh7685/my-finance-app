import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import re
import csv
from datetime import datetime

# ==========================================
# [설정] 앱 기본 구성 및 모던 UI (Custom CSS)
# ==========================================
st.set_page_config(page_title="스마트 자산 & 가계부", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    /* 전체 배경 및 폰트 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif; }
    
    /* 화면 여백 최적화 */
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; max-width: 1200px; }
    
    /* 모던 카드 UI (Metric) */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #f0f2f6;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.04);
        transition: transform 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 25px rgba(0,0,0,0.08);
    }
    
    /* 헤더 스타일링 */
    h1 { color: #1e293b; font-weight: 800; letter-spacing: -0.5px; }
    h2, h3 { color: #334155; font-weight: 700; }
    
    /* 탭 스타일링 */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
        font-weight: 600;
        color: #64748b;
    }
    .stTabs [aria-selected="true"] { color: #0ea5e9 !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# [원칙 3] 상태 관리(Session State) 완벽 통제
# ==========================================
def init_session_state():
    if 'ledger_data' not in st.session_state:
        st.session_state.ledger_data = pd.DataFrame(columns=['날짜', '타입', '대분류', '소분류', '내용', '금액', '결제수단'])
    if 'learned_rules' not in st.session_state:
        st.session_state.learned_rules = {}
    if 'net_worth' not in st.session_state:
        st.session_state.net_worth = {"예적금": 0, "주식/펀드": 0, "부동산/보증금": 0, "기타자산": 0}
    if 'system_msg' not in st.session_state:
        st.session_state.system_msg = None
init_session_state()

# ==========================================
# [원칙 1] 방어적 데이터 파싱 및 AI 학습 엔진
# ==========================================
def safe_parse_date(date_str):
    """날짜 문자열의 온갖 결측치와 이상 포맷을 방어하여 변환"""
    try:
        date_str = str(date_str).strip()
        if '(' in date_str:
            md = date_str.split('(')[0]
            return pd.to_datetime(f"{datetime.now().year}/{md}", format='%Y/%m/%d')
        return pd.to_datetime(date_str)
    except:
        return pd.NaT

def learn_patterns_from_csv(uploaded_file):
    """사용자의 기존 가계부 파일에서 분류 규칙을 추출(학습)하는 엔진"""
    raw_bytes = uploaded_file.getvalue()
    try: raw_text = raw_bytes.decode('utf-8-sig')
    except: raw_text = raw_bytes.decode('cp949', errors='ignore')
        
    reader = csv.reader(io.StringIO(raw_text))
    rules = {}
    date_pattern = re.compile(r'^\d{2}/\d{2}\(.*\)$') 
    date_pattern2 = re.compile(r'^\d{4}-\d{2}-\d{2}$') 
    
    for cols in reader:
        cols = [str(c).strip() for c in cols]
        for i, col in enumerate(cols):
            if date_pattern.match(col) or date_pattern2.match(col):
                if i + 4 < len(cols):
                    main_cat = cols[i+1]
                    content_str = cols[i+3]
                    if content_str and main_cat and main_cat not in ['미분류', 'nan', 'None']:
                        rules[content_str] = main_cat
    return rules

def parse_transaction_data(uploaded_file):
    """기간이 명시된 일반 엑셀/CSV에서 가계부 내역을 추출하는 초정밀 스캐너"""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_ext in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            raw_bytes = uploaded_file.getvalue()
            try: df = pd.read_csv(io.StringIO(raw_bytes.decode('utf-8-sig')))
            except: df = pd.read_csv(io.StringIO(raw_bytes.decode('cp949', errors='ignore')))
            
        header_idx = -1
        for idx, row in df.head(30).iterrows():
            row_strs = [str(x) for x in row.values]
            if any(k in s for s in row_strs for k in ['날짜', '일시', '승인일']) and any(k in s for s in row_strs for k in ['금액', '이용금액', '승인금액']):
                header_idx = idx
                break
                
        if header_idx != -1:
            df.columns = df.iloc[header_idx]
            df = df.iloc[header_idx+1:].reset_index(drop=True)
        
        df.columns = [str(c).replace('\n', '').strip() for c in df.columns]
        
        col_map = {}
        for c in df.columns:
            if any(k in c for k in ['날짜', '일시', '승인일']) and '날짜' not in col_map.values(): col_map[c] = '날짜'
            elif any(k in c for k in ['내용', '가맹점', '사용처', '결제처']) and '내용' not in col_map.values(): col_map[c] = '내용'
            elif any(k in c for k in ['금액', '이용금액', '승인금액']) and '금액' not in col_map.values(): col_map[c] = '금액'
            elif '대분류' in c: col_map[c] = '대분류'
            elif '소분류' in c: col_map[c] = '소분류'
            elif '결제수단' in c or '카드명' in c: col_map[c] = '결제수단'
            
        df = df.rename(columns=col_map)
        
        if not all(k in df.columns for k in ['날짜', '내용', '금액']):
            return pd.DataFrame()
            
        df['금액'] = df['금액'].astype(str).apply(lambda x: re.sub(r'[^\d\.\-]', '', x))
        df['금액'] = pd.to_numeric(df['금액'], errors='coerce').fillna(0)
        
        for col in ['대분류', '소분류', '결제수단']:
            if col not in df.columns: df[col] = ''
        
        # 타입 추론 로직
        def infer_type(row):
            amt = row['금액']
            cat = str(row['대분류'])
            if cat in ['수입', '월급', '기타소득', '상여']: return '수입'
            if cat in ['저축', '예적금', '투자', '연금']: return '저축'
            if amt > 0 and not cat: return '수입'
            return '지출'
            
        df['타입'] = df.apply(infer_type, axis=1)
        # 지출은 절대값으로 통일
        df['금액'] = df['금액'].abs() 
        
        return df[['날짜', '타입', '대분류', '소분류', '내용', '금액', '결제수단']]
    except Exception as e:
        st.error(f"데이터 파싱 오류: {e}")
        return pd.DataFrame()

def apply_learned_rules_to_ledger(df, rules):
    """학습된 패턴 사전을 실제 데이터에 충돌 없이 스마트 매핑"""
    mapped_count = 0
    for idx, row in df.iterrows():
        current_cat = str(row.get('대분류', '')).strip()
        if current_cat in ['', '미분류', 'nan', 'None']:
            content = str(row['내용']).strip()
            
            # 1. 완벽 일치 검색
            if content in rules:
                df.at[idx, '대분류'] = rules[content]
                mapped_count += 1
                continue
                
            # 2. 부분 일치 검색
            for rule_content, rule_cat in rules.items():
                if len(rule_content) > 1 and (rule_content in content or content in rule_content):
                    df.at[idx, '대분류'] = rule_cat
                    mapped_count += 1
                    break
                    
    # 미분류 방어
    df['대분류'] = df['대분류'].apply(lambda x: '미분류' if str(x).strip() in ['', 'nan', 'None'] else x)
    return df, mapped_count

# ==========================================
# 레이아웃 구성
# ==========================================
st.title("💎 스마트 자산관리 & 통합 가계부")
tab1, tab2, tab3 = st.tabs(["📊 자산 포트폴리오 & 대시보드", "📝 통합 가계부 내역", "⚙️ 데이터 연동 및 학습"])

# 시스템 메시지 출력기
if st.session_state.system_msg:
    st.success(st.session_state.system_msg)
    st.session_state.system_msg = None

# ------------------------------------------
# TAB 1: 📊 자산 포트폴리오 & 대시보드
# ------------------------------------------
with tab1:
    df = st.session_state.ledger_data.copy()
    if not df.empty:
        df['날짜_dt'] = df['날짜'].apply(safe_parse_date)
        df = df.dropna(subset=['날짜_dt'])
        
        # 1. 종합 자산 요약 (모던 뷰)
        st.markdown("### 💰 총 자산 포트폴리오")
        # 가계부 내역에서 누적된 저축/투자를 자산으로 편입하는 동적 로직
        total_savings_from_ledger = df[df['타입'] == '저축']['금액'].sum()
        current_savings = st.session_state.net_worth['예적금'] + total_savings_from_ledger
        total_assets = current_savings + sum(v for k, v in st.session_state.net_worth.items() if k != '예적금')
        
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        col_a1.metric("총 자산 (Net Worth)", f"{total_assets:,.0f} 원", "Total Assets")
        col_a2.metric("예적금 및 현금성 자산", f"{current_savings:,.0f} 원")
        col_a3.metric("주식 및 펀드", f"{st.session_state.net_worth['주식/펀드']:,.0f} 원")
        col_a4.metric("부동산 및 보증금", f"{st.session_state.net_worth['부동산/보증금']:,.0f} 원")
        
        st.markdown("---")
        
        # 2. 기간별 가계부 현금흐름 (Cash Flow)
        st.markdown("### 📈 기간별 현금흐름 요약")
        income = df[df['타입'] == '수입']['금액'].sum()
        expense = df[df['타입'] == '지출']['금액'].sum()
        saving = df[df['타입'] == '저축']['금액'].sum()
        balance = income - expense - saving
        
        col_cf1, col_cf2, col_cf3, col_cf4 = st.columns(4)
        col_cf1.metric("기간 내 총 수입", f"{income:,.0f} 원", "+ Income")
        col_cf2.metric("기간 내 총 지출", f"{expense:,.0f} 원", "- Expense", delta_color="inverse")
        col_cf3.metric("기간 내 저축/투자", f"{saving:,.0f} 원", "+ Savings")
        col_cf4.metric("남은 잉여 현금", f"{balance:,.0f} 원", "Cash Balance")
        
        # 3. 고급 시각화 (Plotly)
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("#### 📂 지출 카테고리 분석 (Donut Chart)")
            expense_df = df[df['타입'] == '지출'].copy()
            if not expense_df.empty:
                fig = px.pie(expense_df, values='금액', names='대분류', hole=0.5, 
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("지출 내역이 없습니다.")
                
        with col_chart2:
            st.markdown("#### 📅 일별 지출 트렌드 (Bar Chart)")
            if not expense_df.empty:
                daily_exp = expense_df.groupby('날짜_dt')['금액'].sum().reset_index()
                fig2 = px.bar(daily_exp, x='날짜_dt', y='금액', 
                              color_discrete_sequence=['#3b82f6'])
                fig2.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=350,
                                   xaxis_title="", yaxis_title="지출액(원)")
                st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("💡 등록된 데이터가 없습니다. '⚙️ 데이터 연동 및 학습' 탭에서 파일을 업로드하여 모던 대시보드를 활성화하세요.")

# ------------------------------------------
# TAB 2: 📝 통합 가계부 내역
# ------------------------------------------
with tab2:
    st.markdown("### 📝 상세 거래 내역 필터링")
    if not st.session_state.ledger_data.empty:
        df_display = st.session_state.ledger_data.copy()
        
        # 필터 UI 디자인
        col_f1, col_f2 = st.columns([1, 4])
        with col_f1:
            type_filter = st.radio("내역 구분", ["전체", "지출", "수입", "저축"], horizontal=True)
        
        if type_filter != "전체":
            df_display = df_display[df_display['타입'] == type_filter]
            
        df_display['날짜_dt'] = df_display['날짜'].apply(safe_parse_date)
        df_display = df_display.sort_values('날짜_dt', ascending=False).drop(columns=['날짜_dt'])
        
        # 세련된 데이터프레임 노출
        st.dataframe(
            df_display.style.format({'금액': '{:,.0f} 원'}),
            use_container_width=True,
            height=500
        )
    else:
        st.info("거래 내역이 없습니다.")

# ------------------------------------------
# TAB 3: ⚙️ 데이터 연동 및 학습
# ------------------------------------------
with tab3:
    st.markdown("### 🔄 지능형 데이터 동기화 센터")
    st.write("2026 가계부로 사용자 패턴을 AI에게 학습시키고, 기간이 명시된 미분류 엑셀에 자동으로 카테고리를 적용합니다.")
    
    st.markdown("---")
    
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        st.markdown("#### 🧠 1단계: 패턴 학습용 기준 파일")
        st.caption("과거에 잘 분류해 둔 '가계부.csv' (또는 엑셀) 파일을 올려주세요.")
        file_pattern = st.file_uploader("학습용 파일 선택", type=["csv", "xlsx", "xls"], key='pattern_file')
        
    with col_up2:
        st.markdown("#### 💳 2단계: 추가 등록할 내역 파일")
        st.caption("새롭게 다운로드한 카드/은행 내역 엑셀(CSV)을 올려주세요.")
        file_raw = st.file_uploader("추가 내역 파일 선택", type=["csv", "xlsx", "xls"], key='raw_file')
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🚀 데이터 융합 및 AI 자동 가계부 생성", use_container_width=True, type="primary"):
        if file_pattern and file_raw:
            with st.spinner("AI가 파일 구조를 분석하고 패턴을 매핑하는 중입니다..."):
                
                # 1. 패턴 학습
                learned_rules = learn_patterns_from_csv(file_pattern)
                st.session_state.learned_rules.update(learned_rules)
                
                # 2. 신규 내역 파싱
                raw_df = parse_transaction_data(file_raw)
                
                if raw_df.empty:
                    st.error("🛑 [2단계 내역 파일]에서 유효한 거래 내역(날짜/금액)을 찾을 수 없습니다. 파일 양식을 확인해 주세요.")
                else:
                    # 3. AI 매핑 적용
                    final_df, mapped_count = apply_learned_rules_to_ledger(raw_df, st.session_state.learned_rules)
                    
                    # 4. 기존 데이터와 병합 및 중복 제거 방어 로직
                    if not st.session_state.ledger_data.empty:
                        combined_df = pd.concat([st.session_state.ledger_data, final_df])
                        combined_df = combined_df.drop_duplicates(subset=['날짜', '내용', '금액'], keep='last').reset_index(drop=True)
                        st.session_state.ledger_data = combined_df
                    else:
                        st.session_state.ledger_data = final_df
                    
                    # 시스템 알림 등록 후 새로고침
                    st.session_state.system_msg = f"🎉 **통합 완료!** 기존 엑셀에서 **{len(learned_rules)}개의 패턴을 학습**하였고, 신규 내역 중 **{mapped_count}건을 AI가 자동 분류**하여 대시보드에 연동했습니다."
                    st.rerun()
        else:
            st.warning("⚠️ 정확한 AI 자동 분류를 위해 1단계(학습용)와 2단계(신규 내역) 파일을 모두 업로드해주세요.")
