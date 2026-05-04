import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64

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

# 3. 모델 연결 시스템
@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "API Key 없음"
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]
        chosen_model = next((m for m in priority if m in available_models), available_models[0])
        return genai.GenerativeModel(chosen_model), chosen_model
    except Exception as e: return None, str(e)

model, model_name = init_gemini()

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
                label="🚀 [iPad 필수] 논문 새 창에서 열기 (직접 드래그용)",
                data=file_bytes,
                file_name=uploaded_file.name,
                mime="application/pdf"
            )
            
            page_num = st.select_slider("페이지 이동", options=range(1, total_pages + 1)) - 1
            page = doc.load_page(page_num)

            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)

            st.markdown("---")
            
            with st.expander("📋 논문 텍스트 전체 추출 (원본 형식 100% 유지)", expanded=True):
                
                # 🚀 [수정 1] AI에게도 "원본 그대로 유지하라"고 깐깐하게 명령
                if st.button("🚀 AI 정밀 판독 실행 (텍스트가 엉망일 때 클릭)"):
                    with st.spinner("AI가 원본 형태 그대로 문자를 추출 중입니다..."):
                        try:
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            prompt = """
                            이 논문 페이지의 텍스트를 눈에 보이는 그대로 추출해.
                            1. 굵은 글씨는 마크다운을 써서 똑같이 **굵게**만 표시해. 절대 거대한 제목(###)으로 바꾸지 마.
                            2. 원본에서 작은 글씨라도 들여쓰기가 되어 있거나 엔터(줄바꿈)가 쳐진 곳은 똑같이 줄을 바꿔줘.
                            3. 단순히 단 너비가 좁아서 넘어간 줄은 자연스럽게 이어줘.
                            """
                            response = model.generate_content([prompt, img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"분석 오류: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    final_text = st.session_state[f"ocr_{page_num}"]
                else:
                    # 🚀 [수정 2] 파이썬 추출 로직: 굵은 글씨 보존 + 들여쓰기 감지 시 줄바꿈
                    blocks = page.get_text("dict", sort=True)["blocks"]
                    
                    extracted_parts = []
                    for b in blocks:
                        if b.get("type") != 0: continue
                        
                        block_x0 = b["bbox"][0]
                        paragraph_text = ""
                        
                        for line in b.get("lines", []):
                            line_x0 = line["bbox"][0]
                            
                            # 들여쓰기 감지 (해당 줄이 시작점보다 10픽셀 이상 우측에서 시작하면 엔터 처리)
                            if (line_x0 - block_x0) > 10:
                                if paragraph_text and not paragraph_text.endswith("\n"):
                                    paragraph_text += "\n"
                                    
                            line_text = ""
                            for span in line.get("spans", []):
                                text = span.get("text", "")
                                if not text.strip(): continue
                                
                                # 원본이 굵은 글씨(Bold)면 앞뒤로 ** 를 붙여서 굵게만 만듦
                                if span.get("flags", 0) & 2**4 or "Bold" in span.get("font", ""):
                                    stripped_text = text.strip()
                                    text = text.replace(stripped_text, f"**{stripped_text}**")
                                    
                                line_text += text
                                
                            # 하이픈 처리 (단어가 끊겼을 때만 이어주고, 나머지는 띄어쓰기)
                            if line_text.strip().endswith("-"):
                                paragraph_text += line_text.strip()[:-1]
                            else:
                                paragraph_text += line_text.strip() + " "
                                
                        extracted_parts.append(paragraph_text.strip())

                    # 각 문단 덩어리(블록)들은 두 줄 바꿈으로 깔끔하게 구분
                    final_text = "\n\n".join(extracted_parts)

                st.markdown(final_text)

    with col_tool:
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

        c1, c2 = st.columns(2)
        
        def safe_gen(prompt):
            try: return model.generate_content(prompt).text
            except Exception as e:
                if "429" in str(e): return "⚠️ 할당량 초과입니다. 잠시 후 시도하세요."
                return f"❌ 오류: {e}"

        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("번역 중..."):
                    st.info(safe_gen(f"스포츠 생체역학 전문가로서 한국어로 자연스럽게 직역하세요:\n\n{raw_input}"))

        if c2.button("🧠 심층 역학 분석"):
            if raw_input.strip():
                with st.spinner("분석 중..."):
                    st.success(safe_gen(f"스포츠 생체역학 박사로서 상세 분석하세요:\n\n{raw_input}"))

        st.markdown("---")
        st.subheader("💬 데이터 및 이미지 질의응답")
        data_img = st.file_uploader("📸 사진 업로드", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.append({"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    contents = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                    if data_img: contents.append(Image.open(data_img))
                    ans = safe_gen(contents)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans})

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
