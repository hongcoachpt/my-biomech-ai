import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64

# 1. 페이지 레이아웃 및 보안 설정 (기존 유지)
st.set_page_config(layout="wide", page_title="Biomechanics Pro Lab", page_icon="🔬")

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

api_key = st.secrets.get("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')
else:
    st.error("API Key 설정이 필요합니다.")
    st.stop()

if "chat_history" not in st.session_state: st.session_state.chat_history = []

st.title("🔬 스마트 생체역학 연구실")

# 3. PDF 업로드 및 [인-앱 드래그 전용] 뷰어
uploaded_file = st.file_uploader("논문(PDF) 업로드", type="pdf")

if uploaded_file:
    # 아이패드 화면을 넓게 쓰기 위해 5:5 분할
    col_view, col_tool = st.columns([1, 1])
    file_bytes = uploaded_file.getvalue()
    
    with col_view:
        st.subheader("📄 논문 드래그 구역")
        
        # PDF 로드
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        total_pages = len(doc)
        page_num = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
        page = doc.load_page(page_num)
        
        # [핵심] 아이패드에서 드래그가 가장 잘 되는 '텍스트 레이어' 모드
        # 원본 PDF를 이미지로 띄우고 그 아래/옆에 '진짜 긁히는 글자'를 배치합니다.
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True, caption=f"{page_num + 1} / {total_pages} Page")
        
        # 이 부분이 아이패드에서 '앱 상에서 바로 드래그'하는 핵심 버튼입니다.
        st.info("💡 아래 텍스트 박스에서 원하는 문단을 드래그하여 복사하세요.")
        
        # 텍스트 가독성 및 정렬 알고리즘
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: (b[1], b[0]))
        clean_text = ""
        for b in blocks:
            text = b[4].replace("\n", " ").strip()
            if text: clean_text += text + "\n\n"
        
        # 아이패드 사용자를 위해 높이를 크게 잡은 드래그 전용 창
        # 이 창은 앱 내부에 박혀 있어 바로 보면서 긁기 좋습니다.
        st.text_area("↓↓↓ 여기서 바로 드래그하세요 ↓↓↓", value=clean_text, height=500, key="drag_area")

    with col_tool:
        # --- 분석 도구 (버튼 분리형) ---
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("위에서 드래그한 내용을 여기에 붙여넣으세요", height=200)
        
        c1, c2 = st.columns(2)
        if c1.button("🌐 전문 직역"):
            if raw_input:
                with st.spinner("번역 중..."):
                    res = model.generate_content(f"생체역학 전문 번역: {raw_input}").text
                    st.info(res)
        if c2.button("🧠 역학 분석"):
            if raw_input:
                with st.spinner("분석 중..."):
                    res = model.generate_content(f"Kinetics/Kinematics 기전 분석: {raw_input}").text
                    st.success(res)

        st.markdown("---")
        st.subheader("💬 데이터 및 이미지 질의응답")
        
        # 아이패드 사진첩/캡처 대응 업로더
        data_img = st.file_uploader("📸 그래프 캡처본 업로드 (사진첩)", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 질문 및 데이터 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.insert(0, {"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    req = [f"생체역학 전문가로서 답변: {chat_query}"]
                    if data_img: req.append(Image.open(data_img))
                    resp = model.generate_content(req).text
                    st.session_state.chat_history.insert(0, {"role": "assistant", "content": resp})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
