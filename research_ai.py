import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64

# 1. 페이지 레이아웃 및 보안 설정
st.set_page_config(layout="wide", page_title="Biomechanics Master Lab", page_icon="🔬")

# --- 연구실 보안 잠금 (박사님 개인 비번) ---
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

# API 인증 (Secrets 우선)
api_key = st.secrets.get("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    # 가장 똑똑한 모델 자동 선택
    model = genai.GenerativeModel('gemini-1.5-pro')
else:
    st.error("API Key 설정이 필요합니다.")
    st.stop()

if "chat_history" not in st.session_state: st.session_state.chat_history = []

st.title("🔬 스포츠 생체역학 지능형 분석 연구실")

# 3. PDF 업로드 및 멀티 뷰어 섹션
uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_pdf, col_tool = st.columns([1.1, 1])
    file_bytes = uploaded_file.getvalue()
    
    with col_pdf:
        st.subheader("📄 논문 원문 뷰어")
        
        # [해결] 아이패드에서 가장 확실한 방법: 새 탭에서 열기 버튼
        base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
        pdf_url = f"data:application/pdf;base64,{base64_pdf}"
        
        # 큼지막한 버튼으로 제작
        st.markdown(f'''
            <a href="{pdf_url}" target="_blank" style="text-decoration: none;">
                <div style="background-color: #4CAF50; color: white; padding: 10px; text-align: center; border-radius: 5px; font-weight: bold; margin-bottom: 10px;">
                    🚀 PDF 새 창에서 크게 열기 (드래그/복사용)
                </div>
            </a>
        ''', unsafe_allow_html=True)

        v_mode = st.radio("뷰어 모드 선택", ["인터랙티브 (드래그 시도)", "안전 모드 (이미지)"], horizontal=True)
        
        if v_mode == "인터랙티브 (드래그 시도)":
            pdf_display = f'<iframe src="{pdf_url}" width="100%" height="800" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_num = st.select_slider("페이지 이동", options=range(1, len(doc) + 1)) - 1
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

        st.download_button(label="💾 원문 파일 기기에 저장", data=file_bytes, file_name=uploaded_file.name, mime="application/pdf")
        
        # 가독성 최적화 텍스트 복사창 (아이패드 드래그 보험용)
        st.markdown("---")
        with st.expander("📋 페이지 텍스트 추출 (띄어쓰기 정제됨)", expanded=True):
            if 'doc' not in locals(): doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(page_num if 'page_num' in locals() else 0)
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (b[1], b[0]))
            clean_text = ""
            for b in blocks:
                text = b[4].replace("\n", " ").strip()
                if text: clean_text += text + "\n\n"
            st.text_area("텍스트 내용", value=clean_text, height=300)

    with col_tool:
        # --- 🧪 텍스트 정밀 분석 (버튼 분리형) ---
        st.subheader("🧪 문단 정밀 분석 (토큰 절약형)")
        raw_input = st.text_area("분석할 문단을 아래에 붙여넣으세요", height=200)
        
        btn_col1, btn_col2 = st.columns(2)
        if btn_col1.button("🌐 전문 직역 실행"):
            if raw_input:
                with st.spinner("직역 중..."):
                    tr = model.generate_content(f"생체역학 전문 용어를 살려 한국어로 직역하세요:\n\n{raw_input}").text
                    st.info(f"**[직역]**\n\n{tr}")
        
        if btn_col2.button("🧠 심층 역학 분석 실행"):
            if raw_input:
                with st.spinner("역학 분석 중..."):
                    an = model.generate_content(f"생체역학 박사급 연구원으로서 분석하세요:\n\n{raw_input}").text
                    st.success(f"**[분석]**\n\n{an}")

        st.markdown("---")
        
        # --- 📸 데이터/그래프 이미지 분석 ---
        st.subheader("💬 데이터 및 이미지 질의응답")
        data_img = st.file_uploader("📸 그래프 캡처본 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, caption="업로드된 데이터", width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        
        if st.button("🚀 질문 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.insert(0, {"role": "user", "content": chat_query})
                with st.spinner("AI 연구원이 분석 중..."):
                    req = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                    if data_img: req.append(Image.open(data_img))
                    response = model.generate_content(req)
                    st.session_state.chat_history.insert(0, {"role": "assistant", "content": response.text})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
