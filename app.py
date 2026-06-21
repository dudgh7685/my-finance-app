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

# [방어적 폴백 규칙] 학습 데이터가 없을 때를 대비한 기본 방어선
FALLBACK_RULES = {
    '식비': ['마트', '편의점', '식당', '배달', '커피', '카페', '치킨', '국군복지단'],
    '주거/통신': ['관리비', '통신', '가스', '전기', '사령부', '세종텔레콤'],
    '교통/차량': ['교통대금', '버스', '택시', '코레일', '주유', '하이패스'],
    '생활/쇼핑': ['네이버페이', '카카오페이', '쿠팡', '다이소'],
    '저축/투자': ['증권', '투자', '저축', '예금', '적금']
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
    if 'user_rules' not in st.session_state:
        st.session_state.user_rules = {} # 핵심: 사용자 맞춤형 학습 딕셔너리

init_session_state()

# ==========================================
# [원칙 1] 데이터 클렌징 및 지능형 매핑 로직
# ==========================================
def clean_dataframe(df):
    """결측치, 공백, 줄바꿈을 완벽히 방어하는 전처리 함수"""
    try:
        df = df.dropna(how='all').dropna(axis=1, how='all')
        df.columns = [str(c).replace('\n', '').strip() for c in df.columns]
        df = df.fillna('').astype(str).map(lambda x: x.strip() if isinstance(x, str) else x)
        return df
    except:
        return df

def extract_numbers(val):
    """섞여 있는 특수문자를 제거하고 순수 숫자로만 변환"""
    try:
        if pd.isna(val) or str(val).strip() == '': return 0.0
        cleaned = re.sub(r'[^\d\.\-]', '', str(val))
        return float(cleaned) if cleaned else 0.0
    except:
        return 0.0

def learn_user_patterns(raw_data_dict):
    """2026 가계부.xlsm 에서 사용자의 기존 분류 규칙을 추출해 학습합니다."""
    learned_count = 0
    for sheet_name, df_raw in raw_data_dict.items():
        df = clean_dataframe(df_raw)
        
        # 헤더 방어적 탐색
        header_idx = -1
        for idx, row in df.head(20).iterrows():
            row_strs = [str(x) for x in row.values]
            if '내용' in row_strs and '대분류' in row_strs:
                header_idx = idx
                break
        
        if header_idx != -1:
            df.columns = df.iloc[header_idx]
            df = df.iloc[header_idx+1:].reset_index(drop=True)
            df.columns = [str(c).replace('\n', '').strip() for c in df.columns]
            
            # 패턴 추출 (내용 -> 대분류)
            if '내용' in df.columns and '대분류' in df.columns:
                for _, row in df.iterrows():
                    content = str(row['내용']).strip()
                    category = str(row['대분류']).strip()
                    
                    if content and category and category not in ['미분류', '', 'nan']:
                        if content not in st.session_state.user_rules or st.session_state.user_rules[content] != category:
                            st.session_state.user_rules[content] = category
                            learned_count += 1
    return learned_count

def run_smart_categorization():
    """학습된 패턴을 바탕으로 미분류 데이터를 자동 정리합니다."""
    df = st.session_state.ledger_data
    if df.empty or '내용' not in df.columns or '대분류' not in df.columns:
        return 0, 0
    
    user_count, fallback_count = 0, 0
    mask = df['대분류'].isna() | (df['대분류'] == '') | (df['대분류'].str.contains('미분류', na=False))
    
    for idx, row in df[mask].iterrows():
        content = str(row['내용']).strip()
        
        # 1순위: 사용자가 직접 분류했던 이력 매핑
        if content in st.session_state.user_rules:
            df.at[idx, '대분류'] = st.session_state.user_rules[content]
            user_count += 1
            continue
            
        # 2순위: 기본 제공되는 폴백 키워드로 매핑
        for category, keywords in FALLBACK_RULES.items():
            if any(keyword in content for keyword in keywords):
                df.at[idx, '대분류'] = category
                fallback_count += 1
                break
                
    st.session_state.ledger_data = df
    return user_count, fallback_count

# ==========================================
# 화면 레이아웃 
# ==========================================
st.title("📱 스마트 자산관리 시스템")
tab1, tab2, tab3, tab4 = st.tabs(["🏠 홈", "📝 상세 내역", "📊 자산 현황", "🔄 연동 및 학습"])

# ------------------------------------------
# TAB 1: 홈
# ------------------------------------------
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
            
            income = abs(month_df[month_df['타입'] == '수입']['금액_num'].sum())
            expense = abs(month_df[month_df['타입'] == '지출']['금액_num'].sum())
            balance = income - expense
            
            col1, col2 = st.columns(2)
            col1.metric("이번 달 총 수입", f"{income:,.0f} 원")
            col2.metric("이번 달 총 지출", f"{expense:,.0f} 원", f"-{expense:,.0f} 원", delta_color="inverse")
            st.metric("당월 순현금흐름", f"{balance:,.0f} 원", f"{balance:,.0f} 원")
            
            expense_df = month_df[month_df['타입'] == '지출'].copy()
            if not expense_df.empty and '대분류' in expense_df.columns:
                st.write("### 📂 지출 비율")
                expense_df['절대값'] = expense_df['금액_num'].abs()
                fig = px.pie(expense_df, values='절대값', names='대분류', hole=0.4)
                fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("데이터가 없습니다. '연동' 탭을 이용해 주세요.")

# ------------------------------------------
# TAB 2: 상세 내역 및 [지능형 자동 분류]
# ------------------------------------------
with tab2:
    st.subheader("상세 거래 내역")
    
    # 지능형 분류기 실행 버튼
    if not st.session_state.ledger_data.empty:
        colA, colB = st.columns([3, 1])
        with colA:
            st.caption(f"🧠 현재 학습된 사용자 고유 패턴: {len(st.session_state.user_rules)}개")
        with colB:
            if st.button("🪄 미분류 자동 정리"):
                user_cnt, fb_cnt = run_smart_categorization()
                st.success(f"분류 완료! (사용자 패턴: {user_cnt}건, 기본 패턴: {fb_cnt}건)")

    df_display = st.session_state.ledger_data.copy()
    if not df_display.empty and '날짜' in df_display.columns:
        df_display['금액_num'] = df_display['금액'].apply(extract_numbers)
        df_display['날짜_dt'] = pd.to_datetime(df_display['날짜'], errors='coerce')
        df_display = df_display.dropna(subset=['날짜_dt']).sort_values(by=['날짜_dt'], ascending=False)
        st.dataframe(df_display.drop(columns=['금액_num', '날짜_dt']).head(100), use_container_width=True)
    else:
        st.info("표시할 내역이 없습니다.")

# ------------------------------------------
# TAB 3: 자산 및 신용
# ------------------------------------------
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

# ------------------------------------------
# TAB 4: 데이터 연동 (학습 + 파싱 완벽 통합)
# ------------------------------------------
with tab4:
    st.subheader("데이터 연동 및 패턴 학습 센터")
    st.info("💡 팁: '2026 가계부.xlsm' 파일을 먼저 올리면 사용자님의 분류 방식을 인공지능이 즉시 학습합니다.")
    
    uploaded_file = st.file_uploader("파일 업로드 (CSV, XLSX, XLSM)", type=["csv", "xlsx", "xlsm", "xls"])
    
    if uploaded_file is not None:
        if st.button("파일 분석 및 적용 (안전 모드)"):
            file_name = uploaded_file.name
            file_ext = file_name.split('.')[-1].lower()
            
            try:
                # 1. 파일 안전 로드
                raw_data_dict = {}
                if file_ext in ['xlsx', 'xlsm', 'xls']:
                    raw_data_dict = pd.read_excel(uploaded_file, sheet_name=None, engine='openpyxl')
                else:
                    try: raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
                    except: raw_df = pd.read_csv(uploaded_file, encoding='cp949', errors='ignore')
                    raw_data_dict = {"CSV_Data": raw_df}

                # 2. [학습 엔진 동작] 2026 가계부 파일이 올라왔을 때
                if "2026" in file_name or "가계부.xls" in file_name:
                    learned_rules = learn_user_patterns(raw_data_dict)
                    if learned_rules > 0:
                        st.success(f"🧠 학습 완료! 엑셀 파일에서 {learned_rules}개의 사용자 전용 분류 패턴을 습득했습니다.")
                    else:
                        st.warning("학습할 패턴을 찾지 못했습니다. '내용'과 '대분류' 컬럼이 있는지 확인하세요.")

                # 3. [가계부 내역 동작]
                if "내역" in file_name or ("가계부" in file_name and file_ext == "csv"):
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
                            st.success(f"✅ 거래 내역 {len(df_clean)}건 동기화 완료! ('내역' 탭에서 자동 분류를 실행하세요)")

                # 4. [뱅샐 현황 동작] 콤마 밀림 현상 방어 라인 바이 라인 파싱
                if "현황" in file_name or "뱅샐" in file_name:
                    if file_ext == 'csv':
                        uploaded_file.seek(0)
                        try: raw_text = uploaded_file.getvalue().decode('utf-8-sig')
                        except: raw_text = uploaded_file.getvalue().decode('cp949', errors='ignore')
                        
                        lines = raw_text.split('\n')
                        invest_rows, ins_rows = [], []
                        for line in lines:
                            cols = [c.strip() for c in line.split(',') if c.strip() != '']
                            if len(cols) < 4: continue
                            
                            if '남' in cols or '여' in cols:
                                try: st.session_state.user_info["신용점수"] = int(cols[3])
                                except: pass
                            if cols[0] in ["주식", "펀드", "채권", "투자"] and len(cols) >= 6:
                                invest_rows.append({'투자상품종류': cols[0], '금융사': cols[1], '상품명': cols[2], '투자원금': cols[3], '평가금액': cols[4], '수익률': cols[5]})
                            if ('보험' in cols[0] or '생명' in cols[0]) and len(cols) >= 4:
                                ins_rows.append({'금융사': cols[0], '상품명': cols[1], '상태': cols[2], '납입금액': cols[3]})
                                
                        if invest_rows: st.session_state.investment_data = pd.DataFrame(invest_rows)
                        if ins_rows: st.session_state.insurance_data = pd.DataFrame(ins_rows)
                        st.success("✅ 자산 현황 (신용, 투자, 보험) 동기화 완료!")

            except Exception as e:
                st.error(f"데이터 처리 중 치명적 오류 발생: {e}")
