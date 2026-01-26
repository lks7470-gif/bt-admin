import streamlit as st
import pandas as pd
import time
import math
import os
from datetime import datetime, timedelta

# ==========================================
# 🚀 1. Supabase 연결 (connection.py 사용)
# ==========================================
try:
    from connection import get_supabase_client
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"❌ DB 연결 실패: {e}")
    st.stop()

# ==========================================
# ⚙️ 설정 및 스타일
# ==========================================
st.set_page_config(page_title="BESTROOM 모니터링", page_icon="🖥️", layout="wide", initial_sidebar_state="collapsed")

def get_korea_time():
    return datetime.utcnow() + timedelta(hours=9)

# CSS 스타일 정의
st.markdown("""
<style>
    /* 1. 기본 배경 블랙 설정 */
    .stApp, .main, [data-testid="stAppViewContainer"] { background-color: #000000 !important; color: #e0e0e0 !important; }
    [data-testid="stSidebar"], [data-testid="collapsedControl"], header, footer { display: none !important; }
    .block-container { padding-top: 1rem; padding-bottom: 3rem; max-width: 99% !important; }
    
    /* 2. 상단 집계 박스 스타일 (7단계) */
    .metric-container { display: flex; gap: 10px; margin-bottom: 25px; justify-content: center; }
    .metric-box { 
        background: #111; border: 1px solid #333; border-radius: 10px; 
        width: 13.5%; /* 7개 박스 균등 분할 */
        padding: 12px 5px; text-align: center; box-shadow: 0 4px 15px rgba(255,255,255,0.05); 
    }
    .metric-title { font-size: 14px; color: #888; margin-bottom: 5px; font-weight: bold; white-space: nowrap; }
    .metric-num { font-size: 42px; font-weight: 900; line-height: 1; }
    
    /* 텍스트 컬러 유틸리티 */
    .tx-white { color: #fff; } 
    .tx-blue { color: #00e5ff; } 
    .tx-purple { color: #d500f9; } 
    .tx-yellow { color: #ffeb3b; }
    .tx-orange { color: #ff9100; } 
    .tx-green { color: #00e676; } 
    
    /* 3. 테이블 스타일 */
    .smart-table { width: 100%; border-collapse: separate; border-spacing: 0 10px; }
    .smart-table th { text-align: left; color: #666; font-size: 15px; padding: 10px 20px; border-bottom: 1px solid #333; font-weight: bold; }
    .smart-row { background-color: #0a0a0a; }
    .smart-cell { padding: 15px 20px; border-top: 1px solid #222; border-bottom: 1px solid #222; vertical-align: middle; }
    .smart-row td:first-child { border-left: 1px solid #222; border-top-left-radius: 12px; border-bottom-left-radius: 12px; }
    .smart-row td:last-child { border-right: 1px solid #222; border-top-right-radius: 12px; border-bottom-right-radius: 12px; }
    
    /* 4. 각종 뱃지 및 폰트 */
    .time-badge { background: #222; color: #aaa; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 14px; border: 1px solid #333; }
    .lot-text { font-size: 15px; color: #4fc3f7; font-weight: bold; }
    .cell-cust { font-size: 22px; font-weight: 900; color: #fff; }
    .cell-prod { font-size: 15px; color: #888; }
    .cell-size { font-size: 18px; color: #ffffff; font-weight: 900; } 
    
    .spec-box { background-color: #111; border: 1px solid #444; color: #fff; padding: 12px; border-radius: 8px; font-size: 14px; font-family: 'Consolas', monospace; }
    .secret-box { background: repeating-linear-gradient(45deg, #111, #111 10px, #1a1a1a 10px, #1a1a1a 20px); color: #777; border: 1px dashed #555; text-align: center; padding: 12px; border-radius: 8px; font-size: 14px; }
    
    .status-container { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
    .status-badge { display: inline-block; padding: 5px 10px; border-radius: 15px; font-size: 12px; font-weight: 900; text-transform: uppercase; }
    .pct-text { font-size: 13px; font-weight: 900; color: #fff; }
    
    /* 뱃지 컬러 */
    .badge-white { background: #333; color: #ccc; border: 1px solid #555; }
    .badge-blue { background: #0277bd; color: white; border: 1px solid #0288d1; }
    .badge-purple { background: #7b1fa2; color: white; border: 1px solid #ba68c8; }
    .badge-yellow { background: #fbc02d; color: black; border: 1px solid #fdd835; }
    .badge-orange { background: #ef6c00; color: white; border: 1px solid #f57c00; }
    .badge-green { background: #2e7d32; color: white; border: 1px solid #388e3c; }
    .badge-red { background: #b71c1c; color: white; border: 1px solid #d32f2f; }
    
    /* 5. 미니 프로그레스 바 */
    .mini-progress-bg { width: 100%; height: 6px; background: #222; border-radius: 3px; overflow: hidden; }
    .mini-progress-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
    .bg-w { background: #555; } 
    .bg-b { background: linear-gradient(90deg, #00e5ff, #2979ff); } 
    .bg-p { background: linear-gradient(90deg, #d500f9, #aa00ff); } 
    .bg-y { background: linear-gradient(90deg, #ffeb3b, #fbc02d); }
    .bg-o { background: linear-gradient(90deg, #ff9100, #ff3d00); } 
    .bg-g { background: linear-gradient(90deg, #00e676, #00c853); } 
    .bg-r { background: linear-gradient(90deg, #ff5252, #d50000); }
    
    /* 6. 페이지 번호 표시 */
    .page-indicator { position: fixed; top: 20px; right: 20px; background: rgba(20,20,20,0.8); color: #888; padding: 5px 15px; border-radius: 15px; font-weight: bold; font-size: 14px; border: 1px solid #333; }

    /* 하단 타이머 바 */
    @keyframes load-bar { 0% { width: 0%; } 100% { width: 100%; } }
    .timer-bar-container { position: fixed; bottom: 0; left: 0; width: 100%; height: 6px; background-color: #111; z-index: 999999; }
    .timer-bar-fill { height: 100%; background: linear-gradient(90deg, #00e5ff, #2979ff); box-shadow: 0 0 10px #00e5ff; animation: load-bar 5s linear infinite; }
</style>
""", unsafe_allow_html=True)

