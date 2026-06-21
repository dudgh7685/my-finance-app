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
st.set_page_config(page_title="스마트 통합 자산관리", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif; }
    
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; max-width: 1400px; }
    
    /* 모던 카드 UI */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #f0f2f6;
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.08);
    }
    div[data-testid="metric-container"] label {
        font-size: 14px !important; color: #64748b !important; font-weight: 600 !important;
    }
    div[data-testid="metric-container"] div {
        font-size: 28px !important; color: #0f172a !important; font-weight: 800 !important;
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
# [원칙 3] 상태 관리(Session State) 완벽 통제
# ==========================================
def init_session_state():
    if 'ledger_data' not in st.session_state:
        st.session_state.ledger_data = pd.DataFrame(columns=['날짜', '타입', '대분류', '소분류', '내용', '금액', '결제수단'])
    if 'portfolio_history' not in st.session_state:
        st.session_state.portfolio_history = pd.DataFrame()
    if 'portfolio_assets' not in st.session_state:
        st.session_state.portfolio_assets = pd.DataFrame()
    if 'system_msg' not in st.session_state:
        st.session_state.system_msg = None
init_session_state()

# [가계부 AI 자동 분류 사전]
USER_CUSTOM_RULES = {
    '수입': ['국군재정단', '굿리치', '농협손보지급', '부모급여', '아동수당', '보험금'],
    '예적금': ['청년도약계좌', '주택청약', '군인적금', '군인공제', '정성훈', '이예진'],
    '보험': ['NH손보', '교보', '흥화', '하나손보', '농협보험', '흥국생명', '태아보험', '운전자보험', '실손'],
    '주거/통신': ['참빛원주도시가스', '가스', '주택공단', '군수지원사령부', '한전', '전기료', 'LGUPLUS', '핸드폰', '인터넷', '와우 멤버십'],
    '차량/교통': ['주유소', '오일뱅크', '티머니GO', '코레일', '하이패스', '주차', '택시', '버스', '항공', '공임나라'],
    '식비': ['마트', '세븐일레븐', '국군복지단', '홈플러스', '식자재', '배달', '쿠팡이츠', '식당', '카페', '커피'],
    '생활/쇼핑': ['다이소', '쿠팡', '네이버페이', '카카오페이', '소모품'],
    '자녀/육아': ['분유', '기저귀', '어린이집', '장난감', '육아용품', '첫만남'],
    '건강/의료': ['약국', '세브란스', '의료원', '소아', '병원', '치과', '조리원'],
}

# ==========================================
# [원칙 1] 방어적 데이터 파싱 엔진
# ==========================================
def decode_file(uploaded_file):
    """인코딩 깨짐을 방어하는 범용 디코더"""
    raw_bytes = uploaded_file.getvalue()
    try: return raw_bytes.decode('utf-8-sig')
    except: return raw_bytes.decode('cp949', errors='ignore')

def parse_portfolio_history(uploaded_file):
    """History.csv 파싱 (날짜, 총 평가 금액, 수익률 추출)"""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_ext in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            df = pd.read_csv(io.StringIO(decode_file(uploaded_file)))
            
        df.columns = df.columns.str.strip()
        if '날짜' in df.columns and '총 평가 금액' in df.columns:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            df['총 평가 금액'] = pd.to_numeric(df['총 평가 금액'], errors='coerce').fillna(0)
            if '수익률' in df.columns:
                df['수익률'] = pd.to_numeric(df['수익률'], errors='coerce').fillna(0)
            return df.dropna(subset=['날짜']).sort_values('날짜')
        return pd.DataFrame()
    except: return pd.DataFrame()

def parse_portfolio_assets(uploaded_file):
    """Stock List.csv 파싱 (자산군별 비중 및 금액 추출)"""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_ext in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file, engine='openpyxl', header=None)
        else:
            df = pd.read_csv(io.StringIO(decode_file(uploaded_file)), header=None)
            
        df = df.dropna(how='all').reset_index(drop=True)
        
        asset_names = []
        eval_values = []
        
        for idx, row in df.iterrows():
            row_strs = [str(x).strip() for x in row.values]
            if '관사보증금' in row_strs and '현금' in row_strs:
                asset_names = row_strs
            if len(row_strs) > 0 and '총 평가 금액' in row_strs[0]:
                eval_values = row_strs
                
        if asset_names and eval_values:
            records = []
            for name, val in zip(asset_names, eval_values):
                if name and name not in ['Unnamed', 'nan', '총 합계', '총 평가 금액', '']:
                    try: 
                        num_val = float(re.sub(r'[^\d\.\-]', '', str(val)))
                        if num_val > 0:
                            records.append({'자산명': name, '평가금액': num_val})
                    except: pass
            return pd.DataFrame(records)
        return pd.DataFrame()
    except: return pd.DataFrame()

