import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import qrcode
import io
import base64
import math
import time
from datetime import datetime

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

# 🔥 [스타일] 인쇄 디자인
st.markdown("""
<style>
    .stApp { background-color: #ffffff !important; color: #000000 !important; }
    
    @media print {
        @page { size: A4 portrait; margin: 0; }
        body * { visibility: hidden; }
        
        .printable-area, .printable-area * {
            visibility: visible !important;
            color: black !important;
        }
        .printable-area {
            position: fixed !important; left: 0; top: 0; width: 210mm; height: 297mm;
            background-color: white !important; z-index: 999999; padding: 10mm; display: block !important;
        }

        header, footer, .stButton, [data-testid="stHeader"] { display: none !important; }
        
        /* 지시서 정보 테이블 (좌측) */
        .info-table { width: 100%; border-collapse: collapse; border: 1px solid black !important; font-size: 11pt; }
        .info-table th { background: #f0f0f0 !important; font-weight: bold; width: 20%; border: 1px solid black !important; padding: 5px; }
        .info-table td { text-align: left; border: 1px solid black !important; padding: 5px; }

        /* 하단 QR 그리드 */
        .qr-table { width: 100%; border-collapse: collapse; table-layout: fixed; border: 1px solid black !important; margin-top: 10px; }
        .qr-cell { width: 25%; height: 60mm; border: 1px solid black !important; text-align: center; vertical-align: middle; padding: 5px; }

        /* 대표 QR 박스 (우측 상단) */
        .master-qr-box {
            border: 2px solid black;
            padding: 5px;
            text-align: center;
            height: 140px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            border-radius: 8px;
        }

        /* [대형] 벽 부착용 스타일 */
        .access-qr-box { text-align: center; margin-top: 50px; border: 5px solid #000; padding: 30px; border-radius: 20px; }
        
        /* [소형] 배포용 그리드 스타일 */
        .grid-table { width: 100%; height: 95%; border-collapse: collapse; }
        .grid-cell { width: 50%; height: 25%; border: 1px dashed #999; text-align: center; vertical-align: middle; padding: 10px; }
        .mini-card { border: 2px solid black; border-radius: 10px; padding: 10px; display: inline-block; width: 90%; }
    }
    .printable-area { display: none; }
</style>
""", unsafe_allow_html=True)

def get_dimension_html(w, h, elec):
    return f"<span style='font-size:16pt;'>{w}</span> x <span style='font-size:16pt; font-weight:bold;'>{h}</span>"

def image_to_base64(img):
    """PIL 이미지를 HTML용 Base64 문자열로 변환"""
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# ----------------------------------------------------
# 📄 [핵심] 작업 지시서 HTML (우측 상단 QR 배치)
# ----------------------------------------------------
def create_a4_html(header, items):
    # 1. 대표 QR 이미지 (첫 번째 아이템 기준)
    master_qr_html = ""
    if items:
        # 인쇄용 HTML에는 Base64 문자열이 필요함
        master_img_b64 = image_to_base64(items[0]['img'])
        master_lot = items[0]['lot']
        
        master_qr_html = f"""
        <div class="master-qr-box">
            <div style="font-weight:bold; font-size:11pt; margin-bottom:2px;">Scan for Details</div>
            <img src="data:image/png;base64,{master_img_b64}" style="width: 100px; height: 100px;">
            <div style="font-size:8pt; font-weight:bold; margin-top:2px;">{master_lot}</div>
        </div>
        """

    # 2. 하단 개별 QR 리스트 생성
    cells_data = items[:12] + [None] * (12 - len(items[:12]))
    rows_html = ""
    for r in range(3):
        rows_html += "<tr>"
        for c in range(4):
            idx = r * 4 + c
            item = cells_data[idx]
            if item:
                img_b64 = image_to_base64(item['img'])
                content = f"""<div style="font-size:14pt; margin-bottom:5px;">{get_dimension_html(item['w'], item['h'], item['elec'])}</div><div style="font-size:12pt; font-weight:bold; margin-bottom:5px;">[{item['elec']}]</div><img src="data:image/png;base64,{img_b64}" style="width:100px;"><div style="font-size:10pt; font-weight:bold; margin-top:5px;">{item['lot']}</div><div style="font-size:8pt;">{item['cust']} | {item['prod']}</div>"""
            else: content = ""
            rows_html += f'<td class="qr-cell">{content}</td>'
        rows_html += "</tr>"
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 3. 전체 레이아웃 (테이블 구조로 좌/우 분할)
    return f"""
<div class="printable-area">
    <div style="position:absolute; top:5mm; right:5mm; font-size:9pt; color:#555;">출력일시: {now_str}</div>
    <div style="text-align:center; font-size:10pt; margin-top:5mm;">(주)베스트룸</div>
    <div style="text-align:center; font-size:24pt; font-weight:bold; margin-bottom:20px; text-decoration:underline;">작업 지시서 (Work Order)</div>
    
    <table style="width:100%; border:none; margin-bottom:10px;">
        <tr>
            <td style="width: 75%; vertical-align: top; padding-right: 15px; border:none !important;">
                <table class="info-table">
                    <tr><th>고객사</th><td>{header['cust']}</td><th>제품 종류</th><td>{header['prod']}</td></tr>
                    <tr><th>출고 요청일</th><td>{header['date']}</td><th>원단 정보</th><td>{header['fabric']}</td></tr>
                    <tr><th>작업 가이드</th><td colspan="3">{header['guide']}</td></tr>
                    <tr><th>비고</th><td colspan="3" style="height:50px;">{header['note']}</td></tr>
                </table>
            </td>
            <td style="width: 25%; vertical-align: top; border:none !important;">
                {master_qr_html}
            </td>
        </tr>
    </table>

    <div style="font-size:14pt; font-weight:bold; margin-bottom:5px; margin-top:10px;">📋 생산 리스트 및 개별 QR</div>
    <table class="qr-table">{rows_html}</table>
    <div style="position:absolute; bottom:5mm; left:0; width:100%; text-align:center; font-size:10pt; font-weight:bold;">⚠️ 경고: 본 문서는 대외비 자료이므로 무단 복제 및 외부 유출을 엄격히 금합니다.</div>
</div>
"""

