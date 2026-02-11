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
# 🛠️ [기능 정의 구역] 
# ==============================================================================

# 1. 공정 순서 위반 방지 함수
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
        return False, "데이터 조회 중 오류가 발생했습니다."

    required_previous_step = {
        "원단커팅": ["작업대기"],
        "하프커팅": ["원단커팅", "Full", "풀"], 
        "전극": ["하프커팅", "Half", "하프"],
        "접합": ["전극"],
        "출고": ["접합", "완료", "전극"]
    }

    if last_step == current_step:
        return False, f"⚠️ 이미 '{current_step}' 작업이 등록되어 있습니다."

    valid_prev_steps = required_previous_step.get(current_step)
    if valid_prev_steps:
        is_valid = any(req in last_step for req in valid_prev_steps)
        if not is_valid:
            return False, f"🚨 [순서 오류] 현재 상태는 '{last_step}' 입니다.\n선행 공정이 완료되지 않아 '{current_step}' 작업을 할 수 없습니다."
    
    return True, "OK"

# 2. 이미지 변환 함수
def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# 3. 재고 조회 함수
def fetch_fabric_stock():
    try:
        response = supabase.table("fabric_stock").select("*").execute()
        return {row['lot_no']: row for row in response.data}
    except: return {}

# 4. 폰트 로드 함수
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

# 5. 라벨 이미지 생성 (가로 띠 형태)
def create_label_strip_image(items, rotate=False):
    LABEL_W = 472 
    LABEL_H = 236 
    
    total_count = len(items)
    if total_count == 0: return None

    strip_w = LABEL_W * total_count
    strip_h = LABEL_H
    
    full_img = Image.new('RGB', (strip_w, strip_h), 'white')
    draw = ImageDraw.Draw(full_img)

    font_large = load_korean_font(28) 
    font_medium = load_korean_font(24)

    for i, item in enumerate(items):
        x_offset = i * LABEL_W
        draw.rectangle([x_offset, 0, x_offset + LABEL_W-1, LABEL_H-1], outline="#cccccc", width=2)
        
        # [QR 생성 시 하이픈 제거]
        raw_lot = item['lot']
        clean_lot = raw_lot.replace("-", "") # 하이픈 제거
        
        qr = qrcode.QRCode(box_size=5, border=0)
        qr.add_data(clean_lot) # 제거된 데이터 사용
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").resize((190, 190))
        
        qr_x = x_offset + 10
        qr_y = (LABEL_H - 190) // 2
        full_img.paste(qr_img, (qr_x, qr_y))
        
        text_x = x_offset + 210
        draw.text((text_x, 25), raw_lot, font=font_large, fill="black") # 글자는 하이픈 있는거 그대로
        
        cust_font = font_large if len(item['cust']) < 5 else font_medium
        draw.text((text_x, 75), f"{item['cust']}", font=cust_font, fill="black")
        
        dim_text = f"{item['w']} x {item['h']}"
        draw.text((text_x, 125), dim_text, font=font_large, fill="black")
        
        elec_text = f"[{item['elec']}]"
        draw.text((text_x, 170), elec_text, font=font_large, fill="black")

        if i < total_count - 1:
            line_x = x_offset + LABEL_W - 1
            for ly in range(0, LABEL_H, 10):
                draw.line([(line_x, ly), (line_x, ly+5)], fill="#999999", width=1)

    if rotate:
        full_img = full_img.rotate(90, expand=True)

    buf = io.BytesIO()
    full_img.save(buf, format="PNG")
    return buf.getvalue()

# 6. 인쇄 스크립트 래퍼
def generate_print_html(content_html):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>인쇄 미리보기</title>
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

# 7. 라벨 미리보기 HTML 생성
def get_label_content_html(items, mode="roll", rotate=False, margin_top=0):
    transform_css = "transform: rotate(90deg);" if rotate else ""
    
    css_page = ""
    css_wrap = ""
    
    if mode == "roll":
        css_page = "@page { size: 40mm 20mm; margin: 0; }"
        css_wrap = f"""
            width: 38mm; height: 19mm;
            page-break-after: always;
            display: flex; align-items: center; justify-content: center;
            overflow: hidden;
            border: 1px solid #ddd;
            margin-top: {margin_top}mm; 
        """
    else:
        css_page = "@page { size: A4; margin: 5mm; }"
        css_wrap = """
            width: 42mm; height: 22mm;
            display: inline-flex; align-items: center; justify-content: center;
            margin: 2px;
            border: 1px dashed #ccc;
            float: left;
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;900&display=swap');
            @media print {{
                {css_page}
                body {{ margin: 0; padding: 0; }}
            }}
            .label-box {{
                {css_wrap}
                font-family: 'Roboto', sans-serif;
                background: white;
                box-sizing: border-box;
            }}
            .label-content {{
                width: 38mm; height: 19mm;
                display: flex; align-items: center;
                {transform_css} 
            }}
            .txt-bold {{ font-weight: 900; font-size: 11pt; color: black; line-height: 1.2; }}
            .preview-container {{ display: flex; flex-wrap: wrap; }}
        </style>
    </head>
    <body>
    <div class="preview-container">
    """
    
    for item in items:
        # [QR 하이픈 제거]
        qr_clean = item['lot'].replace("-", "")
        
        qr = qrcode.QRCode(box_size=5, border=0)
        qr.add_data(qr_clean)
        qr.make(fit=True)
        img_b64 = image_to_base64(qr.make_image(fill_color="black", back_color="white"))
        
        lot_id = item['lot']       
        cust_name = item['cust']   
        w, h, elec = item['w'], item['h'], item['elec']
        
        label_div = f"""
        <div class="label-box">
            <div class="label-content">
                <div style="width: 38%; text-align: center; padding-left: 1mm;">
                    <img src="data:image/png;base64,{img_b64}" style="width: 95%; display: block;">
                </div>
                <div style="width: 62%; padding-left: 1.5mm; display: flex; flex-direction: column; justify-content: center;">
                    <div class="txt-bold">{lot_id}</div>
                    <div class="txt-bold" style="margin-top:2px;">{cust_name}</div>
                    <div class="txt-bold" style="margin-top:2px;">{w} x {h}</div>
                    <div class="txt-bold" style="margin-top:2px;">[{elec}]</div>
                </div>
            </div>
        </div>
        """
        html += label_div
        
    html += "</div></body></html>"
    return html

