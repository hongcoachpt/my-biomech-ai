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
    if st.session_state.authenticated: return
    st.title("🔒 Lab Access Control")
    pwd = st.text_input("연구소 비밀번호", type="password")
    if pwd == st.secrets.get("LAB_PASSWORD", "1234"):
        st.session_state.authenticated = True
        st.rerun()
    st.stop()

check_password()

# 3. [박사님 요청] 최신 및 정예 모델 라인업
MODEL_MAP = {
    "🚀 Gemini 2.0 Flash (최신 실험판/초고속)": "gemini-2.0-flash-exp",
    "🧠 Gemini 1.5 Pro (심층 역학 분석/정밀)": "gemini-1.5-pro",
    "⚡ Gemini 1.5 Flash (대량 추출/가성비)": "gemini-1.5-flash"
}

@st.cache_resource
def load_engine(model_id):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None
    try:
        genai.configure(api_key=api_key)
        # 404 에러 방지를 위해 표준 모델명으로 호출
        return genai.GenerativeModel(model_name=model_id)
    except Exception as e:
        st.error(f"연결 실패: {e}")
        return None

# 사이드바 엔진 설정
with st.sidebar:
    st.header("🔬 연구실 엔진 설정")
    choice = st.selectbox("사용할 AI 모델을 선택하세요", list(MODEL_MAP.keys()))
    selected_id = MODEL_MAP[choice]
    model = load_engine(selected_id)
    
    if model:
        st.success(f"✅ {selected_id} 가동 중")
    
    st.markdown("---")
    st.caption("※ 2.0 실험판은 성능은 좋으나 하루 할당량이 적을 수 있습니다. 막히면 1.5 Flash로 전환하세요.")

# 4. 메인 UI
st.title("🔬 스마트 생체역학 통합 연구실")

uploaded_file = st.file_uploader("분석할 논문 PDF 업로드", type="pdf")

if uploaded_file and model:
    col_view, col_tool = st.columns([1.2, 1])
    file_bytes = uploaded_file.getvalue()

    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        with col_view:
            st.subheader("📄 논문 원문 분석기")
            page_num = st.select_slider("페이지 이동", options=range(1, len(doc) + 1)) - 1
            page = doc.load_page(page_num)

            # 고해상도 렌더링
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            st.markdown("---")
            
            # [핵심] 논문 형식 보존 텍스트 추출
            with st.expander("📋 논문 텍스트 추출 (형식 보존)", expanded=True):
                
                # 기본 추출 (자동)
                st.markdown("**[기본 레이아웃 추출]**")
                # blocks 기능을 사용하여 단락 구조를 최대한 유지
                blocks = page.get_text("blocks")
                auto_text = ""
                for b in blocks:
                    auto_text += b[4] + "\n"
                st.text_area("텍스트 데이터", value=auto_text, height=200)

                # AI 정밀 추출 (논문 형식 복원)
                if st.button("🚀 AI 논문 형식 정밀 복원 실행"):
                    with st.spinner("AI가 학술지 양식으로 텍스트를 재구성 중입니다..."):
                        try:
                            img = Image.open(io.BytesIO(page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5)).tobytes()))
                            # AI에게 논문 형식을 강하게 지시
                            prompt = """당신은 전문 학술지 편집자입니다. 이 페이지의 텍스트를 추출하되 다음 형식을 엄수하세요:
                            1. 섹션 제목(Abstract, Intro 등)은 반드시 굵게(**제목**) 표시.
                            2. 논문의 다단 편집(Column) 무시하고 읽기 편한 순서로 문단 재구성.
                            3. 수치나 기호는 변형 없이 그대로 유지.
                            4. 전체적인 느낌이 실제 논문 원고처럼 깔끔해야 함."""
                            res = model.generate_content([prompt, img])
                            st.session_state[f"ocr_{page_num}"] = res.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"분석 실패: {e}. 할당량 초과일 수 있으니 모델을 Flash로 바꿔보세요.")

                if f"ocr_{page_num}" in st.session_state:
                    st.markdown("**[AI 정밀 복원본]**")
                    st.markdown(st.session_state[f"ocr_{page_num}"])

    with col_tool:
        st.subheader("🧪 생체역학 정밀 분석")
        analysis_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

        c1, c2 = st.columns(2)
        if c1.button("🌐 전문 직역"):
            if analysis_input:
                with st.spinner("번역 중..."):
                    res = model.generate_content(f"스포츠 생체역학 전문가로서 한국어로 자연스럽게 직역하세요:\n\n{analysis_input}")
                    st.info(res.text)

        if c2.button("🧠 심층 역학 분석"):
            if analysis_input:
                with st.spinner("역학적 해석 중..."):
                    res = model.generate_content(f"스포츠 생체역학 박사로서 아래 내용을 상세히 분석하고 훈련 현장 적용점을 제시하세요:\n\n{analysis_input}")
                    st.success(res.text)

        st.markdown("---")
        st.subheader("💬 데이터 Q&A")
        data_img = st.file_uploader("📸 그래프/표 사진 업로드", type=["png", "jpg", "jpeg"])
        chat_query = st.text_input("질문을 입력하세요")
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("답변 생성 중..."):
                    contents = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                    if data_img: contents.append(Image.open(data_img))
                    ans = model.generate_content(contents)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans.text})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
