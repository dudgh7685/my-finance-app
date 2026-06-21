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
# 🧠 [영구 내장] 사용자 맞춤형 소비 분류 사전
# 보내주신 정형 텍스트의 패턴을 완벽히 하드코딩하여 탑재했습니다.
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
    if 'investment_data' not in st.session_state:
        st.session_state.investment_data = pd.DataFrame(columns=['투자상품종류', '금융사', '상품명', '투자원금', '평가금액', '수익률'])
    if 'insurance_data' not in st.session_state:
        st.session_state.insurance_data = pd.DataFrame(columns=['금융사', '상품명', '상태', '납입금액'])

init_session_state()

# ==========================================
# [원칙 1] 초정밀 수직 블록 파싱 모듈
# ==========================================
def extract_numbers(val):
    try:
        if pd.isna(val) or str(val).strip() == '': return 0.0
        cleaned = re.sub(r'[^\d\.\-]', '', str(val))
        return float(cleaned) if cleaned else 0.0
    except:
        return 0.0

def parse_vertical_block_file(uploaded_file):
    """수직으로 적재된 다중 카테고리 시트를 줄 단위로 정밀 분해하는 파서"""
    file_name = uploaded_file.name
    file_ext = file_name.split('.')[-1].lower()
    
    if file_ext in ['xlsx', 'xls', 'xlsm']:
        df_raw = pd.read_excel(uploaded_file, sheet_name=0, engine='openpyxl')
    else:
        try: df_raw = pd.read_csv(uploaded_file, encoding='utf-8-sig')
        except: df_raw = pd.read_csv(uploaded_file, encoding='cp949', errors='ignore')
        
    records = []
    current_type = "지출" # 기본값
    
    for _, row in df_raw.iterrows():
        # 데이터 정제 및 양끝 공백 제거
        vals = [str(x).strip() if pd.notna(x) and str(x).strip().lower() != 'nan' else '' for x in row.values]
        
        # 완전히 비어있는 여백 행 패스
        if all(x == '' for x in vals): continue
        
        # 왼쪽 여백 열 제거
        while vals and vals[0] == '': 
            vals = vals[1:]
            
        row_str = " ".join(vals)
        
        # 1. 섹션 헤더 블록 감지 (예: 수입 2,236,320원 block)
        if 'block' in row_str or ('내역' in row_str and ('수입' in row_str or '저축' in row_str or '지출' in row_str)):
            if '수입' in row_str: current_type = '수입'
            elif '저축' in row_str: current_type = '저축'
            elif '지출' in row_str: current_type = '지출'
            continue
            
        # 2. 컬럼명 타이틀 행 패스
        if '날짜' in vals: continue
        
        # 3. b열 인덱스 숫자 밀림 현상 방어 및 자동 보정
        if len(vals) >= 5:
            if '/' not in vals[0] and '-' not in vals[0] and ('/' in vals[1] or '-' in vals[1]):
                vals = vals[1:] # 맨 앞 인덱스 열을 탈락시켜 정렬 맞춤
                
        # 4. 실제 데이터 파싱 추출
        if len(vals) >= 5:
            date_str = vals[0]
            if '/' in date_str or '-' in date_str:
                main_cat = vals[1]
                sub_cat = vals[2]
                content = vals[3]
                amount = vals[4]
                asset = vals[5] if len(vals) > 5 else ""
                
                # 상단 헤더 찌꺼기 2차 방어
                if main_cat in ['대분류', 'nan', ''] or content in ['사용내역', '수입 내역', '저축 내역']:
                    continue
                    
                records.append({
                    '날짜': date_str,
                    '타입': current_type,
                    '대분류': main_cat if main_cat else '미분류',
                    '소분류': sub_cat,
                    '내용': content,
                    '금액': amount,
                    '결제수단': asset
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
tab1, tab2, tab3, tab4 = st.tabs(["🏠 홈", "📝 상세 내역", "📊 자산 현황", "🔄 데이터 연동"])

with tab1:
    st.subheader("이번 달 재정 요약")
    df = st.session_state.ledger_data.copy()
    if not df.empty and '날짜' in df.columns and '금액' in df.columns:
        df['금액_num'] = df['금액'].apply(extract_numbers)
        df['날짜_dt'] = pd.to_datetime(df['날짜'].str.split('(').str[0], format='%m/%d', errors='coerce')
        df = df.dropna(subset=['날짜_dt'])
        
        if not df.empty:
            income = abs(df[df['타입'] == '수입']['금액_num'].sum())
            expense = abs(df[df['타입'] == '지출']['금액_num'].sum())
            saving = abs(df[df['타입'] == '저축']['금액_num'].sum())
            balance = income - expense - saving
            
            col1, col2, col3 = st.columns(3)
            col1.metric("총 수입", f"{income:,.0f} 원")
            col2.metric("총 지출", f"{expense:,.0f} 원")
            col3.metric("총 저축", f"{saving:,.0f} 원")
            st.metric("순현금 잔액", f"{balance:,.0f} 원")
            
            if '대분류' in df.columns:
                st.write("### 📂 주요 지출 분포")
                expense_df = df[df['타입'] == '지출'].copy()
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
        if st.button("🪄 미분류 항목 자동 매핑 실행"):
            cnt = run_smart_categorization()
            st.success(f"매핑 완료! 총 {cnt}건의 미분류 항목을 매칭했습니다.")
            st.rerun()
            
    st.dataframe(st.session_state.ledger_data, use_container_width=True)

with tab3:
    st.subheader("자산 및 금융 현황")
    st.info("체크카드 및 주거래 통장 연동 대기 중")

with tab4:
    st.subheader("데이터 연동 센터")
    uploaded_file = st.file_uploader("가계부 내역 파일 업로드 (CSV, XLSX, XLSM)", type=["csv", "xlsx", "xlsm", "xls"])
    
    if uploaded_file is not None:
        # 무조건 결과를 보여주는 직관적인 버튼 인터페이스
        if st.button("🚀 파일 분석 및 적용하기"):
            with st.spinner("엑셀 구조 정밀 해체 중..."):
                parsed_df = parse_vertical_block_file(uploaded_file)
                
                if not parsed_df.empty:
                    st.session_state.ledger_data = parsed_df
                    st.balloons()
                    st.success(f"🎯 분석 성공! 수직 구조 파일에서 {len(parsed_df)}개의 가계부 데이터를 안전하게 추출해 연동했습니다. '🏠 홈' 이나 '📝 상세 내역' 탭으로 가보세요!")
                else:
                    st.error("🛑 파일 분석 실패: 업로드한 파일에서 유효한 날짜 및 금액 데이터 포맷을 찾을 수 없습니다. 파일 내용을 다시 확인해 주세요.")
