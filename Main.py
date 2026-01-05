# 파일명: Main.py (프로젝트 최상위)
import streamlit as st

st.set_page_config(page_title="(주)베스트룸 생산관리", page_icon="🏭", layout="wide")

# 1. 세션 초기화
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_role' not in st.session_state: st.session_state.user_role = None

# 2. 이미 로그인 되어 있다면? -> 바로 해당 페이지로 쏘기
if st.session_state.logged_in:
    if st.session_state.user_role == "Admin":
        st.switch_page("pages/1_Admin.py")
    elif st.session_state.user_role == "Worker":
        st.switch_page("pages/2_Worker.py")
    elif st.session_state.user_role == "Monitor":
        st.switch_page("pages/3_Monitor.py")

# 3. 로그인 화면 (로그인 안 된 경우)
st.title("🏭 생산관리 시스템 접속")

c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    with st.form("login_form"):
        st.info("로그인을 진행해주세요.")
        role = st.selectbox("직책 선택", ["관리자 (Admin)", "작업자 (Worker)", "모니터링 (Monitor)"])
        pwd = st.text_input("비밀번호", type="password")
        
        submitted = st.form_submit_button("로그인", use_container_width=True)

        if submitted:
            # ---------------------------------------------------------
            # 👇 여기가 핵심입니다! (switch_page 사용)
            # ---------------------------------------------------------
            if role == "관리자 (Admin)" and pwd == "1234":
                st.session_state.logged_in = True
                st.session_state.user_role = "Admin"
                st.switch_page("pages/1_Admin.py") # 관리자 페이지로 이동
                
            elif role == "작업자 (Worker)" and pwd == "0000":
                st.session_state.logged_in = True
                st.session_state.user_role = "Worker"
                st.switch_page("pages/2_Worker.py") # 작업자 페이지로 이동
                
            elif role == "모니터링 (Monitor)" and pwd == "1111":
                st.session_state.logged_in = True
                st.session_state.user_role = "Monitor"
                st.switch_page("pages/3_Monitor.py") # 모니터 페이지로 이동
                
            else:
                st.error("비밀번호가 틀렸습니다.")# 파일명: Main.py (프로젝트 최상위)
import streamlit as st

st.set_page_config(page_title="(주)베스트룸 생산관리", page_icon="🏭", layout="wide")

# 1. 세션 초기화
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_role' not in st.session_state: st.session_state.user_role = None

# 2. 이미 로그인 되어 있다면? -> 바로 해당 페이지로 쏘기
if st.session_state.logged_in:
    if st.session_state.user_role == "Admin":
        st.switch_page("pages/1_Admin.py")
    elif st.session_state.user_role == "Worker":
        st.switch_page("pages/2_Worker.py")
    elif st.session_state.user_role == "Monitor":
        st.switch_page("pages/3_Monitor.py")

# 3. 로그인 화면 (로그인 안 된 경우)
st.title("🏭 생산관리 시스템 접속")

c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    with st.form("login_form"):
        st.info("로그인을 진행해주세요.")
        role = st.selectbox("직책 선택", ["관리자 (Admin)", "작업자 (Worker)", "모니터링 (Monitor)"])
        pwd = st.text_input("비밀번호", type="password")
        
        submitted = st.form_submit_button("로그인", use_container_width=True)

        if submitted:
            # ---------------------------------------------------------
            # 👇 여기가 핵심입니다! (switch_page 사용)
            # ---------------------------------------------------------
            if role == "관리자 (Admin)" and pwd == "1234":
                st.session_state.logged_in = True
                st.session_state.user_role = "Admin"
                st.switch_page("pages/1_Admin.py") # 관리자 페이지로 이동
                
            elif role == "작업자 (Worker)" and pwd == "0000":
                st.session_state.logged_in = True
                st.session_state.user_role = "Worker"
                st.switch_page("pages/2_Worker.py") # 작업자 페이지로 이동
                
            elif role == "모니터링 (Monitor)" and pwd == "1111":
                st.session_state.logged_in = True
                st.session_state.user_role = "Monitor"
                st.switch_page("pages/3_Monitor.py") # 모니터 페이지로 이동
                
            else:
                st.error("비밀번호가 틀렸습니다.")
