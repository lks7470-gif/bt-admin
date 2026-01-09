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
# 🔥 [스타일] CSS 정의 (여백 제거 & 강제 A4)
# ==========================================
# 주의: 아래 문자열의 들여쓰기를 변경하지 마세요.
PRINT_CSS = """
<style>
    .stApp { background-color: #ffffff !important; color: #000000 !important; }
    
    @media print {
        @page { size: A4; margin: 0; }
        body { margin: 0; padding: 0; -webkit-print-color-adjust: exact; }
        
        /* UI 숨김 */
        header, footer, .stButton, .stHeader, .stSidebar, .stToolbar, .stApp > header { display: none !important; }
        
        /* 인쇄 영역 */
        #printable-area {
            position: fixed;
            top: 0; left: 0;
            width: 210mm; height: 297mm;
            background: white;
            z-index: 999999;
            padding: 10mm;
            box-sizing: border-box;
            display: block !important;
        }
        
        #printable-area * { visibility: visible !important; color: black !important; }

        /* 상단 헤더 */
        .header-section { border-bottom: 2px solid black; margin-bottom: 5px; padding-bottom: 5px; }
        
        /* 테이블 */
        .info-table { width: 100%; border-collapse: collapse; border: 2px solid black; font-size: 11pt; margin-bottom: 10px; }
        .info-table th { background: #eee !important; border: 1px solid black; padding: 4px; width: 18%; }
        .info-table td { border: 1px solid black; padding: 4px; text-align: center; }

        /* QR 그리드 (높이 안정화: 180mm) */
        .qr-container { 
            width: 100%; 
            height: 180mm; 
            border: 2px solid black; 
            display: flex; 
            flex-wrap: wrap; 
        }
        
        .qr-item { 
            width: 33.33%; 
            height: 33.33%; 
            border: 1px solid black; 
            box-sizing: border-box;
            display: flex; 
            flex-direction: column; 
            justify-content: center; 
            align-items: center; 
            overflow: hidden;
        }
        
        .qr-img { width: 120px; height: 120px; margin: 5px 0; }
        .t-dim { font-size: 18pt; font-weight: 900; margin-bottom: 2px; }
        .t-elec { font-size: 12pt; font-weight: bold; margin-bottom: 2px; }
        .t-lot { font-size: 9pt; font-weight: bold; font-family: monospace; }
        .t-info { font-size: 8pt; }
        
        .footer-warning { 
            position: absolute; bottom: 10mm; left: 0; width: 100%; 
            text-align: center; font-size: 10pt; font-weight: bold; 
        }
    }
    #printable-area { display: none; }
</style>
"""
st.markdown(PRINT_CSS, unsafe_allow_html=True)

def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# ----------------------------------------------------
# 📄 HTML 생성 (들여쓰기 완전 제거)
# ----------------------------------------------------
def create_a4_html(header, items):
    LIMIT = 9
    cells_data = items[:LIMIT] + [None] * (LIMIT - len(items[:LIMIT]))
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 문자열 연결 방식으로 HTML 생성 (들여쓰기 문제 원천 봉쇄)
    html = '<div id="printable-area">'
    
    # Header
    html += f'<div class="header-section">'
    html += f'<div style="text-align:right; font-size:9pt;">출력일시: {now_str}</div>'
    html += '<div style="text-align:center; font-size:26pt; font-weight:900; margin-bottom:10px; text-decoration:underline;">작업 지시서 (Work Order)</div>'
    
    # Table
    html += '<table class="info-table">'
    html += f'<tr><th>고객사</th><td>{header["cust"]}</td><th>제품 종류</th><td>{header["prod"]}</td></tr>'
    html += f'<tr><th>출고 요청일</th><td>{header["date"]}</td><th>원단 정보</th><td>{header["fabric"]}</td></tr>'
    html += f'<tr><th>작업 가이드</th><td colspan="3" style="text-align:left; padding:5px; font-weight:bold;">{header["guide"]}</td></tr>'
    html += f'<tr><th>비고</th><td colspan="3" style="height:35px; text-align:left; padding:5px;">{header["note"]}</td></tr>'
    html += '</table>'
    html += f'<div style="font-size:14pt; font-weight:bold; margin-bottom:5px;">📋 생산 리스트 (총 {len(items)}개)</div>'
    html += '</div>'
    
    # Grid
    html += '<div class="qr-container">'
    for item in cells_data:
        if item:
            img_b64 = image_to_base64(item['img'])
            html += '<div class="qr-item">'
            html += f'<div class="t-dim">{item["w"]} x {item["h"]}</div>'
            html += f'<div class="t-elec">[{item["elec"]}]</div>'
            html += f'<img src="data:image/png;base64,{img_b64}" class="qr-img">'
            html += f'<div class="t-lot">{item["lot"]}</div>'
            html += f'<div class="t-info">{item["cust"]} | {item["prod"]}</div>'
            html += '</div>'
        else:
            html += '<div class="qr-item"></div>'
    html += '</div>'
    
    # Footer
    html += '<div class="footer-warning">⚠️ 경고: 본 문서는 대외비 자료이므로 무단 복제 및 외부 유출을 엄격히 금합니다.</div>'
    html += '</div>'
    
    return html

