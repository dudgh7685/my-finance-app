import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import re

# ==========================================
# [설정] 앱 기본 구성 및 스타일
# ==========================================
st.set_page_config(page_title="스마트 가계부 & 자산관리", page_icon="💰", layout="centered")
st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eaeaea; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# [원칙 3] 상태 관리(Session State) 완벽 통제
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
    if 'debug_mode' not in st.session_state:
        st.session_state.debug_mode = False
    if 'debug_logs' not in st.session_state:
        st.session_state.debug_logs = {}

init_session_state()

# ==========================================
# [원칙 1] 데이터 정제 (Cleansing) 함수
# ==========================================
def clean_dataframe(df):
    """결측치, 숨은 공백, 특수기호 등을 방어적으로 처리하는 데이터 클렌징 함수"""
    try:
        # 완전히 비어있는 행과 열 제거
        df = df.dropna(how='all').dropna(axis=1, how='all')
        # 컬럼명의 줄바꿈 및 좌우 공백 제거
        df.columns = [str(c).replace('\n', '').strip() for c in df.columns]
        # 모든 데이터의 앞뒤 공백 제거 및 결측치를 빈 문자열로 안전하게 변환
        df = df.fillna('').astype(str).map(lambda x: x.strip() if isinstance(x, str) else x)
        return df
    except Exception as e:
        return df # 실패 시 원본 반환 (앱 다운 방지)

def extract_numbers(val):
    """문자열에 섞인 콤마, 원, % 등을 제거하고 순수 숫자로 변환"""
    try:
        if pd.isna(val) or str(val).strip() == '': return 0.0
        cleaned = re.sub(r'[^\d\.\-]', '', str(val))
        return float(cleaned) if cleaned else 0.0
    except:
        return 0.0

# ==========================================
# 화면 레이아웃 시작
# ==========================================
st.title("📱 개인 자산관리 웹앱")
tab1, tab2, tab3, tab4 = st.tabs(["🏠 홈", "📝 내역", "📊 자산 및 신용", "🔄 데이터 연동"])

# ------------------------------------------
# TAB 1: 홈 / 대시보드
# ------------------------------------------
with tab1:
    st.subheader("이번 달 재정 요약")
    df = st.session_state.ledger_data.copy()
    
    if not df.empty and '날짜' in df.columns and '금액' in df.columns:
        df['금액_num'] = df['금액'].apply(extract_numbers)
        df['날짜_dt'] = pd.to_datetime(df['날짜'], errors='coerce')
        df = df.dropna(subset=['날짜_dt']) # 날짜로 변환 불가능한 찌꺼기 데이터 방어
        
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
                st.write("### 📂 카테고리별 지출 비율")
                expense_df['절대값'] = expense_df['금액_num'].abs()
                fig = px.pie(expense_df, values='절대값', names='대분류', hole=0.4)
                fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("'데이터 연동' 탭에서 데이터를 먼저 구성해 주세요.")

