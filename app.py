import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import re

# ==========================================
# [설정] 앱 기본 구성 및 스타일
# ==========================================
st.set_page_config(page_title="스마트 자산관리", page_icon="💰", layout="centered")
st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eaeaea; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🧠 [핵심] 사용자 맞춤형 영구 분류 사전
# 텍스트로 주신 데이터를 완벽하게 분석하여 하드코딩했습니다.
# ==========================================
USER_CUSTOM_RULES = {
    '수입': ['국군재정단', '굿리치', '농협손보지급', '부모급여', '아동수당', '보험금'],
    '예적금': ['청년도약계좌', '주택청약', '군인적금', '군인공제', '정성훈', '이예진'],
    '보험': ['NH손보', '교보', '흥화', '하나손보', '농협보험', '흥국생명', '태아보험', '운전자보험', '실손'],
    '주거/통신': ['참빛원주도시가스', '가스', '주택공단', '군수지원사령부', '한전', '전기료', '와우 멤버십', 'LGUPLUS', '핸드폰', '인터넷'],
    '차량/교통': ['주유소', '오일뱅크', '티머니GO', '코레일', '원주자유시', '도로공사', '순환도로', '버스', '파킹', '주차', '카클리닉', '자동차검', '공임나라', '케이엠파크', '하이패스'],
    '식비': ['대륙마트', '세븐일레븐', '국군복지단', '복지단', '홈플러스', '필마트', '이마트', '요르딩', '코스트코', '신세계', '키오스크', '짱면사무소', '배스킨라빈스', '순두부', '지에스25', '쿠팡이츠', '커피', '우정집', '강릉집', '호떡', '함영화', '아무리찾아도', '서브웨이', '설렁탕', '까치둥지', '피자', '스시', '수성시루', '식권', '식자재', '고구마', '고춧가루', '매실청', '과일', '외식', '배달'],
    '생활/쇼핑': ['다이소', '가글', '샴푸', '정수필터', '거치대', '휴지', '세제', '소모품'],
    '자녀/육아': ['분유', '기저귀', '어린이집', '육아종합', '아기세제', '타이니모빌', '장난감', '육아용품', '첫만남'],
    '건강/의료': ['약국', '세브란스', '의료원', '소아', '의원', '병원', '치과', '조리원', '건강보조'],
    '꾸밈비': ['동원복', '워크업', '리안헤어', '아이엠아임', '미용', '의류'],
    '경조사/선물': ['어버이날', '결혼식', '투썸플레이스'],
    '기타': ['세외수입현장', '계약금', '포장이사', '입주청소', '복권', '당근페이']
}

# ==========================================
# [원칙 3] 상태 관리(Session State) 통제
# ==========================================
def init_session_state():
    if 'ledger_data' not in st.session_state:
        st.session_state.ledger_data = pd.DataFrame(columns=['날짜', '시간', '타입', '대분류', '소분류', '내용', '금액', '결제수단'])
    if 'user_info' not in st.session_state:
        st.session_state.user_info = {"이름": "사용자", "신용점수": 0}
    if 'investment_data' not in st.session_state:
        st.session_state.investment_data = pd.DataFrame(columns=['투자상품종류', '금융사', '상품명', '투자원금', '평가금액', '수익률'])
    if 'insurance_data' not in st.session_state:
        st.session_state.insurance_data = pd.DataFrame(columns=['금융사', '상품명', '상태', '납입금액'])

init_session_state()

# ==========================================
# [원칙 1] 데이터 클렌징 및 매핑 로직
# ==========================================
def clean_dataframe(df):
    try:
        df = df.dropna(how='all').dropna(axis=1, how='all')
        df.columns = [str(c).replace('\n', '').strip() for c in df.columns]
        df = df.fillna('').astype(str).map(lambda x: x.strip() if isinstance(x, str) else x)
        return df
    except:
        return df

def extract_numbers(val):
    try:
        if pd.isna(val) or str(val).strip() == '': return 0.0
        cleaned = re.sub(r'[^\d\.\-]', '', str(val))
        return float(cleaned) if cleaned else 0.0
    except:
        return 0.0

def run_smart_categorization():
    df = st.session_state.ledger_data
    if df.empty or '내용' not in df.columns:
        return 0
    
    count = 0
    # 대분류가 없거나 미분류인 항목 필터링
    if '대분류' not in df.columns:
        df['대분류'] = '미분류'
        
    mask = df['대분류'].isna() | (df['대분류'] == '') | (df['대분류'].str.contains('미분류', na=False))
    
    for idx, row in df[mask].iterrows():
        content = str(row['내용']).strip()
        
        # 하드코딩된 규칙으로 분류
        matched = False
        for category, keywords in USER_CUSTOM_RULES.items():
            if any(keyword in content for keyword in keywords):
                df.at[idx, '대분류'] = category
                count += 1
                matched = True
                break
                
        # 만약 '쿠팡'인데 못 찾았을 경우 기본 생활비로 방어
        if not matched and '쿠팡' in content:
            df.at[idx, '대분류'] = '생활/쇼핑'
            count += 1
            
    st.session_state.ledger_data = df
    return count

# ==========================================
# 화면 레이아웃 
# ==========================================
st.title("📱 스마트 자산관리 시스템")
tab1, tab2, tab3, tab4 = st.tabs(["🏠 홈", "📝 상세 내역", "📊 자산 현황", "🔄 데이터 연동"])