# 8. 작업지시서 A4 2x4 HTML (QR 하이픈 제거 + 접합생략 디자인 수정)
def get_work_order_html(items):
    html = """
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
            @media print { 
                @page { size: A4; margin: 5mm; } 
                body { margin: 0; padding: 0; -webkit-print-color-adjust: exact; }
                .page-break { page-break-after: always; }
            }
            body { font-family: 'Noto Sans KR', sans-serif; color: #000; }
            
            .print-date { text-align: right; font-size: 10px; color: #555; margin-bottom: 2px; }
            .page-header { text-align: center; font-size: 20pt; font-weight: 900; text-decoration: underline; margin-bottom: 3mm; }
            
            .page-container { 
                display: flex; flex-wrap: wrap; 
                justify-content: space-between; 
                align-content: flex-start; 
                width: 100%; 
                height: auto;
                padding: 0;
            }
            
            .job-card { 
                width: 49%; 
                height: 62.5mm; 
                border: 2px solid #000; 
                box-sizing: border-box; 
                margin-bottom: 1mm; 
                display: flex; flex-direction: column; 
                overflow: hidden;
            }
            
            .card-header { 
                background-color: #e0e0e0; 
                padding: 2px 8px; 
                border-bottom: 1px solid #000; 
                display: flex; justify-content: space-between; align-items: center; 
                height: 24px; 
                white-space: nowrap; overflow: hidden;
            }
            .header-left { display: flex; align-items: center; gap: 6px; }
            .lot-text { font-size: 13px; font-weight: 900; color: #000; }
            .prod-text { font-size: 12px; font-weight: 900; color: #333; }
            .header-right { font-size: 10px; font-weight: 700; color: #333; text-align: right; }
            
            .card-body { display: flex; flex: 1; overflow: hidden; }
            
            .qr-area { 
                width: 80px; 
                display: flex; align-items: center; justify-content: center; 
                border-right: 1px solid #000; 
                padding: 2px;
            }
            .spec-area { flex: 1; padding: 2px 6px; }
            
            .spec-table { width: 100%; border-collapse: collapse; }
            .spec-table td { padding: 1px 0; font-size: 11px; vertical-align: middle; }
            .lbl { font-weight: 900; width: 45px; color: #333; }
            .val { font-weight: 700; color: #000; }
            
            .dim-box { 
                height: 40px; 
                border-top: 2px solid #000; 
                display: flex; align-items: center; justify-content: center; 
                background-color: #fff;
            }
            
            .footer-warning { width: 100%; text-align: center; font-size: 9pt; font-weight: 700; margin-top: 5mm; color: #555; border: none; }
        </style>
    </head>
    <body>
    """
    
    chunk_size = 8
    for i in range(0, len(items), chunk_size):
        chunk = items[i:i + chunk_size]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        html += f'<div class="print-date">출력일시: {now_str}</div>'
        html += '<div class="page-header">작업 지시서 (Work Order)</div>'
        html += '<div class="page-container">'
        
        for item in chunk:
            # [QR 하이픈 제거]
            qr_clean = item['lot'].replace("-", "")
            
            qr = qrcode.QRCode(box_size=5, border=0)
            qr.add_data(qr_clean)
            qr.make(fit=True)
            img_b64 = image_to_base64(qr.make_image(fill_color="black", back_color="white"))
            
            full_id = item['lot']
            
            spec_raw = item.get('spec', '')
            if '|' in spec_raw:
                parts = spec_raw.split('|')
                cut_cond = parts[0].strip()
                lam_cond = parts[1].strip() if len(parts) > 1 else '-'
            else:
                cut_cond = item.get('spec_cut', spec_raw)
                lam_cond = item.get('spec_lam', '-')
            
            is_lam = True
            if "생략" in lam_cond or "없음" in lam_cond or "단품" in lam_cond or lam_cond == "-": is_lam = False
            
            # [수정] 접합생략 표시: 접합생략(취소선+빨강) + 필름마감(검정+정상)
            if not is_lam:
                lam_display = "<span style='text-decoration:line-through; color:red;'>접합생략</span> <span style='color:#000; text-decoration:none; font-weight:700;'>(필름마감)</span>"
            else:
                lam_display = f"<span style='color:#000;'>{lam_cond}</span>"

            note_text = item.get('note', item.get('비고', '-'))
            if not note_text: note_text = "-"

            w, h = item['w'], item['h']
            elec = item['elec']
            
            base_size = "28px"
            inactive_css = f"font-size: {base_size}; font-weight: 500; color: #555; margin: 0 2px;"
            active_css = f"font-size: {base_size}; font-weight: 900; color: #000; text-decoration: underline; margin: 0 2px;"
            
            w_css = inactive_css
            h_css = inactive_css
            
            if "가로" in elec or "(W)" in elec or "W" in elec.upper():
                w_css = active_css
            if "세로" in elec or "(H)" in elec or "H" in elec.upper():
                h_css = active_css
            
            dim_html = f"<span style='{w_css}'>{w}</span><span style='font-size:20px; font-weight:bold; margin:0 5px;'>X</span><span style='{h_css}'>{h}</span>"

            html += f"""
            <div class="job-card">
                <div class="card-header">
                    <div class="header-left">
                        <span class="lot-text">{full_id}</span>
                        <span class="prod-text">[{item['prod']}]</span>
                    </div>
                    <div class="header-right">
                        {item['cust']} | {datetime.now().strftime('%m-%d')}
                    </div>
                </div>
                <div class="card-body">
                    <div class="qr-area"><img src="data:image/png;base64,{img_b64}" style="width:100%;"></div>
                    <div class="spec-area">
                        <table class="spec-table">
                            <tr><td class="lbl">🧵 원단</td><td class="val">{item.get('fabric','-')}</td></tr>
                            <tr><td colspan="2"><hr style="margin: 2px 0; border-top: 1px dashed #ccc;"></td></tr>
                            <tr><td class="lbl">✂️ 커팅</td><td class="val">{cut_cond}</td></tr>
                            <tr><td class="lbl">🔥 접합</td><td class="val">{lam_display}</td></tr>
                            <tr><td class="lbl" style="color:red;">⚠️ 특이</td><td class="val" style="color:red;">{note_text}</td></tr>
                        </table>
                    </div>
                </div>
                <div class="dim-box">
                    {dim_html}
                    <span style="font-size: 18px; font-weight: 900; margin-left: 15px;">[{item['elec']}]</span>
                </div>
            </div>
            """
        html += '</div>'
        html += '<div class="footer-warning">⚠️ 경고: 본 문서는 대외비 자료이므로 무단 복제 및 외부 유출을 엄격히 금합니다.</div>'
        if i + chunk_size < len(items): html += '<div class="page-break"></div>'
            
    html += "</body></html>"
    return html

# 9. 접속 QR
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
# ⚙️ 설정 & 초기화 (UI 시작)
# ==========================================
st.set_page_config(page_title="(주)베스트룸 생산관리", page_icon="🏭", layout="wide")
APP_URL = "https://bt-app-pwgumeleefkwpf3xsu5bob.streamlit.app/"

if 'order_list' not in st.session_state: st.session_state.order_list = []
if 'generated_qrs' not in st.session_state: st.session_state.generated_qrs = []
if 'fabric_db' not in st.session_state: st.session_state.fabric_db = {}
if 'history_data' not in st.session_state: st.session_state.history_data = []

# ==========================================
# 🖥️ 관리자 UI 메인
# ==========================================
st.sidebar.title("👨‍💼 지시서 설정")
if not st.session_state.fabric_db: st.session_state.fabric_db = fetch_fabric_stock()
if st.sidebar.button("🔄 재고 정보 새로고침", use_container_width=True): st.session_state.fabric_db = fetch_fabric_stock(); st.toast("✅ 완료")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["📝 작업 입력", "📄 지시서 인쇄", "🏷️ 라벨 인쇄", "🔄 QR 재발행", "🧵 원단 재고", "📊 발행 이력", "🔍 제품 추적", "🚨 불량 현황", "📱 접속 QR"])

