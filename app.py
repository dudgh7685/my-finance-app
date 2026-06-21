import streamlit as st
import pandas as pd
import plotly.express as px
import io
import csv
import re
from datetime import datetime

# ==========================================
# [설정] 앱 기본 구성 및 스타일
# ==========================================
st.set_page_config(page_title="스마트 가계부 (1단계)", page_icon="📝", layout="wide")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif; }
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; max-width: 1200px; }
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #f0f2f6; padding: 24px;
        border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# [상태 관리] Session State
# ==========================================
def init_session_state():
    if 'ledger_data' not in st.session_state:
        st.session_state.ledger_data = pd.DataFrame()
    if 'learned_rules' not in st.session_state:
        st.session_state.learned_rules = {}
    if 'system_msg' not in st.session_state:
        st.session_state.system_msg = None
init_session_state()

# ==========================================
# [엔진 1] 10일 사이클 계산기
# ==========================================
def get_cycle_label(dt):
    """현재 달 10일 ~ 다음달 9일 사이클로 묶어줍니다."""
    if pd.isna(dt): return "미상"
    y, m, d = dt.year, dt.month, dt.day
    
    if d >= 10:
        start_y, start_m = y, m
    else:
        start_m = m - 1 if m > 1 else 12
        start_y = y if m > 1 else y - 1
        
    end_m = start_m + 1 if start_m < 12 else 1
    end_y = start_y if start_m < 12 else start_y + 1
    
    return f"{start_y}년 {start_m:02d}월 10일 ~ {end_y}년 {end_m:02d}월 09일"

def get_current_cycle_label():
    return get_cycle_label(datetime.now())

# ==========================================
# [엔진 2] 범용 디코더 (NUL Byte 에러 완벽 방어)
# ==========================================
def decode_file(uploaded_file):
    raw_bytes = uploaded_file.getvalue()
    try: 
        text = raw_bytes.decode('utf-8-sig')
    except: 
        text = raw_bytes.decode('cp949', errors='ignore')
    return text.replace('\x00', '')

# ==========================================
# [엔진 3] 패턴 학습 (2026 가계부 -> 규칙 딕셔너리)
# ==========================================
def extract_learning_rules(uploaded_file):
    text = decode_file(uploaded_file)
    reader = csv.reader(io.StringIO(text))
    rules = {}
    
    date_pattern1 = re.compile(r'^\d{2}/\d{2}\(.*\)$') 
    date_pattern2 = re.compile(r'^\d{4}-\d{2}-\d{2}$') 
    
    for row in reader:
        row = [str(x).strip() for x in row]
        for i, val in enumerate(row):
            if date_pattern1.match(val) or date_pattern2.match(val):
                if i + 3 < len(row):
                    main_cat = row[i+1]
                    content = row[i+3]
                    if content and main_cat and main_cat not in ['미분류', 'nan', '', 'None']:
                        rules[content] = main_cat
                break
    return rules

