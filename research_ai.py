import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64

# 1. 페이지 및 보안 설정 (기존 유지)
st.set_page_config(layout="wide", page_title="Biomechanics Interactive Lab", page_icon="🔬")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if not st.session_state.authenticated:
        st.title("🔒 Biomechanics Lab 보안")
        pwd = st.text_input("연구소 비밀번호를 입력하세요", type="password")
        if pwd == st.secrets.get("LAB_PASSWORD", "1234"):
            st.session_state.authenticated = True
            st.rerun()
        elif pwd:
            st.error("비밀번호가 틀렸습니다.")
        st.stop()

check_password()

# API 인증
api_key = st.secrets.get("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')
else:
    st.error("Secrets에서 GOOGLE_API_KEY 설정을 확인하세요.")
    st.stop()

if "chat_history" not in st.session_state: st.session_state.chat_history = []

st.title("🔬 인터랙티브 생체역학 연구실")

# 3. PDF 업로드 및 [직접 드래그] 뷰어
uploaded_file = st.file_uploader("논문(PDF) 업로드", type="pdf")

if uploaded_file:
    # 아이패드에서 드래그 공간을 확보하기 위해 넓게 배치
    col_pdf, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()
    
    with col_pdf:
        st.subheader("📄 논문 원문 (직접 드래그 구역)")
        
        # [핵심] 아이패드 네이티브 드래그를 유도하는 <object> 방식
        base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
        
        # 아이패드 사파리가 PDF 엔진을 직접 가동하게 만드는 HTML5 코드입니다.
        pdf_display = f"""
            <object data="data:application/pdf;base64,{base64_pdf}#toolbar=0&navpanes=0&scrollbar=0" 
                    type="application/pdf" 
                    width="100%" 
                    height="1000px" 
                    style="border: 2px solid #eee; border-radius: 10px;">
                <p>이 브라우저는 PDF 직접 드래그를 지원하지 않습니다. 
                <a href="data:application/pdf;base64,{base64_pdf}" target="_blank">여기를 눌러 새 탭에서 열기</a>를 이용하세요.</p>
            </object>
        """
        st.markdown(pdf_display, unsafe_allow_html=True)
        st.caption("💡 팁: 드래그가 안 되면 주소창 옆 'AA' 버튼을 눌러 '데스크탑 웹사이트 요청'을 켜주세요.")

    with col_tool:
        # --- 분석 도구 ---
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("왼쪽 PDF에서 드래그한 내용을 붙여넣으세요", height=200, placeholder="여기에 Paste!")
        
        c1, c2 = st.columns(2)
        if c1.button("🌐 전문 직역"):
            if raw_input:
                with st.spinner("직역 중..."):
                    res = model.generate_content(f"생체역학 전문 번역: {raw_input}").text
                    st.info(res)
        
        if c2.button("🧠 역학 분석"):
            if raw_input:
                with st.spinner("기전 분석 중..."):
                    res = model.generate_content(f"Kinetics/Kinematics 관점 분석: {raw_input}").text
                    st.success(res)

        st.markdown("---")
        st.subheader("💬 데이터 및 이미지 분석")
        data_img = st.file_uploader("📸 그래프/사진 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.insert(0, {"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    req = [f"생체역학 전문가로서 답변: {chat_query}"]
                    if data_img: req.append(Image.open(data_img))
                    resp = model.generate_content(req).text
                    st.session_state.chat_history.insert(0, {"role": "assistant", "content": resp})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
