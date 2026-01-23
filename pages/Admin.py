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
# ⚙️ 설정 & 초기화
# ==========================================
st.set_page_config(page_title="(주)베스트룸 생산관리", page_icon="🏭", layout="wide")
APP_URL = "https://bt-app-pwgumeleefkwpf3xsu5bob.streamlit.app/"

if 'order_list' not in st.session_state: st.session_state.order_list = []
if 'generated_qrs' not in st.session_state: st.session_state.generated_qrs = []
if 'fabric_db' not in st.session_state: st.session_state.fabric_db = {}
if 'history_data' not in st.session_state: st.session_state.history_data = []

# ==========================================
# 🛠️ 공통 유틸리티 함수
# ==========================================
def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def fetch_fabric_stock():
    try:
        response = supabase.table("fabric_stock").select("*").execute()
        return {row['lot_no']: row for row in response.data}
    except: return {}

# ----------------------------------------------------
# 🖨️ [통합] 인쇄용 HTML 래퍼
# ----------------------------------------------------
def generate_print_html(content_html):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <script>
            setTimeout(function() {{
                window.print();
            }}, 500);
        </script>
    </head>
    <body style="margin:0; padding:0;">
        {content_html}
    </body>
    </html>
    """

# ----------------------------------------------------
# 🏷️ [라벨] 40mm x 20mm 전용 HTML 생성 함수
# ----------------------------------------------------
def get_label_content_html(items):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700;900&display=swap');
            
            @media print {
                @page { size: 40mm 20mm; margin: 0; }
                body { margin: 0; padding: 0; }
                .label-wrap {
                    width: 38mm; height: 19mm;
                    page-break-after: always;
                    display: flex; align-items: center;
                    overflow: hidden;
                    font-family: 'Roboto', sans-serif;
                }
            }
            .label-wrap {
                width: 200px; height: 100px;
                border: 1px solid #ddd; margin: 5px;
                display: inline-flex; align-items: center;
                background: white; font-family: sans-serif;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
            }
        </style>
    </head>
    <body>
    """
    
    for item in items:
        img_b64 = image_to_base64(item['img'])
        lot_id = item['lot']       
        cust_name = item['cust']   
        w, h, elec = item['w'], item['h'], item['elec']
        
        # [핵심] 버스바 위치 강조
        w_style = "font-weight: 400;" 
        h_style = "font-weight: 400;"
        if "가로" in elec: w_style = "font-weight: 900; font-size: 1.1em;"
        if "세로" in elec: h_style = "font-weight: 900; font-size: 1.1em;"
            
        dim_html = f"<span style='{w_style}'>{w}</span>x<span style='{h_style}'>{h}</span>"
        
        label_div = f"""
        <div class="label-wrap">
            <div style="width: 38%; text-align: center; padding-left: 1mm;">
                <img src="data:image/png;base64,{img_b64}" style="width: 95%; display: block;">
            </div>
            <div style="width: 62%; padding-left: 1.5mm; display: flex; flex-direction: column; justify-content: center;">
                <div style="font-size: 10pt; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 1px; color: #333;">{lot_id}</div>
                <div style="font-size: 7pt; font-weight: 400; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">🏢 {cust_name}</div>
                <div style="font-size: 8pt; margin-top: 1px;">📏 {dim_html}</div>
            </div>
        </div>
        """
        html += label_div
        
    html += "</body></html>"
    return html