# [Tab 1] 작업 입력
with tab1:
    st.markdown("### 📝 신규 작업 지시 등록")
    if 'fabric_db' not in st.session_state or not st.session_state.fabric_db: st.session_state.fabric_db = fetch_fabric_stock()
    with st.form("order_form"):
        c1, c2 = st.columns([1, 1])
        customer = c1.text_input("고객사 (Customer)", placeholder="예: A건설")
        product = c2.selectbox("제품 종류", ["스마트글라스", "접합필름", "PDLC원단", "일반유리"])
        st.divider()
        c_mat1, c_mat2 = st.columns(2)
        stock_options = ["➕ 직접 입력 (미등록 원단)"] 
        if st.session_state.fabric_db:
            for lot, info in st.session_state.fabric_db.items():
                remain = info['total_len'] - info['used_len']
                display_text = f"{lot} | {info['name']} (잔량:{remain:.1f}m)"
                stock_options.append(display_text)
        selected_stock = c_mat1.selectbox("🧵 사용할 원단 선택", stock_options)
        
        # [수정] 식별코드(ID) 로직 개선
        default_short = "ROLL" # 기본값
        
        if "직접 입력" in selected_stock:
            fabric_lot = c_mat1.text_input("원단 LOT 번호 입력", placeholder="Roll-2312a-KR")
        else:
            fabric_lot = selected_stock.split(" | ")[0]
            c_mat1.info(f"✅ 선택됨: {fabric_lot}")
            # DB에 저장된 short_code가 있는지 확인
            sel_info = st.session_state.fabric_db.get(fabric_lot, {})
            # short_code가 있으면 그걸 쓰고, 없으면 ROLL을 씀
            if sel_info.get('short_code'):
                default_short = sel_info.get('short_code')

        # 사용자 입력이 가능하도록 value에 기본값을 넣어줌
        fabric_short = c_mat2.text_input("🆔 식별코드 (4자리)", value=default_short, max_chars=4, help="기본값 대신 원하는 4자리 코드 입력 가능")
        
        st.divider()
        c3, c4, c5 = st.columns([1, 1, 1])
        w = c3.number_input("가로 (W)", min_value=0, step=10)
        h = c4.number_input("세로 (H)", min_value=0, step=10)
        elec_type = c5.selectbox("전극 위치", ["없음", "가로(W) 양쪽", "세로(H) 양쪽", "가로(W) 상단", "세로(H) 우측"])
        st.caption("🔧 공정 조건 설정")
        cc1, cc2 = st.columns(2)
        spec_cut = cc1.text_input("✂️ 커팅 조건", placeholder="예: Full(50/80/20)")
        is_lamination = cc2.checkbox("🔥 접합(Lamination) 포함", value=True)
        if is_lamination: spec_lam = cc2.text_input("🔥 접합 조건", placeholder="예: 1단계(60도/30분)")
        else: spec_lam = "⛔ 접합 생략 (필름 마감)"
        note = st.text_input("비고 (특이사항)", placeholder="작업자 전달 사항")
        count = st.number_input("수량", min_value=1, value=1)
        
        if st.form_submit_button("➕ 작업 목록 추가", type="primary", use_container_width=True):
            if not customer or not w or not h: st.error("고객사, 가로, 세로 사이즈는 필수입니다.")
            elif not fabric_lot: st.error("원단 정보가 없습니다.")
            else:
                # [수정] 사용자가 입력한 fabric_short를 최우선으로 사용
                input_short = str(fabric_short).strip().upper()
                final_short = input_short if input_short else "ROLL" # 비어있으면 ROLL
                final_short = final_short.ljust(4, 'X') 

                st.session_state.order_list.append({
                    "고객사": customer, "제품": product, "규격": f"{w}x{h}",
                    "w": w, "h": h, "전극": elec_type, "spec_cut": spec_cut, "spec_lam": spec_lam, "is_lam": is_lamination,
                    "spec": f"{spec_cut} | {spec_lam}", "비고": note, "수량": count, "lot_no": fabric_lot, "lot_short": final_short  
                })
                st.success(f"리스트 추가됨! (ID: {final_short})")

    if st.session_state.order_list:
        st.divider()
        st.markdown(f"### 🛒 발행 대기 목록 ({len(st.session_state.order_list)}건)")
        st.dataframe(pd.DataFrame(st.session_state.order_list)[["고객사", "lot_short", "제품", "규격", "spec_lam", "수량"]], use_container_width=True)
        c1, c2 = st.columns([1, 2])
        if c1.button("🗑️ 목록 초기화", key="btn_clear_list_tab1"): st.session_state.order_list = []; st.rerun()
        if c2.button("🚀 최종 발행 및 저장 (Supabase)", type="primary", use_container_width=True, key="btn_publish_tab1"):
            date_str = datetime.now().strftime("%y%m%d")
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
                        supabase.table("work_orders").insert({
                            "lot_no": final_lot_id, "customer": item['고객사'], "product": item['제품'],
                            "dimension": f"{item['규격']} [{item['전극']}]", "spec": item['spec'],
                            "status": init_status, "note": item['비고'], "fabric_lot_no": item['lot_no']
                        }).execute()
                        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=1)
                        # [수정] QR 데이터 하이픈 제거
                        qr.add_data(final_lot_id.replace("-",""))
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")
                        new_qrs.append({
                            "lot": final_lot_id, "w": item['w'], "h": item['h'], "elec": item['전극'], 
                            "prod": item['제품'], "cust": item['고객사'], "img": img,
                            "fabric": item['lot_no'], "spec_cut": item['spec_cut'], "spec_lam": item['spec_lam'], 
                            "is_lam": item['is_lam'], "note": item['비고']
                        })
                    except Exception as e: st.error(f"저장 중 오류 발생: {e}")
            st.session_state.generated_qrs = new_qrs
            st.session_state.order_list = []
            st.success(f"✅ 총 {len(new_qrs)}건 발행 완료!"); time.sleep(1); st.rerun()

# [Tab 2] 지시서 인쇄
with tab2:
    st.header("📄 작업 지시서 인쇄")
    if st.session_state.generated_qrs:
        content_html = get_work_order_html(st.session_state.generated_qrs)
        st.components.v1.html(content_html, height=1000, scrolling=True)
        c_print, c_down = st.columns(2)
        if c_print.button("🖨️ 지시서 인쇄 (즉시)", type="primary", key="btn_print_order_tab2"):
            full_html = generate_print_html(content_html)
            components.html(full_html, height=0, width=0)
        full_html_down = generate_print_html(content_html)
        c_down.download_button(label="💾 지시서 파일 다운로드 (html)", data=full_html_down, file_name="order_sheet.html", mime="text/html", key="down_order_tab2")
    else: st.info("⚠️ 현재 발행된 작업이 없습니다.")

# ==========================================
# 🏷️ [Tab 3] 라벨 인쇄
# ==========================================
with tab3:
    st.header("🏷️ QR 라벨 인쇄")
    
    if st.session_state.generated_qrs:
        with st.expander("⚙️ 라벨 인쇄 설정", expanded=True):
            c_mode, c_rot, c_margin = st.columns([2, 1, 1])
            print_mode = c_mode.radio("🖨️ 인쇄 방식", ["전용 프린터 (40x20mm 1장씩)", "A4 라벨지 (전체 목록)"], horizontal=True, key="radio_label_mode_tab3")
            mode_code = "roll" if "전용" in print_mode else "a4"
            is_rotate = c_rot.checkbox("🔄 내용 90도 회전", help="라벨이 세로로 나오는 경우 체크하세요.", key="chk_rotate_tab3")
            margin_top = c_margin.number_input("상단 여백 보정(mm)", value=0, step=1, help="인쇄가 밀릴 경우 조정", key="num_margin_tab3")

        content_html_preview = get_label_content_html(st.session_state.generated_qrs, mode=mode_code, rotate=is_rotate, margin_top=margin_top)
        st.components.v1.html(content_html_preview, height=600, scrolling=True)
        
        c_print, c_down = st.columns(2)
        
        if c_print.button("🖨️ 라벨 인쇄 (즉시)", type="primary", key="btn_print_label_tab3"):
            full_html = generate_print_html(content_html_preview)
            components.html(full_html, height=0, width=0)
            
        label_image_data = create_label_strip_image(st.session_state.generated_qrs, rotate=is_rotate)
        
        if label_image_data:
            c_down.download_button(
                label="💾 전체 라벨 이미지(PNG) 다운로드",
                data=label_image_data,
                file_name=f"labels_horizontal_{datetime.now().strftime('%H%M%S')}.png",
                mime="image/png",
                key="btn_down_label_img_tab3",
                help="이 이미지를 다운받아서 라벨 프로그램에 [그림 삽입] 하세요."
            )
    else:
        st.info("👈 먼저 [작업 입력] 탭에서 발행을 진행해주세요.")

