# 파일명: pages/Worker.py
import streamlit as st
import time
import cv2              # 👈 [필수] 카메라 영상 처리용
import numpy as np      # 👈 [필수] 이미지 데이터 변환용
from datetime import datetime

# ==========================================
# 🛑 [문지기] 로그인 안 했으면 메인으로 강제 이동
# ==========================================
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("⚠️ 로그인이 필요합니다. 메인 화면으로 이동합니다...")
    time.sleep(1)
    st.switch_page("Main.py")
    st.stop()

# ==========================================
# 🔌 DB 연결 (connection.py 사용)
# ==========================================
try:
    from connection import get_supabase_client
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"❌ DB 연결 실패: {e}")
    st.stop()

# ==========================================
# ⚙️ 화면 설정 및 스타일
# ==========================================
st.set_page_config(page_title="현장 작업자", page_icon="👷")

st.markdown("""
<style>
    /* 1. 모바일 화면 최적화 (중앙 정렬) */
    .block-container { 
        max-width: 600px !important; 
        padding: 1rem !important; 
        margin: 0 auto !important; 
    }
    
    /* 2. 카메라 화면 테두리 강조 */
    [data-testid="stCameraInput"] video { 
        width: 100% !important;
        border-radius: 15px !important; 
        border: 3px solid #2196F3 !important; 
    }
    
    /* 3. 버튼 크기 키우기 (터치하기 쉽게) */
    div.stButton > button {
        width: 100%;
        height: 60px;
        font-weight: bold;
        font-size: 20px !important;
        border-radius: 12px;
        margin-top: 10px;
    }

    /* 불량 모드일 때 스타일 */
    .defect-box { 
        border: 2px solid red; 
        background-color: #ffe6e6; 
        padding: 10px; 
        border-radius: 10px;
        text-align: center;
        color: red;
        font-weight: bold;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("👷 공정 작업 등록")

# 1. 작업자 선택
worker_list = ["작업자A", "작업자B", "김반장", "이주임", "박대리"]
current_worker = st.selectbox("👤 작업자 선택", worker_list)

st.divider()

# 2. 공정 단계 정의 (순서 체크용)
STEP_LEVEL = {
    "Full Cut": 10, 
    "Half Cut": 20, 
    "전극 완료": 30, 
    "접합: 1. 준비 완료": 41, 
    "접합: 2. 가열 시작": 42, 
    "접합: 3. 공정 완료 (End)": 43,
    "📦 출고 완료": 50 
}

# 3. 불량 신고 모드 스위치
is_defect_mode = st.toggle("🚨 불량 발생 신고", value=False)

if is_defect_mode:
    st.markdown('<div class="defect-box">🚨 불량 등록 모드 ON</div>', unsafe_allow_html=True)
    step = st.selectbox("발견 공정", list(STEP_LEVEL.keys())) 
    defect_type = st.selectbox("불량 유형", ["이물질", "기포/들뜸", "치수 불량", "스크래치", "전극 불량", "원단 불량", "기타"])
    defect_note = st.text_input("상세 내용", placeholder="예: 우측 상단 3cm 찢어짐")
    save_data = f"[{defect_type}] {defect_note}"
    current_level = 999 
else:
    # 정상 작업 모드
    step = st.radio("현재 진행 공정", list(STEP_LEVEL.keys()))
    current_level = STEP_LEVEL.get(step, 0)
    
    save_data = "-"
    
    # 공정별 입력창 (소수점 입력 가능하도록 수정됨)
    if "Cut" in step:
        st.info("⚙️ 장비 세팅값 입력")
        c1, c2, c3 = st.columns(3)
        # [수정] value=0.0, step=0.1, format="%.1f" 추가
        sp = c1.number_input("Speed", value=0.0, step=0.1, format="%.1f")
        mx = c2.number_input("Max", value=0.0, step=0.1, format="%.1f")
        mn = c3.number_input("Min", value=0.0, step=0.1, format="%.1f")
        save_data = f"S:{sp} / M:{mx} / m:{mn}"
        
    elif "End" in step or "공정 완료" in step:
        st.info("🌡️ 최종 온도 입력")
        c1, c2 = st.columns(2)
        # [수정] value=0.0, step=0.1, format="%.1f" 추가
        t1 = c1.number_input("내부(℃)", value=0.0, step=0.1, format="%.1f")
        t2 = c2.number_input("Start(℃)", value=0.0, step=0.1, format="%.1f")
        save_data = f"내부:{t1} / Start:{t2}"
        
    elif "출고" in step:
        st.info("🚚 출고 정보를 확인하세요.")
        note = st.text_input("📝 송장번호/비고 (선택)", placeholder="택배사/송장번호 등")
        if note: save_data = note
    else:
        note = st.text_input("📝 특이사항 (선택)", placeholder="특이사항 없음")
        if note: save_data = note

st.markdown("### 👇 QR 스캔 (카메라)")
st.caption("※ 카메라 권한을 허용해주세요.")

# ==========================================
# 📷 카메라 로직
# ==========================================
img_file = st.camera_input("QR 스캔", label_visibility="collapsed")

if img_file is not None:
    try:
        # 1. 이미지 파일 바이트로 읽기
        bytes_data = img_file.getvalue()
        
        # 2. OpenCV 형식으로 디코딩
        cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
        
        # 3. 흑백 변환
        gray_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)
        
        # 4. QR 코드 디코딩
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(gray_img)

        if data:
            st.success(f"🔍 QR 인식 성공: **{data}**")
            
            # --- DB 조회 및 저장 로직 ---
            # QR에 하이픈이 빠져있으므로, DB 비교시에는 DB 값에서 하이픈을 빼고 비교하거나
            # 저장할 때 하이픈을 뺀 값으로 저장했다면 그대로 비교.
            # 여기서는 DB에 하이픈 없이 저장했다는 가정하에 진행. 
            # 만약 DB에 하이픈이 있다면 .replace() 처리가 필요할 수 있습니다.
            
            # 1. 작업 지시서 상태 조회
            response = supabase.table("work_orders").select("status").eq("lot_no", data).execute()
            
            if not response.data:
                st.error("❌ 등록되지 않은 LOT 번호입니다.")
            else:
                prev_status = response.data[0]['status']
                
                # 불량/보류 체크
                if "불량" in prev_status or "보류" in prev_status:
                    st.error(f"⛔ 경고: 이미 불량 처리된 제품입니다! ({prev_status})")
                    st.stop()

                # 순서 체크 (정상 모드일 때만)
                if not is_defect_mode:
                    prev_level = 0
                    for key, val in STEP_LEVEL.items():
                        if key in prev_status: prev_level = val; break
                    
                    if prev_level >= current_level:
                        st.warning(f"⚠️ 이미 완료된 공정입니다. (현재 상태: {prev_status})")
                        st.stop()
                
                # 저장 버튼
                btn_label = "🚨 불량 등록 실행" if is_defect_mode else "💾 작업 완료 저장"
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
                        
                        # [수정] 출고 완료 시 DB 상태도 '출고'로 변경
                        update_status = "출고" if "출고" in step else step
                        supabase.table("work_orders").update({"status": update_status}).eq("lot_no", data).execute()
                        
                        st.balloons()
                        st.success(f"✅ 작업 저장 완료! ({step})")
                    
                    time.sleep(1.5)
                    st.rerun()

        else:
            st.warning("❌ QR 코드를 찾지 못했습니다. 다시 찍어주세요.")

    except Exception as e:
        st.error("📡 처리 중 오류가 발생했습니다.")
        st.code(f"에러 상세: {e}")

# 화면 하단 여백 확보
st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
