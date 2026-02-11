import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import qrcode
import io
import base64
import math
import time
import re
import os
import requests 
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# ⚙️ [필수] 페이지 설정은 무조건 맨 처음에!
# ==========================================
st.set_page_config(page_title="(주)베스트룸 생산관리", page_icon="🏭", layout="wide")

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

# ==============================================================================
# 🛠️ [기능 정의 구역] 함수들을 먼저 정의합니다 (NameError 방지)
# ==============================================================================

# 1. 공정 순서 위반 방지
def check_process_sequence(lot_no, current_step):
    try:
        response = supabase.table("production_logs") \
            .select("step") \
            .eq("lot_no", lot_no) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        last_step = response.data[0]['step'] if response.data else "작업대기"
    except Exception:
        return False, "데이터 조회 중 오류"
    return True, "OK"

# 2. 이미지 변환
def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# 3. 재고 조회 (단축코드 포함)
def fetch_fabric_stock():
    try:
        response = supabase.table("fabric_stock").select("*").execute()
        return {row['lot_no']: row for row in response.data}
    except: return {}

# 4. 폰트 로드
@st.cache_resource
def load_korean_font(size):
    font_filename = "NanumGothic-Bold.ttf"
    if not os.path.exists(font_filename):
        url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
        try:
            r = requests.get(url)
            with open(font_filename, 'wb') as f:
                f.write(r.content)
        except:
            return ImageFont.load_default()
    return ImageFont.truetype(font_filename, size)