if 'page_index' not in st.session_state: st.session_state.page_index = 0

def load_data():
    try:
        res_orders = supabase.table("work_orders").select("*").order("created_at", desc=True).limit(100).execute()
        df = pd.DataFrame(res_orders.data)
        res_logs = supabase.table("production_logs").select("*").order("created_at", desc=True).limit(200).execute()
        df_log = pd.DataFrame(res_logs.data)
        
        if not df.empty: 
            df['short_time'] = pd.to_datetime(df['created_at']).dt.strftime('%m-%d %H:%M')
        return df, df_log
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

df, df_log = load_data()
ITEMS_PER_PAGE = 8

# 집계 카운터 초기화
cnt_ready = 0
cnt_full = 0
cnt_half = 0
cnt_elec = 0
cnt_lam_wait = 0
cnt_lam_ing = 0
cnt_done = 0

if not df.empty:
    # ------------------------------------------------
    # 📊 상단 박스 집계 로직
    # ------------------------------------------------
    for _, row in df.iterrows():
        s = str(row['status'])
        
        if "불량" in s:
            pass 
        elif "완료" in s or "출고" in s:
            cnt_done += 1
        elif "접합대기" in s:
            cnt_lam_wait += 1
        elif "접합" in s: # 접합 진행중 (완료X, 대기X)
            cnt_lam_ing += 1
        elif "전극" in s:
            cnt_elec += 1
        elif "Half" in s or "하프" in s:
            cnt_half += 1
        elif "Full" in s or "풀" in s or "원단" in s or "Cut" in s:
            cnt_full += 1
        elif "대기" in s:
            cnt_ready += 1

    total_pages = math.ceil(len(df) / ITEMS_PER_PAGE)
    if total_pages < 1: total_pages = 1
    
    if st.session_state.page_index >= total_pages: st.session_state.page_index = 0
    start = st.session_state.page_index * ITEMS_PER_PAGE
    df_view = df.iloc[start : start + ITEMS_PER_PAGE]
else:
    df_view=pd.DataFrame(); total_pages=1

# ==========================================
# 🖼️ 레이아웃 구성
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
    # [수정] 자동전환 / 고객사 / SPEC 토글을 한 줄에 배치
    c3_1, c3_2, c3_3 = st.columns(3)
    with c3_1: is_auto_play = st.toggle("▶️ 자동전환", value=True)
    with c3_2: is_cust_secure = st.toggle("🔒 고객사", value=True)
    with c3_3: is_spec_secure = st.toggle("🔒 SPEC", value=True)

st.markdown(f'<div class="page-indicator">PAGE {st.session_state.page_index + 1} / {total_pages}</div>', unsafe_allow_html=True)

# ------------------------------------------------
# 📊 상단 집계 박스 (7개 구분)
# ------------------------------------------------
st.markdown(f"""
<div class="metric-container">
    <div class="metric-box"><div class="metric-title">⏳ 작업대기</div><div class="metric-num tx-white">{cnt_ready}</div></div>
    <div class="metric-box"><div class="metric-title">✂️ 풀커팅</div><div class="metric-num tx-blue">{cnt_full}</div></div>
    <div class="metric-box"><div class="metric-title">🔪 하프커팅</div><div class="metric-num tx-purple">{cnt_half}</div></div>
    <div class="metric-box"><div class="metric-title">⚡ 전극공정</div><div class="metric-num tx-blue">{cnt_elec}</div></div>
    <div class="metric-box"><div class="metric-title">⏳ 접합대기</div><div class="metric-num tx-yellow">{cnt_lam_wait}</div></div>
    <div class="metric-box"><div class="metric-title">🔥 접합중</div><div class="metric-num tx-orange">{cnt_lam_ing}</div></div>
    <div class="metric-box"><div class="metric-title">📦 생산완료</div><div class="metric-num tx-green">{cnt_done}</div></div>
</div>""", unsafe_allow_html=True)

