import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Biomechanics Pro Lab", page_icon="🔬")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# 2. 보안 시스템
def check_password():
    if st.session_state.authenticated:
        return
    st.title("🔒 Lab Access Control")
    correct_pwd = st.secrets.get("LAB_PASSWORD", "1234")
    pwd = st.text_input("비밀번호 입력", type="password")
    if pwd == correct_pwd:
        st.session_state.authenticated = True
        st.rerun()
    elif pwd:
        st.error("❌ 틀렸습니다.")
    st.stop()

check_password()

# 3. 모델 초기화 (에러 방어형)
@st.cache_resource
def init_gemini(model_choice):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        # 🚀 모델 이름에서 '-latest'를 빼고 가장 표준적인 이름 사용
        m_name = "gemini-1.5-flash" if "Flash" in model_choice else "gemini-1.5-pro"
        return genai.GenerativeModel(model_name=m_name)
    except Exception as e:
        st.error(f"모델 초기화 실패: {e}")
        return None

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 엔진 설정")
    engine = st.radio("모델 선택", ["⚡ Gemini 1.5 Flash (속도)", "🧠 Gemini 1.5 Pro (정밀)"])
    model = init_gemini(engine)
    if model:
        st.success(f"✅ {engine} 준비됨")

# 4. 메인 UI
st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("논문 PDF 업로드", type="pdf")

if uploaded_file:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        with col_view:
            st.subheader("📄 논문 원문")
            page_num = st.select_slider("페이지", options=range(1, len(doc) + 1)) - 1
            page = doc.load_page(page_num)
            
            # 고해상도 출력
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            st.markdown("---")
            with st.expander("📋 텍스트 추출", expanded=True):
                if st.button("🚀 AI 정밀 추출"):
                    with st.spinner("분석 중..."):
                        try:
                            # 이미지를 통한 OCR 수행
                            img = Image.open(io.BytesIO(page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5)).tobytes()))
                            res = model.generate_content(["이 페이지의 텍스트를 논문 양식에 맞춰 추출해줘. 굵은 글씨는 **굵게** 표시해.", img])
                            st.session_state[f"ocr_{page_num}"] = res.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"추출 실패: {e}")
                
                if f"ocr_{page_num}" in st.session_state:
                    st.markdown(st.session_state[f"ocr_{page_num}"])
                else:
                    st.text(page.get_text())

    with col_tool:
        st.subheader("🧪 역학 분석기")
        raw_text = st.text_area("분석할 텍스트", height=200)
        
        if st.button("🧠 심층 분석 실행"):
            if raw_text and model:
                with st.spinner("데이터 해석 중..."):
                    try:
                        ans = model.generate_content(f"생체역학 박사로서 아래 내용을 상세히 분석하세요:\n\n{raw_text}")
                        st.success(ans.text)
                    except Exception as e:
                        st.error(f"분석 실패: {e}")

        st.markdown("---")
        st.subheader("💬 데이터 Q&A")
        chat_input = st.text_input("질문을 입력하세요")
        if st.button("전송"):
            if chat_input and model:
                st.session_state.chat_history.append({"role": "user", "content": chat_input})
                res = model.generate_content(chat_input)
                st.session_state.chat_history.append({"role": "assistant", "content": res.text})
        
        for m in st.session_state.chat_history:
            with st.chat_message(m["role"]): st.write(m["content"])