# [Tab 4] QR 재발행
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
                reprint_type = st.radio("재발행 형태", ["📄 작업지시서 (A4)", "🏷️ 라벨 (전용/A4 선택)"], horizontal=True, key="radio_reprint_type_tab4")
                
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
                    qr = qrcode.QRCode(box_size=5, border=1); qr.add_data(row['lot_no'].replace("-","")); qr.make(fit=True); img = qr.make_image(fill_color="black", back_color="white")
                    rep_items.append({
                        "lot": row['lot_no'], "w": w, "h": h, "elec": elec, "cust": row['customer'], "prod": row['product'], 
                        "fabric": row.get('fabric_lot_no', '-'), "spec": row.get('spec', ''), "note": row.get('note', ''), "img": img
                    })
                
                if "작업지시서" in reprint_type:
                    content_html = get_work_order_html(rep_items)
                    st.components.v1.html(content_html, height=500, scrolling=True)
                    if st.button("🖨️ 지시서 인쇄", type="primary", key="btn_reprint_order_tab4"):
                        full_html = generate_print_html(content_html)
                        components.html(full_html, height=0, width=0)
                else:
                    c_m, c_r = st.columns(2)
                    rpm = c_m.radio("방식", ["전용 프린터", "A4 라벨지"], horizontal=True, key="radio_reprint_label_mode_tab4")
                    rrot = c_r.checkbox("90도 회전", key="chk_reprint_rotate_tab4")
                    rmode = "roll" if "전용" in rpm else "a4"
                    
                    content_html = get_label_content_html(rep_items, mode=rmode, rotate=rrot)
                    st.components.v1.html(content_html, height=500, scrolling=True)
                    
                    c_rp_print, c_rp_down = st.columns(2)
                    if c_rp_print.button("🖨️ 라벨 인쇄", type="primary", key="btn_reprint_label_tab4"):
                        full_html = generate_print_html(content_html)
                        components.html(full_html, height=0, width=0)
                        
                    label_img_data_rep = create_label_strip_image(rep_items, rotate=rrot)
                    if label_img_data_rep:
                        c_rp_down.download_button(
                            label="💾 이미지(PNG) 다운로드",
                            data=label_img_data_rep,
                            file_name=f"reprint_labels_{datetime.now().strftime('%H%M%S')}.png",
                            mime="image/png",
                            key="btn_reprint_img_down_tab4"
                        )
    else: st.info("조회된 데이터가 없습니다.")

with tab5:
    with st.form("fabric_in"):
        st.markdown("##### 📥 원단 입고 등록")
        c1,c2,c3=st.columns(3); n_lot=c1.text_input("LOT"); n_name=c2.text_input("제품명"); n_w=c3.number_input("폭(mm)",1200)
        c4,c5,c6=st.columns(3); n_tot=c4.number_input("총길이(m)",100.0); n_rem=c5.number_input("현재 잔량(m)",100.0)
        # [수정] 단축코드 입력란 추가
        n_short = c6.text_input("단축코드 (4자리)", placeholder="예: TA12")
        
        if st.form_submit_button("입고 등록"):
            # DB 컬럼에 short_code가 있다는 가정하에 진행
            data = {"lot_no":n_lot,"name":n_name,"width":n_w,"total_len":n_tot,"used_len":n_tot-n_rem}
            if n_short: data["short_code"] = n_short
            
            try:
                supabase.table("fabric_stock").insert(data).execute()
                st.rerun()
            except Exception as e:
                st.error(f"저장 실패: {e}")
                
    st.divider()
    res=supabase.table("fabric_stock").select("*").execute(); st.data_editor(pd.DataFrame(res.data),hide_index=True, use_container_width=True)

with tab6:
    st.title("📊 생산 현황 및 이력 관리")
    try:
        res = supabase.table("work_orders").select("*").order("created_at", desc=True).limit(200).execute()
        df_log = pd.DataFrame(res.data)
    except Exception as e: st.error(f"조회 실패: {e}"); df_log = pd.DataFrame()
    if not df_log.empty:
        if "created_at" in df_log.columns: df_log["created_at"] = pd.to_datetime(df_log["created_at"])
        status_counts = df_log['status'].value_counts()
        k1, k2, k3, k4 = st.columns(4)
        wait_cnt = status_counts.get("작업대기", 0) + status_counts.get("작업대기(단품)", 0)
        k1.metric("⚪ 작업 대기", f"{wait_cnt}건")
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
        edited_log = st.data_editor(df_view, hide_index=True, use_container_width=True, column_config={"선택": st.column_config.CheckboxColumn(width="small"), "created_at": st.column_config.DatetimeColumn("발행일시", format="MM-DD HH:mm"), "lot_no": st.column_config.TextColumn("LOT 번호", width="medium"), "status": st.column_config.TextColumn("현재 상태"), "spec": st.column_config.TextColumn("스펙 요약", width="medium")}, key="history_editor")
        selected_rows = edited_log[edited_log["선택"]]
        if not selected_rows.empty:
            st.markdown("---")
            detail_tab, delete_tab = st.tabs(["🔍 상세 조건 확인", "🗑️ 데이터 삭제"])
            with detail_tab:
                row = selected_rows.iloc[0]
                st.info(f"선택된 항목 중 최상단 `{row['lot_no']}` 상세")
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
                    st.markdown(f"#### 📌 LOT: `{row['lot_no']}`")
                    c_cut1, c_cut2 = st.columns(2)
                    with c_cut1: st.markdown("##### ✂️ 풀컷"); st.write(full_cut)
                    with c_cut2: st.markdown("##### 🗡️ 하프컷"); st.write(half_cut)
                    st.divider()
                    st.markdown("##### 🔥 접합 유리 조건")
                    if "생략" in lam_cond or "없음" in lam_cond: st.warning(f"⛔ {lam_cond}")
                    else: st.write(lam_cond.replace("->", " → "))
                    st.caption(f"🧵 원단 정보: {row.get('fabric_lot_no', '-')}")
            with delete_tab:
                st.warning(f"선택된 {len(selected_rows)}건 삭제")
                if st.toggle("🚨 관리자 삭제 모드 켜기"):
                    if st.button("🗑️ 삭제 실행", type="primary", key="btn_delete_log_tab6"):
                        delete_lots = selected_rows['lot_no'].tolist()
                        supabase.table("work_orders").delete().in_("lot_no", delete_lots).execute()
                        st.toast("삭제 완료!"); time.sleep(1); st.rerun()
    else: st.info("조회된 데이터가 없습니다.")

with tab7:
    with st.form("track"): c1,c2=st.columns([4,1]); l=c1.text_input("LOT"); b=c2.form_submit_button("조회")
    if b: r=supabase.table("work_orders").select("*").eq("lot_no",l).execute(); st.write(r.data)

with tab8: 
    st.markdown("### 🚨 불량 현황")
    try:
        res = supabase.table("defects").select("*").execute()
        df_defects = pd.DataFrame(res.data)
        if not df_defects.empty: st.dataframe(df_defects, use_container_width=True)
        else: st.info("✅ 현재 등록된 불량 내역이 없습니다.")
    except Exception as e: st.error(f"데이터 조회 중 오류가 발생했습니다: {e}")

with tab9:
    st.header("📱 현장 접속 QR")
    content_html = get_access_qr_content_html(APP_URL, "big")
    st.components.v1.html(content_html, height=600)
    if st.button("🖨️ 접속 QR 인쇄", key="btn_print_access_qr_tab9"):
        full_html = generate_print_html(content_html)
        components.html(full_html, height=0, width=0)import streamlit as st
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
# 🛠️ [기능 정의 구역] 
# ==============================================================================

