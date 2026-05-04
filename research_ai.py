import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Biomechanics Analyst", page_icon="🔬")

# 2. 자동 로그인 설정 (Secrets 사용)
# 나중에 Streamlit 설정에서 키를 입력하면 여기서 자동으로 가져옵니다.
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction="당신은 스포츠 생체역학 전문가입니다. 한국 체육학회지 논문 스타일로 전문적인 분석을 제공하세요."
    )
else:
    st.error("API Key가 설정되지 않았습니다. Streamlit Cloud의 Secrets 설정을 확인하세요.")
    st.stop()

st.title("🔬 스포츠 생체역학 전문 분석기")
st.caption("고대 박사 과정 연구를 위한 맞춤형 AI 파트너")

# 3. 화면 구성
uploaded_pdf = st.file_uploader("분석할 논문 PDF 업로드", type="pdf")

if uploaded_pdf:
    col1, col2 = st.columns([1.2, 1])
    
    with col1:
        st.subheader("📄 PDF 원문")
        doc = fitz.open(stream=uploaded_pdf.getvalue(), filetype="pdf")
        page_num = st.select_slider("페이지", options=range(1, len(doc) + 1)) - 1
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

    with col2:
        st.subheader("💡 전문 분석창 (Liner Mode)")
        user_text = st.text_area("텍스트를 붙여넣으세요", height=250)
        if st.button("분석 시작") and user_text:
            with st.spinner("분석 중..."):
                response = model.generate_content(f"다음 내용을 생체역학적으로 해석해줘:\n\n{user_text}")
                st.markdown(response.text)

# 4. 사이드바 이미지 분석
with st.sidebar:
    st.header("📊 그래프 분석")
    graph_img = st.file_uploader("그래프 캡처 업로드", type=["png", "jpg"])
    if st.button("그래프 분석") and graph_img:
        img = Image.open(graph_img)
        res = model.generate_content(["이 그래프의 생체역학적 의미를 분석해줘.", img])
        st.write(res.text)
