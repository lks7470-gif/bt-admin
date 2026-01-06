import streamlit as st
from supabase import create_client

@st.cache_resource
def get_supabase_client():
    try:
        # 👇 여기에 주소를 직접 적지 마세요! 그냥 "url"이라고 적으면 알아서 가져옵니다.
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        
        return create_client(url, key)
        
    except Exception as e:
        st.error(f"❌ DB 연결 실패: {e}")
        return None