# 1. 공정 순서 위반 방지 함수
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
        return False, "데이터 조회 중 오류가 발생했습니다."

    required_previous_step = {
        "원단커팅": ["작업대기"],
        "하프커팅": ["원단커팅", "Full", "풀"], 
        "전극": ["하프커팅", "Half", "하프"],
        "접합": ["전극"],
        "출고": ["접합", "완료", "전극"]
    }

    if last_step == current_step:
        return False, f"⚠️ 이미 '{current_step}' 작업이 등록되어 있습니다."

    valid_prev_steps = required_previous_step.get(current_step)
    if valid_prev_steps:
        is_valid = any(req in last_step for req in valid_prev_steps)
        if not is_valid:
            return False, f"🚨 [순서 오류] 현재 상태는 '{last_step}' 입니다.\n선행 공정이 완료되지 않아 '{current_step}' 작업을 할 수 없습니다."
    
    return True, "OK"

# 2. 이미지 변환 함수
def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# 3. 재고 조회 함수
def fetch_fabric_stock():
    try:
        response = supabase.table("fabric_stock").select("*").execute()
        return {row['lot_no']: row for row in response.data}
    except: return {}

# 4. 폰트 로드 함수
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

# 5. 라벨 이미지 생성 (가로 띠 형태)
def create_label_strip_image(items, rotate=False):
    LABEL_W = 472 
    LABEL_H = 236 
    
    total_count = len(items)
    if total_count == 0: return None

    strip_w = LABEL_W * total_count
    strip_h = LABEL_H
    
    full_img = Image.new('RGB', (strip_w, strip_h), 'white')
    draw = ImageDraw.Draw(full_img)

    font_large = load_korean_font(28) 
    font_medium = load_korean_font(24)

    for i, item in enumerate(items):
        x_offset = i * LABEL_W
        draw.rectangle([x_offset, 0, x_offset + LABEL_W-1, LABEL_H-1], outline="#cccccc", width=2)
        
        # [QR 생성 시 하이픈 제거]
        raw_lot = item['lot']
        clean_lot = raw_lot.replace("-", "") # 하이픈 제거
        
        qr = qrcode.QRCode(box_size=5, border=0)
        qr.add_data(clean_lot) # 제거된 데이터 사용
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").resize((190, 190))
        
        qr_x = x_offset + 10
        qr_y = (LABEL_H - 190) // 2
        full_img.paste(qr_img, (qr_x, qr_y))
        
        text_x = x_offset + 210
        draw.text((text_x, 25), raw_lot, font=font_large, fill="black") # 글자는 하이픈 있는거 그대로
        
        cust_font = font_large if len(item['cust']) < 5 else font_medium
        draw.text((text_x, 75), f"{item['cust']}", font=cust_font, fill="black")
        
        dim_text = f"{item['w']} x {item['h']}"
        draw.text((text_x, 125), dim_text, font=font_large, fill="black")
        
        elec_text = f"[{item['elec']}]"
        draw.text((text_x, 170), elec_text, font=font_large, fill="black")

        if i < total_count - 1:
            line_x = x_offset + LABEL_W - 1
            for ly in range(0, LABEL_H, 10):
                draw.line([(line_x, ly), (line_x, ly+5)], fill="#999999", width=1)

    if rotate:
        full_img = full_img.rotate(90, expand=True)

    buf = io.BytesIO()
    full_img.save(buf, format="PNG")
    return buf.getvalue()

# 6. 인쇄 스크립트 래퍼
def generate_print_html(content_html):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>인쇄 미리보기</title>
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

# 7. 라벨 미리보기 HTML 생성
def get_label_content_html(items, mode="roll", rotate=False, margin_top=0):
    transform_css = "transform: rotate(90deg);" if rotate else ""
    
    css_page = ""
    css_wrap = ""
    
    if mode == "roll":
        css_page = "@page { size: 40mm 20mm; margin: 0; }"
        css_wrap = f"""
            width: 38mm; height: 19mm;
            page-break-after: always;
            display: flex; align-items: center; justify-content: center;
            overflow: hidden;
            border: 1px solid #ddd;
            margin-top: {margin_top}mm; 
        """
    else:
        css_page = "@page { size: A4; margin: 5mm; }"
        css_wrap = """
            width: 42mm; height: 22mm;
            display: inline-flex; align-items: center; justify-content: center;
            margin: 2px;
            border: 1px dashed #ccc;
            float: left;
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;900&display=swap');
            @media print {{
                {css_page}
                body {{ margin: 0; padding: 0; }}
            }}
            .label-box {{
                {css_wrap}
                font-family: 'Roboto', sans-serif;
                background: white;
                box-sizing: border-box;
            }}
            .label-content {{
                width: 38mm; height: 19mm;
                display: flex; align-items: center;
                {transform_css} 
            }}
            .txt-bold {{ font-weight: 900; font-size: 11pt; color: black; line-height: 1.2; }}
            .preview-container {{ display: flex; flex-wrap: wrap; }}
        </style>
    </head>
    <body>
    <div class="preview-container">
    """
    
    for item in items:
        # [QR 하이픈 제거]
        qr_clean = item['lot'].replace("-", "")
        
        qr = qrcode.QRCode(box_size=5, border=0)
        qr.add_data(qr_clean)
        qr.make(fit=True)
        img_b64 = image_to_base64(qr.make_image(fill_color="black", back_color="white"))
        
        lot_id = item['lot']       
        cust_name = item['cust']   
        w, h, elec = item['w'], item['h'], item['elec']
        
        label_div = f"""
        <div class="label-box">
            <div class="label-content">
                <div style="width: 38%; text-align: center; padding-left: 1mm;">
                    <img src="data:image/png;base64,{img_b64}" style="width: 95%; display: block;">
                </div>
                <div style="width: 62%; padding-left: 1.5mm; display: flex; flex-direction: column; justify-content: center;">
                    <div class="txt-bold">{lot_id}</div>
                    <div class="txt-bold" style="margin-top:2px;">{cust_name}</div>
                    <div class="txt-bold" style="margin-top:2px;">{w} x {h}</div>
                    <div class="txt-bold" style="margin-top:2px;">[{elec}]</div>
                </div>
            </div>
        </div>
        """
        html += label_div
        
    html += "</div></body></html>"
    return html

