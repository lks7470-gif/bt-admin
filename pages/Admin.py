import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import qrcode
import io
import base64
import math
import time
import re
from datetime import datetime, timedelta

# ==========================================
# 🛑 [문지기] 로그인 체크
# ==========================================
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("⚠️ 로그인이 필요합니다.")
    time.sleep(1)
    st.switch_page("Main.py")
    st.stop()

# ------------------------------------------
# 🔌 DB 연결
# ------------------------------------------
try:
    from connection import get_supabase_client
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"🚨 서버 연결 실패: {e}")
    st.stop()

# ==========================================
# ⚙️ 설정
# ==========================================
st.set_page_config(page_title="(주)베스트룸 생산관리", page_icon="🏭", layout="wide")
APP_URL = "https://bt-app-pwgumeleefkwpf3xsu5bob.streamlit.app/"

if 'order_list' not in st.session_state: st.session_state.order_list = []
if 'generated_qrs' not in st.session_state: st.session_state.generated_qrs = []
if 'fabric_db' not in st.session_state: st.session_state.fabric_db = {}
if 'history_data' not in st.session_state: st.session_state.history_data = []

# ==========================================
# 🔥 [스타일] CSS 정의 (인쇄 백지 해결을 위한 강력한 설정)
# ==========================================
st.markdown("""
<style>
    .stApp { background-color: #ffffff !important; color: #000000 !important; }
    
    @media print {
        /* 1. 용지 설정 */
        @page { size: A4 portrait; margin: 0mm; }
        
        /* 2. 전체 숨김 */
        body * { visibility: hidden; }
        
        /* 3. 인쇄 영역만 강제 표시 */
        #printable-area, #printable-area * {
            visibility: visible !important;
            color: black !important;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }
        
        /* 4. 인쇄 영역 위치 및 크기 고정 */
        #printable-area {
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            width: 210mm !important;
            height: auto !important;
            background-color: white !important;
            padding: 10mm !important;
            margin: 0 !important;
            z-index: 999999 !important;
        }

        /* UI 요소 숨김 */
        header, footer, .stButton, [data-testid="stHeader"], .stSidebar { display: none !important; }
        
        /* --- 테이블 스타일 (가장 안정적) --- */
        .info-table { 
            width: 100%; border-collapse: collapse; 
            border: 2px solid black !important; 
            font-size: 11pt; margin-bottom: 0px !important;
        }
        .info-table th { background: #eee !important; border: 1px solid black !important; padding: 5px; width: 18%; }
        .info-table td { text-align: center; border: 1px solid black !important; padding: 5px; }

        /* QR 그리드 (Table 구조 사용) */
        .qr-table { 
            width: 100%; 
            border-collapse: collapse; 
            border: 2px solid black !important;
            border-top: none !important; 
            table-layout: fixed;
        }
        .qr-cell { 
            width: 33.33%; 
            height: 72mm; /* 높이를 키워서 A4 꽉 차게 */
            border: 1px solid black !important; 
            text-align: center; vertical-align: middle; 
            padding: 5px;
        }
        /* 첫 줄 윗선 제거 */
        .qr-table tr:first-child td { border-top: none !important; }

        .qr-img { width: 130px; height: 130px; margin: 5px auto; display: block; }

        /* 텍스트 스타일 */
        .txt-dim { font-size: 18pt; margin-bottom: 5px; display: block; line-height: 1.2; }
        .txt-elec { font-size: 14pt; font-weight: normal; margin-bottom: 5px; display: block; }
        .txt-lot { font-size: 10pt; font-weight: 900; margin-top: 5px; font-family: monospace; display: block; }
        .txt-info { font-size: 9pt; font-weight: bold; display: block; }

        .footer-warning { width: 100%; text-align: center; font-size: 10pt; font-weight: bold; margin-top: 10px; }
        
        /* 라벨용 */
        .grid-table { width: 100%; border-collapse: collapse; margin-top:10px; }
        .grid-cell { width: 50%; height: 60mm; border: 1px dashed #999; text-align: center; vertical-align: middle; padding: 10px; }
    }
    
    #printable-area { display: none; }
</style>
""", unsafe_allow_html=True)

