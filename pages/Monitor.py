import streamlit as st
import pandas as pd
import time
import math
import os
from datetime import datetime, timedelta

# ==========================================
# 🚀 1. Supabase 연결
# ==========================================
try:
    from connection import get_supabase_client
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"❌ DB 연결 실패: {e}")
    st.stop()

# ==========================================
# ⚙️ 설정 및 초기화
# ==========================================
st.set_page_config(page_title="BESTROOM 모니터링", page_icon="🖥️", layout="wide", initial_sidebar_state="collapsed")

if 'zoom_level' not in st.session_state: st.session_state.zoom_level = 100
if 'page_index' not in st.session_state: st.session_state.page_index = 0

def get_korea_time():
    return datetime.utcnow() + timedelta(hours=9)

# ==========================================
# 🎨 [핵심] 줌 컨트롤러 & 스타일 (CSS)
# ==========================================
st.markdown(f"""
<style>
    /* 🔥 화면 줌 적용 */
    body {{ zoom: {st.session_state.zoom_level}%; }}

    /* 1. 배경 블랙 */
    .stApp, .main, [data-testid="stAppViewContainer"] {{ background-color: #000000 !important; color: #e0e0e0 !important; }}
    [data-testid="stSidebar"], [data-testid="collapsedControl"], header, footer {{ display: none !important; }}
    .block-container {{ padding-top: 1rem; padding-bottom: 3rem; max-width: 99% !important; }}

    /* 2. 줌 컨트롤러 (상단 고정 캡슐) - 페이지 표시 옆에 배치 */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) {{
        position: fixed !important;
        top: 20px;
        right: 150px; /* 페이지 번호(right:20px)의 왼쪽 */
        width: 160px !important;
        background: rgba(30,30,30,0.9);
        z-index: 999999;
        border-radius: 20px;
        padding: 2px 10px;
        border: 1px solid #444;
        align-items: center;
        gap: 0px !important;
    }}
    
    /* 줌 버튼 스타일 (투명하고 작게) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) button {{
        background: transparent !important;
        border: none !important;
        color: #aaa !important;
        font-size: 18px !important;
        padding: 0px !important;
        height: auto !important;
        min-height: 0px !important;
        line-height: 1 !important;
        margin-top: -3px; /* 수직 정렬 보정 */
    }}
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) button:hover {{ color: #00e5ff !important; }}
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) p {{ font-size: 14px; font-weight: bold; margin: 0; padding-top: 2px; color: #fff; }}

    /* 3. 페이지 번호 표시 (우측 상단 고정) */
    .page-indicator {{ 
        position: fixed; top: 20px; right: 20px; 
        background: rgba(20,20,20,0.8); color: #888; 
        padding: 5px 15px; border-radius: 15px; 
        font-weight: bold; font-size: 14px; border: 1px solid #333; 
        z-index: 999999;
    }}

    /* 4. 테이블 및 박스 스타일 */
    .metric-container {{ display: flex; gap: 15px; margin-bottom: 25px; justify-content: center; }}
    .metric-box {{ background: #111; border: 1px solid #333; border-radius: 12px; width: 18%; padding: 15px; text-align: center; box-shadow: 0 4px 15px rgba(255,255,255,0.05); }}
    .metric-title {{ font-size: 16px; color: #888; margin-bottom: 5px; font-weight: bold; }}
    .metric-num {{ font-size: 48px; font-weight: 900; line-height: 1; }}
    .tx-white {{ color: #fff; }} .tx-blue {{ color: #00e5ff; }} .tx-green {{ color: #00e676; }} .tx-orange {{ color: #ff9100; }}
    
    .smart-table {{ width: 100%; border-collapse: separate; border-spacing: 0 10px; }}
    .smart-table th {{ text-align: left; color: #666; font-size: 15px; padding: 10px 20px; border-bottom: 1px solid #333; font-weight: bold; }}
    .smart-row {{ background-color: #0a0a0a; }}
    .smart-cell {{ padding: 15px 20px; border-top: 1px solid #222; border-bottom: 1px solid #222; vertical-align: middle; }}
    .smart-row td:first-child {{ border-left: 1px solid #222; border-top-left-radius: 12px; border-bottom-left-radius: 12px; }}
    .smart-row td:last-child {{ border-right: 1px solid #222; border-top-right-radius: 12px; border-bottom-right-radius: 12px; }}
    
    .time-badge {{ background: #222; color: #aaa; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 14px; border: 1px solid #333; }}
    .lot-text {{ font-size: 15px; color: #4fc3f7; font-weight: bold; }}
    .cell-cust {{ font-size: 22px; font-weight: 900; color: #fff; }}
    .cell-prod {{ font-size: 15px; color: #888; }}
    .cell-size {{ font-size: 18px; color: #ffffff; font-weight: 900; }} 
    .spec-box {{ background-color: #111; border: 1px solid #444; color: #fff; padding: 12px; border-radius: 8px; font-size: 14px; font-family: 'Consolas', monospace; }}
    .secret-box {{ background: repeating-linear-gradient(45deg, #111, #111 10px, #1a1a1a 10px, #1a1a1a 20px); color: #777; border: 1px dashed #555; text-align: center; padding: 12px; border-radius: 8px; font-size: 14px; }}
    
    .status-container {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }}
    .status-badge {{ display: inline-block; padding: 5px 10px; border-radius: 15px; font-size: 12px; font-weight: 900; text-transform: uppercase; }}
    .pct-text {{ font-size: 13px; font-weight: 900; color: #fff; }}
    
    .badge-white {{ background: #333; color: #ccc; border: 1px solid #555; }}
    .badge-blue {{ background: #0277bd; color: white; border: 1px solid #0288d1; }}
    .badge-green {{ background: #2e7d32; color: white; border: 1px solid #388e3c; }}
    .badge-orange {{ background: #ef6c00; color: white; border: 1px solid #f57c00; }}
    .badge-red {{ background: #b71c1c; color: white; border: 1px solid #d32f2f; }}
    
    .mini-progress-bg {{ width: 100%; height: 6px; background: #222; border-radius: 3px; overflow: hidden; }}
    .mini-progress-fill {{ height: 100%; border-radius: 3px; transition: width 0.5s; }}
    .bg-w {{ background: #555; }} .bg-b {{ background: linear-gradient(90deg, #00e5ff, #2979ff); }} 
    .bg-g {{ background: linear-gradient(90deg, #00e676, #00c853); }} .bg-o {{ background: linear-gradient(90deg, #ff9100, #ff3d00); }} .bg-r {{ background: linear-gradient(90deg, #ff5252, #d50000); }}
    
    /* 하단 타이머 애니메이션 */
    @keyframes load-bar {{ 0% {{ width: 0%; }} 100% {{ width: 100%; }} }}
    .timer-bar-container {{ position: fixed; bottom: 0; left: 0; width: 100%; height: 6px; background-color: #111; z-index: 999999; }}
    .timer-bar-fill {{ height: 100%; background: linear-gradient(90deg, #00e5ff, #2979ff); box-shadow: 0 0 10px #00e5ff; animation: load-bar 5s linear infinite; }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔭 [플로팅] 미니 줌 컨트롤러 생성
# ==========================================
# 이 부분이 CSS에 의해 우측 상단 캡슐로 변신합니다.
z1, z2, z3 = st.columns([1, 2, 1])

if z1.button("➖"):
    st.session_state.zoom_level = max(50, st.session_state.zoom_level - 10)
    st.rerun()

z2.markdown(f"<div style='text-align:center;'>🔍 {st.session_state.zoom_level}%</div>", unsafe_allow_html=True)

if z3.button("➕"):
    st.session_state.zoom_level = min(200, st.session_state.zoom_level + 10)
    st.rerun()

# ==========================================
# 📊 데이터 로드 및 로직
# ==========================================
def load_data():
    try:
        res_orders = supabase.table("work_orders").select("*").order("created_at", desc=True).limit(50).execute()
        df = pd.DataFrame(res_orders.data)
        res_logs = supabase.table("production_logs").select("*").order("created_at", desc=True).limit(100).execute()
        df_log = pd.DataFrame(res_logs.data)
        
        if not df.empty: 
            df['short_time'] = pd.to_datetime(df['created_at']).dt.strftime('%m-%d %H:%M')
        return df, df_log
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

df, df_log = load_data()
ITEMS_PER_PAGE = 8

if not df.empty:
    cnt_ready = len(df[df['status'].str.contains("대기", na=False)])
    cnt_cut = len(df[df['status'].str.contains("Cut|커팅", na=False)])
    cnt_elec = len(df[df['status'].str.contains("전극", na=False)])
    cnt_lam = len(df[df['status'].str.contains("접합", na=False)])
    cnt_out = len(df[df['status'].str.contains("출고|완료", na=False)])
    
    total_pages = math.ceil(len(df) / ITEMS_PER_PAGE)
    if total_pages < 1: total_pages = 1
    
    if st.session_state.page_index >= total_pages: st.session_state.page_index = 0
    start = st.session_state.page_index * ITEMS_PER_PAGE
    df_view = df.iloc[start : start + ITEMS_PER_PAGE]
else:
    cnt_ready=cnt_cut=cnt_elec=cnt_lam=cnt_out=0; df_view=pd.DataFrame(); total_pages=1

# ==========================================
# 🖼️ 메인 레이아웃 (헤더 정리됨)
# ==========================================
c1, c2, c3 = st.columns([2, 6, 2])

with c1:
    logo_path = None
    if os.path.exists("pages/company_logo.png"): logo_path = "pages/company_logo.png"
    elif os.path.exists("company_logo.png"): logo_path = "company_logo.png"
    
    if logo_path: st.image(logo_path, width=300)
    else: st.markdown("### 🏭 BESTROOM", unsafe_allow_html=True)

with c2:
    now_time = get_korea_time().strftime("%H:%M:%S")
    st.markdown(f"<h1 style='font-size:36px;'>MONITOR <span style='color:#ffd700;'>{now_time}</span></h1>", unsafe_allow_html=True)

with c3:
    # 줌 버튼은 사라지고, 토글 스위치만 깔끔하게 남음
    st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True) # 줄맞춤용 여백
    col_t1, col_t2 = st.columns(2)
    with col_t1: is_cust_secure = st.toggle("🔒 고객", value=True)
    with col_t2: is_spec_secure = st.toggle("🔒 Spec", value=True)

# 페이지 번호 표시
st.markdown(f'<div class="page-indicator">PAGE {st.session_state.page_index + 1} / {total_pages}</div>', unsafe_allow_html=True)

# 상단 집계 박스
st.markdown(f"""
<div class="metric-container">
    <div class="metric-box"><div class="metric-title">⏳ 작업대기</div><div class="metric-num tx-white">{cnt_ready}</div></div>
    <div class="metric-box"><div class="metric-title">✂️ 커팅공정</div><div class="metric-num tx-blue">{cnt_cut}</div></div>
    <div class="metric-box"><div class="metric-title">⚡ 전극공정</div><div class="metric-num tx-blue">{cnt_elec}</div></div>
    <div class="metric-box"><div class="metric-title">🔥 접합공정</div><div class="metric-num tx-orange">{cnt_lam}</div></div>
    <div class="metric-box"><div class="metric-title">📦 완료/출고</div><div class="metric-num tx-green">{cnt_out}</div></div>
</div>""", unsafe_allow_html=True)

# 메인 테이블
if not df_view.empty:
    html = '<table class="smart-table"><thead><tr><th width="15%">TIME / LOT</th><th width="15%">CUSTOMER / PRODUCT</th><th width="19%">SIZE</th><th width="18%">STATUS (Process %)</th><th width="33%">SPECIFICATION</th></tr></thead><tbody>'
    
    for _, row in df_view.iterrows():
        lot = row['lot_no']; cust = row['customer']; prod = row['product']
        size = row['dimension']; spec = row['spec']; time_str = row.get('short_time','-')
        status_txt = str(row['status'])
        
        if is_cust_secure: cust_display = '<div class="secret-box">🔒 대외비</div>'
        else: cust_display = f'<div class="cell-cust">{cust}</div><div class="cell-prod">{prod}</div>'

        if is_spec_secure: spec_display = '<div class="secret-box">🔒 CONFIDENTIAL</div>'
        else: spec_display = f'<div class="spec-box">{spec}</div>'
        
        # 상태별 로직
        step_pct=5; badge="badge-white"; txt="작업 대기"; bar="bg-w"
        if not df_log.empty:
            my_logs = df_log[df_log['lot_no'] == lot]
            if not my_logs.empty:
                last_step = my_logs.iloc[-1]['step']
                if "Cut" in last_step: step_pct=25; txt="✂️ 커팅 중"; badge="badge-blue"; bar="bg-b"
                elif "전극" in last_step: step_pct=50; txt="⚡ 전극 중"; badge="badge-blue"; bar="bg-b"
                elif "접합" in last_step:
                    if "완료" in last_step: step_pct=100; txt="✅ 생산 완료"; badge="badge-green"; bar="bg-g"
                    else: step_pct=75; txt="🔥 접합 중"; badge="badge-orange"; bar="bg-o"
        
        # 상태 텍스트 오버라이드
        if "불량" in status_txt: step_pct=100; txt="⛔ 불량 발생"; badge="badge-red"; bar="bg-r"
        elif "완료" in status_txt: step_pct=100; txt="✅ 생산 완료"; badge="badge-green"; bar="bg-g"

        status_html = f"""
        <div style="display:flex; flex-direction:column; justify-content:center;">
            <div class="status-container">
                <span class="status-badge {badge}" style="font-size:11px; padding:4px 8px;">{txt}</span>
                <span class="pct-text" style="font-size:11px;">{step_pct}%</span>
            </div>
            <div class="mini-progress-bg"><div class="mini-progress-fill {bar}" style="width:{step_pct}%"></div></div>
        </div>
        """

        html += f"""<tr class="smart-row">
            <td class="smart-cell"><div class="time-badge">{time_str}</div><div class="lot-text">{lot}</div></td>
            <td class="smart-cell">{cust_display}</td>
            <td class="smart-cell"><div class="cell-size">{size}</div></td>
            <td class="smart-cell">{status_html}</td>
            <td class="smart-cell">{spec_display}</td>
        </tr>"""
    st.markdown(html + "</tbody></table>", unsafe_allow_html=True)
else:
    st.info("현재 표시할 작업 지시가 없습니다.")

# ==========================================
# 🔄 부드러운 하단 타이머 바
# ==========================================
st.markdown("""
<div class="timer-bar-container">
    <div class="timer-bar-fill"></div>
</div>
""", unsafe_allow_html=True)

time.sleep(5)
st.session_state.page_index = (st.session_state.page_index + 1) % total_pages

try: st.rerun()
except AttributeError: st.experimental_rerun()