# 8. 작업지시서 A4 2x4 HTML (QR 하이픈 제거 + 접합생략 디자인 수정)
def get_work_order_html(items):
    html = """
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
            @media print { 
                @page { size: A4; margin: 5mm; } 
                body { margin: 0; padding: 0; -webkit-print-color-adjust: exact; }
                .page-break { page-break-after: always; }
            }
            body { font-family: 'Noto Sans KR', sans-serif; color: #000; }
            
            .print-date { text-align: right; font-size: 10px; color: #555; margin-bottom: 2px; }
            .page-header { text-align: center; font-size: 20pt; font-weight: 900; text-decoration: underline; margin-bottom: 3mm; }
            
            .page-container { 
                display: flex; flex-wrap: wrap; 
                justify-content: space-between; 
                align-content: flex-start; 
                width: 100%; 
                height: auto;
                padding: 0;
            }
            
            .job-card { 
                width: 49%; 
                height: 62.5mm; 
                border: 2px solid #000; 
                box-sizing: border-box; 
                margin-bottom: 1mm; 
                display: flex; flex-direction: column; 
                overflow: hidden;
            }
            
            .card-header { 
                background-color: #e0e0e0; 
                padding: 2px 8px; 
                border-bottom: 1px solid #000; 
                display: flex; justify-content: space-between; align-items: center; 
                height: 24px; 
                white-space: nowrap; overflow: hidden;
            }
            .header-left { display: flex; align-items: center; gap: 6px; }
            .lot-text { font-size: 13px; font-weight: 900; color: #000; }
            .prod-text { font-size: 12px; font-weight: 900; color: #333; }
            .header-right { font-size: 10px; font-weight: 700; color: #333; text-align: right; }
            
            .card-body { display: flex; flex: 1; overflow: hidden; }
            
            .qr-area { 
                width: 80px; 
                display: flex; align-items: center; justify-content: center; 
                border-right: 1px solid #000; 
                padding: 2px;
            }
            .spec-area { flex: 1; padding: 2px 6px; }
            
            .spec-table { width: 100%; border-collapse: collapse; }
            .spec-table td { padding: 1px 0; font-size: 11px; vertical-align: middle; }
            .lbl { font-weight: 900; width: 45px; color: #333; }
            .val { font-weight: 700; color: #000; }
            
            .dim-box { 
                height: 40px; 
                border-top: 2px solid #000; 
                display: flex; align-items: center; justify-content: center; 
                background-color: #fff;
            }
            
            .footer-warning { width: 100%; text-align: center; font-size: 9pt; font-weight: 700; margin-top: 5mm; color: #555; border: none; }
        </style>
    </head>
    <body>
    """
    
    chunk_size = 8
    for i in range(0, len(items), chunk_size):
        chunk = items[i:i + chunk_size]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        html += f'<div class="print-date">출력일시: {now_str}</div>'
        html += '<div class="page-header">작업 지시서 (Work Order)</div>'
        html += '<div class="page-container">'
        
        for item in chunk:
            # [QR 하이픈 제거]
            qr_clean = item['lot'].replace("-", "")
            
            qr = qrcode.QRCode(box_size=5, border=0)
            qr.add_data(qr_clean)
            qr.make(fit=True)
            img_b64 = image_to_base64(qr.make_image(fill_color="black", back_color="white"))
            
            full_id = item['lot']
            
            spec_raw = item.get('spec', '')
            if '|' in spec_raw:
                parts = spec_raw.split('|')
                cut_cond = parts[0].strip()
                lam_cond = parts[1].strip() if len(parts) > 1 else '-'
            else:
                cut_cond = item.get('spec_cut', spec_raw)
                lam_cond = item.get('spec_lam', '-')
            
            is_lam = True
            if "생략" in lam_cond or "없음" in lam_cond or "단품" in lam_cond or lam_cond == "-": is_lam = False
            
            # [수정] 접합생략 표시: 접합생략(취소선+빨강) + 필름마감(검정+정상)
            if not is_lam:
                lam_display = "<span style='text-decoration:line-through; color:red;'>접합생략</span> <span style='color:#000; text-decoration:none; font-weight:700;'>(필름마감)</span>"
            else:
                lam_display = f"<span style='color:#000;'>{lam_cond}</span>"

            note_text = item.get('note', item.get('비고', '-'))
            if not note_text: note_text = "-"

            w, h = item['w'], item['h']
            elec = item['elec']
            
            base_size = "28px"
            inactive_css = f"font-size: {base_size}; font-weight: 500; color: #555; margin: 0 2px;"
            active_css = f"font-size: {base_size}; font-weight: 900; color: #000; text-decoration: underline; margin: 0 2px;"
            
            w_css = inactive_css
            h_css = inactive_css
            
            if "가로" in elec or "(W)" in elec or "W" in elec.upper():
                w_css = active_css
            if "세로" in elec or "(H)" in elec or "H" in elec.upper():
                h_css = active_css
            
            dim_html = f"<span style='{w_css}'>{w}</span><span style='font-size:20px; font-weight:bold; margin:0 5px;'>X</span><span style='{h_css}'>{h}</span>"

            html += f"""
            <div class="job-card">
                <div class="card-header">
                    <div class="header-left">
                        <span class="lot-text">{full_id}</span>
                        <span class="prod-text">[{item['prod']}]</span>
                    </div>
                    <div class="header-right">
                        {item['cust']} | {datetime.now().strftime('%m-%d')}
                    </div>
                </div>
                <div class="card-body">
                    <div class="qr-area"><img src="data:image/png;base64,{img_b64}" style="width:100%;"></div>
                    <div class="spec-area">
                        <table class="spec-table">
                            <tr><td class="lbl">🧵 원단</td><td class="val">{item.get('fabric','-')}</td></tr>
                            <tr><td colspan="2"><hr style="margin: 2px 0; border-top: 1px dashed #ccc;"></td></tr>
                            <tr><td class="lbl">✂️ 커팅</td><td class="val">{cut_cond}</td></tr>
                            <tr><td class="lbl">🔥 접합</td><td class="val">{lam_display}</td></tr>
                            <tr><td class="lbl" style="color:red;">⚠️ 특이</td><td class="val" style="color:red;">{note_text}</td></tr>
                        </table>
                    </div>
                </div>
                <div class="dim-box">
                    {dim_html}
                    <span style="font-size: 18px; font-weight: 900; margin-left: 15px;">[{item['elec']}]</span>
                </div>
            </div>
            """
        html += '</div>'
        html += '<div class="footer-warning">⚠️ 경고: 본 문서는 대외비 자료이므로 무단 복제 및 외부 유출을 엄격히 금합니다.</div>'
        if i + chunk_size < len(items): html += '<div class="page-break"></div>'
            
    html += "</body></html>"
    return html

# 9. 접속 QR
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
# ⚙️ 설정 & 초기화 (UI 시작)
# ==========================================
st.set_page_config(page_title="(주)베스트룸 생산관리", page_icon="🏭", layout="wide")
APP_URL = "https://bt-app-pwgumeleefkwpf3xsu5bob.streamlit.app/"

if 'order_list' not in st.session_state: st.session_state.order_list = []
if 'generated_qrs' not in st.session_state: st.session_state.generated_qrs = []
if 'fabric_db' not in st.session_state: st.session_state.fabric_db = {}
if 'history_data' not in st.session_state: st.session_state.history_data = []

# ==========================================
# 🖥️ 관리자 UI 메인
# ==========================================
st.sidebar.title("👨‍💼 지시서 설정")
if not st.session_state.fabric_db: st.session_state.fabric_db = fetch_fabric_stock()
if st.sidebar.button("🔄 재고 정보 새로고침", use_container_width=True): st.session_state.fabric_db = fetch_fabric_stock(); st.toast("✅ 완료")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["📝 작업 입력", "📄 지시서 인쇄", "🏷️ 라벨 인쇄", "🔄 QR 재발행", "🧵 원단 재고", "📊 발행 이력", "🔍 제품 추적", "🚨 불량 현황", "📱 접속 QR"])

