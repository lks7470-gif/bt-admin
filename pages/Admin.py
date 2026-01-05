# 파일명: pages/Worker.py
import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import cv2
import numpy as np
import time

# (from supabase... 는 삭제해도 되고 둬도 되지만, 안 쓰면 지우는 게 깔끔합니다)

# 👇 여기 딱 2줄로 연결 끝!
from connection import get_supabase_client
supabase = get_supabase_client()

# ==========================================
# ⚙️ 화면 설정
# ==========================================
st.set_page_config(page_title="현장 작업자", page_icon="👷")

# UI 스타일 (PC 중앙 정렬 + 모바일 꽉 참 + 하단 여백 확보)
st.markdown("""
<style>
    /* 1. PC에서 너무 퍼지지 않게 중앙 정렬 (600px 제한) */
    .block-container { 
        max-width: 600px !important; 
        padding: 1rem !important; 
        margin: 0 auto !important; 
    }
    
    /* 2. 카메라 화면: 비율 유지하며 깔끔하게 */
    [data-testid="stCameraInput"] video { 
        width: 100% !important;
        border-radius: 15px !important; 
        border: 3px solid #2196F3 !important; 
        object-fit: contain !important; 
    }
    
    /* 3. 버튼 스타일: 큼직하고 시원하게 */
    div.stButton > button {
        width: 100%;
        height: 60px;
        font-weight: bold;
        font-size: 20px !important;
        border-radius: 12px;
        background-color: #2196F3;
        color: white;
        margin-top: 10px;
    }

    /* 불량 모드 박스 */
    .defect-mode-box { 
        border: 3px solid #FF5252; 
        padding: 10px; 
        border-radius: 10px; 
        background-color: #FFEBEE; 
        color: #D32F2F; 
        font-weight: bold; 
        text-align: center; 
        margin-bottom: 10px; 
    }
</style>
""", unsafe_allow_html=True)

st.title("👷 공정 작업 등록")

# 1. 작업자 선택
worker_list = ["작업자A", "작업자B", "김반장", "이주임", "박대리"]
current_worker = st.selectbox("👤 작업자 선택", worker_list)

st.divider()

# 공정 단계
STEP_LEVEL = {
    "Full Cut": 10, "Half Cut": 20, "전극 완료": 30, 
    "접합: 1. 준비 완료": 41, "접합: 2. 가열 시작": 42, "접합: 3. 공정 완료 (End)": 43
}

# 불량 모드 스위치
is_defect_mode = st.toggle("🚨 불량 발생 신고", value=False)

if is_defect_mode:
    st.markdown('<div class="defect-mode-box">🚨 불량 등록 모드</div>', unsafe_allow_html=True)
    step = st.selectbox("발견 공정", list(STEP_LEVEL.keys())) 
    defect_type = st.selectbox("불량 유형", ["이물질", "기포/들뜸", "치수 불량", "스크래치", "전극 불량", "원단 불량", "기타"])
    defect_note = st.text_input("상세 내용", placeholder="예: 우측 상단 3cm 찢어짐")
    save_data = f"[{defect_type}] {defect_note}"
    current_level = 999 
else:
    step = st.radio("현재 공정", list(STEP_LEVEL.keys()))
    current_level = STEP_LEVEL.get(step, 0)
    
    save_data = "-"
    # 공정별 입력창 (보내주신 파일 기능 반영)
    if "Cut" in step:
        st.info("⚙️ 장비 세팅값 입력")
        c1, c2, c3 = st.columns(3)
        sp = c1.number_input("Speed", value=0); mx = c2.number_input("Max", value=0); mn = c3.number_input("Min", value=0)
        save_data = f"S:{sp} / M:{mx} / m:{mn}"
    elif "End" in step or "공정 완료" in step:
        st.info("🌡️ 최종 온도 입력")
        c1, c2 = st.columns(2)
        t1 = c1.number_input("내부(℃)", value=0.0); t2 = c2.number_input("Start(℃)", value=0.0)
        save_data = f"내부:{t1} / Start:{t2}"
    else:
        note = st.text_input("📝 특이사항 (선택)", placeholder="특이사항 없음")
        if note: save_data = note

st.markdown("### 👇 QR 스캔")
st.caption("※ 화면 중앙에 QR코드를 맞춰주세요.")

# ==========================================
# 📷 카메라 로직
# ==========================================
img_file = st.camera_input("QR 스캔", label_visibility="collapsed")

if img_file is not None:
    bytes_data = img_file.getvalue()
    cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    gray_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)
    
    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(gray_img)

    if data:
        st.success(f"🔍 인식 성공: **{data}**")
        
        try:
            # Supabase 조회
            response = supabase.table("work_orders").select("status").eq("lot_no", data).execute()
            
            if not response.data:
                st.error("❌ 등록되지 않은 LOT 번호입니다.")
            else:
                prev_status = response.data[0]['status']
                
                # 불량/순서 체크
                if "불량" in prev_status or "보류" in prev_status:
                    st.error(f"⛔ 경고: 불량/보류 제품입니다! ({prev_status})")
                    st.stop()

                if not is_defect_mode:
                    prev_level = 0
                    for key, val in STEP_LEVEL.items():
                        if key in prev_status: prev_level = val; break
                    
                    if prev_level >= current_level:
                        st.warning(f"⚠️ 작업 불가! (현재 상태: {prev_status})")
                        st.info("이미 완료되었거나, 더 높은 단계의 공정입니다.")
                        st.stop()
                
                # 저장 버튼
                btn_label = "🚨 불량 등록" if is_defect_mode else "💾 작업 완료 저장"
                btn_type = "secondary" if is_defect_mode else "primary"

                if st.button(btn_label, type=btn_type, use_container_width=True):
                    if is_defect_mode:
                        supabase.table("defects").insert({
                            "lot_no": data, "step": step, "defect_type": defect_type, 
                            "note": defect_note, "status": "조치대기", "worker": current_worker
                        }).execute()
                        supabase.table("work_orders").update({"status": f"⛔ 불량({defect_type})"}).eq("lot_no", data).execute()
                        st.success(f"🚨 불량 등록 완료! ({defect_type})")
                    else:
                        supabase.table("production_logs").insert({
                            "lot_no": data, "step": step, "data": save_data, 
                            "worker": current_worker, "result": "OK"
                        }).execute()
                        supabase.table("work_orders").update({"status": step}).eq("lot_no", data).execute()
                        st.balloons()
                        st.success(f"✅ 작업 저장 완료! ({step})")
                    
                    # 1초 후 새로고침
                    time.sleep(1)
                    st.rerun()

        except Exception as e:
            st.error("📡 저장 중 오류가 발생했습니다.")
            st.code(f"에러 내용: {e}")

    else:
        st.warning("❌ QR 인식을 못 했습니다. 다시 찍어주세요.")

# 🔥 [핵심] 화면 맨 아래에 넉넉한 여백 추가 (버튼이 바닥에 붙지 않게 함)

st.markdown("<div style='height: 150px;'></div>", unsafe_allow_html=True)
