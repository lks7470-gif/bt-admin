import streamlit as st

st.set_page_config(page_title="(주)베스트룸 생산관리", page_icon="🏭", layout="wide")

# 1. 세션 상태 초기화
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_role' not in st.session_state: st.session_state.user_role = None

# 2. 이미 로그인 된 상태라면? -> 페이지 자동 이동
if st.session_state.logged_in:
    if st.session_state.user_role == "Admin":
        st.switch_page("pages/1_Admin.py")
    elif st.session_state.user_role == "Worker":
        st.switch_page("pages/2_Worker.py")
    elif st.session_state.user_role == "Monitor":
        st.switch_page("pages/3_Monitor.py")

# 3. 로그인 화면 (로그인 안 된 경우에만 실행됨)
st.title("🏭 생산관리 시스템 접속")

c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    # 🚨 주의: 이 form 코드가 파일에 딱 한 번만 있어야 합니다!
    with st.form("login_form"):
        st.info("로그인을 진행해주세요.")
        role = st.selectbox("직책 선택", ["관리자 (Admin)", "작업자 (Worker)", "모니터링 (Monitor)"])
        pwd = st.text_input("비밀번호", type="password")
        
        submitted = st.form_submit_button("로그인", use_container_width=True)

        if submitted:
            if role == "관리자 (Admin)" and pwd == "1234":
                st.session_state.logged_in = True
                st.session_state.user_role = "Admin"
                st.switch_page("pages/1_Admin.py") 
                
            elif role == "작업자 (Worker)" and pwd == "0000":
                st.session_state.logged_in = True
                st.session_state.user_role = "Worker"
                st.switch_page("pages/2_Worker.py")
                
            elif role == "모니터링 (Monitor)" and pwd == "1111":
                st.session_state.logged_in = True
                st.session_state.user_role = "Monitor"
                st.switch_page("pages/3_Monitor.py")
                
            else:
                st.error("비밀번호가 틀렸습니다.")