# 5. 라벨 이미지 생성 (하이픈 제거 적용)
def create_label_strip_image(items, rotate=False):
    LABEL_W = 472; LABEL_H = 236
    total_count = len(items)
    if total_count == 0: return None
    strip_w = LABEL_W * total_count; strip_h = LABEL_H
    full_img = Image.new('RGB', (strip_w, strip_h), 'white')
    draw = ImageDraw.Draw(full_img)
    font_large = load_korean_font(28)
    font_medium = load_korean_font(24)

    for i, item in enumerate(items):
        x_offset = i * LABEL_W
        draw.rectangle([x_offset, 0, x_offset + LABEL_W-1, LABEL_H-1], outline="#cccccc", width=2)
        
        # [QR 하이픈 제거]
        qr_data_clean = item['lot'].replace("-", "")
        qr = qrcode.QRCode(box_size=5, border=0)
        qr.add_data(qr_data_clean)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").resize((190, 190))
        
        full_img.paste(qr_img, (x_offset + 10, (LABEL_H - 190) // 2))
        text_x = x_offset + 210
        draw.text((text_x, 25), item['lot'], font=font_large, fill="black")
        draw.text((text_x, 75), f"{item['cust']}", font=font_large if len(item['cust']) < 5 else font_medium, fill="black")
        draw.text((text_x, 125), f"{item['w']} x {item['h']}", font=font_large, fill="black")
        draw.text((text_x, 170), f"[{item['elec']}]", font=font_large, fill="black")
        
        if i < total_count - 1:
            line_x = x_offset + LABEL_W - 1
            draw.line([(line_x, 0), (line_x, LABEL_H)], fill="#999999", width=1)

    if rotate: full_img = full_img.rotate(90, expand=True)
    buf = io.BytesIO(); full_img.save(buf, format="PNG")
    return buf.getvalue()

# 6. 인쇄 스크립트
def generate_print_html(content_html):
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Print</title>
    <script>setTimeout(function() {{ window.print(); }}, 500);</script></head>
    <body style="margin:0; padding:0;">{content_html}</body></html>"""

# 7. 라벨 미리보기 HTML
def get_label_content_html(items, mode="roll", rotate=False, margin_top=0):
    transform_css = "transform: rotate(90deg);" if rotate else ""
    css_wrap = f"width: 38mm; height: 19mm; page-break-after: always; display: flex; align-items: center; justify-content: center; overflow: hidden; border: 1px solid #ddd; margin-top: {margin_top}mm;" if mode == "roll" else "width: 42mm; height: 22mm; display: inline-flex; align-items: center; justify-content: center; margin: 2px; border: 1px dashed #ccc; float: left;"
    
    html = f"""<!DOCTYPE html><html><head><style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;900&display=swap');
    @media print {{ @page {{ size: 40mm 20mm; margin: 0; }} body {{ margin: 0; }} }}
    .label-box {{ {css_wrap} font-family: 'Roboto', sans-serif; background: white; box-sizing: border-box; }}
    .txt-bold {{ font-weight: 900; font-size: 11pt; color: black; line-height: 1.2; }}
    </style></head><body><div style="display:flex; flex-wrap:wrap;">"""
    
    for item in items:
        qr_clean = item['lot'].replace("-", "")
        qr = qrcode.QRCode(box_size=5, border=0); qr.add_data(qr_clean); qr.make(fit=True)
        img_b64 = image_to_base64(qr.make_image(fill_color="black", back_color="white"))
        
        html += f"""<div class="label-box"><div style="width:38mm; height:19mm; display:flex; align-items:center; {transform_css}">
        <div style="width:38%; text-align:center;"><img src="data:image/png;base64,{img_b64}" style="width:95%;"></div>
        <div style="width:62%; padding-left:1.5mm;"><div class="txt-bold">{item['lot']}</div><div class="txt-bold">{item['cust']}</div><div class="txt-bold">{item['w']} x {item['h']}</div><div class="txt-bold">[{item['elec']}]</div></div>
        </div></div>"""
    return html + "</div></body></html>"

# 8. 작업지시서 A4 2x4 HTML
def get_work_order_html(items):
    html = """<html><head><style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
    @media print { @page { size: A4; margin: 5mm; } body { margin: 0; } .page-break { page-break-after: always; } }
    body { font-family: 'Noto Sans KR', sans-serif; color: #000; }
    .job-card { width: 49%; height: 62.5mm; border: 2px solid #000; box-sizing: border-box; margin-bottom: 1mm; display: flex; flex-direction: column; overflow: hidden; }
    .card-header { background-color: #e0e0e0; padding: 2px 8px; border-bottom: 1px solid #000; display: flex; justify-content: space-between; align-items: center; height: 24px; }
    .dim-box { height: 40px; border-top: 2px solid #000; display: flex; align-items: center; justify-content: center; background-color: #fff; }
    .spec-table { width: 100%; border-collapse: collapse; }
    .spec-table td { padding: 1px 0; font-size: 11px; vertical-align: middle; }
    .lbl { font-weight: 900; width: 45px; color: #333; } .val { font-weight: 700; color: #000; }
    </style></head><body><div style="display:flex; flex-wrap:wrap; justify-content:space-between;">"""
    
    chunk_size = 8
    for i in range(0, len(items), chunk_size):
        chunk = items[i:i + chunk_size]
        html += f'<div style="width:100%; text-align:center; font-size:20pt; font-weight:900; margin-bottom:3mm; text-decoration:underline;">작업 지시서 (Work Order)</div><div style="display:flex; flex-wrap:wrap; justify-content:space-between; width:100%;">'
        
        for item in chunk:
            qr_clean = item['lot'].replace("-", "") 
            qr = qrcode.QRCode(box_size=5, border=0); qr.add_data(qr_clean); qr.make(fit=True)
            img_b64 = image_to_base64(qr.make_image(fill_color="black", back_color="white"))
            
            is_lam = True
            lam_cond = item.get('spec_lam', '-')
            if "생략" in lam_cond or "없음" in lam_cond or "단품" in lam_cond or lam_cond == "-": is_lam = False
            
            if not is_lam:
                lam_display = "<span style='text-decoration:line-through; color:red; font-weight:bold;'>접합생략</span> <span style='color:#000; text-decoration:none; font-weight:bold;'>(필름마감)</span>"
            else:
                lam_display = f"<span style='color:#000;'>{lam_cond}</span>"

            w, h, elec = item['w'], item['h'], item['elec']
            base_css = "font-size: 28px; color: #000; margin: 0 2px;"
            w_css = base_css + ("font-weight: 900; text-decoration: underline;" if "가로" in elec or "W" in elec.upper() else "font-weight: 500; color: #555;")
            h_css = base_css + ("font-weight: 900; text-decoration: underline;" if "세로" in elec or "H" in elec.upper() else "font-weight: 500; color: #555;")
            
            html += f"""
            <div class="job-card">
                <div class="card-header">
                    <div><span style="font-size:13px; font-weight:900;">{item['lot']}</span> <span style="font-size:12px; font-weight:900; color:#333;">[{item['prod']}]</span></div>
                    <div style="font-size:10px; font-weight:700;">{item['cust']} | {datetime.now().strftime('%m-%d')}</div>
                </div>
                <div style="display:flex; flex:1; overflow:hidden;">
                    <div style="width:80px; display:flex; align-items:center; justify-content:center; border-right:1px solid #000;"><img src="data:image/png;base64,{img_b64}" style="width:100%;"></div>
                    <div style="flex:1; padding:2px 6px;">
                        <table class="spec-table">
                            <tr><td class="lbl">🧵 원단</td><td class="val">{item.get('fabric','-')}</td></tr>
                            <tr><td colspan="2"><hr style="margin:2px 0; border-top:1px dashed #ccc;"></td></tr>
                            <tr><td class="lbl">✂️ 커팅</td><td class="val">{item.get('spec_cut','-')}</td></tr>
                            <tr><td class="lbl">🔥 접합</td><td class="val">{lam_display}</td></tr>
                            <tr><td class="lbl" style="color:red;">⚠️ 특이</td><td class="val" style="color:red;">{item.get('note','-')}</td></tr>
                        </table>
                    </div>
                </div>
                <div class="dim-box">
                    <span style='{w_css}'>{w}</span><span style='font-size:20px; font-weight:bold; margin:0 5px;'>X</span><span style='{h_css}'>{h}</span>
                    <span style="font-size:18px; font-weight:900; margin-left:15px;">[{elec}]</span>
                </div>
            </div>"""
        html += '</div><div class="page-break"></div>'
    return html + "</body></html>"

# 9. [복구] 접속 QR 생성 함수
def get_access_qr_content_html(url, mode="big"):
    qr = qrcode.QRCode(box_size=10, border=1); qr.add_data(url); qr.make(fit=True)
    img_b64 = image_to_base64(qr.make_image(fill_color="black", back_color="white"))
    return f'<div style="text-align:center; padding-top:50mm;"><div style="border:5px solid black; padding:30px; display:inline-block; border-radius:20px;"><div style="font-size:30pt; font-weight:900;">🏭 시스템 접속 QR</div><br><img src="data:image/png;base64,{img_b64}" style="width:350px;"></div></div>'

# 10. 견적서 HTML
def get_quotation_html(cust_data, items_df, totals):
    logo_base64 = ""
    if os.path.exists("pages/company_logo.png"):
        with open("pages/company_logo.png", "rb") as f: logo_base64 = base64.b64encode(f.read()).decode()
    elif os.path.exists("company_logo.png"):
        with open("company_logo.png", "rb") as f: logo_base64 = base64.b64encode(f.read()).decode()
            
    today_str = datetime.now().strftime("%Y-%m-%d")
    html = f"""<html><head><style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
    body {{ font-family: 'Noto Sans KR', sans-serif; font-size: 11px; margin: 0; padding: 20px; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid #000; }} th, td {{ border: 1px solid #000; padding: 4px 6px; }}
    .title {{ text-align: center; font-size: 30px; font-weight: 900; margin-bottom: 25px; letter-spacing: 10px; }}
    .header-layout {{ width: 100%; border: none; margin-bottom: 10px; }} .header-layout td {{ border: none; padding: 0; vertical-align: top; }}
    .info-box {{ width: 100%; border: 2px solid #000; }} .info-box td {{ border: 1px solid #000; }}
    .label-cell {{ background-color: #e0e0e0; text-align: center; font-weight: bold; width: 80px; }}
    .item-table {{ width: 100%; margin-top: 5px; border: 2px solid #000; }}
    .item-header {{ background-color: #f2f2f2; text-align: center; font-weight: bold; height: 30px; }}
    .item-row td {{ height: 24px; font-size: 11px; }}
    .txt-c {{ text-align: center; }} .txt-r {{ text-align: right; padding-right: 5px; }}
    </style></head><body>
    <div class="title">견 적 서</div>
    <table class="header-layout"><tr><td width="48%"><table class="info-box">
    <tr><td class="label-cell">수신처</td><td class="value-cell" style="font-weight:bold; color:#0033cc;">{cust_data['name']}</td></tr>
    <tr><td class="label-cell">참 조</td><td class="value-cell">{cust_data['ref']}</td></tr>
    </table></td><td width="4%"></td><td width="48%"><table class="info-box">
    <tr><td rowspan="4" width="20%" style="text-align:center;"><img src="data:image/png;base64,{logo_base64}" style="max-width:80px;"></td><td class="label-cell">등록번호</td><td colspan="3">108-81-49494</td></tr>
    <tr><td class="label-cell">상 호</td><td>(주)베스트룸</td><td class="label-cell">대표</td><td>이 광 석</td></tr>
    <tr><td class="label-cell">주 소</td><td colspan="3" style="font-size:10px;">강원도 강릉시 과학단지로 106-40</td></tr>
    <tr><td class="label-cell">전 화</td><td>033-655-2745</td><td class="label-cell">담당</td><td>김명자 이사</td></tr>
    </table></td></tr></table>
    <table class="item-table"><tr class="item-header"><td>구분</td><td>품명</td><td>수량</td><td>단가</td><td>공급가액</td><td>비고</td></tr>"""
    
    for _, row in items_df.iterrows():
        price = f"{int(row['단가']):,}" if row['단가'] else "-"
        total = f"{int(row['공급가']):,}" if row['공급가'] else "-"
        html += f"""<tr class="item-row"><td class="txt-c">{row['구분']}</td><td>{row['품명']}</td><td class="txt-c">{row['수량']}</td><td class="txt-r">{price}</td><td class="txt-r">{total}</td><td>{row['비고']}</td></tr>"""
        
    for _ in range(max(0, 15 - len(items_df))): html += '<tr class="item-row"><td></td><td></td><td></td><td></td><td></td><td></td></tr>'
    
    html += f"""<tr style="background-color:#fff5e6; font-weight:bold; height:30px;"><td colspan="4" class="txt-c">합 계</td><td colspan="2" class="txt-r" style="color:#cc0000; font-size:14px;">₩ {totals['grand_total']:,}</td></tr></table></body></html>"""
    return html

# ==========================================
# 🖥️ 관리자 UI 시작
# ==========================================
APP_URL = "https://bt-app-pwgumeleefkwpf3xsu5bob.streamlit.app/"
if 'order_list' not in st.session_state: st.session_state.order_list = []
if 'generated_qrs' not in st.session_state: st.session_state.generated_qrs = []
if 'fabric_db' not in st.session_state: st.session_state.fabric_db = {}
if 'quote_items' not in st.session_state: st.session_state.quote_items = pd.DataFrame([{"구분": "자재비", "품명": "SMART 뷰 유리", "수량": 1, "단위": "EA", "단가": 0, "공급가": 0, "비고": ""}])

st.sidebar.title("👨‍💼 지시서 설정")
if st.sidebar.button("🔄 재고 정보 새로고침", use_container_width=True): 
    st.session_state.fabric_db = fetch_fabric_stock()
    st.toast("✅ 완료")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs(["📝 작업 입력", "📄 지시서 인쇄", "🏷️ 라벨 인쇄", "🔄 QR 재발행", "🧵 원단 재고", "📊 발행 이력", "🔍 제품 추적", "🚨 불량 현황", "📱 접속 QR", "📑 견적서 작성"])

# [Tab 1] 작업 입력
with tab1:
    st.markdown("### 📝 신규 작업 지시 등록")
    if not st.session_state.fabric_db: st.session_state.fabric_db = fetch_fabric_stock()
    
    with st.form("order_form"):
        c1, c2 = st.columns([1, 1])
        customer = c1.text_input("고객사 (Customer)", placeholder="예: A건설")
        product = c2.selectbox("제품 종류", ["스마트글라스", "접합필름", "PDLC원단", "일반유리"])
        st.divider()
        c_mat1, c_mat2 = st.columns(2)
        
        stock_options = ["➕ 직접 입력"] 
        if st.session_state.fabric_db:
            for lot, info in st.session_state.fabric_db.items():
                stock_options.append(f"{lot} | {info['name']}")
        
        selected_stock = c_mat1.selectbox("🧵 사용할 원단 선택", stock_options)
        
        default_short = "ROLL"
        fabric_lot = ""
        
        if "직접 입력" in selected_stock:
            fabric_lot = c_mat1.text_input("원단 LOT 번호 입력", placeholder="Roll-2312a-KR")
        else:
            fabric_lot = selected_stock.split(" | ")[0]
            c_mat1.info(f"✅ 선택됨: {fabric_lot}")
            sel_info = st.session_state.fabric_db.get(fabric_lot, {})
            if sel_info.get('short_code'): default_short = sel_info.get('short_code')
        
        fabric_short = c_mat2.text_input("🆔 식별코드 (4자리)", value=default_short, max_chars=4, key=f"short_code_{fabric_lot}")
        
        st.divider()
        c3, c4, c5 = st.columns([1, 1, 1])
        w = c3.number_input("가로 (W)", min_value=0, step=10)
        h = c4.number_input("세로 (H)", min_value=0, step=10)
        elec_type = c5.selectbox("전극 위치", ["없음", "가로(W) 양쪽", "세로(H) 양쪽", "가로(W) 상단", "세로(H) 우측"])
        
        cc1, cc2 = st.columns(2)
        spec_cut = cc1.text_input("✂️ 커팅 조건", placeholder="예: Full(50/80/20)")
        is_lamination = cc2.checkbox("🔥 접합(Lamination) 포함", value=True)
        spec_lam = cc2.text_input("🔥 접합 조건", placeholder="예: 1단계") if is_lamination else "⛔ 접합 생략 (필름 마감)"
        
        note = st.text_input("비고", placeholder="특이사항")
        count = st.number_input("수량", min_value=1, value=1)
        
        if st.form_submit_button("➕ 작업 목록 추가", type="primary", use_container_width=True):
            input_short = str(fabric_short).strip().upper()
            final_short = input_short if input_short else "ROLL"
            final_short = final_short.ljust(4, 'X')
            
            st.session_state.order_list.append({
                "고객사": customer, "제품": product, "규격": f"{w}x{h}", "w": w, "h": h, "전극": elec_type,
                "spec_cut": spec_cut, "spec_lam": spec_lam, "is_lam": is_lamination,
                "spec": f"{spec_cut} | {spec_lam}", "비고": note, "수량": count, "lot_no": fabric_lot, "lot_short": final_short
            })
            st.success(f"리스트 추가됨! (ID: {final_short})")

    if st.session_state.order_list:
        st.dataframe(pd.DataFrame(st.session_state.order_list)[["고객사", "lot_short", "제품", "규격", "spec_lam", "수량"]], use_container_width=True)
        if st.button("🚀 최종 발행 및 저장"):
            date_str = datetime.now().strftime("%y%m%d")
            prod_map = {"스마트글라스": "G", "접합필름": "F", "PDLC원단": "P", "일반유리": "N"}
            new_qrs = []
            cnt = 0
            for item in st.session_state.order_list:
                prod_char = prod_map.get(item['제품'], "X")
                for _ in range(item['수량']):
                    final_lot_id = f"{item['lot_short']}{date_str}{prod_char}{cnt:02d}"
                    cnt = (cnt + 1) % 100
                    try:
                        supabase.table("work_orders").insert({
                            "lot_no": final_lot_id, "customer": item['고객사'], "product": item['제품'],
                            "dimension": f"{item['규격']} [{item['전극']}]", "spec": item['spec'],
                            "status": "작업대기" if item['is_lam'] else "작업대기(단품)", "note": item['비고'], "fabric_lot_no": item['lot_no']
                        }).execute()
                        new_qrs.append({**item, "lot": final_lot_id})
                    except: pass
            st.session_state.generated_qrs = new_qrs
            st.session_state.order_list = []
            st.rerun()

# [Tab 2] 지시서 인쇄
with tab2:
    if st.session_state.generated_qrs:
        html = get_work_order_html(st.session_state.generated_qrs)
        st.components.v1.html(html, height=1000, scrolling=True)
        if st.button("🖨️ 인쇄하기"): components.html(generate_print_html(html), height=0)
    else: st.info("발행된 작업이 없습니다.")

# [Tab 3] 라벨 인쇄
with tab3:
    if st.session_state.generated_qrs:
        html = get_label_content_html(st.session_state.generated_qrs)
        st.components.v1.html(html, height=600, scrolling=True)
        if st.button("🖨️ 라벨 인쇄"): components.html(generate_print_html(html), height=0)
    else: st.info("발행된 작업이 없습니다.")

# [Tab 4] QR 재발행
with tab4:
    with st.form("reprint"):
        s_d = st.date_input("날짜")
        if st.form_submit_button("조회"):
            res = supabase.table("work_orders").select("*").gte("created_at", s_d.strftime("%Y-%m-%d 00:00:00")).execute()
            st.session_state.reprint_data = res.data
    
    if 'reprint_data' in st.session_state and st.session_state.reprint_data:
        df = pd.DataFrame(st.session_state.reprint_data)
        edited = st.data_editor(df.assign(선택=False), column_config={"선택": st.column_config.CheckboxColumn()})
        sel = edited[edited["선택"]]
        if not sel.empty:
            if st.button("🖨️ 선택 항목 재발행"):
                rep_items = []
                for _, r in sel.iterrows():
                    w, h, elec = "0", "0", ""
                    match = re.search(r'(\d+)x(\d+)\s*\[(.*?)\]', r['dimension'])
                    if match: w, h, elec = match.groups()
                    rep_items.append({"lot": r['lot_no'], "cust": r['customer'], "prod": r['product'], "w": w, "h": h, "elec": elec, "fabric": r.get('fabric_lot_no','-'), "spec_cut": r.get('spec',''), "spec_lam": r.get('spec',''), "note": r.get('note','')})
                
                html = get_work_order_html(rep_items)
                components.html(generate_print_html(html), height=0)

# [Tab 5] 원단 재고
with tab5:
    with st.form("fabric_in"):
        c1, c2, c3 = st.columns(3)
        n_lot = c1.text_input("LOT"); n_name = c2.text_input("제품명"); n_short = c3.text_input("단축코드(4자리)")
        if st.form_submit_button("입고 등록"):
            supabase.table("fabric_stock").insert({"lot_no": n_lot, "name": n_name, "short_code": n_short}).execute()
            st.rerun()
    st.data_editor(pd.DataFrame(supabase.table("fabric_stock").select("*").execute().data))

# [Tab 6] 발행 이력 (작업자 데이터 확인)
with tab6:
    res = supabase.table("work_orders").select("*").order("created_at", desc=True).limit(200).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        sel_rows = st.data_editor(df.assign(선택=False), column_config={"선택": st.column_config.CheckboxColumn()})
        sel = sel_rows[sel_rows["선택"]]
        if not sel.empty:
            # [추가] 작업자 상세 로그 조회
            sel_row = sel.iloc[0]
            st.markdown(f"#### 📜 [{sel_row['lot_no']}] 작업자 상세 입력 로그")
            logs = supabase.table("production_logs").select("*").eq("lot_no", sel_row['lot_no']).order("created_at").execute()
            if logs.data: 
                # 데이터프레임으로 깔끔하게 보여주기
                st.dataframe(pd.DataFrame(logs.data)[['step', 'data', 'worker', 'created_at']], use_container_width=True)
            else: st.warning("작업 이력이 없습니다.")
            
            st.divider()
            if st.button("🗑️ 삭제 실행", type="primary"):
                supabase.table("work_orders").delete().in_("lot_no", sel['lot_no'].tolist()).execute()
                st.rerun()

# [Tab 7] 제품 추적 (복구)
with tab7:
    with st.form("track_form"):
        track_lot = st.text_input("추적할 LOT 번호 입력")
        if st.form_submit_button("검색"):
            r = supabase.table("production_logs").select("*").eq("lot_no", track_lot).order("created_at").execute()
            if r.data: st.dataframe(r.data)
            else: st.error("이력이 없습니다.")

# [Tab 8] 불량 현황 (복구)
with tab8:
    st.markdown("### 🚨 불량 등록 현황")
    r = supabase.table("defects").select("*").order("created_at", desc=True).execute()
    if r.data: st.dataframe(r.data)
    else: st.info("불량 내역이 없습니다.")

# [Tab 9] 접속 QR (복구)
with tab9:
    html = get_access_qr_content_html(APP_URL)
    st.components.v1.html(html, height=500)
    if st.button("🖨️ 접속 QR 인쇄"): components.html(generate_print_html(html), height=0)

# [Tab 10] 견적서
with tab10:
    st.markdown("### 📑 견적서 작성")
    c1, c2 = st.columns(2)
    q_cust = c1.text_input("고객사명"); q_ref = c2.text_input("참조")
    
    edited = st.data_editor(st.session_state.quote_items, num_rows="dynamic", use_container_width=True)
    if not edited.empty:
        edited['수량'] = pd.to_numeric(edited['수량'], errors='coerce').fillna(0)
        edited['단가'] = pd.to_numeric(edited['단가'], errors='coerce').fillna(0)
        edited['공급가'] = edited['수량'] * edited['단가']
        total = int(edited['공급가'].sum())
        vat = int(total * 0.1)
        
        st.metric("총 합계", f"{total + vat:,} 원")
        if st.button("🖨️ 견적서 인쇄"):
            html = get_quotation_html({"name": q_cust, "ref": q_ref}, edited, {"grand_total": total+vat, "supply": total, "vat": vat})
            components.html(generate_print_html(html), height=0)
