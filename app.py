import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re
import csv

# ==========================================
# [설정] 앱 기본 구성 및 스타일
# ==========================================
st.set_page_config(page_title="스마트 자산관리", page_icon="💰", layout="wide")
st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eaeaea; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# [원칙 3] 상태 관리(Session State) 통제
# ==========================================
def init_session_state():
    if 'ledger_data' not in st.session_state:
        st.session_state.ledger_data = pd.DataFrame(columns=['날짜', '타입', '대분류', '소분류', '내용', '금액', '결제수단'])
    if 'learned_rules' not in st.session_state:
        st.session_state.learned_rules = {}
    if 'upload_success' not in st.session_state:
        st.session_state.upload_success = False
    if 'upload_msg' not in st.session_state:
        st.session_state.upload_msg = ""
init_session_state()

# ==========================================
# [원칙 1] 데이터 파싱 및 학습 엔진
# ==========================================
def safe_parse_date(date_str):
    try:
        if '(' in str(date_str):
            md = str(date_str).split('(')[0]
            return pd.to_datetime(f"2026/{md}", format='%Y/%m/%d')
        return pd.to_datetime(date_str)
    except:
        return pd.NaT

def learn_patterns_from_2026_csv(uploaded_file):
    """1단계: 2026 가계부.csv (기준 파일)에서 사용자의 분류 패턴을 추출합니다."""
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
                    
                    # 내용과 대분류가 존재하고, 미분류가 아닌 경우에만 학습 사전에 추가
                    if content_str and main_cat and main_cat != '미분류':
                        rules[content_str] = main_cat
    return rules

def parse_raw_transactions(uploaded_file):
    """2단계: 기간이 명시된 가계부 내역(실제 데이터)을 로드하여 표본화합니다."""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    if file_ext in ['xlsx', 'xls']:
        df = pd.read_excel(uploaded_file, engine='openpyxl')
    else:
        raw_bytes = uploaded_file.getvalue()
        try: raw_text = raw_bytes.decode('utf-8-sig')
        except: raw_text = raw_bytes.decode('cp949', errors='ignore')
        df = pd.read_csv(io.StringIO(raw_text))

    # 방어적 헤더 탐색 (가계부 양식마다 표 시작 위치가 다름을 방어)
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
    
    # 컬럼 이름 표준화 (날짜, 내용, 금액)
    col_map = {}
    for c in df.columns:
        if any(k in c for k in ['날짜', '일시', '승인일']) and '날짜' not in col_map.values(): col_map[c] = '날짜'
        elif any(k in c for k in ['내용', '가맹점', '사용처', '결제처']) and '내용' not in col_map.values(): col_map[c] = '내용'
        elif any(k in c for k in ['금액', '이용금액', '승인금액']) and '금액' not in col_map.values(): col_map[c] = '금액'
        elif '대분류' in c: col_map[c] = '대분류'
        elif '소분류' in c: col_map[c] = '소분류'
        elif '결제수단' in c or '카드명' in c: col_map[c] = '결제수단'
        
    df = df.rename(columns=col_map)
    
    if '날짜' not in df.columns or '내용' not in df.columns or '금액' not in df.columns:
        return pd.DataFrame()
        
    # 데이터 정제
    df['금액'] = df['금액'].astype(str).apply(lambda x: re.sub(r'[^\d\.\-]', '', x))
    df['금액'] = pd.to_numeric(df['금액'], errors='coerce').fillna(0)
    
    if '대분류' not in df.columns: df['대분류'] = '미분류'
    if '결제수단' not in df.columns: df['결제수단'] = ''
    if '소분류' not in df.columns: df['소분류'] = ''
    if '타입' not in df.columns: df['타입'] = '지출'
    
    return df[['날짜', '타입', '대분류', '소분류', '내용', '금액', '결제수단']]

def apply_learned_rules_to_ledger(df, rules):
    """3단계: 학습된 패턴 사전을 실제 데이터에 충돌 없이 매핑합니다."""
    mapped_count = 0
    for idx, row in df.iterrows():
        current_cat = str(row.get('대분류', '')).strip()
        
        # 비어있거나 미분류인 항목만 매핑
        if current_cat in ['', '미분류', 'nan', 'None']:
            content = str(row['내용']).strip()
            matched = False
            
            # 1. 완벽 일치 검색
            if content in rules:
                df.at[idx, '대분류'] = rules[content]
                mapped_count += 1
                matched = True
                
            # 2. 부분 일치 검색 (완벽 일치가 없을 경우 키워드 추론)
            if not matched:
                for rule_content, rule_cat in rules.items():
                    if len(rule_content) > 1 and (rule_content in content or content in rule_content):
                        df.at[idx, '대분류'] = rule_cat
                        mapped_count += 1
                        break
    return df, mapped_count