# 메인 테이블
if not df_view.empty:
    html = '<table class="smart-table"><thead><tr><th width="15%">TIME / LOT</th><th width="15%">CUSTOMER / PRODUCT</th><th width="19%">SIZE</th><th width="18%">STATUS (Process %)</th><th width="33%">SPECIFICATION</th></tr></thead><tbody>'
    
    for _, row in df_view.iterrows():
        lot = row['lot_no']; cust = row['customer']; prod = row['product']
        size = row['dimension']; spec = row['spec']; time_str = row.get('short_time','-')
        status_txt_db = str(row['status'])
        
        if is_cust_secure: cust_display = '<div class="secret-box">🔒 대외비</div>'
        else: cust_display = f'<div class="cell-cust">{cust}</div><div class="cell-prod">{prod}</div>'

        if is_spec_secure: spec_display = '<div class="secret-box">🔒 CONFIDENTIAL</div>'
        else: spec_display = f'<div class="spec-box">{spec}</div>'
        
        # -----------------------------------------------------------
        # 🔥 상태 및 퍼센트 계산 로직 (단품 vs 일반)
        # -----------------------------------------------------------
        step_pct = 5; badge = "badge-white"; txt = "작업 대기"; bar = "bg-w"
        
        # 단품 여부 확인
        is_short_product = "단품" in status_txt_db or "생략" in str(spec) or "No Lam" in str(spec)

        # 로그 기반 상세 상태 추적 (DB 상태값이 없을 경우 대비)
        if not df_log.empty:
            my_logs = df_log[df_log['lot_no'] == lot]
            if not my_logs.empty:
                last_step = str(my_logs.iloc[-1]['step'])
                
                # (A) 커팅
                if "Full" in last_step or "풀" in last_step or "원단" in last_step:
                    step_pct = 20 if not is_short_product else 30
                    txt = "✂️ 원단 풀커팅"
                    badge = "badge-blue"; bar = "bg-b"
                elif "Half" in last_step or "하프" in last_step:
                    step_pct = 40 if not is_short_product else 60
                    txt = "🔪 정밀 하프커팅"
                    badge = "badge-purple"; bar = "bg-p"
                
                # (B) 전극
                elif "전극" in last_step:
                    if is_short_product:
                        step_pct = 100
                        txt = "✅ 생산 완료 (단품)"
                        badge = "badge-green"; bar = "bg-g"
                    else:
                        step_pct = 60
                        txt = "⚡ 전극 부착"
                        badge = "badge-blue"; bar = "bg-b"
                
                # (C) 접합
                elif "접합" in last_step:
                    if "완료" in last_step:
                        step_pct = 100
                        txt = "✅ 생산 완료"
                        badge = "badge-green"; bar = "bg-g"
                    elif "대기" in last_step:
                        step_pct = 70
                        txt = "⏳ 접합 대기"
                        badge = "badge-yellow"; bar = "bg-y"
                    else:
                        step_pct = 85
                        txt = "🔥 접합 진행중"
                        badge = "badge-orange"; bar = "bg-o"
        
        # DB 상태값 최우선 오버라이드 (완료/대기/진행중 구분)
        if "접합대기" in status_txt_db:
            step_pct = 70
            txt = "⏳ 접합 대기"
            badge = "badge-yellow"; bar = "bg-y"
        elif "접합" in status_txt_db and "대기" not in status_txt_db: # 그냥 '접합' 상태라면 진행중
             step_pct = 85
             txt = "🔥 접합 진행중"
             badge = "badge-orange"; bar = "bg-o"
        elif "불량" in status_txt_db: 
            step_pct = 100
            txt = "⛔ 불량 발생"
            badge = "badge-red"; bar = "bg-r"
        elif "완료" in status_txt_db or "출고" in status_txt_db:
            step_pct = 100
            txt = "✅ 생산 완료"
            badge = "badge-green"; bar = "bg-g"

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

# [수정] 자동전환 기능이 켜져있을 때만 타이머바 표시 및 페이지 넘김
if is_auto_play:
    st.markdown("""
    <div class="timer-bar-container">
        <div class="timer-bar-fill"></div>
    </div>
    """, unsafe_allow_html=True)

    time.sleep(5)
    st.session_state.page_index = (st.session_state.page_index + 1) % total_pages
    try: st.rerun()
    except AttributeError: st.experimental_rerun()
else:
    # 정지 상태일 때 표시할 UI
    st.info(f"⏸️ 화면 전환이 일시 정지되었습니다. (현재 페이지: {st.session_state.page_index + 1}/{total_pages})")
    if st.button("🔄 데이터 수동 새로고침"):
        try: st.rerun()
        except AttributeError: st.experimental_rerun()
