# 파일명: Admin.py
import streamlit as st
import streamlit.components.v1 as components 
from supabase import create_client, Client
from datetime import datetime
import pandas as pd
import qrcode
import io
import base64
import math
import time

# [필수] 메뉴 라이브러리
from streamlit_option_menu import option_menu 

from connection import get_supabase_client
supabase = get_supabase_client()

# ---------------------------------------------------------
# 1. 기본 설정 (가장 먼저!)
# ---------------------------------------------------------
st.set_page_config(page_title="(주)베스트룸 생산관리", page_icon="🏭", layout="wide")

# 세션 초기화
if 'order_list' not in st.session_state: st.session_state.order_list = []
if 'generated_qrs' not in st.session_state: st.session_state.generated_qrs = []
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'fabric_db' not in st.session_state: st.session_state.fabric_db = {}

# ---------------------------------------------------------
# 2. 사이드바 메뉴 (화면 그리기 최상단)
# ---------------------------------------------------------
with st.sidebar:
    # 메뉴를 가장 먼저 그립니다
    selected = option_menu(
        "메뉴 선택", 
        ["Admin", "Monitor", "Worker"], 
        icons=['gear', 'eye', 'person'], 
        menu_icon="cast", 
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "#fafafa"},
            "icon": {"color": "black", "font-size": "20px"}, 
            "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#4CAF50"},
        }
    )
    st.divider()

# ---------------------------------------------------------
# 3. 로그인 체크 (로그인 안되어 있으면 여기서 멈춤)
# ---------------------------------------------------------
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.info("🔒 생산관리 시스템 로그인")
        pwd = st.text_input("비밀번호", type="password")
        if st.button("로그인", use_container_width=True):
            if pwd == "1234":
                st.session_state.logged_in = True
                st.rerun()
            else: st.error("비밀번호 불일치")
    st.stop() # 로그인 안되면 아래 코드 실행 안 함

# ---------------------------------------------------------
# 4. 스타일 (인쇄용)
# ---------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #ffffff; }
    @media print {
        @page { size: A4 portrait; margin: 0; }
        body * { visibility: hidden; }
        .printable-area, .printable-area * { visibility: visible !important; color: black !important; }
        .printable-area { position: fixed; left: 0; top: 0; width: 210mm; height: 297mm; background: white; padding: 10mm; display: block; }
        header, footer, .stButton { display: none !important; }
        .qr-table { width: 100%; border-collapse: collapse; border: 1px solid black; }
        .qr-cell { width: 25%; height: 60mm; border: 1px solid black; text-align: center; vertical-align: middle; }
    }
    .printable-area { display: none; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 5. 공통 함수
# ---------------------------------------------------------
def image_to_base64(img):
    buffered = io.BytesIO(); img.save(buffered, format="PNG"); return base64.b64encode(buffered.getvalue()).decode()

def fetch_fabric_stock():
    try:
        response = supabase.table("fabric_stock").select("*").execute()
        return {row['lot_no']: row for row in response.data}
    except: return {}

# ---------------------------------------------------------
# 6. 페이지별 로직 (Admin / Worker / Monitor)
# ---------------------------------------------------------

if selected == "Admin":
    # === Admin 사이드바 ===
    st.sidebar.title("👨‍💼 지시서 설정") # 👈 제목이 여기 있어야 합니다!
    
    # 원단 정보 로드
    if not st.session_state.fabric_db: st.session_state.fabric_db = fetch_fabric_stock()
    if st.sidebar.button("🔄 재고 새로고침"): st.session_state.fabric_db = fetch_fabric_stock()

    # 입력 폼
    customer = st.sidebar.text_input("고객사명", "A건설")
    delivery_date = st.sidebar.date_input("출고 요청일")
    product_type = st.sidebar.selectbox("제품 종류", ["스마트글라스", "접합필름", "PDLC원단", "일반유리"])
    
    st.sidebar.markdown("---")
    fabric_lot = st.sidebar.text_input("원단 LOT", "Roll-2312-A")
    curr = st.session_state.fabric_db.get(fabric_lot)
    
    if curr: 
        st.sidebar.success(f"폭: {curr['width']}mm / 잔량: {curr['total_len'] - curr['used_len']:.1f}m")
    else: 
        st.sidebar.warning("원단 정보 없음")

    # === Admin 메인 화면 ===
    st.title("👨‍💼 관리자 페이지")
    tab1, tab2 = st.tabs(["작업 지시", "이력 조회"])
    
    with tab1:
        st.subheader("지시서 발행")
        # 여기에 지시서 발행 로직 (이전 코드의 내용)
        st.info("이곳에 작업 입력 폼이 표시됩니다.")

    with tab2:
        st.subheader("발행 이력")
        # 여기에 이력 조회 로직

elif selected == "Worker":
    st.title("👷 작업자 페이지")
    st.info("작업자 전용 화면입니다. (지시서 설정 메뉴가 안 보여야 정상)")
    
    # 작업자용 사이드바 예시
    with st.sidebar:
        st.success("작업자 모드 가동 중")
        st.text_input("작업자 ID 입력")

elif selected == "Monitor":
    st.title("🖥️ 모니터링")
    st.metric(label="오늘 생산량", value="15 EA", delta="3 EA")