# ------------------------------------------
# TAB 2: 상세 내역
# ------------------------------------------
with tab2:
    st.subheader("상세 거래 내역")
    df_display = st.session_state.ledger_data.copy()
    
    if not df_display.empty and '날짜' in df_display.columns:
        df_display['금액_num'] = df_display['금액'].apply(extract_numbers)
        df_display['날짜_dt'] = pd.to_datetime(df_display['날짜'], errors='coerce')
        df_display = df_display.dropna(subset=['날짜_dt']).sort_values(by=['날짜_dt'], ascending=False)
        
        # 상위 50개만 렌더링 (모바일 속도 방어)
        st.dataframe(df_display.drop(columns=['금액_num', '날짜_dt']).head(50), use_container_width=True)
    else:
        st.info("거래 내역이 없습니다.")

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
# TAB 4: 데이터 연동 (핵심 방어적 파서)
# ------------------------------------------
with tab4:
    st.subheader("데이터 연동 센터")
    
    # 엑셀 확장을 명시적으로 선언하여 application/... 에러 방지
    uploaded_file = st.file_uploader("파일 업로드 (CSV, XLSX, XLSM)", type=["csv", "xlsx", "xlsm", "xls"])
    
    if uploaded_file is not None:
        if st.button("파일 분석 및 적용 (안전 모드)"):
            file_ext = uploaded_file.name.split('.')[-1].lower()
            success_count = 0
            
            try:
                # [1] 확장자에 따른 안전한 파일 읽기 (try-except 방어)
                st.session_state.debug_logs.clear()
                
                if file_ext in ['xlsx', 'xlsm', 'xls']:
                    try:
                        # 엑셀 파일은 시트가 여러 개일 수 있으므로 딕셔너리로 전체 로드
                        raw_data_dict = pd.read_excel(uploaded_file, sheet_name=None, engine='openpyxl')
                    except Exception as e:
                        st.error(f"엑셀 엔진 로드 실패 (openpyxl 설치 확인 필요): {e}")
                        st.stop()
                elif file_ext == 'csv':
                    try: raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
                    except: raw_df = pd.read_csv(uploaded_file, encoding='cp949', errors='ignore')
                    raw_data_dict = {"CSV_Data": raw_df}
                else:
                    st.error("지원하지 않는 포맷입니다.")
                    st.stop()

                # [2] 원칙 2: 추측 금지 -> 각 시트별 데이터 구조 스캔 및 매핑
                for sheet_name, raw_df in raw_data_dict.items():
                    df_clean = clean_dataframe(raw_df)
                    
                    # 로드된 데이터의 형태를 세션에 저장 (파싱 실패 시 디버깅용)
                    st.session_state.debug_logs[sheet_name] = df_clean.head(15)
                    
                    # 헤더 탐색 방어 로직: 엑셀 위쪽에 쓰레기값이 있을 경우를 대비해 '날짜' 또는 '금액'이 있는 행을 헤더로 승격
                    header_idx = -1
                    for idx, row in df_clean.head(20).iterrows():
                        row_strs = [str(x) for x in row.values]
                        if '날짜' in row_strs or '금액' in row_strs or '투자상품종류' in row_strs:
                            header_idx = idx
                            break
                    
                    if header_idx != -1:
                        df_clean.columns = df_clean.iloc[header_idx]
                        df_clean = df_clean.iloc[header_idx+1:].reset_index(drop=True)
                        df_clean.columns = [str(c).replace('\n', '').strip() for c in df_clean.columns]
                    
                    # 가계부 내역 시트 판단
                    if '날짜' in df_clean.columns and '금액' in df_clean.columns:
                        st.session_state.ledger_data = df_clean
                        success_count += 1
                        st.success(f"✅ '{sheet_name}' 시트 -> 가계부 내역으로 인식 성공!")
                    
                    # 투자 현황 시트 판단
                    elif '투자상품종류' in df_clean.columns and '투자원금' in df_clean.columns:
                        st.session_state.investment_data = df_clean
                        success_count += 1
                        st.success(f"✅ '{sheet_name}' 시트 -> 투자 자산으로 인식 성공!")
                        
                # [3] 원칙 2: 완벽 매핑이 안 되었을 경우 디버그 모드 활성화
                if success_count == 0:
                    st.session_state.debug_mode = True
                    st.warning("⚠️ 자동 데이터 매핑에 실패했습니다. 엑셀 파일의 구조가 일반적이지 않습니다.")
                else:
                    st.session_state.debug_mode = False
                    
            except Exception as e:
                st.error(f"데이터 처리 중 치명적 오류 발생: {e}")
                st.session_state.debug_mode = True

    # ------------------------------------------
    # 원칙 2: 팩트 체크를 위한 디버그 뷰어 (자동 활성화)
    # ------------------------------------------
    if st.session_state.get('debug_mode', False) and st.session_state.get('debug_logs'):
        st.error("🛑 **[엔지니어 진단 모드]** 아래 데이터 구조를 확인 후 저에게 알려주세요.")
        st.markdown("엑셀 파일이 어떻게 생겼는지 파이썬이 읽어들인 실제 원본 데이터를 출력합니다. **이 화면의 표 일부를 텍스트로 복사해서 저에게 주시면 완벽한 커스텀 파싱 코드를 즉시 짜드립니다.**")
        
        for sheet, debug_df in st.session_state.debug_logs.items():
            st.write(f"📂 **시트명: {sheet} (상위 15행)**")
            st.dataframe(debug_df, use_container_width=True)
