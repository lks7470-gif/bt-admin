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
# ⚙️ 페이지 설정 (반드시 맨 위)
# ==========================================
st.set_page_config(page_title="(주)베스트룸 생산관리", page_icon="🏭", layout="wide")

# ==========================================
# 🛑 로그인 체크
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

def check_process_sequence(lot_no, current_step):
    try:
        response = (supabase.table("production_logs")
                    .select("step")
                    .eq("lot_no", lot_no)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute())
        last_step = response.data[0]['step'] if response.data else "작업대기"
    except Exception: 
        return False, "오류 발생"
    return True, "OK"

def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def fetch_fabric_stock():
    try:
        response = supabase.table("fabric_stock").select("*").execute()
        return {row['lot_no']: row for row in response.data}
    except Exception: 
        return {}

@st.cache_resource
def load_korean_font(size):
    font_filename = "NanumGothic-Bold.ttf"
    if not os.path.exists(font_filename):
        try:
            r = requests.get("https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf")
            with open(font_filename, 'wb') as f: 
                f.write(r.content)
        except Exception: 
            return ImageFont.load_default()
    return ImageFont.truetype(font_filename, size)

def create_label_strip_image(items, rotate=False):
    LABEL_W = 472; LABEL_H = 236
    if not items: 
        return None
    strip_w = LABEL_W * len(items)
    strip_h = LABEL_H
    full_img = Image.new('RGB', (strip_w, strip_h), 'white')
    draw = ImageDraw.Draw(full_img)
    font_lg = load_korean_font(28)
    font_md = load_korean_font(24)

    for i, it in enumerate(items):
        x = i * LABEL_W
        draw.rectangle([x, 0, x + LABEL_W-1, LABEL_H-1], outline="#cccccc", width=2)
        
        lot = it.get('lot', '')
        cust = str(it.get('cust', ''))
        w = str(it.get('w', '0'))
        h = str(it.get('h', '0'))
        e = str(it.get('elec', ''))
        
        qr = qrcode.QRCode(box_size=5, border=0)
        qr.add_data(lot.replace("-", ""))
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").resize((190, 190))
        full_img.paste(qr_img, (x + 10, (LABEL_H - 190) // 2))
        
        tx = x + 210
        draw.text((tx, 25), lot, font=font_lg, fill="black")
        draw.text((tx, 75), cust, font=font_lg if len(cust)<5 else font_md, fill="black")
        draw.text((tx, 125), f"{w} x {h}", font=font_lg, fill="black")
        draw.text((tx, 170), f"[{e}]", font=font_lg, fill="black")
        
        if i < len(items) - 1: 
            draw.line([(x + LABEL_W - 1, 0), (x + LABEL_W - 1, LABEL_H)], fill="#999", width=1)

    if rotate: 
        full_img = full_img.rotate(90, expand=True)
    buf = io.BytesIO()
    full_img.save(buf, format="PNG")
    return buf.getvalue()

def generate_print_html(content_html):
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Print</title>
    <script>setTimeout(function() {{ window.print(); }}, 500);</script></head>
    <body style="margin:0; padding:0;">{content_html}</body></html>"""

def get_label_content_html(items, mode="roll", rotate=False, margin_top=0):
    tr_css = "transform: rotate(90deg);" if rotate else ""
    wrap_css = f"width: 38mm; height: 19mm; page-break-after: always; display: flex; align-items: center; justify-content: center; overflow: hidden; border: 1px solid #ddd; margin-top: {margin_top}mm;" if mode == "roll" else "width: 42mm; height: 22mm; display: inline-flex; align-items: center; justify-content: center; margin: 2px; border: 1px dashed #ccc; float: left;"
    
    html = f"""<!DOCTYPE html><html><head><style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;900&display=swap');
    @media print {{ @page {{ size: 40mm 20mm; margin: 0; }} body {{ margin: 0; }} }}
    .lb {{ {wrap_css} font-family: 'Roboto', sans-serif; background: white; box-sizing: border-box; }}
    .tb {{ font-weight: 900; font-size: 11pt; color: black; line-height: 1.2; }}
    </style></head><body><div style="display:flex; flex-wrap:wrap;">"""
    
    for it in items:
        lot = it.get('lot', '')
        qr = qrcode.QRCode(box_size=5, border=0)
        qr.add_data(lot.replace("-", ""))
        qr.make(fit=True)
        img = image_to_base64(qr.make_image(fill_color="black", back_color="white"))
        
        html += f"""
        <div class="lb">
            <div style="width:38mm; height:19mm; display:flex; align-items:center; {tr_css}">
                <div style="width:38%; text-align:center;"><img src="data:image/png;base64,{img}" style="width:95%;"></div>
                <div style="width:62%; padding-left:1.5mm;">
                    <div class="tb">{lot}</div>
                    <div class="tb">{it.get('cust', '')}</div>
                    <div class="tb">{it.get('w', '0')} x {it.get('h', '0')}</div>
                    <div class="tb">[{it.get('elec', '')}]</div>
                </div>
            </div>
        </div>
        """
    html += "</div></body></html>"
    return html

def get_work_order_html(items):
    html = """<html><head><style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
    @media print { @page { size: A4; margin: 5mm; } body { margin: 0; } .pb { page-break-after: always; } }
    body { font-family: 'Noto Sans KR', sans-serif; color: #000; }
    .card { width: 49%; height: 62.5mm; border: 2px solid #000; box-sizing: border-box; margin-bottom: 1mm; display: flex; flex-direction: column; overflow: hidden; }
    .chead { background-color: #e0e0e0; padding: 2px 8px; border-bottom: 1px solid #000; display: flex; justify-content: space-between; align-items: center; height: 24px; }
    .dim { height: 40px; border-top: 2px solid #000; display: flex; align-items: center; justify-content: center; background-color: #fff; }
    .stbl { width: 100%; border-collapse: collapse; } .stbl td { padding: 1px 0; font-size: 11px; vertical-align: middle; }
    .lbl { font-weight: 900; width: 45px; color: #333; } .val { font-weight: 700; color: #000; }
    </style></head><body><div style="display:flex; flex-wrap:wrap; justify-content:space-between;">"""
    
    chunk = 8
    print_date = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    for i in range(0, len(items), chunk):
        sub = items[i:i + chunk]
        
        html += f"""
        <div style="width:100%; position:relative; margin-bottom:3mm; text-align:center;">
            <span style="font-size:20pt; font-weight:900; text-decoration:underline;">작업 지시서 (Work Order)</span>
            <span style="position:absolute; right:5px; bottom:0; font-size:10pt; color:#555; font-weight:bold;">발행일시: {print_date}</span>
        </div>
        """
        html += '<div style="display:flex; flex-wrap:wrap; justify-content:space-between; width:100%;">'
        
        for it in sub:
            lot = it.get('lot', '')
            qr = qrcode.QRCode(box_size=5, border=0)
            qr.add_data(lot.replace("-", ""))
            qr.make(fit=True)
            img = image_to_base64(qr.make_image(fill_color="black", back_color="white"))
            
            lam_txt = f"<span style='color:#000;'>{it.get('spec_lam','-')}</span>"
            if "생략" in str(it.get('spec_lam','')): 
                lam_txt = "<span style='text-decoration:line-through; color:red; font-weight:bold;'>접합생략</span> <span style='color:#000; font-weight:bold;'>(필름마감)</span>"
            
            w = str(it.get('w', '0'))
            h = str(it.get('h', '0'))
            e = str(it.get('elec', ''))
            wc = "font-weight:900; text-decoration:underline;" if "가로" in e or "W" in e.upper() else "font-weight:500; color:#555;"
            hc = "font-weight:900; text-decoration:underline;" if "세로" in e or "H" in e.upper() else "font-weight:500; color:#555;"
            
            html += f"""
            <div class="card">
                <div class="chead">
                    <div><span style="font-size:13px; font-weight:900;">{lot}</span> <span style="font-size:12px; font-weight:900; color:#333;">[{it.get('prod', '')}]</span></div>
                    <div style="font-size:10px; font-weight:700;">{it.get('cust', '')} | {datetime.now().strftime('%m-%d')}</div>
                </div>
                <div style="display:flex; flex:1; overflow:hidden;">
                    <div style="width:80px; display:flex; align-items:center; justify-content:center; border-right:1px solid #000;"><img src="data:image/png;base64,{img}" style="width:100%;"></div>
                    <div style="flex:1; padding:2px 6px;">
                        <table class="stbl">
                            <tr><td class="lbl">🧵 원단</td><td class="val">{it.get('fabric','-')}</td></tr>
                            <tr><td colspan="2"><hr style="margin:2px 0; border-top:1px dashed #ccc;"></td></tr>
                            <tr><td class="lbl">✂️ 커팅</td><td class="val">{it.get('spec_cut','-')}</td></tr>
                            <tr><td class="lbl">🔥 접합</td><td class="val">{lam_txt}</td></tr>
                            <tr><td class="lbl" style="color:red;">⚠️ 특이</td><td class="val" style="color:red;">{it.get('note','-')}</td></tr>
                        </table>
                    </div>
                </div>
                <div class="dim">
                    <span style="font-size:28px; {wc}">{w}</span><span style="font-size:20px; font-weight:bold; margin:0 5px;">X</span><span style="font-size:28px; {hc}">{h}</span><span style="font-size:18px; font-weight:900; margin-left:15px;">[{e}]</span>
                </div>
            </div>
            """
        html += '</div>'
        html += '<div style="width:100%; text-align:center; font-size:11px; color:#444; margin-top:3mm; font-weight:bold; letter-spacing:1px;">※ 본 문서는 (주)베스트룸의 소중한 자산이므로 무단 복제 및 외부 유출을 엄격히 금합니다.</div>'
        html += '<div class="pb"></div>'
    return html + "</body></html>"

def get_access_qr_content_html(url):
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = image_to_base64(qr.make_image(fill_color="black", back_color="white"))
    html = f"""
    <div style="text-align:center; padding-top:50mm;">
        <div style="border:5px solid black; padding:30px; display:inline-block; border-radius:20px;">
            <div style="font-size:30pt; font-weight:900;">🏭 시스템 접속 QR</div><br>
            <img src="data:image/png;base64,{img}" style="width:350px;">
        </div>
    </div>
    """
    return html

# 10. 견적서 HTML
def get_quotation_html(cust_data, items_df, totals):
    logo = ""
    if os.path.exists("pages/company_logo.png"):
        with open("pages/company_logo.png", "rb") as f: logo = base64.b64encode(f.read()).decode()
    elif os.path.exists("company_logo.png"):
        with open("company_logo.png", "rb") as f: logo = base64.b64encode(f.read()).decode()
    
    today = datetime.now().strftime("%Y-%m-%d")
    q_no = f"BR{datetime.now().strftime('%Y%m%d')}-01"
    row_h = "height: 28px;" 
    
    html = f"""<html><head><style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
    @media print {{ @page {{ size: A4; margin: 10mm; }} body {{ margin: 0; zoom: 92%; }} }}
    body {{ font-family: 'Noto Sans KR', sans-serif; font-size: 11px; margin: 0; padding: 15px; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid #000; }}
    th, td {{ border: 1px solid #000; padding: 2px 5px; vertical-align: middle; }}
    .title {{ text-align: center; font-size: 30px; font-weight: 900; margin-bottom: 15px; letter-spacing: 10px; }}
    .grey {{ background-color: #e0e0e0; text-align: center; font-weight: bold; }}
    .txt-c {{ text-align: center; }} .txt-r {{ text-align: right; }} .txt-l {{ text-align: left; }}
    .no-b {{ border: none; }}
    .sub-row {{ background-color: #f9fbe7; font-weight: bold; }}
    </style></head><body>
    <div class="title">견 적 서</div>
    <table style="margin-bottom:5px;">
        <tr style="{row_h}">
            <td rowspan="4" width="20%" class="txt-c no-b" style="border:1px solid #000; padding:5px;"><img src="data:image/png;base64,{logo}" style="max-width:110px; display:block; margin:auto;"></td>
            <td class="grey" width="12%">사업자등록번호</td><td colspan="3" class="txt-c">108-81-49494</td><td class="grey" width="10%">대표자</td><td class="txt-c" width="10%">이 광 석</td>
        </tr>
        <tr style="{row_h}"><td class="grey">상 호</td><td colspan="3" class="txt-c">(주)베스트룸</td><td class="grey"></td><td></td></tr>
        <tr style="{row_h}"><td class="grey">주 소</td><td colspan="5" class="txt-c">강원도 강릉시 과학단지로 106-40</td></tr>
        <tr style="{row_h}"><td class="grey">전 화</td><td class="txt-c" width="25%">033 655 2745</td><td class="grey" width="10%">이메일</td><td colspan="3" class="txt-c"></td></tr>
    </table>
    <table style="border:none; margin-bottom:0;">
        <tr>
            <td width="40%" style="padding:0; border:none; vertical-align:top;">
                <table style="width:100%; border-right:none; border-bottom:none;">
                    <tr style="{row_h}"><td rowspan="2" class="grey" width="18%" style="vertical-align:middle;">수신처</td><td class="grey" width="22%" style="color:#0033cc;">고객사</td><td class="txt-c" style="color:#0033cc; font-weight:bold;">{cust_data['name']}</td></tr>
                    <tr style="{row_h}"><td class="grey">참 조</td><td class="txt-c">{cust_data['ref']}</td></tr>
                    <tr style="{row_h}"><td class="grey">연락처</td><td colspan="2" class="txt-c">{cust_data['contact']}</td></tr>
                    <tr style="{row_h}"><td class="grey">팩 스</td><td colspan="2" class="txt-c">{cust_data.get('fax','')}</td></tr>
                    <tr style="{row_h}"><td class="grey">E-mail</td><td colspan="2" class="txt-c">{cust_data.get('email','')}</td></tr>
                </table>
            </td>
            <td width="60%" style="padding:0; border:none; vertical-align:top;">
                <table style="width:100%; border-left:none; border-bottom:none;">
                    <tr style="{row_h}"><td class="grey" width="25%">발행일자 / 유효기간</td><td class="txt-c">{today} &nbsp; / &nbsp; 30일</td></tr>
                    <tr style="{row_h}"><td class="grey">결 제 조 건</td><td class="txt-c">Remark 참고</td></tr>
                    <tr style="{row_h}"><td class="grey">결 제 계 좌</td><td class="txt-c"></td></tr>
                    <tr style="{row_h}"><td class="grey">담당자 (책임 업무)</td><td class="txt-c">김명자 이사 (010 3439 0936)</td></tr>
                    <tr style="{row_h}"><td class="grey">담당자 (기타 지원)</td><td class="txt-c"></td></tr>
                </table>
            </td>
        </tr>
    </table>
    <table style="margin-top:0; border-top:1px solid #000;">
        <tr style="{row_h}"><td class="grey" width="15%">견적서 번호</td><td class="txt-c" style="font-weight:bold;">{q_no}</td></tr>
    </table>
    <div style="text-align:center; font-weight:bold; margin:10px 0;">아래와 같이 견적 합니다.</div>
    
    <table style="margin-top:5px;">
        <tr class="grey" style="height:30px;">
            <td width="8%">Section</td><td width="20%">Description</td><td width="15%">세부내용</td><td width="7%">Sqm</td><td width="5%">Q'ty</td><td width="12%">U/Price</td><td width="13%">Total</td><td width="20%">Remark</td>
        </tr>
    """
    
    mat_df = items_df[items_df['구분'].str.contains("자재", na=False)]
    con_df = items_df[items_df['구분'].str.contains("시공", na=False)]
    etc_df = items_df[~items_df['구분'].str.contains("자재|시공", na=False)]
    
    def add_rows(df, sub_label):
        rows_html = ""
        sub_total = 0
        for _, row in df.iterrows():
            p = f"{int(row['단가']):,}" if row['단가'] > 0 else ""
            t = f"{int(row['공급가']):,}" if row['공급가'] > 0 else ""
            sub_total += int(row['공급가'])
            
            rows_html += f"""
            <tr style="height:25px;">
                <td class="txt-c">{row.get('구분','')}</td>
                <td class="txt-l" style="padding-left:5px;">{row.get('품명','')}</td>
                <td class="txt-c">{row.get('세부내용','')}</td>
                <td class="txt-c">{row.get('Sqm','')}</td>
                <td class="txt-c">{row.get('수량','')}</td>
                <td class="txt-r" style="padding-right:5px;">{p}</td>
                <td class="txt-r" style="padding-right:5px;">{t}</td>
                <td class="txt-l" style="padding-left:5px; font-size:10px;">{row.get('비고','')}</td>
            </tr>
            """
        if sub_total > 0:
            rows_html += f"""
            <tr class="sub-row" style="height:25px;">
                <td colspan="6" class="txt-c">{sub_label} 소계</td>
                <td class="txt-r" style="padding-right:5px;">{sub_total:,}</td>
                <td></td>
            </tr>
            """
        return rows_html

    html += add_rows(mat_df, "자재비")
    html += add_rows(con_df, "시공비")
    html += add_rows(etc_df, "기타")
        
    total_rows = len(mat_df) + len(con_df) + len(etc_df) + 2 
    for _ in range(max(0, 15 - total_rows)): 
        html += '<tr style="height:25px;"><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>'
    
    html += f"""
        <tr style="background-color:#fff3e0; height:28px; font-weight:bold;">
            <td colspan="4" class="txt-c">공급가액 : {totals['supply']:,} &nbsp; / &nbsp; 부가세(VAT) : {totals['vat']:,}</td>
            <td class="txt-c" style="background-color:#ffe0b2;">합 계</td>
            <td colspan="3" class="txt-r" style="padding-right:15px; color:#000; font-size:14px;">₩ {totals['grand_total']:,}</td>
        </tr>
    </table>
    <div style="margin-top:15px; font-size:10px; line-height:1.5; border:1px solid #000; padding:8px; border-radius:5px; page-break-inside: avoid;">
        <b>※ Remark (참고사항)</b><br>
        1. 납품기일은 협의 입니다.<br>
        2. CONTROLLER 포함<br>
        3. <b>결제조건:</b> 발주시 자재비(VAT포함) 선입금, 시공완료 후 5일 이내 시공비(VAT포함) 입금 기준 (발주 후에는 FILM이 재단되므로 취소 불가합니다)<br>
        4. 사업자등록증: 팩스 033-655-2751 / 이메일 bttax@betroom.co.kr 송부요청드립니다.<br>
        5. 필름 시공장소까지 전기 (220V) 콘센트 선작업 제공 기준입니다. (별도 선작업 시 비용 추가)<br>
        6. 시공시 필요되는 특장차 별도. 시공비는 서울/경기 수도권 기준입니다.<br>
        7. 프레임은 검정이며, 샴페인골드, 로즈골드 변경 가능 (추가 5만원)
    </div>
    </body></html>"""
    return html

# ==========================================
# 🖥️ 관리자 UI 시작
# ==========================================
APP_URL = "https://bt-app-pwgumeleefkwpf3xsu5bob.streamlit.app/"
if 'order_list' not in st.session_state: st.session_state.order_list = []
if 'generated_qrs' not in st.session_state: st.session_state.generated_qrs = []
if 'fabric_db' not in st.session_state: st.session_state.fabric_db = {}

# [견적서 초기 데이터]
if 'quote_items' not in st.session_state: 
    st.session_state.quote_items = pd.DataFrame([
        {"구분": "자재비", "품명": "SMART 뷰 유리", "W(mm)": 1200, "H(mm)": 2400, "유리": "Clear", "두께": "4+4", "세부내용": "1200*2400 / Clear / 4+4", "Sqm": 2.88, "수량": 1, "단가": 912000, "공급가": 0, "비고": ""},
        {"구분": "자재비", "품명": "부자재", "W(mm)":0, "H(mm)":0, "유리":"", "두께":"", "세부내용": "스위치 타입", "Sqm": "", "수량": 1, "단가": 75000, "공급가": 0, "비고": ""},
        {"구분": "시공비", "품명": "시공비", "W(mm)":0, "H(mm)":0, "유리":"", "두께":"", "세부내용": "", "Sqm": "", "수량": 1, "단가": 350000, "공급가": 0, "비고": "1일 시공"}
    ])

st.sidebar.title("👨‍💼 지시서 설정")
if st.sidebar.button("🔄 재고 정보 새로고침", use_container_width=True): 
    st.session_state.fabric_db = fetch_fabric_stock()
    st.toast("✅ 재고 최신화 완료!")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "📝 작업 입력", "📄 지시서 인쇄", "🏷️ 라벨 인쇄", "🔄 QR 재발행", 
    "🧵 원단 재고", "📊 발행 이력", "🔍 제품 추적", "🚨 불량 현황", 
    "📱 접속 QR", "📑 견적서 작성"
])

# Tab 1: 작업 입력
with tab1:
    st.markdown("### 📝 신규 작업 지시 등록")
    
    with st.expander("📖 관리자/작업자 시스템 사용 설명서 (클릭해서 열기)"):
        st.markdown("""
        **[1] 지시서 발행 방법 (관리자)**
        1. 아래 폼에 고객사, 제품, 가로/세로 규격을 입력합니다.
        2. `사용할 원단`을 선택하면 **식별코드**가 자동으로 입력됩니다. (이 코드는 지시서 맨 앞 영문 4자리로 출력되며 자유롭게 수정 가능합니다.)
        3. `➕ 작업 목록 추가`를 눌러 리스트를 만들고, `🚀 최종 발행 및 저장`을 누릅니다.
        4. 인쇄 탭으로 이동하여 지시서를 프린트합니다. (이때 원단 재고는 자동으로 차감됩니다!)

        **[2] 현장 스마트폰 입력 방법 (작업자)**
        1. 작업장 벽에 붙은 `시스템 접속 QR`을 핸드폰 카메라로 찍어 접속합니다.
        2. 화면에서 본인 이름과 진행할 공정(Full Cut, 접합 등)을 선택합니다.
        3. 장비의 세팅값이나 현재 온도를 입력칸에 적어줍니다.
        4. 화면의 `QR 스캔` 카메라로 제품에 붙은 지시서 QR을 찍고 파란색 `저장` 버튼을 누르면 끝납니다.
        *(※ 불량이 났을 때는 상단 `🚨 불량 발생 신고` 스위치를 켜고 저장하세요!)*
        """)

    if not st.session_state.fabric_db: 
        st.session_state.fabric_db = fetch_fabric_stock()
    
    with st.form("order_form"):
        c1, c2 = st.columns([1, 1])
        customer = c1.text_input("고객사 (Customer)", placeholder="예: A건설")
        product = c2.selectbox("제품 종류", ["스마트글라스", "접합필름", "PDLC원단", "일반유리"])
        
        st.divider()
        
        # [원단 선택 및 잔량 표시 로직 보강]
        c_mat1, c_mat2 = st.columns(2)
        stock_options = ["➕ 직접 입력"] 
        if st.session_state.fabric_db:
            for lot, info in st.session_state.fabric_db.items(): 
                try:
                    tot = float(info.get('total_len', 0) or 0)
                    usd = float(info.get('used_len', 0) or 0)
                    rm = tot - usd
                    stock_options.append(f"{lot} | {info.get('name','')} (잔량: {rm:.1f}m)")
                except Exception:
                    stock_options.append(f"{lot} | {info.get('name','')}")
                    
        selected_stock = c_mat1.selectbox("🧵 사용할 원단 선택", stock_options)
        
        default_short = "ROLL"
        fabric_lot = ""
        
        if "직접 입력" in selected_stock: 
            fabric_lot = c_mat1.text_input("원단 LOT 번호 입력", placeholder="Roll-2312a-KR")
        else:
            fabric_lot = selected_stock.split(" | ")[0]
            sel_info = st.session_state.fabric_db.get(fabric_lot, {})
            
            # [재고 부족 경고창 띄우기]
            try:
                tot = float(sel_info.get('total_len', 0) or 0)
                used = float(sel_info.get('used_len', 0) or 0)
                rem = tot - used
                
                if rem <= 0:
                    c_mat1.error(f"🚨 재고 소진: {fabric_lot} (현재 잔량: {rem:.1f}m - 입고가 필요합니다!)")
                elif rem <= 10:
                    c_mat1.warning(f"⚠️ 재고 임박: {fabric_lot} (현재 잔량: {rem:.1f}m 남았습니다.)")
                else:
                    c_mat1.info(f"✅ 선택됨: {fabric_lot} (잔량: {rem:.1f}m)")
            except Exception:
                c_mat1.info(f"✅ 선택됨: {fabric_lot}")

            if sel_info.get('short_code'): 
                default_short = sel_info.get('short_code')
        
        fabric_short = c_mat2.text_input("🆔 식별코드 (4자리)", value=default_short, max_chars=4, key=f"sc_{fabric_lot}")
        
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
                "고객사": customer, "제품": product, "규격": f"{w}x{h}", "w": w, "h": h, 
                "전극": elec_type, "spec_cut": spec_cut, "spec_lam": spec_lam, 
                "is_lam": is_lamination, "spec": f"{spec_cut} | {spec_lam}", 
                "비고": note, "수량": count, "lot_no": fabric_lot, "lot_short": final_short
            })
            st.success(f"추가됨! (ID: {final_short})")
            
    if st.session_state.order_list:
        st.dataframe(pd.DataFrame(st.session_state.order_list)[["고객사", "lot_short", "제품", "규격", "spec_lam", "수량"]], use_container_width=True)
        
        if st.button("🚀 최종 발행 및 저장"):
            date_str = datetime.now().strftime("%y%m%d")
            prod_map = {"스마트글라스": "G", "접합필름": "F", "PDLC원단": "P", "일반유리": "N"}
            new_qrs = []
            cnt = 0
            
            for item in st.session_state.order_list:
                lot = item.get('lot_no', '')
                if lot and "직접 입력" not in lot and lot != "미등록 원단":
                    try:
                        h_m = float(item.get('h', 0)) / 1000.0 
                        qty = float(item.get('수량', 1))
                        consumed = h_m * qty 

                        res = supabase.table("fabric_stock").select("used_len, total_len").eq("lot_no", lot).execute()
                        if res.data:
                            raw_used = res.data[0].get('used_len')
                            raw_tot = res.data[0].get('total_len')
                            
                            try:
                                curr_used = float(raw_used) if raw_used is not None else 0.0
                                tot_len = float(raw_tot) if raw_tot is not None else 0.0
                            except (TypeError, ValueError):
                                curr_used = 0.0
                                tot_len = 0.0
                                
                            new_used = curr_used + consumed
                            rem_stock = tot_len - new_used # 방어막 계산

                            up_res = supabase.table("fabric_stock").update({"used_len": new_used}).eq("lot_no", lot).execute()
                            if up_res.data:
                                # [사후 알림/경고창 띄우기]
                                if rem_stock < 0:
                                    st.error(f"🚨 [{lot}] 원단 재고 초과! (부족분: {abs(rem_stock):.2f}m)")
                                elif rem_stock <= 10:
                                    st.warning(f"⚠️ [{lot}] 원단 잔량 부족 주의 (남은 량: {rem_stock:.2f}m)")
                                else:
                                    st.toast(f"🧵 [{lot}] 원단 {consumed:.3f}m 차감 성공! (잔량: {rem_stock:.2f}m)")
                    except Exception as e:
                        st.error(f"🚨 {lot} 재고 차감 중 오류 발생: {e}")

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
                        
                        new_qrs.append({
                            "lot": final_lot_id, "w": item['w'], "h": item['h'], "elec": item['전극'], 
                            "prod": item['제품'], "cust": item['고객사'], 
                            "fabric": item['lot_no'], "spec_cut": item['spec_cut'], "spec_lam": item['spec_lam'], "note": item['비고']
                        })
                    except Exception as e:
                        st.error(f"작업 지시서 생성 중 오류: {e}")
                        
            st.session_state.generated_qrs = new_qrs
            st.session_state.order_list = []
            st.session_state.fabric_db = fetch_fabric_stock() 
            st.success("✅ 발행 및 재고 자동 차감이 완료되었습니다!")
            time.sleep(2)
            st.rerun()

# Tab 2: 지시서
with tab2:
    if st.session_state.generated_qrs:
        html = get_work_order_html(st.session_state.generated_qrs)
        st.components.v1.html(html, height=1000, scrolling=True)
        if st.button("🖨️ 인쇄하기"): 
            components.html(generate_print_html(html), height=0)
    else: 
        st.info("발행된 작업이 없습니다.")

# Tab 3: 라벨
with tab3:
    if st.session_state.generated_qrs:
        html = get_label_content_html(st.session_state.generated_qrs)
        st.components.v1.html(html, height=600, scrolling=True)
        if st.button("🖨️ 라벨 인쇄"): 
            components.html(generate_print_html(html), height=0)
        img_data = create_label_strip_image(st.session_state.generated_qrs)
        if img_data: 
            st.download_button("💾 이미지 다운로드", img_data, file_name="labels.png")
    else: 
        st.info("발행된 작업이 없습니다.")

# Tab 4: 재발행
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
                    if match: 
                        w, h, elec = match.groups()
                    rep_items.append({
                        "lot": r['lot_no'], "cust": r['customer'], "prod": r['product'], 
                        "w": w, "h": h, "elec": elec, "fabric": r.get('fabric_lot_no','-'), 
                        "spec_cut": r.get('spec',''), "spec_lam": r.get('spec',''), "note": r.get('note','')
                    })
                html = get_work_order_html(rep_items)
                components.html(generate_print_html(html), height=0)

# Tab 5: 재고
with tab5:
    with st.form("fabric_in"):
        st.markdown("##### 📥 원단 입고 등록")
        c1, c2, c3 = st.columns(3)
        n_lot = c1.text_input("LOT 번호")
        n_name = c2.text_input("제품명")
        n_w = c3.number_input("폭(mm)", min_value=0, value=1200, step=10)

        c4, c5, c6 = st.columns(3)
        n_tot = c4.number_input("총길이(m)", min_value=0.0, value=100.0, step=1.0)
        n_rem = c5.number_input("현재 잔량(m)", min_value=0.0, value=100.0, step=1.0)
        n_short = c6.text_input("단축코드(4자리)", placeholder="예: TA12", help="선택사항")

        if st.form_submit_button("입고 등록"):
            if not n_lot or not n_name: 
                st.error("⚠️ LOT 번호와 제품명은 필수입니다.")
            else:
                data = {
                    "lot_no": n_lot, 
                    "name": n_name, 
                    "width": n_w, 
                    "total_len": n_tot, 
                    "used_len": n_tot - n_rem,
                    "reg_date": datetime.now().strftime("%Y-%m-%d")
                }
                if n_short: 
                    try:
                        data["short_code"] = n_short
                        supabase.table("fabric_stock").insert(data).execute()
                        st.success(f"✅ {n_lot} 입고 완료!")
                        st.session_state.fabric_db = fetch_fabric_stock()
                        time.sleep(1)
                        st.rerun()
                    except Exception:
                        data.pop("short_code")
                        try:
                            supabase.table("fabric_stock").insert(data).execute()
                            st.success(f"✅ {n_lot} 입고 완료! (단축코드 제외)")
                            st.session_state.fabric_db = fetch_fabric_stock()
                            time.sleep(1)
                            st.rerun()
                        except Exception as e: 
                            st.error(f"🚨 저장 실패: {e}")
                else:
                    try:
                        supabase.table("fabric_stock").insert(data).execute()
                        st.success(f"✅ {n_lot} 입고 완료!")
                        st.session_state.fabric_db = fetch_fabric_stock()
                        time.sleep(1)
                        st.rerun()
                    except Exception as e: 
                        st.error(f"🚨 저장 실패: {e}")

    try:
        res = supabase.table("fabric_stock").select("*").execute()
        if res.data: 
            st.data_editor(pd.DataFrame(res.data), hide_index=True, use_container_width=True)
        else: 
            st.info("등록된 원단 재고가 없습니다.")
    except Exception: 
        pass

# Tab 6: 이력
with tab6:
    res = supabase.table("work_orders").select("*").order("created_at", desc=True).limit(200).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        sel_rows = st.data_editor(df.assign(선택=False), column_config={"선택": st.column_config.CheckboxColumn()})
        sel = sel_rows[sel_rows["선택"]]
        if not sel.empty:
            sel_row = sel.iloc[0]
            st.markdown(f"#### 📜 [{sel_row['lot_no']}] 작업자 상세 입력 로그")
            logs = supabase.table("production_logs").select("*").eq("lot_no", sel_row['lot_no']).order("created_at").execute()
            if logs.data: 
                st.dataframe(pd.DataFrame(logs.data)[['step', 'data', 'worker', 'created_at']], use_container_width=True)
            else: 
                st.warning("작업 이력이 없습니다.")
            
            if st.button("🗑️ 삭제 실행", type="primary"):
                supabase.table("work_orders").delete().in_("lot_no", sel['lot_no'].tolist()).execute()
                st.rerun()

# Tab 7, 8, 9
with tab7:
    with st.form("track_form"):
        track_lot = st.text_input("추적할 LOT 번호 입력")
        if st.form_submit_button("검색"):
            r = supabase.table("production_logs").select("*").eq("lot_no", track_lot).order("created_at").execute()
            if r.data: 
                st.dataframe(r.data)
            else: 
                st.error("이력이 없습니다.")

with tab8:
    st.markdown("### 🚨 불량 등록 현황")
    r = supabase.table("defects").select("*").order("created_at", desc=True).execute()
    if r.data: 
        st.dataframe(r.data)
    else: 
        st.info("불량 내역이 없습니다.")

with tab9:
    html = get_access_qr_content_html(APP_URL)
    st.components.v1.html(html, height=500)
    if st.button("🖨️ 접속 QR 인쇄"): 
        components.html(generate_print_html(html), height=0)

# Tab 10: 견적서
with tab10:
    st.markdown("### 📑 견적서 작성 (자동 계산 + 소계)")
    c1, c2, c3 = st.columns(3)
    
    q_cust = c1.text_input("고객사명", placeholder="예: 에코하우징", key="q_cust_input")
    q_ref = c2.text_input("참조", placeholder="예: 조성옥 대표님", key="q_ref_input")
    q_contact = c3.text_input("연락처", placeholder="예: 010-9941-6763", key="q_contact_input")
    q_fax = st.text_input("팩스", placeholder="", key="q_fax_input")
    q_email = st.text_input("E-mail", placeholder="", key="q_email_input")
    
    st.info("💡 '가로/세로'를 비워두면(0), 수기로 입력한 '단가'가 적용됩니다. (시공비 등 입력 시 활용)")
    
    edited = st.data_editor(
        st.session_state.quote_items,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "구분": st.column_config.TextColumn("Section", width="small"),
            "품명": st.column_config.TextColumn("Description", width="medium"),
            "W(mm)": st.column_config.NumberColumn("가로(mm)", step=10),
            "H(mm)": st.column_config.NumberColumn("세로(mm)", step=10),
            "유리": st.column_config.SelectboxColumn("유리종류", options=["Clear", "Low iron", "Dark grey"], default="Clear"),
            "두께": st.column_config.SelectboxColumn("두께", options=["4+4", "5+5", "6+6"], default="4+4"),
            "세부내용": st.column_config.TextColumn("Details"), 
            "Sqm": st.column_config.TextColumn("Sqm", disabled=True),
            "수량": st.column_config.NumberColumn("Q'ty", min_value=0, step=1),
            "단가": st.column_config.NumberColumn("U/Price", min_value=0, step=100, format="%d"),
            "공급가": st.column_config.NumberColumn("Total", disabled=True, format="%d"),
            "비고": st.column_config.TextColumn("Remark"),
        }
    )
    
    if not edited.empty:
        for i, row in edited.iterrows():
            try:
                val_w = row.get('W(mm)')
                val_h = row.get('H(mm)')
                val_qty = row.get('수량')
                val_price = row.get('단가')
                
                w = float(val_w) if pd.notna(val_w) and val_w != "" else 0.0
                h = float(val_h) if pd.notna(val_h) and val_h != "" else 0.0
                qty = float(val_qty) if pd.notna(val_qty) and val_qty != "" else 0.0
                user_price = float(val_price) if pd.notna(val_price) and val_price != "" else 0.0
                
                if w > 0 and h > 0:
                    rw = math.ceil(w / 100) * 100
                    rh = math.ceil(h / 100) * 100
                    area = (rw * rh) / 1_000_000
                    
                    base_price = 300150
                    p_w = 0; p_h = 0
                    if rw > 2000: p_w = 0.15
                    elif rw > 1800: p_w = 0.10
                    elif rw > 1500: p_w = 0.05
                    
                    if rh > 3200: p_h = 0.15
                    elif rh > 2800: p_h = 0.10
                    elif rh > 2400: p_h = 0.05
                    elif rh > 2000: p_h = 0.0
                    
                    f_glass = 1.12 if "Low" in str(row.get('유리','')) else 1.0
                    f_thick = 1.0
                    if "5+5" in str(row.get('두께','')): f_thick = 1.08
                    elif "6+6" in str(row.get('두께','')): f_thick = 1.15
                    
                    unit_m2_price = base_price * f_glass * f_thick * (1 + p_w + p_h)
                    unit_sheet_price = unit_m2_price * area
                    
                    edited.at[i, 'Sqm'] = f"{area:.2f}"
                    edited.at[i, '단가'] = round(unit_sheet_price, -2)
                    edited.at[i, '공급가'] = edited.at[i, '단가'] * qty
                    edited.at[i, '세부내용'] = f"{int(w)}*{int(h)} / {row.get('유리','')} / {row.get('두께','')}"
                else:
                    edited.at[i, 'Sqm'] = ""
                    edited.at[i, '공급가'] = user_price * qty
            except Exception: 
                pass
        
        st.session_state.quote_items = edited.copy()

        total_supply = int(edited['공급가'].sum())
        total_vat = int(total_supply * 0.1)
        grand_total = total_supply + total_vat
        
        st.divider()
        k1, k2, k3 = st.columns(3)
        k1.metric("공급가액", f"{total_supply:,} 원")
        k2.metric("부가세 (10%)", f"{total_vat:,} 원")
        k3.metric("총 합계", f"{grand_total:,} 원")
        
        if st.button("🖨️ 견적서 인쇄 / 미리보기", type="primary", use_container_width=True):
            if not q_cust: 
                st.warning("고객사명을 입력해주세요.")
            else:
                cust_data = {"name": q_cust, "ref": q_ref, "contact": q_contact, "fax": q_fax, "email": q_email}
                totals = {"supply": total_supply, "vat": total_vat, "grand_total": grand_total}
                html = get_quotation_html(cust_data, edited, totals)
                components.html(generate_print_html(html), height=0)
                st.components.v1.html(html, height=1000, scrolling=True)
