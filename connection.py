import streamlit as st
from supabase import create_client

@st.cache_resource
def get_supabase_client():
    try:
        # 👇 [핵심] 주소를 직접 쓰지 말고, 이렇게 ["supabase"]["url"] 이라고 적어야 합니다!
        url = st.secrets["supabase"]["https://fkebyokmlhkbxcbyjijb.supabase.co"]
        key = st.secrets["supabase"]["eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZrZWJ5b2ttbGhrYnhjYnlqaWpiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY4NjY4MTUsImV4cCI6MjA4MjQ0MjgxNX0.SRvsxwIa6oIUoqlAJBl1lDy1sSM27CZiCYEsDzkIyhc"]
        
        return create_client(url, key)
        
    except Exception as e:
        st.error(f"❌ DB 연결 실패: {e}")
        return None
