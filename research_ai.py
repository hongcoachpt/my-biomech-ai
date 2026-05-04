import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import re

# 1. 페이지 레이아웃 및 세션 초기화
st.set_page_config(layout="wide", page_title="Biomechanics Pro Lab", page_icon="🔬")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# 2. 보안 잠금 시스템
def check_password():
    if st.session_state.authenticated:
        return
    st.title("🔒 Biomechanics Lab 보안")
    correct_pwd = st.secrets.get("LAB_PASSWORD", "1234")
    pwd = st.text_input("연구소 비밀번호를 입력하세요", type="password")
    if pwd:
        if pwd == correct_pwd:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ 비밀번호가 다릅니다.")
    st.stop()

check_password()

# 3. 하이브리드 모델 연결 시스템 (최신 주소 규격 적용)
@st.cache_resource
def get_gemini_model(model_name):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None
    try:
        genai.configure(api_key=api_key)
        # 🚀 안정적인 API 버전 호출을 위해 모델 생성 방식 최적화
        return genai.GenerativeModel(model_name=model_name)
    except Exception: return None

# 사이드바 엔진 설정
with st.sidebar:
    st.header("🔬 Lab 엔진 설정")
    model_choice = st.radio(
        "사용할 AI 엔진을 선택하세요",
        [
            "⚡ Gemini 1.5 Flash (가성비 / 하루 1500회)",
            "🧠 Gemini 1.5 Pro (고성능 / 하루 50회)"
        ]
    )
    
    # 🚀 [404 에러 해결 핵심] 가장 확실한 최신 안정 버전 명칭으로 교체
    if "Flash" in model_choice:
        chosen_model_name = "gemini-1.5-flash-latest"
    else:
        chosen_model_name = "gemini-1.5-pro-latest"
    
    model = get_gemini_model(chosen_model_name)
    
    st.markdown("---")
    if model:
        st.success(f"✅ 엔진 대기 중: {chosen_model_name}")
    else:
        st.error(f"❌ API 연결 실패")
    
    st.caption("Flash는 번역/추출용, Pro는 심층 분석용으로 추천합니다.")

# 4. 메인 UI
st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        total_pages = len(doc)

        with col_view:
            st.subheader("📄 논문 원문 분석기")
            
            st.download_button(
                label="🚀 논문 새 창에서 열기 (iPad용)",
                data=file_bytes,
                file_name=uploaded_file.name,
                mime="application/pdf"
            )
            
            page_num = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
            page = doc.load_page(page_num)

            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            st.markdown("---")
            
            with st.expander("📋 논문 텍스트 전체 추출", expanded=True):
                if st.button("🚀 AI 정밀 판독 실행"):
                    with st.spinner("AI가 텍스트를 읽어오는 중입니다..."):
                        try:
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            prompt = "이 학술 논문의 텍스트를 원본 양식대로 추출해줘. 굵은 글씨는 **굵게** 표시하고 문단은 유지해줘."
                            response = model.generate_content([prompt, img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"에러 발생: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    st.markdown(st.session_state[f"ocr_{page_num}"])
                else:
                    # 기본 로직
                    text = page.get_text("text", sort=True)
                    st.markdown(text)

    with col_tool:
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 붙여넣으세요", height=200)

        c1, c2 = st.columns(2)
        
        def safe_gen(prompt):
            try: return model.generate_content(prompt).text
            except Exception as e: return f"❌ 오류: {e}"

        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("번역 중..."):
                    st.info(safe_gen(f"생체역학 전문가로서 자연스럽게 한국어로 직역하세요:\n\n{raw_input}"))

        if c2.button("🧠 심층 역학 분석"):
            if raw_input.strip():
                with st.spinner("심층 분석 중..."):
                    st.success(safe_gen(f"생체역학 박사로서 아래 내용을 상세히 분석하세요:\n\n{raw_input}"))

        st.markdown("---")
        st.subheader("💬 데이터 및 이미지 Q&A")
        data_img = st.file_uploader("📸 그래프/표 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("답변 생성 중..."):
                    contents = [chat_query]
                    if data_img: contents.append(Image.open(data_img))
                    ans = safe_gen(contents)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
