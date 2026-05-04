import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import re

# 1. 페이지 레이아웃 및 보안 설정
st.set_page_config(layout="wide", page_title="Biomechanics Master Lab", page_icon="🔬")

# --- 보안 잠금 시스템 ---
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

# --- [해결] 404 에러 방지용 동적 모델 연결 시스템 ---
@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        return None, None
    try:
        genai.configure(api_key=api_key)
        # 현재 API 키로 사용 가능한 모든 모델 목록을 가져옵니다.
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 우선순위에 따라 모델을 선택합니다.
        priority = ["models/gemini-1.5-pro", "models/gemini-1.5-flash", "models/gemini-pro"]
        chosen_model = next((m for m in priority if m in available_models), available_models[0])
        
        return genai.GenerativeModel(chosen_model), chosen_model
    except Exception as e:
        return None, str(e)

model, model_name = init_gemini()

if model:
    st.sidebar.success(f"✅ 엔진 가동 중: {model_name}")
else:
    st.sidebar.error(f"❌ AI 연결 실패: {model_name}")
    st.stop()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("🔬 스마트 생체역학 통합 연구실")

# 3. PDF 업로드 및 멀티 뷰어
uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total_pages = len(doc)

        with col_view:
            st.subheader("📄 논문 원문")
            page_num = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
            page = doc.load_page(page_num)

            # 고해상도 이미지 렌더링
            pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
            page_img = Image.open(io.BytesIO(pix.tobytes()))
            st.image(page_img, use_container_width=True)

            st.markdown("---")
            with st.expander("📝 현재 페이지 텍스트 추출 및 AI 판독", expanded=True):
                
                # 🚀 [해결] AI 정밀 판독 (OCR) - 404 방지 로직 적용
                if st.button("🚀 AI 정밀 판독 실행 (텍스트 누락 시 클릭)"):
                    with st.spinner("AI가 이미지를 직접 분석 중입니다..."):
                        try:
                            ocr_prompt = "이 이미지의 논문 내용을 텍스트로 추출해줘. 제목/소제목은 굵게 표시하고 문단을 잘 나눠줘."
                            # 동적으로 선택된 모델을 사용하여 분석
                            response = model.generate_content([ocr_prompt, page_img])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI 분석 오류: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    result_text = st.session_state[f"ocr_{page_num}"]
                else:
                    # 기본 추출 방식 (백업)
                    result_text = page.get_text("text", sort=True)

                st.markdown(result_text)
                st.text_area("✂️ 드래그 복사용", value=result_text, height=350, key=f"txt_{page_num}")

    with col_tool:
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

        c1, c2 = st.columns(2)
        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("전문 번역 중..."):
                    res = model.generate_content(f"생체역학 전문가로서 번역해줘:\n\n{raw_input}")
                    st.info(res.text)

        if c2.button("🧠 심층 역학 분석"):
            if raw_input.strip():
                with st.spinner("역학적 기전 분석 중..."):
                    res = model.generate_content(f"생체역학 박사로서 분석해줘:\n\n{raw_input}")
                    st.success(res.text)

        st.markdown("---")
        st.subheader("💬 데이터 통합 질의응답")
        data_img = st.file_uploader("📸 그래프/사진 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 질문 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    contents = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                    if data_img: contents.append(Image.open(data_img))
                    response = model.generate_content(contents)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