with tab1:
    st.subheader("이번 달 재정 요약")
    df = st.session_state.ledger_data.copy()
    if not df.empty and '날짜' in df.columns and '금액' in df.columns:
        df['금액_num'] = df['금액'].apply(extract_numbers)
        df['날짜_dt'] = pd.to_datetime(df['날짜'], errors='coerce')
        df = df.dropna(subset=['날짜_dt'])
        if not df.empty:
            df['연월'] = df['날짜_dt'].dt.strftime('%Y-%m')
            month_df = df[df['연월'] == df['연월'].max()]
            income = abs(month_df[month_df['타입'] == '수입']['금액_num'].sum()) if '타입' in month_df.columns else 0
            expense = abs(month_df[month_df['타입'] == '지출']['금액_num'].sum()) if '타입' in month_df.columns else abs(month_df['금액_num'].sum())
            balance = income - expense
            
            col1, col2 = st.columns(2)
            col1.metric("이번 달 총 수입", f"{income:,.0f} 원")
            col2.metric("이번 달 총 지출", f"{expense:,.0f} 원", f"-{expense:,.0f} 원", delta_color="inverse")
            st.metric("당월 순현금흐름", f"{balance:,.0f} 원", f"{balance:,.0f} 원")
            
            if '대분류' in month_df.columns:
                st.write("### 📂 지출 비율")
                expense_df = month_df[month_df['금액_num'] < 0].copy() if '타입' not in month_df.columns else month_df[month_df['타입'] == '지출'].copy()
                if not expense_df.empty:
                    expense_df['절대값'] = expense_df['금액_num'].abs()
                    fig = px.pie(expense_df, values='절대값', names='대분류', hole=0.4)
                    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("데이터가 없습니다. '데이터 연동' 탭을 이용해 주세요.")

with tab2:
    st.subheader("상세 거래 내역")
    if not st.session_state.ledger_data.empty:
        colA, colB = st.columns([3, 1])
        with colA:
            st.caption(f"🧠 사용자 맞춤형 AI 분류 엔진 가동 중")
        with colB:
            if st.button("🪄 자동 분류 실행"):
                cnt = run_smart_categorization()
                st.success(f"분류 완료! ({cnt}건 자동 적용)")

    df_display = st.session_state.ledger_data.copy()
    if not df_display.empty and '날짜' in df_display.columns:
        df_display['금액_num'] = df_display['금액'].apply(extract_numbers)
        df_display['날짜_dt'] = pd.to_datetime(df_display['날짜'], errors='coerce')
        df_display = df_display.dropna(subset=['날짜_dt']).sort_values(by=['날짜_dt'], ascending=False)
        st.dataframe(df_display.drop(columns=['금액_num', '날짜_dt']).head(100), use_container_width=True)

with tab3:
    st.subheader("자산 및 신용 현황")
    if st.session_state.user_info['신용점수'] > 0:
        st.success(f"현재 KCB 신용점수: **{st.session_state.user_info['신용점수']} 점**")
    col_inv, col_ins = st.columns(2)
    with col_inv:
        st.write("📈 **투자 자산**")
        st.dataframe(st.session_state.investment_data, use_container_width=True)
    with col_ins:
        st.write("🛡️ **보험 현황**")
        st.dataframe(st.session_state.insurance_data, use_container_width=True)

with tab4:
    st.subheader("데이터 연동 센터")
    st.info("💡 이미 분류 규칙이 내장되어 있습니다. 가계부 내역 파일(CSV)만 올려주시면 됩니다!")
    
    uploaded_file = st.file_uploader("가계부 내역 파일 업로드 (CSV, XLSX)", type=["csv", "xlsx", "xls"])
    
    if uploaded_file is not None:
        if st.button("파일 분석 및 적용"):
            file_name = uploaded_file.name
            file_ext = file_name.split('.')[-1].lower()
            
            try:
                # 파일 로드
                if file_ext in ['xlsx', 'xls']:
                    # CSV 변환 없이 엑셀 파일을 올릴 경우, 안전하게 첫 시트만 읽음
                    raw_df = pd.read_excel(uploaded_file, sheet_name=0, engine='openpyxl')
                    raw_data_dict = {"Data": raw_df}
                else:
                    try: raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
                    except: raw_df = pd.read_csv(uploaded_file, encoding='cp949', errors='ignore')
                    raw_data_dict = {"CSV_Data": raw_df}

                # 데이터 처리
                for sheet_name, raw_df in raw_data_dict.items():
                    df_clean = clean_dataframe(raw_df)
                    header_idx = -1
                    for idx, row in df_clean.head(20).iterrows():
                        row_strs = [str(x) for x in row.values]
                        if '날짜' in row_strs and '금액' in row_strs:
                            header_idx = idx
                            break
                    
                    if header_idx != -1:
                        df_clean.columns = df_clean.iloc[header_idx]
                        df_clean = df_clean.iloc[header_idx+1:].reset_index(drop=True)
                        df_clean.columns = [str(c).replace('\n', '').strip() for c in df_clean.columns]
                    
                    if '날짜' in df_clean.columns and '금액' in df_clean.columns:
                        st.session_state.ledger_data = df_clean
                        st.success(f"✅ 거래 내역 {len(df_clean)}건 적용 완료! ('📝 상세 내역' 탭에서 [자동 분류 실행] 버튼을 눌러주세요)")

            except Exception as e:
                st.error(f"데이터 처리 중 오류 발생: {e}")