def parse_ledger_data(uploaded_file):
    """가계부 내역 (수직 블록 및 일반 엑셀/CSV 통합) 완벽 방어 파서"""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    try:
        # [방어 로직] 엑셀일 경우 openpyxl, CSV일 경우 pandas로 우선 안전하게 로드
        if file_ext in ['xlsx', 'xls']:
            df_raw = pd.read_excel(uploaded_file, engine='openpyxl', header=None)
        else:
            raw_text = decode_file(uploaded_file)
            # CSV 모듈이 뻗지 않도록 혹시 모를 NUL byte 제거
            raw_text = raw_text.replace('\x00', '') 
            reader = csv.reader(io.StringIO(raw_text))
            df_raw = pd.DataFrame(list(reader))
    except Exception as e:
        return pd.DataFrame()
        
    records = []
    date_pattern = re.compile(r'^\d{2}/\d{2}\(.*\)$') 
    date_pattern2 = re.compile(r'^\d{4}-\d{2}-\d{2}$') 
    
    # DataFrame을 순회하며 날짜 패턴이 있는지 정밀 스캔
    for _, row in df_raw.iterrows():
        cols = [str(c).strip() if pd.notna(c) else '' for c in row.values]
        
        for i, col in enumerate(cols):
            if date_pattern.match(col) or date_pattern2.match(col):
                if i + 4 < len(cols):
                    date_str = col
                    main_cat = cols[i+1]
                    sub_cat = cols[i+2]
                    content_str = cols[i+3]
                    amount_str = cols[i+4]
                    asset_memo = cols[i+5] if i+5 < len(cols) else ""
                    
                    amt_clean = re.sub(r'[^\d\.\-]', '', amount_str)
                    if not amt_clean: continue
                    try: amt_float = float(amt_clean)
                    except: continue
                        
                    t_type_raw = cols[i-1] if i > 0 else ""
                    if t_type_raw in ['고정지출', '변동지출']: t_type = '지출'
                    elif t_type_raw in ['수입', '저축', '지출']: t_type = t_type_raw
                    else:
                        if main_cat in ['월급', '기타소득', '상여']: t_type = '수입'
                        elif main_cat in ['예적금', '투자', '연금', '목적통장']: t_type = '저축'
                        else: t_type = '지출'
                        
                    records.append({
                        '날짜': date_str, '타입': t_type, 
                        '대분류': main_cat if main_cat else '미분류',
                        '소분류': sub_cat, '내용': content_str, 
                        '금액': amt_float, '결제수단': asset_memo
                    })
                    break # 이 줄에서 거래 내역을 찾았으면 다음 줄로 넘어감
                    
    return pd.DataFrame(records)

def apply_auto_categorization(df):
    """AI 키워드 매핑 엔진"""
    if df.empty or '내용' not in df.columns: return 0
    count = 0
    mask = df['대분류'].isna() | (df['대분류'] == '') | (df['대분류'].str.contains('미분류', na=False))
    
    for idx, row in df[mask].iterrows():
        content = str(row['내용']).strip()
        for category, keywords in USER_CUSTOM_RULES.items():
            if any(keyword in content for keyword in keywords):
                df.at[idx, '대분류'] = category
                count += 1
                break
    return count

