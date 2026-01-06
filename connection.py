# 파일명: connection.py
import streamlit as st
from supabase import create_client

# 1. 캐싱을 사용해 한 번 연결하면 계속 재사용 (속도 향상)
@st.cache_resource
def get_supabase_client():
    try:
        # Streamlit 'secrets' 금고에서 키를 꺼내옴
        url = st.secrets["supabase"]["https://fkebyokmlhkbxcbyjijb.supabase.co"]
        key = st.secrets["supabase"]["eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZrZWJ5b2ttbGhrYnhjYnlqaWpiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY4NjY4MTUsImV4cCI6MjA4MjQ0MjgxNX0.SRvsxwIa6oIUoqlAJBl1lDy1sSM27CZiCYEsDzkIyhc"]
        return create_client(url, key)
    except Exception as e:
        st.error("❌ Secrets 설정 오류: connection.py가 올바른지 확인하세요.")
        st.stop()