# ----------------------------------------------------
# 📄 [작업지시서] A4 공간 활용형 HTML
# ----------------------------------------------------
def get_work_order_html(items):
    html = """
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
            @media print { @page { size: A4; margin: 10mm; } }
            body { font-family: 'Noto Sans KR', sans-serif; padding: 20px; }
            .job-card { border: 2px solid #000; margin-bottom: 20px; page-break-inside: avoid; }
            .header { background-color: #eee; padding: 10px; border-bottom: 1px solid #000; display: flex; justify-content: space-between; align-items: center; }
            .lot-id { font-size: 24px; font-weight: 900; }
            .info-container { display: flex; border-bottom: 1px solid #000; }
            .qr-box { width: 120px; padding: 10px; border-right: 1px solid #000; display: flex; align-items: center; justify-content: center; }
            .spec-box { flex: 1; padding: 10px; }
            .spec-table { width: 100%; border-collapse: collapse; }
            .spec-table td { padding: 4px; font-size: 14px; }
            .label { font-weight: bold; width: 80px; color: #555; }
            .value { font-weight: bold; font-size: 16px; color: #000; }
            .check-box { display: inline-block; width: 15px; height: 15px; border: 1px solid #000; text-align: center; line-height: 12px; margin-right: 5px; }
            .dim-box { padding: 15px; text-align: center; font-size: 22px; font-weight: bold; }
            .page-header { text-align:center; font-size:20pt; font-weight:900; margin-bottom:20px; text-decoration:underline; }
        </style>
    </head>
    <body>
    """
    
    html += f'<div class="page-header">작업 지시서 (Work Order)</div>'
    
    for item in items:
        img_b64 = image_to_base64(item['img'])
        full_id = item['lot']
        
        fabric_full = item.get('fabric', '-') 
        spec_raw = item.get('spec', '')
        
        # Spec 파싱
        if '|' in spec_raw:
            parts = spec_raw.split('|')
            cut_cond = parts[0].strip()
            lam_cond = parts[1].strip() if len(parts) > 1 else '-'
        else:
            cut_cond = item.get('spec_cut', spec_raw)
            lam_cond = item.get('spec_lam', '-')
        
        # [핵심 로직] 접합 생략 여부 판단
        is_lam = True
        if "생략" in lam_cond or "없음" in lam_cond or "단품" in lam_cond or lam_cond == "-":
            is_lam = False
        
        lam_check_mark = "V" if is_lam else "&nbsp;"
        lam_style = "color: #000;" if is_lam else "color: #ccc; text-decoration: line-through;"
        
        html += f"""
        <div class="job-card">
            <div class="header">
                <span class="lot-id">{full_id}</span>
                <span>{item['cust']} | {datetime.now().strftime('%Y-%m-%d')}</span>
            </div>
            <div class="info-container">
                <div class="qr-box"><img src="data:image/png;base64,{img_b64}" width="100"></div>
                <div class="spec-box">
                    <table class="spec-table">
                        <tr><td class="label">🧵 원단명</td><td class="value">{fabric_full}</td></tr>
                        <tr><td colspan="2"><hr style="margin: 5px 0; border-top: 1px dashed #ccc;"></td></tr>
                        <tr><td class="label">✂️ 커팅</td><td class="value">{cut_cond}</td></tr>
                        <tr><td class="label">🔥 접합</td>
                            <td class="value" style="{lam_style}">
                                <span class="check-box">{lam_check_mark}</span>{lam_cond}
                            </td>
                        </tr>
                    </table>
                </div>
            </div>
            <div class="dim-box">{item['prod']} / {item['w']} x {item['h']} / {item['elec']}</div>
        </div>
        """
        
    html += "</body></html>"
    return html

# ----------------------------------------------------
# 📱 접속 QR HTML
# ----------------------------------------------------
def get_access_qr_content_html(url, mode="big"):
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img_b64 = image_to_base64(qr.make_image(fill_color="black", back_color="white"))
    
    if mode == "big":
        html = f"""<div style="text-align:center; padding-top:50mm;"><div style="border:5px solid black; padding:50px; display:inline-block; border-radius:30px;"><div style="font-size:40pt; font-weight:900; margin-bottom:30px;">🏭 접속 QR</div><img src="data:image/png;base64,{img_b64}" style="width:400px; height:400px;"><div style="font-size:15pt; margin-top:20px; font-family:monospace;">{url}</div></div></div>"""
    else:
        html = '<table style="width:100%; border-collapse:collapse;">'
        for r in range(4):
            html += '<tr>'
            for c in range(2):
                html += f"""<td style="border:1px dashed #999; padding:10px; text-align:center;"><div style="font-weight:bold; font-size:16pt;">시스템 접속</div><img src="data:image/png;base64,{img_b64}" style="width:100px;"></td>"""
            html += '</tr>'
        html += "</table>"
    return html