def safe_parse_date(date_str):
    try:
        date_str = str(date_str).strip()
        if '(' in date_str:
            md = date_str.split('(')[0]
            return pd.to_datetime(f"{datetime.now().year}/{md}", format='%Y/%m/%d')
        return pd.to_datetime(date_str)
    except:
        return pd.NaT

# ==========================================
# 화면 레이아웃
# ==========================================
st.title("💎 Smart Wealth Dashboard")
tab1, tab2, tab3 = st.tabs(["📊 통합 자산 포트폴리오", "📝 스마트 가계부 내역", "⚙️ 데이터 연동 센터"])

if st.session_state.system_msg:
    st.success(st.session_state.system_msg)
    st.session_state.system_msg = None

# ------------------------------------------
# TAB 1: 📊 통합 자산 포트폴리오
# ------------------------------------------
with tab1:
    hist_df = st.session_state.portfolio_history
    asset_df = st.session_state.portfolio_assets
    
    if not hist_df.empty and not asset_df.empty:
        latest_data = hist_df.iloc[-1]
        total_assets = latest_data['총 평가 금액']
        total_roi = latest_data['수익률'] * 100 if '수익률' in latest_data else 0
        
        cash_assets = asset_df[asset_df['자산명'].str.contains('현금|예적금', na=False)]['평가금액'].sum()
        invest_assets = asset_df[asset_df['자산명'].str.contains('주식|채권|금|펀드', na=False)]['평가금액'].sum()
        real_estate = asset_df[asset_df['자산명'].str.contains('보증금|청약', na=False)]['평가금액'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 평가 자산 (Net Worth)", f"{total_assets:,.0f} 원", f"총 수익률 {total_roi:+.2f}%")
        col2.metric("투자 자산 (주식/채권/금)", f"{invest_assets:,.0f} 원")
        col3.metric("현금성 자산 (현금/예적금)", f"{cash_assets:,.0f} 원")
        col4.metric("부동산 자산 (보증금/청약)", f"{real_estate:,.0f} 원")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("#### 📈 자산 성장 추세 (Net Worth Trend)")
            fig1 = px.area(hist_df, x='날짜', y='총 평가 금액', 
                           color_discrete_sequence=['#3b82f6'],
                           line_shape='spline')
            fig1.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=0, r=0, t=20, b=0), height=350,
                xaxis_title="", yaxis_title="총 자산(원)", hovermode="x unified"
            )
            fig1.update_yaxes(showgrid=True, gridcolor='#f1f5f9')
            st.plotly_chart(fig1, use_container_width=True)
            
        with c2:
            st.markdown("#### 🍩 포트폴리오 비중")
            fig2 = px.pie(asset_df, values='평가금액', names='자산명', hole=0.6,
                          color_discrete_sequence=px.colors.qualitative.Pastel)
            fig2.update_traces(textposition='inside', textinfo='percent')
            fig2.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=350, showlegend=True,
                               legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("💡 등록된 자산 포트폴리오 데이터가 없습니다. '⚙️ 데이터 연동 센터'에서 History와 Stock List 파일을 업로드하세요.")