def create_label_html(items):
    cells_data = items[:12] + [None] * (12 - len(items[:12]))
    html = '<div id="printable-area"><div style="text-align:center; font-size:20pt; font-weight:bold; margin-bottom:20px;">🏷️ QR 라벨 출력</div>'
    html += '<div class="qr-container" style="height:auto; border:none;">'
    
    style = 'width:25%; height:60mm; border:1px solid black; display:flex; flex-direction:column; align-items:center; justify-content:center; box-sizing:border-box;'
    
    for item in cells_data:
        html += f'<div style="{style}">'
        if item:
            img_b64 = image_to_base64(item['img'])
            html += f'<div style="font-size:16pt; font-weight:bold;">{item["w"]}x{item["h"]}</div>'
            html += f'<div style="font-size:12pt;">[{item["elec"]}]</div>'
            html += f'<img src="data:image/png;base64,{img_b64}" style="width:100px;">'
            html += f'<div style="font-size:9pt; font-weight:bold;">{item["lot"]}</div>'
        html += '</div>'
    html += '</div></div>'
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
        html = '<div id="printable-area"><div style="display:flex; flex-wrap:wrap;">'
        for _ in range(8):
            html += f"""<div style="width:50%; height:25%; border:1px dashed gray; display:flex; justify-content:center; align-items:center;">
                <div style="border:2px solid black; padding:10px; border-radius:10px; text-align:center;">
                    <div style="font-size:15pt; font-weight:bold;">접속 QR</div>
                    <img src="data:image/png;base64,{img_b64}" style="width:100px;">
                </div></div>"""
        html += "</div></div>"
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
    
    if print_mode == "🆕 방금 발행":
        if st.session_state.generated_qrs:
            qrs = st.session_state.generated_qrs
            header_info = {'cust': qrs[0]['cust'], 'prod': qrs[0]['prod'], 'date': delivery_date.strftime('%Y-%m-%d'), 'fabric': fabric_lot, 'guide': guide_full_text, 'note': admin_notes}
            html_content = create_a4_html(header_info, qrs)
            st.markdown(html_content, unsafe_allow_html=True)
            if st.button("🖨️ 인쇄창 열기 (Print)", type="primary"):
                components.html("<script>parent.window.print()</script>", height=0, width=0)
        else:
            st.info("⚠️ 현재 발행된 작업이 없습니다.")
            
    else:
        # [수정] NameError 방지를 위해 st.form 구조 단순화 및 변수명 명확화
        st.caption("🔍 조회 기간을 설정하세요 (시작일 ~ 종료일)")
        
        # 폼 사용하지 않고 바로 입력받음 (즉시 반응형)
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        d_range = col1.date_input("조회 기간", value=(datetime.now() - timedelta(days=7), datetime.now()), key="hist_date")
        s_cust = col2.text_input("고객사", key="hist_cust")
        s_lot = col3.text_input("LOT 번호", key="hist_lot")
        do_search = col4.button("🔍 조회", type="primary", key="hist_btn")
        
        if do_search:
            if isinstance(d_range, tuple):
                if len(d_range) == 2: start_date, end_date = d_range
                elif len(d_range) == 1: start_date = end_date = d_range[0]
                else: start_date = end_date = datetime.now()
            else: start_date = end_date = d_range

            start_ts = start_date.strftime("%Y-%m-%d 00:00:00")
            end_ts = end_date.strftime("%Y-%m-%d 23:59:59")
            
            query = supabase.table("work_orders").select("*").gte("created_at", start_ts).lte("created_at", end_ts)
            if s_cust: query = query.ilike("customer", f"%{s_cust}%")
            if s_lot: query = query.ilike("lot_no", f"%{s_lot}%")
            
            try:
                res = query.execute()
                st.session_state.history_data = res.data
            except Exception as e:
                st.error(f"조회 실패: {e}"); st.session_state.history_data = []
        
        if st.session_state.history_data:
            edited_hist = st.data_editor(
                pd.DataFrame(st.session_state.history_data).assign(선택=False), 
                hide_index=True, use_container_width=True,
                column_config={"선택": st.column_config.CheckboxColumn(width="small")}
            )
            
            selected_rows = edited_hist[edited_hist["선택"]]
            
            if not selected_rows.empty:
                st.divider()
                st.success(f"✅ {len(selected_rows)}개 항목 선택됨")
                
                print_items = []
                first_row = selected_rows.iloc[0]
                header_info = {
                    'cust': first_row['customer'], 
                    'prod': first_row['product'], 
                    'date': pd.to_datetime(first_row['created_at']).strftime('%Y-%m-%d'), 
                    'fabric': first_row.get('fabric_lot_no', 'Unknown'), 
                    'guide': first_row.get('spec', ''), 
                    'note': first_row.get('note', '')
                }

                for _, row in selected_rows.iterrows():
                    dim_str = row['dimension']
                    
                    # [수정] 파싱 로직 강화 & 실패 시 원본 표시
                    w, h, elec = "규격", "확인", dim_str
                    try:
                        # 1. 숫자 x 숫자
                        size_match = re.search(r'(\d+)\s*[xX*]\s*(\d+)', dim_str) 
                        if size_match: 
                            w, h = size_match.group(1), size_match.group(2)
                        
                        # 2. 전극 정보 추출 (대괄호 안 or 나머지 텍스트)
                        elec_match = re.search(r'\[(.*?)\]', dim_str)
                        if elec_match: 
                            elec = elec_match.group(1)
                        else:
                            # 숫자x숫자 패턴 제거한 나머지를 전극정보로 간주
                            remains = re.sub(r'(\d+)\s*[xX*]\s*(\d+)', '', dim_str).strip()
                            if remains: elec = remains
                    except: pass

                    qr = qrcode.QRCode(box_size=5, border=2)
                    qr.add_data(row['lot_no'])
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")

                    print_items.append({"lot": row['lot_no'], "w": w, "h": h, "elec": elec, "prod": row['product'], "cust": row['customer'], "img": img})
                
                html_content = create_a4_html(header_info, print_items)
                st.markdown(html_content, unsafe_allow_html=True)
                
                if st.button("🖨️ 선택 항목 인쇄하기", type="primary"):
                    components.html("<script>parent.window.print()</script>", height=0, width=0)
            else:
                st.info("👆 인쇄할 항목을 체크(v) 하세요.")
        else:
            st.write("조회된 데이터가 없습니다.")

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

# [접속 QR 탭]
with tab9:
    st.header("📱 현장 접속 QR 인쇄")
    qr_mode = st.radio("인쇄 스타일을 선택하세요", ["벽 부착용 (대형 1개)", "배포용 (소형 8개)"], horizontal=True)
    
    # 1. QR 이미지 생성 (PIL 객체)
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(APP_URL)
    qr.make(fit=True)
    img_pil = qr.make_image(fill_color="black", back_color="white")
    
    # 2. 화면 표시용 (BytesIO 사용 -> 에러 방지)
    buf = io.BytesIO()
    img_pil.save(buf, format="PNG")
    byte_im = buf.getvalue()

    c1, c2 = st.columns([1, 3])
    with c1:
        st.image(byte_im, width=200, caption="접속 URL QR")
    with c2:
        st.success(f"접속 주소: {APP_URL}")
        
        mode_key = "big" if "대형" in qr_mode else "small"
        st.markdown(create_access_qr_html(APP_URL, mode_key), unsafe_allow_html=True)
        
        if st.button("🖨️ QR 인쇄하기", type="primary", use_container_width=True):
            components.html("<script>parent.window.print()</script>", height=0, width=0)
