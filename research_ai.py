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

# 2. 보안 시스템 (박사님 전용)
def check_password():
    if st.session_state.authenticated: return
    st.title("🔒 Lab Access Control")
    pwd = st.text_input("연구소 비밀번호", type="password")
    if pwd == st.secrets.get("LAB_PASSWORD", "1234"):
        st.session_state.authenticated = True
        st.rerun()
    st.stop()

check_password()

# 3. [박사님 요청] 딱 중요한 모델 3개만 엄선
MODEL_MAP = {
    "⚡ Gemini 1.5 Flash (가성비/OCR 최강)": "gemini-1.5-flash",
    "🧠 Gemini 1.5 Pro (심층 분석/고성능)": "gemini-1.5-pro",
    "🚀 Gemini 2.0 Flash (최신/초고속)": "gemini-2.0-flash-exp"
}

@st.cache_resource
def load_engine(model_id):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_id)
    except Exception as e:
        st.error(f"연결 실패: {e}")
        return None

# 사이드바: 복잡한 리스트 대신 정예 멤버만 선택
with st.sidebar:
    st.header("🔬 엔진 선택")
    choice = st.selectbox("사용할 모델을 고르세요", list(MODEL_MAP.keys()))
    selected_id = MODEL_MAP[choice]
    model = load_engine(selected_id)
    
    if model:
        st.success(f"✅ {selected_id} 가동 중")
    
    st.markdown("---")
    st.caption("• Flash: 텍스트 추출, 번역용 (하루 1500회)\n• Pro: 데이터 심층 해석용 (하루 50회)")

# 4. 메인 분석 UI
st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("분석할 PDF 업로드", type="pdf")

if uploaded_file and model:
    col_view, col_tool = st.columns([1.2, 1])
    with col_view:
        st.subheader("📄 논문 원문")
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page_num = st.select_slider("페이지", options=range(1, len(doc) + 1)) - 1
        page = doc.load_page(page_num)
        
        # 선명한 이미지 뷰어
        pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
        st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

        if st.button("🚀 정밀 텍스트 추출"):
            with st.spinner("AI 판독 중..."):
                img = Image.open(io.BytesIO(page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5)).tobytes()))
                res = model.generate_content(["이 페이지의 텍스트를 논문 양식 그대로 추출해. 굵은 글씨는 **굵게** 표시해줘.", img])
                st.session_state[f"ocr_{page_num}"] = res.text
                st.rerun()

        if f"ocr_{page_num}" in st.session_state:
            st.markdown("---")
            st.markdown(st.session_state[f"ocr_{page_num}"])

    with col_tool:
        st.subheader("🧪 전문가 분석 도구")
        raw_input = st.text_area("분석할 문단을 붙여넣으세요", height=200)
        
        btn_col1, btn_col2 = st.columns(2)
        if btn_col1.button("🌐 전문 직역"):
            if raw_input:
                with st.spinner("번역 중..."):
                    st.info(model.generate_content(f"생체역학 전문가로서 자연스럽게 직역하세요:\n\n{raw_input}").text)

        if btn_col2.button("🧠 심층 역학 분석"):
            if raw_input:
                with st.spinner("심층 분석 중..."):
                    st.success(model.generate_content(f"스포츠 생체역학 박사로서 아래 내용을 상세히 분석하세요:\n\n{raw_input}").text)

        st.markdown("---")
        st.subheader("💬 데이터 Q&A")
        data_img = st.file_uploader("📸 그래프/표 사진 업로드", type=["png", "jpg", "jpeg"])
        chat_q = st.text_input("AI에게 직접 질문하세요")
        if st.button("🚀 질문 전송"):
            if chat_q or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_q})
                contents = [chat_q]
                if data_img: contents.append(Image.open(data_img))
                ans = model.generate_content(contents)
                st.session_state.chat_history.append({"role": "assistant", "content": ans.text})

        for m in st.session_state.chat_history:
            with st.chat_message(m["role"]): st.markdown(m["content"])