# ==========================================
# 🖥️ 관리자 UI 메인
# ==========================================
st.sidebar.title("👨‍💼 지시서 설정")
if not st.session_state.fabric_db: st.session_state.fabric_db = fetch_fabric_stock()
if st.sidebar.button("🔄 재고 정보 새로고침", use_container_width=True): st.session_state.fabric_db = fetch_fabric_stock(); st.toast("✅ 완료")

# 탭 구성
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["📝 작업 입력", "📄 지시서 인쇄", "🏷️ 라벨 인쇄", "🔄 QR 재발행", "🧵 원단 재고", "📊 발행 이력", "🔍 제품 추적", "🚨 불량 현황", "📱 접속 QR"])

# ==========================================
# 📝 [Tab 1] 신규 작업 지시 생성 (재고 연동됨)
# ==========================================
with tab1:
    st.markdown("### 📝 신규 작업 지시 등록")
    
    # 1. 재고 DB 불러오기 (없으면 빈 딕셔너리)
    if 'fabric_db' not in st.session_state or not st.session_state.fabric_db:
        st.session_state.fabric_db = fetch_fabric_stock()

    with st.form("order_form"):
        c1, c2 = st.columns([1, 1])
        customer = c1.text_input("고객사 (Customer)", placeholder="예: A건설")
        product = c2.selectbox("제품 종류", ["스마트글라스", "접합필름", "PDLC원단", "일반유리"])
        
        st.divider()
        
        # ----------------------------------------------------------------
        # 🧵 원자재 정보 (재고 리스트 연동 수정)
        # ----------------------------------------------------------------
        c_mat1, c_mat2 = st.columns(2)
        
        # (A) 재고 리스트 만들기: "LOT번호 | 제품명 (잔량: xxx m)"
        stock_options = ["➕ 직접 입력 (미등록 원단)"] 
        if st.session_state.fabric_db:
            for lot, info in st.session_state.fabric_db.items():
                remain = info['total_len'] - info['used_len']
                # 잔량이 0보다 큰 것만 보여주기 (옵션)
                display_text = f"{lot} | {info['name']} (잔량:{remain:.1f}m)"
                stock_options.append(display_text)
        
        # (B) 선택 상자
        selected_stock = c_mat1.selectbox("🧵 사용할 원단 선택", stock_options)
        
        # (C) 선택에 따른 값 처리
        if "직접 입력" in selected_stock:
            # 직접 입력 모드일 때만 텍스트 입력창 활성화
            fabric_lot = c_mat1.text_input("원단 LOT 번호 입력", placeholder="Roll-2312a-KR")
            default_short = ""
        else:
            # 리스트에서 선택했을 때 -> 파이프(|)로 쪼개서 LOT 번호만 추출
            # 예: "Roll-001 | 제품A (잔량:50m)" -> "Roll-001"
            fabric_lot = selected_stock.split(" | ")[0]
            # 선택된 정보를 화면에 보여줌 (읽기 전용처럼 보이게)
            c_mat1.info(f"✅ 선택됨: {fabric_lot}")
            default_short = fabric_lot[:4].upper()

        # (D) ID 약어 입력 (자동 채움)
        # 이미 값이 있다면 유지, 없다면 추출한 4자리 사용
        fabric_short = c_mat2.text_input("🆔 ID용 약어 (4자리)", value=default_short, max_chars=4, help="QR 코드에 들어갈 식별 코드 (예: HCLA)")

        st.divider()

        # (3) 규격 및 전극
        c3, c4, c5 = st.columns([1, 1, 1])
        w = c3.number_input("가로 (W)", min_value=0, step=10)
        h = c4.number_input("세로 (H)", min_value=0, step=10)
        elec_type = c5.selectbox("전극 위치", ["없음", "가로(W) 양쪽", "세로(H) 양쪽", "가로(W)", "세로(H)"])

        # (4) 상세 스펙 (접합 체크박스 포함)
        st.caption("🔧 공정 조건 설정")
        cc1, cc2 = st.columns(2)
        spec_cut = cc1.text_input("✂️ 커팅 조건", placeholder="예: Full(50/80/20)")
        
        is_lamination = cc2.checkbox("🔥 접합(Lamination) 포함", value=True)
        if is_lamination:
            spec_lam = cc2.text_input("🔥 접합 조건", placeholder="예: 1단계(60도/30분)")
        else:
            spec_lam = "⛔ 접합 생략 (필름 마감)"
        
        note = st.text_input("비고 (특이사항)", placeholder="작업자 전달 사항")
        count = st.number_input("수량", min_value=1, value=1)

        # 2. 장바구니 담기
        if st.form_submit_button("➕ 작업 목록 추가", type="primary", use_container_width=True):
            if not customer or not w or not h:
                st.error("고객사, 가로, 세로 사이즈는 필수입니다.")
            elif not fabric_lot:
                st.error("원단 정보가 없습니다. 원단을 선택하거나 직접 입력해주세요.")
            else:
                final_short = fabric_short if fabric_short else fabric_lot[:4].upper().ljust(4, 'X')
                
                st.session_state.order_list.append({
                    "고객사": customer, "제품": product, "규격": f"{w}x{h}",
                    "w": w, "h": h, "전극": elec_type,
                    "spec_cut": spec_cut, "spec_lam": spec_lam, "is_lam": is_lamination,
                    "spec": f"{spec_cut} | {spec_lam}", 
                    "비고": note, "수량": count,
                    "lot_no": fabric_lot,     
                    "lot_short": final_short  
                })
                
                msg = f"리스트 추가됨! (ID 약어: {final_short})"
                if not is_lamination: msg += " - ⚡ 접합 공정 생략"
                st.success(msg)

    # 3. 대기 목록 확인 및 최종 발행
    if st.session_state.order_list:
        st.divider()
        st.markdown(f"### 🛒 발행 대기 목록 ({len(st.session_state.order_list)}건)")
        st.dataframe(pd.DataFrame(st.session_state.order_list)[["고객사", "lot_short", "제품", "규격", "lot_no", "수량"]], use_container_width=True)

        c1, c2 = st.columns([1, 2])
        if c1.button("🗑️ 목록 초기화"): st.session_state.order_list = []; st.rerun()

        # [최종 발행 로직] 13자리 ID 생성
        if c2.button("🚀 최종 발행 및 저장 (Supabase)", type="primary", use_container_width=True):
            date_str = datetime.now().strftime("%y%m%d") # 250122
            product_type_map = {"스마트글라스": "G", "접합필름": "F", "PDLC원단": "P", "일반유리": "N"}
            new_qrs = []
            cnt = 0

            for item in st.session_state.order_list:
                film_part = str(item['lot_short']).upper()
                prod_char = product_type_map.get(item['제품'], "X")

                for _ in range(item['수량']):
                    seq_str = f"{cnt:02d}"
                    final_lot_id = f"{film_part}{date_str}{prod_char}{seq_str}"
                    cnt = (cnt + 1) % 100
                    
                    init_status = "작업대기" if item['is_lam'] else "작업대기(단품)"

                    try:
                        # 1. 작업 지시서 저장
                        supabase.table("work_orders").insert({
                            "lot_no": final_lot_id,
                            "customer": item['고객사'],
                            "product": item['제품'],
                            "dimension": f"{item['규격']} [{item['전극']}]",
                            "spec": item['spec'],
                            "status": init_status,
                            "note": item['비고'],
                            "fabric_lot_no": item['lot_no']
                        }).execute()
                        
                        # [추가 기능] 원단 사용량 차감 (선택 사항)
                        # 여기서는 복잡해질 수 있어 일단 로그만 남깁니다. 
                        # 추후 자동으로 Tab 5의 재고를 깎는 기능도 넣을 수 있습니다.

                        # QR 생성
                        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=1)
                        qr.add_data(final_lot_id)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")
                        
                        new_qrs.append({
                            "lot": final_lot_id, "w": item['w'], "h": item['h'], "elec": item['전극'], 
                            "prod": item['제품'], "cust": item['고객사'], "img": img,
                            "fabric": item['lot_no'], "spec_cut": item['spec_cut'], "spec_lam": item['spec_lam'], "is_lam": item['is_lam']
                        })
                    except Exception as e:
                        st.error(f"저장 중 오류 발생: {e}")

            st.session_state.generated_qrs = new_qrs
            st.session_state.order_list = []
            st.success(f"✅ 총 {len(new_qrs)}건 발행 완료!"); time.sleep(1); st.rerun()