# ==========================================
# 레이아웃 구성
# ==========================================
st.title("📱 스마트 자산관리 시스템")
tab1, tab2, tab3 = st.tabs(["🏠 홈 요약", "📝 상세 내역", "🔄 데이터 연동 센터 (패턴 학습)"])

with tab1:
    st.subheader("재정 요약 대시보드")
    df = st.session_state.ledger_data.copy()
    if not df.empty:
        df['날짜_dt'] = df['날짜'].apply(safe_parse_date)
        df = df.dropna(subset=['날짜_dt']).sort_values('날짜_dt', ascending=False)
        
        # 수입, 지출, 저축 판별 휴리스틱 방어 로직
        income = abs(df[df['대분류'].isin(['수입', '월급', '기타소득', '상여'])]['금액'].sum())
        saving = abs(df[df['대분류'].isin(['저축', '예적금', '투자', '연금'])]['금액'].sum())
        expense_df = df[~df['대분류'].isin(['수입', '월급', '기타소득', '상여', '저축', '예적금', '투자', '연금'])].copy()
        expense = abs(expense_df['금액'].sum())
        balance = income - expense - saving
        
        col1, col2, col3 = st.columns(3)
        col1.metric("총 수입", f"{income:,.0f} 원")
        col2.metric("총 지출", f"{expense:,.0f} 원")
        col3.metric("총 저축", f"{saving:,.0f} 원")
        st.metric("순현금 잔액", f"{balance:,.0f} 원")
        
        if not expense_df.empty:
            st.write("### 📂 지출 카테고리 비율")
            expense_df['절대값'] = expense_df['금액'].abs()
            fig = px.pie(expense_df, values='절대값', names='대분류', hole=0.4)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("데이터가 없습니다. '데이터 연동 센터' 탭에서 두 파일을 올려주세요.")

with tab2:
    st.subheader("기간 명시 엑셀 기준 거래 내역")
    if not st.session_state.ledger_data.empty:
        df_display = st.session_state.ledger_data.copy()
        df_display['날짜_dt'] = df_display['날짜'].apply(safe_parse_date)
        df_display = df_display.sort_values('날짜_dt', ascending=False).drop(columns=['날짜_dt'])
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("거래 내역이 없습니다.")

with tab3:
    st.subheader("데이터 연동 및 패턴 동기화")
    st.write("2026 가계부에서 사용자의 분류 습관을 학습하고, 실제 기간 명시 엑셀에 자동으로 적용합니다.")
    
    if st.session_state.upload_success:
        st.balloons()
        st.success(st.session_state.upload_msg)
        st.session_state.upload_success = False
        
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🧠 1단계: 패턴 학습용 (기준)")
        st.caption("분류가 잘 되어있는 2026 가계부.csv 파일을 올려주세요.")
        file_pattern = st.file_uploader("학습용 CSV 파일 선택", type=["csv"], key='pattern_file')
        
    with col2:
        st.markdown("#### 📊 2단계: 실제 데이터용 (타겟)")
        st.caption("기간이 명시된 미분류 가계부 내역 파일을 올려주세요.")
        file_raw = st.file_uploader("실제 내역 파일 선택 (CSV/XLSX)", type=["csv", "xlsx", "xls"], key='raw_file')
        
    if st.button("🚀 두 파일 비교 분석 및 가계부 자동 작성", use_container_width=True):
        if file_pattern and file_raw:
            with st.spinner("패턴 학습 및 데이터 분석 중..."):
                # 1. 2026 가계부.csv 에서 딕셔너리 학습
                learned_rules = learn_patterns_from_2026_csv(file_pattern)
                st.session_state.learned_rules = learned_rules
                
                # 2. 기간 명시 가계부 내역에서 로우 데이터 추출
                raw_df = parse_raw_transactions(file_raw)
                
                if raw_df.empty:
                    st.error("🛑 [2단계 실제 데이터] 파일에서 날짜, 내용, 금액 컬럼을 찾을 수 없습니다.")
                else:
                    # 3. 추출된 로우 데이터에 학습된 패턴 딕셔너리 덮어씌우기
                    final_df, mapped_count = apply_learned_rules_to_ledger(raw_df, learned_rules)
                    
                    # 4. 세션에 최종 저장 및 새로고침
                    st.session_state.ledger_data = final_df
                    st.session_state.upload_success = True
                    st.session_state.upload_msg = f"🎯 완벽합니다! 2026 가계부에서 **{len(learned_rules)}개의 패턴을 학습**하였고, 기간 명시 데이터에 적용하여 **{mapped_count}건을 자동 분류**했습니다!"
                    st.rerun()
        else:
            st.warning("⚠️ 정확한 비교 분석을 위해 1단계(패턴 학습)와 2단계(실제 데이터) 파일을 모두 업로드해주세요.")
