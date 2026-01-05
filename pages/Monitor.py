# 파일명: pages/Monitor.py
import streamlit as st
import time

# ==========================================
# 🛑 [문지기] 로그인 안 했으면 메인으로 강제 이동
# ==========================================
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("⚠️ 로그인이 필요합니다. 메인 화면으로 이동합니다...")
    time.sleep(1) # 유저가 메시지를 볼 시간을 줌
    st.switch_page("Main.py") # 메인으로 강제 소환!
    st.stop() # 아래 코드 실행 중단

# ------------------------------------------
# 👇 원래 있던 코드들 (DB 연결 등)은 이 밑에 있어야 함
# ------------------------------------------
from connection import get_supabase_client
supabase = get_supabase_client()

# 연결 가져오기 (connection.py가 알아서 금고에서 키를 꺼내옵니다)
try:
    supabase = get_supabase_client()
    if not supabase:
        st.error("🚨 서버 연결 실패! (connection.py 파일 확인 필요)")
        st.stop()
except Exception as e:
    st.error(f"🚨 연결 오류: {e}")
    st.stop()


# ==========================================
# ⚙️ 설정 및 스타일
# ==========================================
st.set_page_config(page_title="BESTROOM 모니터링", page_icon="🖥️", layout="wide", initial_sidebar_state="collapsed")

def get_korea_time():
    return datetime.utcnow() + timedelta(hours=9)