def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# ----------------------------------------------------
# 🔍 치수 강조 로직 (가로 vs 세로)
# ----------------------------------------------------
def get_styled_dimensions(w, h, elec):
    """
    [가로] 포함 -> 가로(W) 진하게, 세로(H) 연하게
    [세로] 포함 -> 가로(W) 연하게, 세로(H) 진하게
    """
    style_bold = "font-weight: 900; font-size: 1.2em; color: black;"  
    style_light = "font-weight: 400; font-size: 1.0em; color: #999;" 

    if "가로" in elec:
        w_html = f"<span style='{style_bold}'>{w}</span>"
        h_html = f"<span style='{style_light}'>{h}</span>"
    elif "세로" in elec:
        w_html = f"<span style='{style_light}'>{w}</span>"
        h_html = f"<span style='{style_bold}'>{h}</span>"
    else:
        w_html = f"<span style='font-weight:bold; color:black;'>{w}</span>"
        h_html = f"<span style='font-weight:bold; color:black;'>{h}</span>"

    return f"<div class='txt-dim'>{w_html} x {h_html}</div>"

def format_electrode_text(text):
    """ 전극 텍스트 내 숫자만 진하게 """
    if not text: return ""
    return re.sub(r'(\d+)', r'<span style="font-weight:900; font-size:1.2em; color:black;">\1</span>', str(text))

# ----------------------------------------------------
# 📄 작업 지시서 HTML (Table 구조 - 인쇄 안정성 최우선)
# ----------------------------------------------------
def create_a4_html(header, items):
    LIMIT = 9
    cells_data = items[:LIMIT] + [None] * (LIMIT - len(items[:LIMIT]))
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = '<div id="printable-area">'
    
    html += f'<div style="text-align:right; font-size:9pt; margin-bottom:5px;">출력일시: {now_str}</div>'
    html += '<div style="text-align:center; font-size:28pt; font-weight:900; margin-bottom:10px; text-decoration:underline;">작업 지시서 (Work Order)</div>'
    
    html += '<table class="info-table">'
    html += f'<tr><th>고객사</th><td>{header["cust"]}</td><th>제품 종류</th><td>{header["prod"]}</td></tr>'
    html += f'<tr><th>출고 요청일</th><td>{header["date"]}</td><th>원단 정보</th><td>{header["fabric"]}</td></tr>'
    html += f'<tr><th>작업 가이드</th><td colspan="3" style="text-align:left; padding:5px; font-weight:bold;">{header["guide"]}</td></tr>'
    html += f'<tr><th>비고</th><td colspan="3" style="height:35px; text-align:left; padding:5px;">{header["note"]}</td></tr>'
    html += '</table>'
    
    html += '<table class="qr-table">'
    for r in range(3):
        html += '<tr>'
        for c in range(3):
            idx = r * 3 + c
            item = cells_data[idx]
            html += '<td class="qr-cell">'
            if item:
                img_b64 = image_to_base64(item['img'])
                # 1. 치수 강조 적용
                dim_html = get_styled_dimensions(item['w'], item['h'], item['elec'])
                # 2. 전극 숫자 강조
                elec_html = format_electrode_text(item['elec'])

                html += f'{dim_html}'
                html += f'<div class="txt-elec">[{elec_html}]</div>' 
                html += f'<img src="data:image/png;base64,{img_b64}" class="qr-img">'
                html += f'<div class="txt-lot">{item["lot"]}</div>'
                html += f'<div class="txt-info">{item["cust"]} | {item["prod"]}</div>'
            html += '</td>'
        html += '</tr>'
    html += '</table>'
    
    html += '<div class="footer-warning">⚠️ 경고: 본 문서는 대외비 자료이므로 무단 복제 및 외부 유출을 엄격히 금합니다.</div>'
    html += '</div>'
    return html

def create_label_html(items):
    cells_data = items[:12] + [None] * (12 - len(items[:12]))
    html = '<div id="printable-area"><div style="text-align:center; font-size:20pt; font-weight:bold; margin-bottom:20px;">🏷️ QR 라벨 출력</div>'
    html += '<table class="grid-table" style="width:100%;">'
    
    for r in range(3):
        html += '<tr>'
        for c in range(4):
            idx = r * 4 + c
            item = cells_data[idx]
            html += '<td class="grid-cell" style="width:25%;">'
            if item:
                img_b64 = image_to_base64(item['img'])
                
                # 라벨용 치수 강조 (간단 버전)
                w, h, elec = item['w'], item['h'], item['elec']
                w_s, h_s = "", ""
                if "가로" in elec: w_s = "font-weight:900; font-size:1.1em;"
                elif "세로" in elec: h_s = "font-weight:900; font-size:1.1em;"
                
                elec_html = format_electrode_text(elec)
                html += f'<div style="font-size:16pt; margin-bottom:2px;"><span style="{w_s}">{w}</span>x<span style="{h_s}">{h}</span></div>'
                html += f'<div style="font-size:12pt; margin-bottom:5px;">[{elec_html}]</div>'
                html += f'<img src="data:image/png;base64,{img_b64}" style="width:100px;">'
                html += f'<div style="font-size:9pt; font-weight:900;">{item["lot"]}</div>'
            html += '</td>'
        html += '</tr>'
    html += '</table></div>'
    return html