# ------------------------------------------
# TAB 2: 📝 스마트 가계부 내역
# ------------------------------------------
with tab2:
    ledger_df = st.session_state.ledger_data.copy()
    if not ledger_df.empty:
        col_hdr1, col_hdr2 = st.columns([3, 1])
        with col_hdr1:
            st.markdown("### 📝 기간별 거래 내역")
        with col_hdr2:
            if st.button("🪄 미분류 항목 AI 자동 매핑", use_container_width=True):
                cnt = apply_auto_categorization(st.session_state.ledger_data)
                st.session_state.system_msg = f"✅ 매핑 완료! {cnt}건의 미분류 항목이 성공적으로 분류되었습니다."
                st.rerun()
                
        income = abs(ledger_df[ledger_df['타입'] == '수입']['금액'].sum())
        expense = abs(ledger_df[ledger_df['타입'] == '지출']['금액'].sum())
        saving = abs(ledger_df[ledger_df['타입'] == '저축']['금액'].sum())
        
        m1, m2, m3 = st.columns(3)
        m1.metric("총 수입", f"{income:,.0f} 원")
        m2.metric("총 지출", f"{expense:,.0f} 원")
        m3.metric("총 저축액", f"{saving:,.0f} 원")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        filter_type = st.radio("보기 필터", ["전체", "지출", "수입", "저축"], horizontal=True)
        if filter_type != "전체":
            ledger_df = ledger_df[ledger_df['타입'] == filter_type]
            
        ledger_df['날짜_dt'] = ledger_df['날짜'].apply(safe_parse_date)
        ledger_df = ledger_df.sort_values('날짜_dt', ascending=False).drop(columns=['날짜_dt'])    
            
        st.dataframe(ledger_df.style.format({'금액': '{:,.0f}'}), use_container_width=True, height=400)
    else:
        st.info("💡 거래 내역이 없습니다. 가계부 엑셀 파일을 연동해주세요.")

# ------------------------------------------
# TAB 3: ⚙️ 데이터 연동 센터
# ------------------------------------------
with tab3:
    st.markdown("### 🔄 파일 다중 연동 센터")
    st.write("보유하신 포트폴리오 파일(History, Stock List)과 가계부 내역 엑셀/CSV를 한 번에 업로드하세요. 시스템이 파일명을 인식하여 알맞은 위치에 자동 배치합니다.")
    
    uploaded_files = st.file_uploader("파일 업로드 (여러 파일 동시 선택 가능)", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("🚀 전체 데이터 분석 및 시스템 동기화", type="primary", use_container_width=True):
            with st.spinner("AI가 파일 구조를 정밀 분석하여 대시보드를 구성하고 있습니다..."):
                parsed_count = {'history': False, 'assets': False, 'ledger': 0}
                
                for f in uploaded_files:
                    fname = f.name.lower()
                    
                    # 1. 포트폴리오 History 파싱
                    if "history" in fname:
                        df_hist = parse_portfolio_history(f)
                        if not df_hist.empty:
                            st.session_state.portfolio_history = df_hist
                            parsed_count['history'] = True
                            
                    # 2. 포트폴리오 자산 비중 파싱
                    elif "stock list" in fname or "portfolio" in fname and "history" not in fname:
                        f.seek(0)
                        df_assets = parse_portfolio_assets(f)
                        if not df_assets.empty:
                            st.session_state.portfolio_assets = df_assets
                            parsed_count['assets'] = True
                            
                    # 3. 가계부 내역 파싱
                    else:
                        f.seek(0)
                        df_ledger = parse_ledger_data(f)
                        if not df_ledger.empty:
                            if not st.session_state.ledger_data.empty:
                                combined = pd.concat([st.session_state.ledger_data, df_ledger])
                                combined = combined.drop_duplicates(subset=['날짜', '내용', '금액'], keep='last').reset_index(drop=True)
                                st.session_state.ledger_data = combined
                            else:
                                st.session_state.ledger_data = df_ledger
                            parsed_count['ledger'] += len(df_ledger)

                msg_parts = []
                if parsed_count['history']: msg_parts.append("📈 자산 성장 기록(History)")
                if parsed_count['assets']: msg_parts.append("🍩 자산 비중(Stock List)")
                if parsed_count['ledger'] > 0: msg_parts.append(f"📝 가계부 내역({parsed_count['ledger']}건)")
                
                if msg_parts:
                    st.session_state.system_msg = f"🎯 **분석 완료!** 성공적으로 적용된 데이터: " + ", ".join(msg_parts)
                    st.rerun()
                else:
                    st.error("🛑 업로드된 엑셀/CSV 파일에서 유효한 포트폴리오나 가계부 데이터를 찾을 수 없습니다.")
