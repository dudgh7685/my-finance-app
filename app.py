import streamlit as st
import pandas as pd
import io

# [학습 엔진] 사용자의 분류 이력을 저장하는 세션 상태
if 'user_rules' not in st.session_state:
    st.session_state.user_rules = {} # {'지출처명': '분류명'}

def learn_from_2026_file(xlsm_file):
    """2026 가계부.xlsm 파일에서 사용자의 분류 패턴을 학습합니다."""
    try:
        df = pd.read_excel(xlsm_file, engine='openpyxl')
        # '내용' 컬럼과 '대분류' 컬럼이 있는 행을 학습
        if '내용' in df.columns and '대분류' in df.columns:
            for _, row in df.dropna(subset=['내용', '대분류']).iterrows():
                st.session_state.user_rules[str(row['내용']).strip()] = str(row['대분류']).strip()
            return len(st.session_state.user_rules)
    except:
        return 0

def run_smart_categorization():
    """학습된 패턴을 사용하여 미분류 항목을 매핑합니다."""
    df = st.session_state.ledger_data
    count = 0
    for idx, row in df.iterrows():
        content = str(row['내용']).strip()
        # 미분류이거나 분류가 비어있을 때
        if pd.isna(row['대분류']) or row['대분류'] in ['', '미분류']:
            if content in st.session_state.user_rules:
                df.at[idx, '대분류'] = st.session_state.user_rules[content]
                count += 1
    st.session_state.ledger_data = df
    return count

# [TAB 4 수정]
with tab4:
    st.subheader("학습 및 연동 센터")
    st.write("1. 먼저 '2026 가계부.xlsm'을 올려 분류 패턴을 학습시키세요.")
    st.write("2. 그 다음 가계부 내역 CSV를 올려 미분류 항목을 자동 정리하세요.")
    
    uploaded_file = st.file_uploader("파일 선택", type=["csv", "xlsm", "xlsx"])
    
    if uploaded_file is not None:
        if st.button("파일 분석 및 학습/적용"):
            if "2026" in uploaded_file.name:
                count = learn_from_2026_file(uploaded_file)
                st.success(f"✅ 사용자의 분류 패턴 {count}개를 학습 완료했습니다!")
            else:
                # 가계부 내역 업로드 및 자동 분류
                # (이전 코드의 파싱 로직 포함...)
                auto_count = run_smart_categorization()
                st.success(f"✅ 내역 적용 완료! (자동 분류된 항목: {auto_count}건)")
