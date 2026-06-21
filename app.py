import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re
import csv
from datetime import datetime

# ==========================================
# [설정] 앱 기본 구성 및 모던 UI (Custom CSS)
# ==========================================
st.set_page_config(page_title="스마트 통합 자산관리", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif; }
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; max-width: 1400px; }
    
    /* 모던 카드 UI */
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #f0f2f6; padding: 24px;
        border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-4px); box-shadow: 0 8px 32px rgba(0,0,0,0.08);
    }
    div[data-testid="metric-container"] label {
        font-size: 14px !important; color: #64748b !important; font-weight: 600 !important;
    }
    div[data-testid="metric-container"] div {
        font-size: 26px !important; color: #0f172a !important; font-weight: 800 !important;
    }
    
    /* 탭 스타일링 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 2px solid #f1f5f9; }
    .stTabs [data-baseweb="tab"] {
        padding: 12px 24px; border-radius: 8px 8px 0 0; font-weight: 700; color: #94a3b8;
    }
    .stTabs [aria-selected="true"] { color: #3b82f6 !important; border-bottom: 3px solid #3b82f6 !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# [원칙 3] 상태 관리(Session State) 통제
# ==========================================
def init_session_state():
    if 'ledger_data' not in st.session_state:
        st.session_state.ledger_data = pd.DataFrame()
    if 'learned_rules' not in st.session_state:
        st.session_state.learned_rules = {}
    if 'portfolio_history' not in st.session_state:
        st.session_state.portfolio_history = pd.DataFrame()
    if 'portfolio_assets' not in st.session_state:
        st.session_state.portfolio_assets = pd.DataFrame()
    if 'system_msg' not in st.session_state:
        st.session_state.system_msg = None
init_session_state()

# ==========================================
# [엔진 1] 10일 단위 월별 사이클 계산기
# ==========================================
def get_cycle_label(dt):
    """주어진 날짜가 속한 '10일 ~ 다음달 9일' 사이클을 계산합니다."""
    if pd.isna(dt): return "미상"
    y, m, d = dt.year, dt.month, dt.day
    
    if d >= 10:
        start_y, start_m = y, m
    else:
        start_m = m - 1 if m > 1 else 12
        start_y = y if m > 1 else y - 1
        
    end_m = start_m + 1 if start_m < 12 else 1
    end_y = start_y if start_m < 12 else start_y + 1
    
    return f"{start_y}년 {start_m}월 10일 ~ {end_y}년 {end_m}월 9일"

# ==========================================
# [원칙 1] 방어적 데이터 파싱 및 학습 엔진
# ==========================================
def decode_file(uploaded_file):
    raw_bytes = uploaded_file.getvalue()
    try: return raw_bytes.decode('utf-8-sig')
    except: return raw_bytes.decode('cp949', errors='ignore')

def learn_patterns_from_custom_ledger(uploaded_file):
    """사용자가 다듬은 2026 가계부.csv 에서 분류 패턴을 완벽히 흡수합니다."""
    text = decode_file(uploaded_file)
    rules = {}
    
    # 1. 정식 헤더가 살아있는지 검사
    df = pd.read_csv(io.StringIO(text), on_bad_lines='skip')
    content_col = next((c for c in df.columns if '내용' in c or '사용처' in c), None)
    cat_col = next((c for c in df.columns if '대분류' in c or '카테고리' in c), None)
    
    if content_col and cat_col:
        for _, row in df.iterrows():
            c = str(row[content_col]).strip()
            cat = str(row[cat_col]).strip()
            if c and cat and cat not in ['미분류', 'nan', '']: rules[c] = cat
    else:
        # 2. 헤더마저 날아간 순수 데이터 형태라면 스캔 엔진 가동
        reader = csv.reader(io.StringIO(text))
        for row in reader:
            row = [str(x).strip() for x in row]
            for i, val in enumerate(row):
                if re.match(r'^\d{2}/\d{2}', val) or re.match(r'^\d{4}-\d{2}-\d{2}', val):
                    if i + 3 < len(row):
                        cat = row[i+1]
                        c = row[i+3]
                        if c and cat and cat not in ['미분류', 'nan', '']: rules[c] = cat
    return rules

def parse_raw_ledger(uploaded_file):
    """기간이 명시된 최신 가계부 내역(엑셀/CSV) 파싱"""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_ext in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            df = pd.read_csv(io.StringIO(decode_file(uploaded_file)))
            
        # 컬럼 공백 제거 및 필수 컬럼 확인
        df.columns = df.columns.str.strip()
        col_map = {}
        for c in df.columns:
            if any(k in c for k in ['날짜', '일시', '승인일']): col_map[c] = '날짜'
            elif any(k in c for k in ['내용', '가맹점', '사용처']): col_map[c] = '내용'
            elif any(k in c for k in ['금액', '이용금액']): col_map[c] = '금액'
            elif '대분류' in c: col_map[c] = '대분류'
            elif '타입' in c or '구분' in c: col_map[c] = '타입'
            
        df = df.rename(columns=col_map)
        if not all(k in df.columns for k in ['날짜', '내용', '금액']): return pd.DataFrame()
        
        # 데이터 정제
        df['날짜_dt'] = pd.to_datetime(df['날짜'], errors='coerce')
        df = df.dropna(subset=['날짜_dt'])
        df['주기'] = df['날짜_dt'].apply(get_cycle_label) # 10일 사이클 라벨링
        df['금액'] = pd.to_numeric(df['금액'].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce').fillna(0)
        
        if '대분류' not in df.columns: df['대분류'] = '미분류'
        if '타입' not in df.columns: 
            df['타입'] = df['금액'].apply(lambda x: '수입' if x > 0 else '지출')
            
        return df[['날짜', '날짜_dt', '주기', '타입', '대분류', '내용', '금액']]
    except Exception as e: return pd.DataFrame()

def apply_learned_rules(df, rules):
    """학습된 패턴을 기간 명시 데이터에 덮어씌웁니다."""
    if df.empty: return df, 0
    mapped_count = 0
    for idx, row in df.iterrows():
        content = str(row['내용']).strip()
        current_cat = str(row['대분류']).strip()
        
        if current_cat in ['미분류', 'nan', '', 'None']:
            # 정확히 일치하거나 내용에 키워드가 포함되어 있으면 맵핑
            if content in rules:
                df.at[idx, '대분류'] = rules[content]
                mapped_count += 1
            else:
                for rule_k, rule_v in rules.items():
                    if len(rule_k) > 1 and rule_k in content:
                        df.at[idx, '대분류'] = rule_v
                        mapped_count += 1
                        break
    return df, mapped_count

def parse_portfolio_history(uploaded_file):
    try:
        df = pd.read_csv(io.StringIO(decode_file(uploaded_file)))
        df.columns = df.columns.str.strip()
        if '날짜' in df.columns and '총 평가 금액' in df.columns:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            df['총 평가 금액'] = pd.to_numeric(df['총 평가 금액'], errors='coerce').fillna(0)
            return df.dropna(subset=['날짜']).sort_values('날짜')
    except: pass
    return pd.DataFrame()

def parse_portfolio_assets(uploaded_file):
    try:
        df = pd.read_csv(io.StringIO(decode_file(uploaded_file)), header=None).dropna(how='all')
        asset_names, eval_values = [], []
        for _, row in df.iterrows():
            row_strs = [str(x).strip() for x in row.values]
            if '관사보증금' in row_strs: asset_names = row_strs
            if len(row_strs) > 0 and '총 평가 금액' in row_strs[0]: eval_values = row_strs
                
        if asset_names and eval_values:
            records = [{'자산명': n, '평가금액': float(re.sub(r'[^\d\.\-]', '', str(v)))} 
                       for n, v in zip(asset_names, eval_values) if n and v and n not in ['총 합계', '총 평가 금액']]
            return pd.DataFrame(records)
    except: pass
    return pd.DataFrame()

# ==========================================
# 화면 레이아웃
# ==========================================
st.title("💎 Smart Wealth & Ledger Dashboard")
tab1, tab2, tab3 = st.tabs(["📝 10일 주기 통합 가계부", "📊 자산 포트폴리오", "⚙️ 데이터 융합 센터"])

if st.session_state.system_msg:
    st.success(st.session_state.system_msg)
    st.session_state.system_msg = None

# ------------------------------------------
# TAB 1: 📝 10일 주기 통합 가계부
# ------------------------------------------
with tab1:
    ledger_df = st.session_state.ledger_data.copy()
    
    if not ledger_df.empty:
        st.markdown("### 📅 월별 가계부 요약 (10일 ~ 익월 9일)")
        
        # 1. 10일 단위 사이클 추출 및 현재 달 자동 포커스
        cycles = sorted(ledger_df['주기'].unique(), reverse=True)
        current_cycle = get_cycle_label(datetime.now())
        
        # 만약 현재 날짜의 사이클이 데이터에 존재하면 그것을 기본값으로, 없으면 가장 최신 데이터를 기본값으로
        default_index = cycles.index(current_cycle) if current_cycle in cycles else 0
        
        selected_cycle = st.selectbox("조회할 월별 기간을 선택하세요", cycles, index=default_index)
        
        # 선택된 사이클의 데이터만 필터링
        cycle_df = ledger_df[ledger_df['주기'] == selected_cycle]
        
        # 2. 요약 메트릭
        income = abs(cycle_df[cycle_df['타입'].isin(['수입', '월급'])]['금액'].sum())
        expense = abs(cycle_df[cycle_df['타입'].isin(['지출', '변동지출', '고정지출'])]['금액'].sum())
        saving = abs(cycle_df[cycle_df['타입'].isin(['저축', '예적금'])]['금액'].sum())
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("해당 기간 총 수입", f"{income:,.0f} 원")
        col2.metric("해당 기간 총 지출", f"{expense:,.0f} 원")
        col3.metric("해당 기간 저축액", f"{saving:,.0f} 원")
        col4.metric("기간 내 잉여 현금", f"{(income - expense - saving):,.0f} 원")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 3. 차트 및 데이터 테이블
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("#### 📂 지출 비중")
            expense_df = cycle_df[cycle_df['타입'].isin(['지출', '변동지출', '고정지출'])].copy()
            if not expense_df.empty:
                expense_df['절대값'] = expense_df['금액'].abs()
                fig = px.pie(expense_df, values='절대값', names='대분류', hole=0.5,
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_traces(textinfo='percent+label', textposition='inside')
                fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("지출 내역이 없습니다.")
                
        with c2:
            st.markdown("#### 📝 상세 내역")
            display_df = cycle_df.sort_values('날짜_dt', ascending=False).drop(columns=['날짜_dt', '주기'])
            st.dataframe(display_df.style.format({'금액': '{:,.0f}'}), use_container_width=True, height=350)
    else:
        st.info("💡 가계부 데이터가 없습니다. '데이터 융합 센터' 탭에서 데이터를 연동해 주세요.")

# ------------------------------------------
# TAB 2: 📊 자산 포트폴리오
# ------------------------------------------
with tab2:
    hist_df = st.session_state.portfolio_history
    asset_df = st.session_state.portfolio_assets
    
    if not hist_df.empty and not asset_df.empty:
        st.markdown("### 💰 총 자산 포트폴리오 요약")
        latest = hist_df.iloc[-1]
        
        cash = asset_df[asset_df['자산명'].str.contains('현금|예적금', na=False)]['평가금액'].sum()
        invest = asset_df[asset_df['자산명'].str.contains('주식|채권|금', na=False)]['평가금액'].sum()
        real_estate = asset_df[asset_df['자산명'].str.contains('보증금|청약', na=False)]['평가금액'].sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 평가 자산 (Net Worth)", f"{latest['총 평가 금액']:,.0f} 원")
        m2.metric("투자 자산 (주식/채권/금)", f"{invest:,.0f} 원")
        m3.metric("현금성 자산 (현금/예적금)", f"{cash:,.0f} 원")
        m4.metric("부동산 자산 (보증금/청약)", f"{real_estate:,.0f} 원")
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("#### 📈 자산 성장 추세")
            fig1 = px.area(hist_df, x='날짜', y='총 평가 금액', color_discrete_sequence=['#10b981'])
            fig1.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=350, xaxis_title="", yaxis_title="")
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            st.markdown("#### 🍩 포트폴리오 구성")
            fig2 = px.pie(asset_df, values='평가금액', names='자산명', hole=0.6)
            fig2.update_traces(textinfo='percent', textposition='inside')
            fig2.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=350, showlegend=True,
                               legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5))
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("💡 자산 포트폴리오 데이터가 없습니다. History와 Stock List 파일을 업로드해주세요.")

# ------------------------------------------
# TAB 3: ⚙️ 데이터 융합 센터
# ------------------------------------------
with tab3:
    st.markdown("### 🔄 원스톱 데이터 업로드")
    st.write("2026 가계부, 가계부 내역, History, Stock List 파일들을 이곳에 한 번에 모두 올려주세요.")
    
    uploaded_files = st.file_uploader("파일 일괄 업로드", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("🚀 전체 데이터 분석 및 시스템 동기화", type="primary", use_container_width=True):
            with st.spinner("AI가 파일 구조를 정밀 분석하여 대시보드를 구성하고 있습니다..."):
                file_flags = {'history': False, 'assets': False, 'pattern': False, 'raw': False}
                raw_df = pd.DataFrame()
                
                # 1. 포트폴리오 및 가계부 패턴 선별 파싱
                for f in uploaded_files:
                    fname = f.name.lower()
                    if "history" in fname:
                        st.session_state.portfolio_history = parse_portfolio_history(f)
                        file_flags['history'] = True
                    elif "stock list" in fname or "portfolio" in fname and "history" not in fname:
                        f.seek(0)
                        st.session_state.portfolio_assets = parse_portfolio_assets(f)
                        file_flags['assets'] = True
                    elif "2026 가계부" in fname:
                        f.seek(0)
                        rules = learn_patterns_from_custom_ledger(f)
                        st.session_state.learned_rules.update(rules)
                        file_flags['pattern'] = True
                    elif "내역" in fname:
                        f.seek(0)
                        raw_df = parse_raw_ledger(f)
                        file_flags['raw'] = True
                
                # 2. 가계부 내역에 학습된 패턴 적용
                if not raw_df.empty:
                    final_df, mapped_count = apply_learned_rules(raw_df, st.session_state.learned_rules)
                    st.session_state.ledger_data = final_df
                    msg_ledger = f"📝 기간 명시 가계부 내역 {len(final_df)}건 적용 (미분류 {mapped_count}건 AI 맵핑)"
                else:
                    msg_ledger = ""

                # 결과 알림
                msg_parts = []
                if file_flags['history']: msg_parts.append("📈 자산성장(History)")
                if file_flags['assets']: msg_parts.append("🍩 자산비중(Stock)")
                if file_flags['pattern']: msg_parts.append(f"🧠 학습된 패턴({len(st.session_state.learned_rules)}개)")
                if msg_ledger: msg_parts.append(msg_ledger)
                
                if msg_parts:
                    st.session_state.system_msg = f"🎯 **동기화 완료!** 적용 항목: " + " / ".join(msg_parts)
                    st.rerun()
                else:
                    st.error("🛑 인식할 수 있는 데이터 구조를 찾지 못했습니다.")