def create_label_html(items):
    cells_data = items[:12] + [None] * (12 - len(items[:12]))
    rows_html = ""
    for r in range(3):
        rows_html += "<tr>"
        for c in range(4):
            idx = r * 4 + c
            item = cells_data[idx]
            if item:
                img_b64 = image_to_base64(item['img'])
                content = f"""<div style="font-size:16pt; font-weight:bold; margin-bottom:2px;">{item['w']}x{item['h']}</div><div style="font-size:12pt; margin-bottom:5px;">[{item['elec']}]</div><img src="data:image/png;base64,{img_b64}" style="width:110px;"><div style="font-size:9pt; font-weight:bold; margin-top:2px;">{item['lot']}</div>"""
            else: content = ""
            rows_html += f'<td class="qr-cell" style="vertical-align:middle;">{content}</td>'
        rows_html += "</tr>"
    return f"""<div class="printable-area"><div style="font-size:18px; font-weight:bold; margin-bottom:10px; text-align:center;">🏷️ QR 라벨 출력</div><table class="qr-table" style="border: 2px solid black;">{rows_html}</table></div>"""

def create_access_qr_html(url, mode="big"):
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_b64 = image_to_base64(img)
    
    if mode == "big":
        return f"""<div class="printable-area"><div style="margin-top: 30mm;"></div><div class="access-qr-box"><div style="font-size: 40px; font-weight: 900; margin-bottom: 20px;">🏭 생산관리 시스템 접속</div><div style="font-size: 20px; margin-bottom: 20px;">휴대폰 카메라를 켜고 아래 QR코드를 스캔하세요.</div><img src="data:image/png;base64,{img_b64}" style="width: 400px; height: 400px;"><div style="font-size: 14px; color: #333; margin-top: 10px; font-family: monospace;">{url}</div></div></div>"""
    else:
        rows = ""; 
        for r in range(4):
            rows += "<tr>"
            for c in range(2): rows += f"""<td class="grid-cell"><div class="mini-card"><div style="font-weight:bold; font-size:16pt; margin-bottom:5px;">🏭 시스템 접속</div><img src="data:image/png;base64,{img_b64}" style="width: 120px;"><div style="font-size:10px; margin-top:5px;">(주)베스트룸 생산관리</div></div></td>"""
            rows += "</tr>"
        return f"""<div class="printable-area"><div style="text-align:center; font-weight:bold; padding:10px;">✂️ 점선을 따라 잘라서 사용하세요</div><table class="grid-table">{rows}</table></div>"""

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
    if print_mode == "🆕 방금 발행":
        if st.session_state.generated_qrs:
            qrs = st.session_state.generated_qrs
            header_info = {'cust': qrs[0]['cust'], 'prod': qrs[0]['prod'], 'date': delivery_date.strftime('%Y-%m-%d'), 'fabric': fabric_lot, 'guide': guide_full_text, 'note': admin_notes}
            st.markdown(create_a4_html(header_info, qrs), unsafe_allow_html=True)
            if st.button("🖨️ 인쇄창 열기 (Print)", type="primary"): components.html("<script>parent.window.print()</script>", height=0, width=0)
        else: st.info("데이터 없음")
    else:
        with st.form("history_search"):
            c1, c2 = st.columns([3, 1]); h_date = c1.date_input("날짜", value=datetime.now()); search_btn = c2.form_submit_button("조회")
            if search_btn:
                start = h_date.strftime("%Y-%m-%d 00:00:00"); end = h_date.strftime("%Y-%m-%d 23:59:59")
                try: res = supabase.table("work_orders").select("*").gte("created_at", start).lte("created_at", end).execute(); st.session_state.history_data = res.data
                except: st.session_state.history_data = []
        if 'history_data' in st.session_state and st.session_state.history_data:
            edited_hist = st.data_editor(pd.DataFrame(st.session_state.history_data).assign(선택=False), hide_index=True, use_container_width=True)
            if not edited_hist[edited_hist["선택"]].empty:
                if st.button("🖨️ 인쇄하기"): components.html("<script>parent.window.print()</script>", height=0, width=0)

