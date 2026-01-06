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
        # 🚨 에러가 나면 상세 내용을 화면에 보여줌
        st.error("❌ 연결 실패! 아래 에러 내용을 확인하세요.")
        st.error(f"에러 메시지: {e}")
        
        # 힌트: 현재 서버가 알고 있는 비밀번호 서랍 목록을 보여줌
        st.info(f"현재 인식된 Secrets 목록: {list(st.secrets.keys())}")
        
        return None