def create_access_qr_html(url, mode="big"):
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_b64 = image_to_base64(img)
    
    if mode == "big":
        html = f"""<div id="printable-area" style="text-align:center; padding-top:50mm;">
            <div style="border:5px solid black; padding:50px; display:inline-block; border-radius:30px;">
                <div style="font-size:40pt; font-weight:900; margin-bottom:30px;">🏭 접속 QR</div>
                <img src="data:image/png;base64,{img_b64}" style="width:400px; height:400px;">
                <div style="font-size:15pt; margin-top:20px; font-family:monospace;">{url}</div>
            </div></div>"""
    else:
        html = '<div id="printable-area"><table class="grid-table">'
        for r in range(4):
            html += '<tr>'
            for c in range(2):
                html += f"""<td class="grid-cell"><div style="border:2px solid black; border-radius:10px; padding:10px;"><div style="font-weight:bold; font-size:16pt; margin-bottom:5px;">🏭 시스템 접속</div><img src="data:image/png;base64,{img_b64}" style="width: 120px;"><div style="font-size:10px; margin-top:5px;">(주)베스트룸 생산관리</div></div></td>"""
            html += '</tr>'
        html += "</table></div>"
    return html

def fetch_fabric_stock():
    try:
        response = supabase.table("fabric_stock").select("*").execute()
        return {row['lot_no']: row for row in response.data}
    except: return {}

# ==========================================
# 🖥️ 관리자 UI
# ==========================================
st.sidebar.title("👨‍💼 지시서 설정")
if not st.session_state.fabric_db: st.session_state.fabric_db = fetch_fabric_stock()
if st.sidebar.button("🔄 재고 정보 새로고침", use_container_width=True): st.session_state.fabric_db = fetch_fabric_stock(); st.toast("✅ 완료")

customer = st.sidebar.text_input("🏢 고객사명", value="A건설", key="side_customer")
delivery_date = st.sidebar.date_input("📅 출고 요청일", key="side_date")
product_type = st.sidebar.selectbox("🧶 제품 종류", ["스마트글라스", "접합필름", "PDLC원단", "일반유리"], key="side_product")
st.sidebar.markdown("---")
fabric_lot = st.sidebar.text_input("원단 LOT No", value="Roll-2312-A", key="side_fabric_lot")
curr_fabric = st.session_state.fabric_db.get(fabric_lot)
fab_w = float(curr_fabric['width']) if curr_fabric else 1200
fab_remain = float(curr_fabric['total_len']) - float(curr_fabric['used_len']) if curr_fabric else 100.0
if curr_fabric: st.sidebar.success(f"✅ 확인됨 (폭: {fab_w}mm)"); st.sidebar.info(f"📏 잔량: {fab_remain:.1f} m")
else: st.sidebar.warning("⚠️ 미등록 원단")

st.sidebar.divider()
with st.sidebar.expander("✂️ 커팅 조건", expanded=True):
    c1, c2 = st.columns(2); fs = c1.number_input("F속도", 50); fm = c1.number_input("F Max", 80); fmn = c1.number_input("F Min", 20); hs = c2.number_input("H속도", 100); hm = c2.number_input("H Max", 40); hmn = c2.number_input("H Min", 10)
with st.sidebar.expander("🔥 접합 조건", expanded=True):
    l1_c1, l1_c2 = st.columns(2); temp1 = l1_c1.number_input("1온도", 60); time1 = l1_c2.number_input("1시간", 30); use_step2 = st.checkbox("2단계", True); temp2=100; time2=50; temp3=110; time3=10
    if use_step2: l2_c1, l2_c2 = st.columns(2); temp2 = l2_c1.number_input("2온도", 100); time2 = l2_c2.number_input("2시간", 50)
    use_step3 = st.checkbox("3단계", True)
    if use_step3: l3_c1, l3_c2 = st.columns(2); temp3 = l3_c1.number_input("3온도", 110); time3 = l3_c2.number_input("3시간", 10)