# ==========================================
# 📄 [Tab 2] 작업 지시서 인쇄
# ==========================================
with tab2:
    st.header("📄 작업 지시서 인쇄")
    if st.session_state.generated_qrs:
        content_html = get_work_order_html(st.session_state.generated_qrs)
        st.components.v1.html(content_html, height=1000, scrolling=True)
        if st.button("🖨️ 지시서 인쇄", type="primary"):
            full_html = generate_print_html(content_html)
            components.html(full_html, height=0, width=0)
    else:
        st.info("⚠️ 현재 발행된 작업이 없습니다.")

# ==========================================
# 🏷️ [Tab 3] 라벨 인쇄 (40x20mm)
# ==========================================
with tab3:
    st.header("🏷️ QR 라벨 인쇄 (40x20mm)")
    if st.session_state.generated_qrs:
        content_html = get_label_content_html(st.session_state.generated_qrs)
        st.components.v1.html(content_html, height=600, scrolling=True)
        if st.button("🖨️ 라벨 인쇄", type="primary"):
            full_html = generate_print_html(content_html)
            components.html(full_html, height=0, width=0)
    else:
        st.info("👈 먼저 [작업 입력] 탭에서 발행을 진행해주세요.")

# ==========================================
# 🔄 [Tab 4] QR 재발행
# ==========================================
with tab4:
    st.header("🔄 QR 재발행")
    with st.form("reprint"):
        c1,c2=st.columns([3,1]); s_d=c1.date_input("날짜"); btn=c2.form_submit_button("조회")
        if btn:
            try: 
                start_ts = s_d.strftime("%Y-%m-%d 00:00:00"); end_ts = s_d.strftime("%Y-%m-%d 23:59:59")
                res=supabase.table("work_orders").select("*").gte("created_at", start_ts).lte("created_at", end_ts).execute()
                st.session_state.reprint_data=res.data
            except Exception as e: st.error(f"오류: {e}")
            
    if 'reprint_data' in st.session_state and st.session_state.reprint_data:
        df=pd.DataFrame(st.session_state.reprint_data)
        if not df.empty:
            edited_reprint = st.data_editor(df.assign(선택=False), hide_index=True, column_config={"선택": st.column_config.CheckboxColumn()})
            sel_rows = edited_reprint[edited_reprint["선택"]]
            
            if not sel_rows.empty:
                st.divider()
                reprint_type = st.radio("재발행 형태", ["📄 작업지시서 (A4)", "🏷️ 라벨 (40x20mm)"], horizontal=True)
                
                rep_items = []
                for _, row in sel_rows.iterrows():
                    dim_str = row['dimension']; w, h, elec = "0", "0", "Unknown"
                    try:
                        match = re.search(r'(\d+)x(\d+)\s*\[(.*?)\]', dim_str) 
                        if match: w, h, elec = match.group(1), match.group(2), match.group(3)
                        else:
                            elec_match = re.search(r'\[(.*?)\]', dim_str); elec = elec_match.group(1) if elec_match else ""
                            nums = re.findall(r'\d+', dim_str); 
                            if len(nums) >= 2: w, h = nums[0], nums[1]
                    except: pass
                    
                    qr = qrcode.QRCode(box_size=5, border=1); qr.add_data(row['lot_no']); qr.make(fit=True); img = qr.make_image(fill_color="black", back_color="white")
                    
                    rep_items.append({
                        "lot": row['lot_no'], "w": w, "h": h, "elec": elec, 
                        "cust": row['customer'], "prod": row['product'], 
                        "fabric": row.get('fabric_lot_no', '-'), "spec": row.get('spec', ''), "img": img
                    })
                
                if "작업지시서" in reprint_type:
                    content_html = get_work_order_html(rep_items)
                else:
                    content_html = get_label_content_html(rep_items)
                    
                st.components.v1.html(content_html, height=500, scrolling=True)
                
                if st.button("🖨️ 선택 항목 재발행", type="primary"):
                    full_html = generate_print_html(content_html)
                    components.html(full_html, height=0, width=0)

