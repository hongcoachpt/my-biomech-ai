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

# 2. 보안 잠금
def check_password():
    if st.session_state.authenticated: return
    st.title("🔒 Lab Access Control")
    pwd = st.text_input("연구소 비밀번호", type="password")
    if pwd == st.secrets.get("LAB_PASSWORD", "1234"):
        st.session_state.authenticated = True
        st.rerun()
    st.stop()

check_password()

# 3. [핵심] 가용한 모든 모델 목록 가져오기
@st.cache_resource
def list_available_models():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return []
    genai.configure(api_key=api_key)
    try:
        # 사용 가능한 모델 중 콘텐츠 생성이 가능한 것만 필터링
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        return models
    except Exception as e:
        st.error(f"모델 목록 로드 실패: {e}")
        return []

# 사이드바에서 박사님이 직접 모델 선택
with st.sidebar:
    st.header("🔬 Lab 엔진 자유 선택")
    model_list = list_available_models()
    
    if model_list:
        # 박사님이 리스트에서 직접 모델을 고릅니다.
        selected_model_name = st.selectbox(
            "사용할 모델 엔진을 선택하세요",
            model_list,
            index=model_list.index("models/gemini-1.5-flash") if "models/gemini-1.5-flash" in model_list else 0
        )
        model = genai.GenerativeModel(selected_model_name)
        st.success(f"✅ 엔진 대기 중: {selected_model_name}")
    else:
        st.error("❌ 가용한 모델이 없습니다. API Key를 확인하세요.")
        model = None

    st.markdown("---")
    st.caption("Tip: 2.5 버전이나 Pro 버전에서 429 에러가 나면 1.5-flash로 바꿔보세요.")

# 4. 메인 UI
st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file and model:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        with col_view:
            st.subheader("📄 논문 원문")
            page_num = st.select_slider("페이지", options=range(1, len(doc) + 1)) - 1
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            if st.button("🚀 선택한 모델로 텍스트 추출"):
                with st.spinner(f"{selected_model_name} 분석 중..."):
                    img = Image.open(io.BytesIO(page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5)).tobytes()))
                    try:
                        res = model.generate_content(["이 페이지의 텍스트를 추출하고 굵은 글씨는 **굵게** 표시해.", img])
                        st.session_state[f"ocr_{page_num}"] = res.text
                        st.rerun()
                    except Exception as e:
                        st.error(f"분석 실패: {e}")
            
            if f"ocr_{page_num}" in st.session_state:
                st.markdown("---")
                st.markdown(st.session_state[f"ocr_{page_num}"])

    with col_tool:
        st.subheader("🧪 생체역학 전문 분석")
        raw_text = st.text_area("분석할 문단을 붙여넣으세요", height=200)
        
        c1, c2 = st.columns(2)
        if c1.button("🌐 전문 직역"):
            if raw_text:
                with st.spinner("번역 중..."):
                    st.info(model.generate_content(f"스포츠 생체역학 전문가로서 한국어로 직역하세요:\n\n{raw_text}").text)
        
        if c2.button("🧠 심층 역학 분석"):
            if raw_text:
                with st.spinner("심층 분석 중..."):
                    st.success(model.generate_content(f"스포츠 생체역학 박사로서 상세 분석하세요:\n\n{raw_text}").text)

        st.markdown("---")
        st.subheader("💬 데이터 및 이미지 Q&A")
        data_img = st.file_uploader("📸 그래프/표 사진 업로드", type=["png", "jpg", "jpeg"])
        chat_query = st.text_area("질문을 입력하세요")
        if st.button("🚀 질문 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                contents = [chat_query]
                if data_img: contents.append(Image.open(data_img))
                ans = model.generate_content(contents)
                st.session_state.chat_history.append({"role": "assistant", "content": ans.text})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