with tab3:
    st.header("🏷️ QR 라벨 인쇄 (스티커용)")
    if st.session_state.generated_qrs:
        st.markdown(create_label_html(st.session_state.generated_qrs), unsafe_allow_html=True)
        if st.button("🖨️ 스티커 인쇄", type="primary"): components.html("<script>parent.window.print()</script>", height=0, width=0)
    else:
        st.info("👈 먼저 [작업 입력] 탭에서 발행을 진행해주세요.")

with tab4:
    with st.form("reprint"):
        c1,c2=st.columns([3,1]); s_d=c1.date_input("날짜"); btn=c2.form_submit_button("조회")
        if btn:
            try: res=supabase.table("work_orders").select("*").gte("created_at",s_d).execute(); st.session_state.reprint_data=res.data
            except: pass
    if 'reprint_data' in st.session_state:
        df=pd.DataFrame(st.session_state.reprint_data)
        if not df.empty:
            sel=st.data_editor(df.assign(선택=False),hide_index=True)
            if st.button("재발행"): st.success("선택된 QR 재발행 준비 완료")

with tab5:
    with st.form("fabric"):
        c1,c2,c3=st.columns(3); n_lot=c1.text_input("LOT"); n_name=c2.text_input("제품명"); n_w=c3.number_input("폭",1200)
        c4,c5,c6=st.columns(3); n_tot=c4.number_input("총길이",100.0); n_rem=c5.number_input("잔량",100.0)
        if st.form_submit_button("입고"):
            supabase.table("fabric_stock").insert({"lot_no":n_lot,"name":n_name,"width":n_w,"total_len":n_tot,"used_len":n_tot-n_rem}).execute(); st.rerun()
    res=supabase.table("fabric_stock").select("*").execute(); st.data_editor(pd.DataFrame(res.data),hide_index=True)

with tab6: res=supabase.table("work_orders").select("*").order("created_at",desc=True).limit(50).execute(); st.dataframe(pd.DataFrame(res.data),use_container_width=True)
with tab7:
    with st.form("track"): c1,c2=st.columns([4,1]); l=c1.text_input("LOT"); b=c2.form_submit_button("조회")
    if b: r=supabase.table("work_orders").select("*").eq("lot_no",l).execute(); st.write(r.data)
with tab8: res=supabase.table("defects").select("*").execute(); st.dataframe(pd.DataFrame(res.data))

# [접속 QR 탭 (수정됨)]
with tab9:
    st.header("📱 현장 접속 QR 인쇄")
    qr_mode = st.radio("인쇄 스타일을 선택하세요", ["벽 부착용 (대형 1개)", "배포용 (소형 8개)"], horizontal=True)
    
    # QR 생성
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(APP_URL)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # [핵심 수정] st.image 에 표시할 때는 바이트 버퍼를 사용 (안정성 확보)
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    
    c1, c2 = st.columns([1, 3])
    with c1:
        # 여기에 img 객체 대신 버퍼를 넣어서 에러 방지
        st.image(img_buffer, width=200, caption="접속 URL QR")
    with c2:
        st.success(f"접속 주소: {APP_URL}")
        
        mode_key = "big" if "대형" in qr_mode else "small"
        st.markdown(create_access_qr_html(APP_URL, mode_key), unsafe_allow_html=True)
        if st.button("🖨️ QR 인쇄하기", type="primary", use_container_width=True):
            components.html("<script>parent.window.print()</script>", height=0, width=0)
