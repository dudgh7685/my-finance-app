import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re
from datetime import datetime

# ==========================================
# [설정] 앱 기본 구성 및 스타일
# ==========================================
st.set_page_config(page_title="스마트 가계부 (1단계 완성)", page_icon="📝", layout="wide")

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
    if 'user_rules' not in st.session_state:
        st.session_state.user_rules = {} # 사용자가 화면에서 직접 수정한 규칙 저장용
init_session_state()

# ==========================================
# 🧠 [엔진 1] 초강력 내장 키워드 매핑 사전 (영구 탑재)
# ==========================================
# 사용자님의 파일들을 분석하여 하드코딩했습니다. 패턴 파일을 올릴 필요가 없습니다.
BUILTIN_RULES = {
    '수입': ['재정단', '급여', '월급', '수당', '캐시백', '할인', '환급', '이자', '보험금', '지원금', '첫만남'],
    '저축/투자': ['적금', '예금', '청약', '도약', '공제', '증권', '투자', '연금', '주식'],
    '주거/통신': ['관리비', '가스', '전기', '통신', 'LGU+', 'SKT', 'KT', '인터넷', '구독', '멤버십', '플러스'],
    '차량/교통': ['주유', '오일', '하이패스', '도로', '고속', '주차', '택시', '버스', 'SRT', 'KTX', '기차', '항공', '공임나라', '타이어', '카클리닉'],
    '식비': ['마트', '편의점', '식자재', '배달', '요기요', '배민', '쿠팡이츠', '식당', '카페', '커피', '베이커리', '빵', '치킨', '피자', '복지단', '아우어', '농협하나로'],
    '생활/쇼핑': ['다이소', '쿠팡', '올리브영', '네이버페이', '카카오페이', '페이', '쇼핑', '의류', '미용', '사무기'],
    '자녀/육아': ['분유', '기저귀', '소아과', '장난감', '어린이집', '유치원', '육아', '산후'],
    '건강/의료': ['병원', '의원', '약국', '치과', '한의원', '건강'],
    '경조사': ['축의금', '조의금', '결혼', '장례', '상조', '모임']
}

CATEGORY_LIST = list(BUILTIN_RULES.keys()) + ['기타지출', '미분류']

def get_category_by_keyword(content):
    content_str = str(content).strip().replace(" ", "")
    # 1순위: 사용자가 앱에서 직접 수정한 규칙 우선
    if content_str in st.session_state.user_rules:
        return st.session_state.user_rules[content_str]
    
    # 2순위: 내장된 키워드 포함 여부 검사 (강력한 단어 스캔)
    for category, keywords in BUILTIN_RULES.items():
        for kw in keywords:
            if kw in content_str:
                return category
    return '미분류'

# ==========================================
# [엔진 2] 10일 사이클 계산기
# ==========================================
def get_cycle_label(dt):
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
# [엔진 3] 데이터 파서 (가계부 전용)
# ==========================================
def decode_file(uploaded_file):
    raw_bytes = uploaded_file.getvalue()
    try: return raw_bytes.decode('utf-8-sig').replace('\x00', '')
    except: return raw_bytes.decode('cp949', errors='ignore').replace('\x00', '')