st.markdown("""
<style>
    /* 1. 배경 블랙 */
    .stApp, .main, [data-testid="stAppViewContainer"] { background-color: #000000 !important; color: #e0e0e0 !important; }
    
    /* 2. 전체화면 모드 */
    [data-testid="stSidebar"], [data-testid="collapsedControl"], header, footer { display: none !important; }
    .block-container { padding-top: 0.5rem; padding-bottom: 1rem; max-width: 99% !important; }
    
    /* 3. 집계 박스 */
    .metric-container { display: flex; gap: 15px; margin-bottom: 25px; justify-content: center; }
    .metric-box { 
        background: #111; border: 1px solid #333; border-radius: 12px; 
        width: 18%; padding: 15px; text-align: center; 
        box-shadow: 0 4px 15px rgba(255,255,255,0.05); 
    }
    .metric-title { font-size: 16px; color: #888; margin-bottom: 5px; font-weight: bold; }
    .metric-num { font-size: 48px; font-weight: 900; line-height: 1; }
    .tx-white { color: #fff; text-shadow: 0 0 10px rgba(255,255,255,0.3); }
    .tx-blue { color: #00e5ff; text-shadow: 0 0 10px rgba(0,229,255,0.5); } 
    .tx-green { color: #00e676; text-shadow: 0 0 10px rgba(0,230,118,0.5); } 
    .tx-orange { color: #ff9100; text-shadow: 0 0 10px rgba(255,145,0,0.5); }
    
    /* 4. 테이블 디자인 (비율 조정됨) */
    .smart-table { width: 100%; border-collapse: separate; border-spacing: 0 10px; }
    .smart-table th { 
        text-align: left; color: #666; font-size: 15px; padding: 10px 20px; 
        border-bottom: 1px solid #333; letter-spacing: 1px; font-weight: bold;
    }
    .smart-row { background-color: #0a0a0a; transition: transform 0.2s; }
    .smart-cell { 
        padding: 15px 20px; border-top: 1px solid #222; border-bottom: 1px solid #222; vertical-align: middle; 
    }
    .smart-row td:first-child { border-left: 1px solid #222; border-top-left-radius: 12px; border-bottom-left-radius: 12px; }
    .smart-row td:last-child { border-right: 1px solid #222; border-top-right-radius: 12px; border-bottom-right-radius: 12px; }
    
    /* 5. 내부 텍스트 스타일 */
    .time-badge { background: #222; color: #aaa; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 14px; font-family: monospace; border: 1px solid #333; margin-bottom: 4px; display: inline-block; }
    .lot-text { font-size: 15px; color: #4fc3f7; font-weight: bold; letter-spacing: 0.5px; }
    .cell-cust { font-size: 22px; font-weight: 900; color: #fff; margin-bottom: 4px; }
    .cell-prod { font-size: 15px; color: #888; }
    
    /* SIZE 폰트 (18px 유지) */
    .cell-size { font-size: 18px; color: #ffffff; font-weight: 900; letter-spacing: -0.5px; } 
    
    /* 6. SPEC 박스 */
    .spec-box { 
        background-color: #111; border: 1px solid #444; color: #fff; 
        padding: 12px; border-radius: 8px; font-size: 14px; font-family: 'Consolas', monospace; 
        line-height: 1.5; white-space: normal;
    }
    .secret-box {
        background: repeating-linear-gradient(45deg, #111, #111 10px, #1a1a1a 10px, #1a1a1a 20px);
        color: #777; border: 1px dashed #555; text-align: center; padding: 12px; 
        font-style: italic; font-weight: bold; border-radius: 8px; font-size: 14px;
    }
    
    /* 7. 상태(Status) 디자인 */
    .status-container { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
    .status-badge { display: inline-block; padding: 5px 10px; border-radius: 15px; font-size: 12px; font-weight: 900; text-transform: uppercase; }
    .pct-text { font-size: 13px; font-weight: 900; color: #fff; text-shadow: 0 0 5px rgba(255,255,255,0.2); }
    
    .badge-white { background: #333; color: #ccc; border: 1px solid #555; }
    .badge-blue { background: #0277bd; color: white; border: 1px solid #0288d1; }
    .badge-green { background: #2e7d32; color: white; border: 1px solid #388e3c; }
    .badge-orange { background: #ef6c00; color: white; border: 1px solid #f57c00; }
    .badge-red { background: #b71c1c; color: white; border: 1px solid #d32f2f; }
    
    .mini-progress-bg { width: 100%; height: 6px; background: #222; border-radius: 3px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.5); }
    .mini-progress-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
    .bg-w { background: #555; } .bg-b { background: linear-gradient(90deg, #00e5ff, #2979ff); } 
    .bg-g { background: linear-gradient(90deg, #00e676, #00c853); } 
    .bg-o { background: linear-gradient(90deg, #ff9100, #ff3d00); } 
    .bg-r { background: linear-gradient(90deg, #ff5252, #d50000); }
    
    /* 로고 대체 스타일 */
    .logo-placeholder {
        width: 100%; height: 60px; background: #111; border: 2px dashed #333;
        display: flex; align-items: center; justify-content: center;
        color: #555; font-weight: bold; border-radius: 10px;
    }
    
    .page-indicator { position: fixed; top: 20px; right: 20px; background: rgba(20,20,20,0.8); color: #888; padding: 5px 15px; border-radius: 15px; font-weight: bold; font-size: 14px; border: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

if 'page_index' not in st.session_state: st.session_state.page_index = 0

def load_data():
    try:
        res_orders = supabase.table("work_orders").select("*").order("created_at", desc=True).limit(50).execute()
        df = pd.DataFrame(res_orders.data)
        res_logs = supabase.table("production_logs").select("*").order("created_at", desc=True).limit(100).execute()
        df_log = pd.DataFrame(res_logs.data)
        if not df.empty: df['short_time'] = pd.to_datetime(df['created_at']).dt.strftime('%m-%d %H:%M')
        return df, df_log
    except: return pd.DataFrame(), pd.DataFrame()

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

# [상단 레이아웃] 로고(2) : 타이틀(6) : 버튼(2)
c1, c2, c3 = st.columns([2, 6, 2])
with c1:
    logo_path = None
    if os.path.exists("pages/company_logo.png"): logo_path = "pages/company_logo.png"
    elif os.path.exists("company_logo.png"): logo_path = "company_logo.png"
    
    if logo_path:
        st.image(logo_path, width=300)
    else:
        st.markdown('<div class="logo-placeholder">LOGO FILE NEEDED</div>', unsafe_allow_html=True)

with c2:
    now_time = get_korea_time().strftime("%H:%M:%S")
    st.markdown(f"<h1 style='margin-bottom:30px; font-weight:900; text-align:left; font-size: 36px; letter-spacing: -1px;'>BESTROOM FACTORY MONITOR <span style='color:#ffd700; font-size:28px; margin-left:15px; font-family:monospace;'>{now_time}</span></h1>", unsafe_allow_html=True)

with c3:
    col_t1, col_t2 = st.columns(2)
    with col_t1: is_cust_secure = st.toggle("🔒 고객사", value=True)
    with col_t2: is_spec_secure = st.toggle("🔒 SPEC", value=True)

st.markdown(f'<div class="page-indicator">PAGE {st.session_state.page_index + 1} / {total_pages}</div>', unsafe_allow_html=True)

st.markdown(f"""
<div class="metric-container">
    <div class="metric-box"><div class="metric-title">⏳ 작업대기</div><div class="metric-num tx-white">{cnt_ready}</div></div>
    <div class="metric-box"><div class="metric-title">✂️ 커팅공정</div><div class="metric-num tx-blue">{cnt_cut}</div></div>
    <div class="metric-box"><div class="metric-title">⚡ 전극공정</div><div class="metric-num tx-blue">{cnt_elec}</div></div>
    <div class="metric-box"><div class="metric-title">🔥 접합공정</div><div class="metric-num tx-orange">{cnt_lam}</div></div>
    <div class="metric-box"><div class="metric-title">📦 완료/출고</div><div class="metric-num tx-green">{cnt_out}</div></div>
</div>""", unsafe_allow_html=True)

if not df_view.empty:
    # [수정] SIZE 19%, STATUS 18%, SPEC 33% (나머지 15+15=30, 총 100%)
    html = '<table class="smart-table"><thead><tr><th width="15%">TIME / LOT</th><th width="15%">CUSTOMER / PRODUCT</th><th width="19%">SIZE</th><th width="18%">STATUS (Process %)</th><th width="33%">SPECIFICATION</th></tr></thead><tbody>'
    
    for _, row in df_view.iterrows():
        lot = row['lot_no']; cust = row['customer']; prod = row['product']
        size = row['dimension']; spec = row['spec']; time_str = row.get('short_time','-')
        status_txt = str(row['status'])
        
        if is_cust_secure: cust_display = '<div class="secret-box">🔒 대외비</div>'
        else: cust_display = f'<div class="cell-cust">{cust}</div><div class="cell-prod">{prod}</div>'

        if is_spec_secure: spec_display = '<div class="secret-box">🔒 CONFIDENTIAL (대외비)</div>'
        else: spec_display = f'<div class="spec-box">{spec}</div>'
        
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
        
        if "불량" in status_txt: step_pct=100; txt="⛔ 불량 발생"; badge="badge-red"; bar="bg-r"
        elif "완료" in status_txt: step_pct=100; txt="✅ 생산 완료"; badge="badge-green"; bar="bg-g"
        elif "접합" in status_txt: step_pct=75; txt="🔥 접합 중"; badge="badge-orange"; bar="bg-o"
        elif "전극" in status_txt: step_pct=50; txt="⚡ 전극 중"; badge="badge-blue"; bar="bg-b"
        elif "Cut" in status_txt or "커팅" in status_txt: step_pct=25; txt="✂️ 커팅 중"; badge="badge-blue"; bar="bg-b"

        status_html = f"""
        <div style="display:flex; flex-direction:column; justify-content:center;">
            <div class="status-container">
                <span class="status-badge {badge}" style="font-size:11px; padding:4px 8px;">{txt}</span>
                <span class="pct-text" style="font-size:11px;">{step_pct}%</span>
            </div>
            <div class="mini-progress-bg">
                <div class="mini-progress-fill {bar}" style="width:{step_pct}%"></div>
            </div>
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

st.session_state.page_index = (st.session_state.page_index + 1) % total_pages
time.sleep(5) 

st.rerun()