lam_text = f"1단계({temp1}℃/{time1}분)"
if use_step2: lam_text += f" → 2단계({temp2}℃/{time2}분)"
if use_step3: lam_text += f" → 3단계({temp3}℃/{time3}분)"
guide_full_text = f"Full({fs}/{fm}/{fmn}) | Half({hs}/{hm}/{hmn}) | {lam_text}"
admin_notes = st.sidebar.text_area("비고", key="admin_notes_1")

# 메인 탭
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["📝 작업 입력", "📄 지시서 인쇄", "🏷️ 라벨 인쇄", "🔄 QR 재발행", "🧵 원단 재고", "📊 발행 이력", "🔍 제품 추적", "🚨 불량 현황", "📱 접속 QR"])

with tab1:
    st.title("📝 관리자용 - 지시서 발행")
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
        in_w = c1.number_input("가로(mm)", value=1000); in_h = c2.number_input("세로(mm)", value=2000); in_elec = c3.selectbox("전극", ["없음", "가로(1면)", "세로(1면)", "양쪽가로", "양쪽세로"]); in_qty = c4.number_input("수량", min_value=1, value=1) 
        per_row = max(1, int(fab_w / in_w)) if in_w > 0 else 1
        est_len = (math.ceil(in_qty / per_row) * in_h) / 1000.0
        st.info(f"예상 소모량: {est_len:.1f} m")
        if st.button("➕ 장바구니 추가", use_container_width=True):
            st.session_state.order_list.append({"고객사": customer, "제품": product_type, "규격": f"{int(in_w)}x{int(in_h)}", "전극": in_elec, "수량": int(in_qty), "스펙": guide_full_text, "비고": admin_notes, "w": int(in_w), "h": int(in_h), "lot_no": fabric_lot, "calc_len": est_len})

    if st.session_state.order_list:
        df = pd.DataFrame(st.session_state.order_list)
        df.insert(0, "선택", False)
        edited_df = st.data_editor(df, key="editor", hide_index=True, use_container_width=True, column_config={"선택": st.column_config.CheckboxColumn(default=False)})
        c1, c2 = st.columns([1,4])
        if c1.button("🗑️ 삭제"):
            for i in sorted(edited_df[edited_df["선택"]].index.tolist(), reverse=True): del st.session_state.order_list[i]
            st.rerun()
        if c2.button("🚀 최종 발행 및 저장 (Supabase)", type="primary", use_container_width=True):
            today_str = datetime.now().strftime("%y%m%d"); base_time = datetime.now().strftime('%H%M%S'); new_qrs, cnt = [], 0
            for item in st.session_state.order_list:
                for _ in range(item['수량']):
                    cnt += 1; lot_id = f"LOT-{today_str}-{base_time}-{cnt:03d}"
                    supabase.table("work_orders").insert({"lot_no": lot_id, "customer": item['고객사'], "product": item['제품'], "dimension": f"{item['규격']} [{item['전극']}]", "spec": item['스펙'], "status": "작업대기", "note": item['비고'], "fabric_lot_no": item['lot_no']}).execute()
                    qr = qrcode.QRCode(box_size=5, border=2); qr.add_data(lot_id); qr.make(fit=True); img = qr.make_image(fill_color="black", back_color="white")
                    new_qrs.append({"lot": lot_id, "w": item['w'], "h": item['h'], "elec": item['전극'], "prod": item['제품'], "cust": item['고객사'], "img": img})
                try:
                    curr = supabase.table("fabric_stock").select("used_len").eq("lot_no", item['lot_no']).execute()
                    if curr.data: supabase.table("fabric_stock").update({"used_len": float(curr.data[0]['used_len']) + item['calc_len']}).eq("lot_no", item['lot_no']).execute()
                except: pass
            st.session_state.generated_qrs = new_qrs; st.session_state.order_list = []; st.session_state.fabric_db = fetch_fabric_stock(); st.success("✅ Supabase 저장 완료!"); st.rerun()

with tab2:
    st.header("📄 작업 지시서 인쇄")
    print_mode = st.radio("출력 대상", ["🆕 방금 발행", "📅 이력 조회"], horizontal=True)
    
    # Case 1: 방금 발행
    if print_mode == "🆕 방금 발행":
        if st.session_state.generated_qrs:
            qrs = st.session_state.generated_qrs
            header_info = {'cust': qrs[0]['cust'], 'prod': qrs[0]['prod'], 'date': delivery_date.strftime('%Y-%m-%d'), 'fabric': fabric_lot, 'guide': guide_full_text, 'note': admin_notes}
            html_content = create_a4_