def parse_raw_ledger(uploaded_file):
    file_ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_ext in ['xlsx', 'xls']:
            xls = pd.ExcelFile(uploaded_file, engine='openpyxl')
            target_sheet = xls.sheet_names[0]
            for s in xls.sheet_names:
                if any(keyword in s for keyword in ['내역', '거래', '가계부']):
                    target_sheet = s; break
            df = pd.read_excel(xls, sheet_name=target_sheet)
        else:
            text = decode_file(uploaded_file)
            df = pd.read_csv(io.StringIO(text))
            
        df.columns = [str(c).strip() for c in df.columns]
        
        # 헤더 자동 탐색
        if not (any('날짜' in c for c in df.columns) and any('금액' in c for c in df.columns)):
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
            
        df = df.rename(columns=col_map)
        if not all(k in df.columns for k in ['날짜', '내용', '금액']): 
            return pd.DataFrame()
            
        df['날짜_dt'] = pd.to_datetime(df['날짜'], errors='coerce')
        df = df.dropna(subset=['날짜_dt'])
        df['주기'] = df['날짜_dt'].apply(get_cycle_label) 
        
        # 금액 부호(+,-)를 스캔하여 수입/지출 완벽 분리
        df['원금액'] = pd.to_numeric(df['금액'].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce').fillna(0)
        df['타입'] = df['원금액'].apply(lambda x: '수입' if x > 0 else '지출')
        df['금액'] = df['원금액'].abs()
        
        # 인공지능 키워드 자동 분류 적용!
        df['대분류'] = df['내용'].apply(get_category_by_keyword)
        
        return df[['날짜', '날짜_dt', '주기', '타입', '대분류', '내용', '금액']]
    except Exception as e:
        st.error(f"파싱 에러: {e}")
        return pd.DataFrame()

# ==========================================
# UI 렌더링
# ==========================================
# 💡 [사이드바] 파일 업로드 (새로고침을 덜 타게 하는 고정 영역)
with st.sidebar:
    st.header("📂 내역 업로드")
    st.info("💡 F5(새로고침)를 누르면 초기화됩니다. 탭을 클릭해서 이동하세요!")
    file_raw = st.file_uploader("기간 명시 엑셀(.xlsx, .csv)", type=["csv", "xlsx"])
    
    if file_raw:
        if st.button("🚀 즉시 분석 및 적용", use_container_width=True, type="primary"):
            with st.spinner("AI가 데이터를 분류 중입니다..."):
                parsed_df = parse_raw_ledger(file_raw)
                if not parsed_df.empty:
                    st.session_state.ledger_data = parsed_df
                    st.success("✅ 분류 완료! 우측 화면을 확인하세요.")
                else:
                    st.error("데이터를 찾을 수 없습니다.")
                    
    if not st.session_state.ledger_data.empty:
        st.markdown("---")
        # 엑셀 다운로드 기능 제공
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state.ledger_data.drop(columns=['날짜_dt']).to_excel(writer, index=False, sheet_name='가계부내역')
        excel_data = output.getvalue()
        st.download_button("💾 완성된 가계부 엑셀 다운로드", data=excel_data, file_name="자동완성_가계부.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.title("📝 스마트 가계부 (1단계 완성)")
tab1, tab2 = st.tabs(["📊 월별 대시보드 (10일 주기)", "🛠️ 미분류 직접 수정 (에디터)"])

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
        
        income_df = cycle_df[cycle_df['타입'] == '수입']
        saving_df = cycle_df[cycle_df['대분류'].isin(['저축/투자'])]
        expense_df = cycle_df[(cycle_df['타입'] == '지출') & (~cycle_df['대분류'].isin(['저축/투자']))]
        
        income = income_df['금액'].sum()
        saving = saving_df['금액'].sum()
        expense = expense_df['금액'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("해당 기간 수입 (입금)", f"{income:,.0f} 원")
        col2.metric("해당 기간 지출 (출금)", f"{expense:,.0f} 원")
        col3.metric("해당 기간 저축/투자", f"{saving:,.0f} 원")
        col4.metric("기간 내 잉여 현금", f"{(income - expense - saving):,.0f} 원")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("#### 📂 지출 비중 분석")
            if not expense_df.empty:
                fig = px.pie(expense_df, values='금액', names='대분류', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_traces(textinfo='percent+label', textposition='inside')
                fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("지출 내역이 없습니다.")
                
        with c2:
            st.markdown(f"#### 📝 상세 내역 ({len(cycle_df)}건)")
            display_df = cycle_df.sort_values('날짜_dt', ascending=False).drop(columns=['날짜_dt', '주기'])
            st.dataframe(display_df.style.format({'금액': '{:,.0f}'}), use_container_width=True, height=350)
    else:
        st.info("👈 왼쪽 사이드바에서 기간이 명시된 엑셀/CSV 파일을 업로드해주세요. (패턴 학습 파일은 필요 없습니다!)")

# ------------------------------------------
# TAB 2: 미분류 항목 관리 에디터
# ------------------------------------------
with tab2:
    st.markdown("### 🛠️ 미분류 항목 일괄 수정")
    st.write("AI가 인식하지 못한 '미분류' 항목을 아래 표에서 직접 클릭해서 수정하세요. (수정 시 다음부터 자동으로 기억합니다!)")
    
    if not st.session_state.ledger_data.empty:
        unmapped_df = st.session_state.ledger_data[st.session_state.ledger_data['대분류'] == '미분류'].copy()
        
        if not unmapped_df.empty:
            # st.data_editor를 사용하여 엑셀처럼 화면에서 바로 수정 가능하게 만듦
            edited_df = st.data_editor(
                unmapped_df[['날짜', '내용', '금액', '대분류']],
                column_config={
                    "대분류": st.column_config.SelectboxColumn("카테고리 선택", options=CATEGORY_LIST, required=True),
                    "금액": st.column_config.NumberColumn(format="%d 원")
                },
                disabled=["날짜", "내용", "금액"],
                use_container_width=True,
                hide_index=True
            )
            
            if st.button("💾 수정한 카테고리 일괄 저장 및 학습", type="primary"):
                # 변경된 내용을 원본 데이터프레임과 규칙 사전에 반영
                for idx, row in edited_df.iterrows():
                    content = str(row['내용']).strip().replace(" ", "")
                    new_cat = row['대분류']
                    if new_cat != '미분류':
                        # 규칙 사전에 추가 (다음 번 업로드 시 자동 적용됨)
                        st.session_state.user_rules[content] = new_cat
                        
                        # 원본 데이터프레임 업데이트
                        mask = (st.session_state.ledger_data['내용'] == row['내용']) & (st.session_state.ledger_data['대분류'] == '미분류')
                        st.session_state.ledger_data.loc[mask, '대분류'] = new_cat
                        
                st.success("✅ 저장이 완료되었습니다! 대시보드(Tab 1)에 즉시 반영되었습니다.")
                st.rerun()
        else:
            st.success("🎉 완벽합니다! 모든 항목이 깔끔하게 분류되어 '미분류' 내역이 단 1건도 없습니다.")
    else:
        st.info("👈 데이터를 먼저 업로드해주세요.")