# ==========================================
# [엔진 4] 실제 내역 파싱 및 룰 적용
# ==========================================
def parse_and_apply_ledger(uploaded_file, rules):
    file_ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_ext in ['xlsx', 'xls']:
            # 다중 시트 엑셀 방어: '내역'이나 '거래'가 포함된 시트를 최우선으로 찾아 읽음
            xls = pd.ExcelFile(uploaded_file, engine='openpyxl')
            target_sheet = xls.sheet_names[0]
            for s in xls.sheet_names:
                if any(keyword in s for keyword in ['내역', '거래', '가계부']):
                    target_sheet = s
                    break
            df = pd.read_excel(xls, sheet_name=target_sheet)
        else:
            text = decode_file(uploaded_file)
            df = pd.read_csv(io.StringIO(text))
            
        # 1. 헤더 탐색 및 매핑 (엄격하고 유연하게 확장)
        df.columns = [str(c).strip() for c in df.columns]
        
        has_date = any('날짜' in c for c in df.columns)
        has_content = any(k in c for c in df.columns for k in ['내용', '내역', '사용처', '가맹점'])
        has_amount = any(k in c for c in df.columns for k in ['금액', '이용금액'])
        
        if not (has_date and has_content and has_amount):
            for idx, row in df.head(30).iterrows():
                row_strs = [str(x) for x in row.values]
                if any('날짜' in s for s in row_strs) and any(k in s for s in row_strs for k in ['금액', '이용금액']):
                    df.columns = df.iloc[idx]
                    df = df.iloc[idx+1:].reset_index(drop=True)
                    break
                    
        df.columns = [str(c).strip() for c in df.columns]
        col_map = {}
        for c in df.columns:
            if any(k in c for k in ['날짜', '일시', '승인일']): col_map[c] = '날짜'
            elif any(k in c for k in ['내용', '내역', '가맹점', '사용처']): col_map[c] = '내용'
            elif any(k in c for k in ['금액', '이용금액']): col_map[c] = '금액'
            elif '대분류' in c: col_map[c] = '대분류'
            elif '타입' in c or '구분' in c: col_map[c] = '타입'
            
        df = df.rename(columns=col_map)
        if not all(k in df.columns for k in ['날짜', '내용', '금액']): 
            return pd.DataFrame(), 0
            
        # 2. 데이터 정제
        df['날짜_dt'] = pd.to_datetime(df['날짜'], errors='coerce')
        df = df.dropna(subset=['날짜_dt'])
        df['주기'] = df['날짜_dt'].apply(get_cycle_label) 
        df['금액'] = pd.to_numeric(df['금액'].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce').fillna(0)
        
        if '대분류' not in df.columns: df['대분류'] = '미분류'
        if '타입' not in df.columns: 
            df['타입'] = df['금액'].apply(lambda x: '수입' if x > 0 else '지출')
        df['금액'] = df['금액'].abs()
        
        # 3. 패턴 적용 (핵심)
        mapped_count = 0
        for idx, row in df.iterrows():
            content = str(row['내용']).strip()
            current_cat = str(row['대분류']).strip()
            
            if current_cat in ['미분류', 'nan', '', 'None']:
                # 완전 일치
                if content in rules:
                    df.at[idx, '대분류'] = rules[content]
                    mapped_count += 1
                else:
                    # 부분 일치 (예: '국군복지단' 룰이 '국군복지단 원주점'에 적용되도록)
                    for rule_content, rule_cat in rules.items():
                        if len(rule_content) > 1 and rule_content in content:
                            df.at[idx, '대분류'] = rule_cat
                            mapped_count += 1
                            break
                            
        return df[['날짜', '날짜_dt', '주기', '타입', '대분류', '내용', '금액']], mapped_count
    except Exception as e:
        st.error(f"파싱 에러: {e}")
        return pd.DataFrame(), 0

# ==========================================
# UI 렌더링
# ==========================================
st.title("📝 스마트 가계부 (1단계: 자동 분류)")
tab1, tab2 = st.tabs(["📝 월별 가계부 내역 (10일 주기)", "⚙️ 데이터 연동 센터"])

if st.session_state.system_msg:
    st.success(st.session_state.system_msg)
    st.session_state.system_msg = None

# ------------------------------------------
# TAB 1: 월별 가계부 내역
# ------------------------------------------
with tab1:
    ledger_df = st.session_state.ledger_data.copy()
    
    if not ledger_df.empty:
        cycles = sorted(ledger_df['주기'].unique(), reverse=True)
        current_cycle = get_current_cycle_label()
        default_index = cycles.index(current_cycle) if current_cycle in cycles else 0
        
        selected_cycle = st.selectbox("📅 조회할 월별 기간(매월 10일 기준)을 선택하세요", cycles, index=default_index)
        cycle_df = ledger_df[ledger_df['주기'] == selected_cycle]
        
        income_df = cycle_df[cycle_df['타입'].isin(['수입', '월급']) | cycle_df['대분류'].isin(['수입', '월급', '기타소득', '상여'])]
        saving_df = cycle_df[cycle_df['타입'].isin(['저축', '예적금']) | cycle_df['대분류'].isin(['저축', '예적금', '투자', '연금'])]
        expense_df = cycle_df.drop(income_df.index).drop(saving_df.index)
        
        income = income_df['금액'].sum()
        saving = saving_df['금액'].sum()
        expense = expense_df['금액'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("해당 기간 총 수입", f"{income:,.0f} 원")
        col2.metric("해당 기간 총 지출", f"{expense:,.0f} 원")
        col3.metric("해당 기간 저축액", f"{saving:,.0f} 원")
        col4.metric("기간 내 잉여 현금", f"{(income - expense - saving):,.0f} 원")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("#### 📂 지출 비중 분석")
            if not expense_df.empty:
                fig = px.pie(expense_df, values='금액', names='대분류', hole=0.5,
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_traces(textinfo='percent+label', textposition='inside')
                fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("지출 내역이 없습니다.")
                
        with c2:
            st.markdown(f"#### 📝 상세 내역 ({len(cycle_df)}건)")
            display_df = cycle_df.sort_values('날짜_dt', ascending=False).drop(columns=['날짜_dt', '주기', '타입'])
            st.dataframe(display_df.style.format({'금액': '{:,.0f}'}), use_container_width=True, height=350)
    else:
        st.info("💡 데이터가 없습니다. '데이터 연동 센터'에서 가계부 파일 2개를 올려주세요.")

# ------------------------------------------
# TAB 2: 데이터 연동 센터
# ------------------------------------------
with tab2:
    st.markdown("### 🔄 패턴 학습 및 가계부 적용")
    st.write("사용자님의 '2026 가계부' 패턴을 추출하여, 기간이 명시된 최신 가계부에 덮어씌웁니다.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 1. 패턴 학습용 파일 (기준)")
        file_pattern = st.file_uploader("2026 가계부.csv 업로드", type=["csv", "xlsx", "xls"], key="pattern")
    with col2:
        st.markdown("#### 2. 실제 내역 파일 (타겟)")
        file_raw = st.file_uploader("가계부 내역 파일 업로드", type=["csv", "xlsx", "xls"], key="raw")
        
    if st.button("🚀 데이터 분석 및 가계부 10일 주기 생성", type="primary", use_container_width=True):
        if file_pattern and file_raw:
            with st.spinner("패턴 추출 및 가계부 작성 중..."):
                # 1. 패턴 추출
                rules = extract_learning_rules(file_pattern)
                st.session_state.learned_rules = rules
                
                # 2. 내역 파싱 및 패턴 덮어쓰기
                final_df, mapped_count = parse_and_apply_ledger(file_raw, rules)
                
                if final_df.empty:
                    st.error("🛑 실제 내역 파일에서 정상적인 [날짜, 내용, 금액] 데이터를 찾을 수 없습니다.")
                else:
                    st.session_state.ledger_data = final_df
                    st.session_state.system_msg = f"🎯 **가계부 생성 완료!** 2026 가계부에서 **{len(rules)}개의 패턴**을 찾아내어, 최신 내역의 미분류 항목 **{mapped_count}건을 완벽하게 재분류**했습니다."
                    st.rerun()
        else:
            st.warning("⚠️ 학습용 파일과 실제 내역 파일을 모두 업로드해주세요.")
