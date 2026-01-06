import streamlit as st
from supabase import create_client

@st.cache_resource
def get_supabase_client():
    try:
        # secrets.toml 파일에서 [supabase] 라는 이름의 서랍을 엽니다.
        # 아래 두 줄이 핵심입니다! 절대 주소를 직접 적지 마세요.
        url = st.secrets["supabase"]["https://fkebyokmlhkbxcbyjijb.supabase.co"]
        key = st.secrets["supabase"]["eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZrZWJ5b2ttbGhrYnhjYnlqaWpiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY4NjY4MTUsImV4cCI6MjA4MjQ0MjgxNX0.SRvsxwIa6oIUoqlAJBl1lDy1sSM27CZiCYEsDzkIyhc"]
        
        return create_client(url, key)
        
    except Exception as e:
        st.error("❌ DB 연결 설정 오류 (connection.py)")
        st.error(f"에러 내용: {e}")
        return None