# ==========================================
# 🧵 [Tab 5] 원단 재고
# ==========================================
with tab5:
    with st.form("fabric_in"):
        st.markdown("##### 📥 원단 입고 등록")
        c1,c2,c3=st.columns(3); n_lot=c1.text_input("LOT"); n_name=c2.text_input("제품명"); n_w=c3.number_input("폭(mm)",1200)
        c4,c5,c6=st.columns(3); n_tot=c4.number_input("총길이(m)",100.0); n_rem=c5.number_input("현재 잔량(m)",100.0)
        if st.form_submit_button("입고 등록"):
            supabase.table("fabric_stock").insert({"lot_no":n_lot,"name":n_name,"width":n_w,"total_len":n_tot,"used_len":n_tot-n_rem}).execute(); st.rerun()
    st.divider()
    res=supabase.table("fabric_stock").select("*").execute(); st.data_editor(pd.DataFrame(res.data),hide_index=True, use_container_width=True)

# ==========================================
# 📊 [Tab 6] 통합 관제 및 이력 관리
# ==========================================
with tab6:
    st.title("📊 생산 현황 및 이력 관리")
    try:
        res = supabase.table("work_orders").select("*").order("created_at", desc=True).limit(200).execute()
        df_log = pd.DataFrame(res.data)
    except Exception as e: st.error(f"조회 실패: {e}"); df_log = pd.DataFrame()

    if not df_log.empty:
        if "created_at" in df_log.columns: df_log["created_at"] = pd.to_datetime(df_log["created_at"])

        st.markdown("### 🏭 실시간 공정 현황")
        status_counts = df_log['status'].value_counts()
        k1, k2, k3, k4 = st.columns(4)
        wait_cnt = status_counts.get("작업대기", 0) + status_counts.get("작업대기(단품)", 0) # 단품 대기도 포함
        k1.metric("⚪ 작업 대기", f"{wait_cnt}건")
        
        # 진행중: 대기, 완료, End, 불량 제외
        ing_cnt = sum([v for k, v in status_counts.items() if not any(x in k for x in ["작업대기", "완료", "End", "불량"])])
        k2.metric("🔵 공정 진행중", f"{ing_cnt}건")
        
        done_cnt = status_counts.get("완료", 0) + status_counts.get("End", 0)
        k3.metric("🟢 생산 완료", f"{done_cnt}건")
        
        defect_cnt = df_log[df_log['status'].str.contains("불량|보류", na=False)].shape[0]
        k4.metric("🔴 불량/이슈", f"{defect_cnt}건")

        st.divider()
        st.markdown("### 📋 발행 이력 조회")
        
        c_filter1, c_filter2 = st.columns(2)
        filter_status = c_filter1.multiselect("상태별 필터", options=df_log['status'].unique())
        filter_lot = c_filter2.text_input("LOT 번호 검색", placeholder="SG-...")
        
        df_view = df_log.copy()
        if filter_status: df_view = df_view[df_view['status'].isin(filter_status)]
        if filter_lot: df_view = df_view[df_view['lot_no'].str.contains(filter_lot, case=False)]

        df_view.insert(0, "선택", False)
        
        edited_log = st.data_editor(
            df_view, hide_index=True, use_container_width=True,
            column_config={
                "선택": st.column_config.CheckboxColumn(width="small"),
                "created_at": st.column_config.DatetimeColumn("발행일시", format="MM-DD HH:mm"),
                "lot_no": st.column_config.TextColumn("LOT 번호", width="medium"),
                "status": st.column_config.TextColumn("현재 상태"),
                "spec": st.column_config.TextColumn("스펙 요약", width="medium"),
            }, key="history_editor"
        )

        selected_rows = edited_log[edited_log["선택"]]
        
        if not selected_rows.empty:
            st.markdown("---")
            detail_tab, delete_tab = st.tabs(["🔍 상세 조건 확인", "🗑️ 데이터 삭제"])
            
            with detail_tab:
                row = selected_rows.iloc[0]
                st.info(f"선택된 항목 중 최상단 `{row['lot_no']}`의 상세 내용입니다.")
                spec_text = row.get("spec", "")
                
                full_cut, half_cut, lam_cond = "정보 없음", "정보 없음", "정보 없음"
                if spec_text:
                    parts = spec_text.split('|')
                    for p in parts:
                        p = p.strip()
                        if "Full" in p: full_cut = p.replace("Full", "").strip("()")
                        elif "Half" in p: half_cut = p.replace("Half", "").strip("()")
                        elif "단계" in p or "℃" in p or "생략" in p or "없음" in p: lam_cond = p
                
                with st.container(border=True):
                    st.markdown(f"#### 📌 LOT: `{row['lot_no']}` 작업 지시서")
                    c_cut1, c_cut2 = st.columns(2)
                    with c_cut1:
                        st.markdown("##### ✂️ 풀컷 (Full Cut)")
                        st.write(full_cut)
                    with c_cut2:
                        st.markdown("##### 🗡️ 하프컷 (Half Cut)")
                        st.write(half_cut)
                    st.divider()
                    st.markdown("##### 🔥 접합 유리 조건")
                    
                    # 접합 생략 시 강조
                    if "생략" in lam_cond or "없음" in lam_cond:
                        st.warning(f"⛔ {lam_cond}")
                    else:
                        st.write(lam_cond.replace("->", " → "))
                        
                    st.caption(f"🧵 원단 정보: {row.get('fabric_lot_no', '-')}")

            with delete_tab:
                st.warning(f"선택된 {len(selected_rows)}개의 데이터를 영구 삭제합니다.")
                if st.toggle("🚨 관리자 삭제 모드 켜기"):
                    c_confirm, c_btn = st.columns([3, 1])
                    if c_btn.button("🗑️ 삭제 실행", type="primary"):
                        delete_lots = selected_rows['lot_no'].tolist()
                        supabase.table("work_orders").delete().in_("lot_no", delete_lots).execute()
                        st.toast("삭제 완료!"); time.sleep(1); st.rerun()
    else:
        st.info("조회된 데이터가 없습니다.")

# ==========================================
# 🔍 [Tab 7, 8, 9] 기타 기능
# ==========================================
with tab7:
    with st.form("track"): c1,c2=st.columns([4,1]); l=c1.text_input("LOT"); b=c2.form_submit_button("조회")
    if b: r=supabase.table("work_orders").select("*").eq("lot_no",l).execute(); st.write(r.data)

with tab8: res=supabase.table("defects").select("*").execute(); st.dataframe(pd.DataFrame(res.data), use_container_width=True)

with tab9:
    st.header("📱 현장 접속 QR")
    content_html = get_access_qr_content_html(APP_URL, "big")
    st.components.v1.html(content_html, height=600)
    if st.button("🖨️ 접속 QR 인쇄"):
        full_html = generate_print_html(content_html)
        components.html(full_html, height=0, width=0)