# [Tab 1] 작업 입력
with tab1:
    st.markdown("### 📝 신규 작업 지시 등록")
    if 'fabric_db' not in st.session_state or not st.session_state.fabric_db: st.session_state.fabric_db = fetch_fabric_stock()
    with st.form("order_form"):
        c1, c2 = st.columns([1, 1])
        customer = c1.text_input("고객사 (Customer)", placeholder="예: A건설")
        product = c2.selectbox("제품 종류", ["스마트글라스", "접합필름", "PDLC원단", "일반유리"])
        st.divider()
        c_mat1, c_mat2 = st.columns(2)
        stock_options = ["➕ 직접 입력 (미등록 원단)"] 
        if st.session_state.fabric_db:
            for lot, info in st.session_state.fabric_db.items():
                remain = info['total_len'] - info['used_len']
                display_text = f"{lot} | {info['name']} (잔량:{remain:.1f}m)"
                stock_options.append(display_text)
        selected_stock = c_mat1.selectbox("🧵 사용할 원단 선택", stock_options)
        
        # [수정] 식별코드(ID) 로직 개선
        default_short = "ROLL" # 기본값
        
        if "직접 입력" in selected_stock:
            fabric_lot = c_mat1.text_input("원단 LOT 번호 입력", placeholder="Roll-2312a-KR")
        else:
            fabric_lot = selected_stock.split(" | ")[0]
            c_mat1.info(f"✅ 선택됨: {fabric_lot}")
            # DB에 저장된 short_code가 있는지 확인
            sel_info = st.session_state.fabric_db.get(fabric_lot, {})
            # short_code가 있으면 그걸 쓰고, 없으면 ROLL을 씀
            if sel_info.get('short_code'):
                default_short = sel_info.get('short_code')

        # 사용자 입력이 가능하도록 value에 기본값을 넣어줌
        fabric_short = c_mat2.text_input("🆔 식별코드 (4자리)", value=default_short, max_chars=4, help="기본값 대신 원하는 4자리 코드 입력 가능")
        
        st.divider()
        c3, c4, c5 = st.columns([1, 1, 1])
        w = c3.number_input("가로 (W)", min_value=0, step=10)
        h = c4.number_input("세로 (H)", min_value=0, step=10)
        elec_type = c5.selectbox("전극 위치", ["없음", "가로(W) 양쪽", "세로(H) 양쪽", "가로(W) 상단", "세로(H) 우측"])
        st.caption("🔧 공정 조건 설정")
        cc1, cc2 = st.columns(2)
        spec_cut = cc1.text_input("✂️ 커팅 조건", placeholder="예: Full(50/80/20)")
        is_lamination = cc2.checkbox("🔥 접합(Lamination) 포함", value=True)
        if is_lamination: spec_lam = cc2.text_input("🔥 접합 조건", placeholder="예: 1단계(60도/30분)")
        else: spec_lam = "⛔ 접합 생략 (필름 마감)"
        note = st.text_input("비고 (특이사항)", placeholder="작업자 전달 사항")
        count = st.number_input("수량", min_value=1, value=1)
        
        if st.form_submit_button("➕ 작업 목록 추가", type="primary", use_container_width=True):
            if not customer or not w or not h: st.error("고객사, 가로, 세로 사이즈는 필수입니다.")
            elif not fabric_lot: st.error("원단 정보가 없습니다.")
            else:
                # [수정] 사용자가 입력한 fabric_short를 최우선으로 사용
                input_short = str(fabric_short).strip().upper()
                final_short = input_short if input_short else "ROLL" # 비어있으면 ROLL
                final_short = final_short.ljust(4, 'X') 

                st.session_state.order_list.append({
                    "고객사": customer, "제품": product, "규격": f"{w}x{h}",
                    "w": w, "h": h, "전극": elec_type, "spec_cut": spec_cut, "spec_lam": spec_lam, "is_lam": is_lamination,
                    "spec": f"{spec_cut} | {spec_lam}", "비고": note, "수량": count, "lot_no": fabric_lot, "lot_short": final_short  
                })
                st.success(f"리스트 추가됨! (ID: {final_short})")

    if st.session_state.order_list:
        st.divider()
        st.markdown(f"### 🛒 발행 대기 목록 ({len(st.session_state.order_list)}건)")
        st.dataframe(pd.DataFrame(st.session_state.order_list)[["고객사", "lot_short", "제품", "규격", "spec_lam", "수량"]], use_container_width=True)
        c1, c2 = st.columns([1, 2])
        if c1.button("🗑️ 목록 초기화", key="btn_clear_list_tab1"): st.session_state.order_list = []; st.rerun()
        if c2.button("🚀 최종 발행 및 저장 (Supabase)", type="primary", use_container_width=True, key="btn_publish_tab1"):
            date_str = datetime.now().strftime("%y%m%d")
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
                        supabase.table("work_orders").insert({
                            "lot_no": final_lot_id, "customer": item['고객사'], "product": item['제품'],
                            "dimension": f"{item['규격']} [{item['전극']}]", "spec": item['spec'],
                            "status": init_status, "note": item['비고'], "fabric_lot_no": item['lot_no']
                        }).execute()
                        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=1)
                        # [수정] QR 데이터 하이픈 제거
                        qr.add_data(final_lot_id.replace("-",""))
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")
                        new_qrs.append({
                            "lot": final_lot_id, "w": item['w'], "h": item['h'], "elec": item['전극'], 
                            "prod": item['제품'], "cust": item['고객사'], "img": img,
                            "fabric": item['lot_no'], "spec_cut": item['spec_cut'], "spec_lam": item['spec_lam'], 
                            "is_lam": item['is_lam'], "note": item['비고']
                        })
                    except Exception as e: st.error(f"저장 중 오류 발생: {e}")
            st.session_state.generated_qrs = new_qrs
            st.session_state.order_list = []
            st.success(f"✅ 총 {len(new_qrs)}건 발행 완료!"); time.sleep(1); st.rerun()

# [Tab 2] 지시서 인쇄
with tab2:
    st.header("📄 작업 지시서 인쇄")
    if st.session_state.generated_qrs:
        content_html = get_work_order_html(st.session_state.generated_qrs)
        st.components.v1.html(content_html, height=1000, scrolling=True)
        c_print, c_down = st.columns(2)
        if c_print.button("🖨️ 지시서 인쇄 (즉시)", type="primary", key="btn_print_order_tab2"):
            full_html = generate_print_html(content_html)
            components.html(full_html, height=0, width=0)
        full_html_down = generate_print_html(content_html)
        c_down.download_button(label="💾 지시서 파일 다운로드 (html)", data=full_html_down, file_name="order_sheet.html", mime="text/html", key="down_order_tab2")
    else: st.info("⚠️ 현재 발행된 작업이 없습니다.")

# ==========================================
# 🏷️ [Tab 3] 라벨 인쇄
# ==========================================
with tab3:
    st.header("🏷️ QR 라벨 인쇄")
    
    if st.session_state.generated_qrs:
        with st.expander("⚙️ 라벨 인쇄 설정", expanded=True):
            c_mode, c_rot, c_margin = st.columns([2, 1, 1])
            print_mode = c_mode.radio("🖨️ 인쇄 방식", ["전용 프린터 (40x20mm 1장씩)", "A4 라벨지 (전체 목록)"], horizontal=True, key="radio_label_mode_tab3")
            mode_code = "roll" if "전용" in print_mode else "a4"
            is_rotate = c_rot.checkbox("🔄 내용 90도 회전", help="라벨이 세로로 나오는 경우 체크하세요.", key="chk_rotate_tab3")
            margin_top = c_margin.number_input("상단 여백 보정(mm)", value=0, step=1, help="인쇄가 밀릴 경우 조정", key="num_margin_tab3")

        content_html_preview = get_label_content_html(st.session_state.generated_qrs, mode=mode_code, rotate=is_rotate, margin_top=margin_top)
        st.components.v1.html(content_html_preview, height=600, scrolling=True)
        
        c_print, c_down = st.columns(2)
        
        if c_print.button("🖨️ 라벨 인쇄 (즉시)", type="primary", key="btn_print_label_tab3"):
            full_html = generate_print_html(content_html_preview)
            components.html(full_html, height=0, width=0)
            
        label_image_data = create_label_strip_image(st.session_state.generated_qrs, rotate=is_rotate)
        
        if label_image_data:
            c_down.download_button(
                label="💾 전체 라벨 이미지(PNG) 다운로드",
                data=label_image_data,
                file_name=f"labels_horizontal_{datetime.now().strftime('%H%M%S')}.png",
                mime="image/png",
                key="btn_down_label_img_tab3",
                help="이 이미지를 다운받아서 라벨 프로그램에 [그림 삽입] 하세요."
            )
    else:
        st.info("👈 먼저 [작업 입력] 탭에서 발행을 진행해주세요.")

