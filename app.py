import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re
import csv

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
# 🧠 [영구 내장] 사용자 맞춤형 소비 분류 사전
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
        st.session_state.ledger_data = pd.DataFrame(columns=['날짜', '타입', '대분류', '소분류', '내용', '금액', '결제수단'])
    if 'user_info' not in st.session_state:
        st.session_state.user_info = {"이름": "사용자", "신용점수": 0}
init_session_state()

# ==========================================
# [원칙 1] 특수 정밀 스캔 엔진 (CSV 레이더)
# ==========================================
def safe_parse_date(date_str):
    try:
        if '(' in date_str:
            md = date_str.split('(')[0] # '01/09(Fri)' -> '01/09'
            return pd.to_datetime(f"2026/{md}", format='%Y/%m/%d')
        return pd.to_datetime(date_str)
    except:
        return pd.NaT

def scan_and_extract_csv(uploaded_file):
    """빈칸이 난무하는 대시보드형 CSV에서 날짜 패턴을 추적하여 데이터를 낚아채는 스캐너"""
    raw_bytes = uploaded_file.getvalue()
    try: raw_text = raw_bytes.decode('utf-8-sig')
    except: raw_text = raw_bytes.decode('cp949', errors='ignore')
        
    reader = csv.reader(io.StringIO(raw_text))
    records = []
    
    # 정규식 패턴: '01/09(Fri)' 또는 '2026-01-09' 같은 날짜 모양을 감지
    date_pattern = re.compile(r'^\d{2}/\d{2}\(.*\)$') 
    date_pattern2 = re.compile(r'^\d{4}-\d{2}-\d{2}$') 
    
    for cols in reader:
        cols = [str(c).strip() for c in cols]
        
        for i, col in enumerate(cols):
            # 스캔하다가 날짜 모양의 데이터를 발견하면!
            if date_pattern.match(col) or date_pattern2.match(col):
                if i + 4 < len(cols): # 옆으로 데이터가 충분히 있는지 확인
                    date_str = col
                    main_cat = cols[i+1]
                    sub_cat = cols[i+2]
                    content_str = cols[i+3]
                    amount_str = cols[i+4]
                    asset_memo = cols[i+5] if i+5 < len(cols) else ""
                    t_type_raw = cols[i-1] if i > 0 else ""
                    
                    # 금액 정제 (숫자와 점, 마이너스만 남김)
                    amt_clean = re.sub(r'[^\d\.\-]', '', amount_str)
                    if not amt_clean: continue
                    try: amt_float = float(amt_clean)
                    except: continue
                        
                    # 타입 (수입/지출/저축) 자동 보정
                    if t_type_raw in ['고정지출', '변동지출']: t_type = '지출'
                    elif t_type_raw in ['수입', '저축', '지출']: t_type = t_type_raw
                    else:
                        if main_cat in ['월급', '기타소득', '상여']: t_type = '수입'
                        elif main_cat in ['예적금', '투자', '연금', '목적통장']: t_type = '저축'
                        else: t_type = '지출'
                        
                    records.append({
                        '날짜': date_str,
                        '타입': t_type,
                        '대분류': main_cat if main_cat else '미분류',
                        '소분류': sub_cat,
                        '내용': content_str,
                        '금액': amt_float,
                        '결제수단': asset_memo
                    })
    
    return pd.DataFrame(records)

def run_smart_categorization():
    df = st.session_state.ledger_data
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
    st.session_state.ledger_data = df
    return count

# ==========================================
# 레이아웃 구성
# ==========================================
st.title("📱 스마트 자산관리 시스템")
tab1, tab2, tab3 = st.tabs(["🏠 홈 요약", "📝 상세 내역", "🔄 데이터 연동"])

with tab1:
    st.subheader("재정 요약 대시보드")
    df = st.session_state.ledger_data.copy()
    if not df.empty:
        df['날짜_dt'] = df['날짜'].apply(safe_parse_date)
        df = df.dropna(subset=['날짜_dt']).sort_values('날짜_dt', ascending=False)
        
        income = abs(df[df['타입'] == '수입']['금액'].sum())
        expense = abs(df[df['타입'] == '지출']['금액'].sum())
        saving = abs(df[df['타입'] == '저축']['금액'].sum())
        balance = income - expense - saving
        
        col1, col2, col3 = st.columns(3)
        col1.metric("총 수입", f"{income:,.0f} 원")
        col2.metric("총 지출", f"{expense:,.0f} 원")
        col3.metric("총 저축(예적금)", f"{saving:,.0f} 원")
        st.metric("순현금 잔액", f"{balance:,.0f} 원")
        
        st.write("### 📂 지출 카테고리 비율")
        expense_df = df[df['타입'] == '지출'].copy()
        if not expense_df.empty:
            expense_df['절대값'] = expense_df['금액'].abs()
            fig = px.pie(expense_df, values='절대값', names='대분류', hole=0.4)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("데이터가 없습니다. '데이터 연동' 탭에서 CSV 파일을 올려주세요.")

with tab2:
    st.subheader("상세 거래 내역")
    if not st.session_state.ledger_data.empty:
        if st.button("🪄 미분류 항목 자동 매핑 실행"):
            cnt = run_smart_categorization()
            st.success(f"매핑 완료! 총 {cnt}건의 미분류 항목을 매칭했습니다.")
            st.rerun()
            
        df_display = st.session_state.ledger_data.copy()
        df_display['날짜_dt'] = df_display['날짜'].apply(safe_parse_date)
        df_display = df_display.sort_values('날짜_dt', ascending=False).drop(columns=['날짜_dt'])
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("거래 내역이 없습니다.")

with tab3:
    st.subheader("데이터 연동 센터")
    uploaded_file = st.file_uploader("PC에서 변환하신 '가계부.csv' 파일을 선택해 주세요.", type=["csv"])
    
    if uploaded_file is not None:
        if st.button("🚀 특수 스캔 엔진으로 분석 및 적용"):
            with st.spinner("복잡한 CSV 구조에서 데이터를 발라내는 중..."):
                parsed_df = scan_and_extract_csv(uploaded_file)
                
                if not parsed_df.empty:
                    st.session_state.ledger_data = parsed_df
                    st.balloons()
                    st.success(f"🎯 완벽합니다! 흩어진 표 안에서 총 **{len(parsed_df)}건의 실제 거래 내역**을 1초 만에 안전하게 추출했습니다. '🏠 홈 요약' 탭에서 차트를 확인해 보세요!")
                else:
                    st.error("🛑 날짜 패턴을 찾지 못했습니다. 올바른 파일인지 확인해 주세요.")