# [Tab 4] QR 재발행
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
                reprint_type = st.radio("재발행 형태", ["📄 작업지시서 (A4)", "🏷️ 라벨 (전용/A4 선택)"], horizontal=True, key="radio_reprint_type_tab4")
                
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
                    qr = qrcode.QRCode(box_size=5, border=1); qr.add_data(row['lot_no'].replace("-","")); qr.make(fit=True); img = qr.make_image(fill_color="black", back_color="white")
                    rep_items.append({
                        "lot": row['lot_no'], "w": w, "h": h, "elec": elec, "cust": row['customer'], "prod": row['product'], 
                        "fabric": row.get('fabric_lot_no', '-'), "spec": row.get('spec', ''), "note": row.get('note', ''), "img": img
                    })
                
                if "작업지시서" in reprint_type:
                    content_html = get_work_order_html(rep_items)
                    st.components.v1.html(content_html, height=500, scrolling=True)
                    if st.button("🖨️ 지시서 인쇄", type="primary", key="btn_reprint_order_tab4"):
                        full_html = generate_print_html(content_html)
                        components.html(full_html, height=0, width=0)
                else:
                    c_m, c_r = st.columns(2)
                    rpm = c_m.radio("방식", ["전용 프린터", "A4 라벨지"], horizontal=True, key="radio_reprint_label_mode_tab4")
                    rrot = c_r.checkbox("90도 회전", key="chk_reprint_rotate_tab4")
                    rmode = "roll" if "전용" in rpm else "a4"
                    
                    content_html = get_label_content_html(rep_items, mode=rmode, rotate=rrot)
                    st.components.v1.html(content_html, height=500, scrolling=True)
                    
                    c_rp_print, c_rp_down = st.columns(2)
                    if c_rp_print.button("🖨️ 라벨 인쇄", type="primary", key="btn_reprint_label_tab4"):
                        full_html = generate_print_html(content_html)
                        components.html(full_html, height=0, width=0)
                        
                    label_img_data_rep = create_label_strip_image(rep_items, rotate=rrot)
                    if label_img_data_rep:
                        c_rp_down.download_button(
                            label="💾 이미지(PNG) 다운로드",
                            data=label_img_data_rep,
                            file_name=f"reprint_labels_{datetime.now().strftime('%H%M%S')}.png",
                            mime="image/png",
                            key="btn_reprint_img_down_tab4"
                        )
    else: st.info("조회된 데이터가 없습니다.")

with tab5:
    with st.form("fabric_in"):
        st.markdown("##### 📥 원단 입고 등록")
        c1,c2,c3=st.columns(3); n_lot=c1.text_input("LOT"); n_name=c2.text_input("제품명"); n_w=c3.number_input("폭(mm)",1200)
        c4,c5,c6=st.columns(3); n_tot=c4.number_input("총길이(m)",100.0); n_rem=c5.number_input("현재 잔량(m)",100.0)
        # [수정] 단축코드 입력란 추가
        n_short = c6.text_input("단축코드 (4자리)", placeholder="예: TA12")
        
        if st.form_submit_button("입고 등록"):
            # DB 컬럼에 short_code가 있다는 가정하에 진행
            data = {"lot_no":n_lot,"name":n_name,"width":n_w,"total_len":n_tot,"used_len":n_tot-n_rem}
            if n_short: data["short_code"] = n_short
            
            try:
                supabase.table("fabric_stock").insert(data).execute()
                st.rerun()
            except Exception as e:
                st.error(f"저장 실패: {e}")
                
    st.divider()
    res=supabase.table("fabric_stock").select("*").execute(); st.data_editor(pd.DataFrame(res.data),hide_index=True, use_container_width=True)

with tab6:
    st.title("📊 생산 현황 및 이력 관리")
    try:
        res = supabase.table("work_orders").select("*").order("created_at", desc=True).limit(200).execute()
        df_log = pd.DataFrame(res.data)
    except Exception as e: st.error(f"조회 실패: {e}"); df_log = pd.DataFrame()
    if not df_log.empty:
        if "created_at" in df_log.columns: df_log["created_at"] = pd.to_datetime(df_log["created_at"])
        status_counts = df_log['status'].value_counts()
        k1, k2, k3, k4 = st.columns(4)
        wait_cnt = status_counts.get("작업대기", 0) + status_counts.get("작업대기(단품)", 0)
        k1.metric("⚪ 작업 대기", f"{wait_cnt}건")
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
        edited_log = st.data_editor(df_view, hide_index=True, use_container_width=True, column_config={"선택": st.column_config.CheckboxColumn(width="small"), "created_at": st.column_config.DatetimeColumn("발행일시", format="MM-DD HH:mm"), "lot_no": st.column_config.TextColumn("LOT 번호", width="medium"), "status": st.column_config.TextColumn("현재 상태"), "spec": st.column_config.TextColumn("스펙 요약", width="medium")}, key="history_editor")
        selected_rows = edited_log[edited_log["선택"]]
        if not selected_rows.empty:
            st.markdown("---")
            detail_tab, delete_tab = st.tabs(["🔍 상세 조건 확인", "🗑️ 데이터 삭제"])
            with detail_tab:
                row = selected_rows.iloc[0]
                st.info(f"선택된 항목 중 최상단 `{row['lot_no']}` 상세")
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
                    st.markdown(f"#### 📌 LOT: `{row['lot_no']}`")
                    c_cut1, c_cut2 = st.columns(2)
                    with c_cut1: st.markdown("##### ✂️ 풀컷"); st.write(full_cut)
                    with c_cut2: st.markdown("##### 🗡️ 하프컷"); st.write(half_cut)
                    st.divider()
                    st.markdown("##### 🔥 접합 유리 조건")
                    if "생략" in lam_cond or "없음" in lam_cond: st.warning(f"⛔ {lam_cond}")
                    else: st.write(lam_cond.replace("->", " → "))
                    st.caption(f"🧵 원단 정보: {row.get('fabric_lot_no', '-')}")
            with delete_tab:
                st.warning(f"선택된 {len(selected_rows)}건 삭제")
                if st.toggle("🚨 관리자 삭제 모드 켜기"):
                    if st.button("🗑️ 삭제 실행", type="primary", key="btn_delete_log_tab6"):
                        delete_lots = selected_rows['lot_no'].tolist()
                        supabase.table("work_orders").delete().in_("lot_no", delete_lots).execute()
                        st.toast("삭제 완료!"); time.sleep(1); st.rerun()
    else: st.info("조회된 데이터가 없습니다.")

with tab7:
    with st.form("track"): c1,c2=st.columns([4,1]); l=c1.text_input("LOT"); b=c2.form_submit_button("조회")
    if b: r=supabase.table("work_orders").select("*").eq("lot_no",l).execute(); st.write(r.data)

with tab8: 
    st.markdown("### 🚨 불량 현황")
    try:
        res = supabase.table("defects").select("*").execute()
        df_defects = pd.DataFrame(res.data)
        if not df_defects.empty: st.dataframe(df_defects, use_container_width=True)
        else: st.info("✅ 현재 등록된 불량 내역이 없습니다.")
    except Exception as e: st.error(f"데이터 조회 중 오류가 발생했습니다: {e}")

with tab9:
    st.header("📱 현장 접속 QR")
    content_html = get_access_qr_content_html(APP_URL, "big")
    st.components.v1.html(content_html, height=600)
    if st.button("🖨️ 접속 QR 인쇄", key="btn_print_access_qr_tab9"):
        full_html = generate_print_html(content_html)
        components.html(full_html, height=0, width=0)
