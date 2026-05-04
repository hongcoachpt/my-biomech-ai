import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import re

# 1. 페이지 설정
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
            
            with st.expander("📋 논문 텍스트 전체 추출 (안정화된 순정 문단 모드)", expanded=True):
                
                if st.button("🚀 AI 정밀 판독 실행 (텍스트가 엉망일 때 클릭)"):
                    with st.spinner("AI가 원본 형태 그대로 문자를 추출 중입니다..."):
                        try:
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            prompt = "이 논문의 텍스트를 추출해. 문단이 중간에 끊기지 않도록 자연스럽게 이어주고, 굵은 글씨는 마크다운으로 **굵게** 처리해줘."
                            response = model.generate_content([prompt, img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"분석 오류: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    final_text = st.session_state[f"ocr_{page_num}"]
                else:
                    # 🚀 [핵심] 가장 기본적이고 안정적인 파이썬 내장 블록 정렬 기능 사용
                    # sort=True를 통해 알아서 2단 편집을 왼쪽에서 오른쪽으로, 위에서 아래로 정렬합니다.
                    blocks = page.get_text("dict", sort=True)["blocks"]
                    
                    extracted_parts = []
                    for b in blocks:
                        if b.get("type") != 0: continue # 텍스트 블록만 추출
                        
                        para_text = "" # 하나의 문단(블록)을 담을 바구니
                        
                        for line in b.get("lines", []):
                            line_text = ""
                            for span in line.get("spans", []):
                                text = span.get("text", "")
                                # 공백만 있는 스팬은 그대로 유지하여 띄어쓰기 보존
                                if not text.strip(): 
                                    line_text += text
                                    continue
                                
                                # 원본이 굵은 글씨(Bold)인지 확인
                                is_bold = (span.get("flags", 0) & 2**4) or ("Bold" in span.get("font", ""))
                                if is_bold:
                                    # 띄어쓰기 훼손 없이 핵심 단어에만 굵게 표시
                                    m = re.match(r'^(\s*)(.*?)(\s*)$', text)
                                    if m:
                                        leading, core, trailing = m.groups()
                                        if core:
                                            text = f"{leading}**{core}**{trailing}"
                                
                                line_text += text
                                
                            line_text = line_text.strip()
                            if not line_text: continue
                            
                            # 줄과 줄 사이를 연결 (하이픈으로 끝나는 단어는 이어붙임)
                            if para_text.endswith("-"):
                                para_text = para_text[:-1] + line_text
                            else:
                                if para_text:
                                    para_text += " " + line_text
                                else:
                                    para_text = line_text
                                    
                        if para_text.strip():
                            extracted_parts.append(para_text.strip())

                    # 각 문단(블록)들은 엔터 두 번으로 확실히 구분
                    final_text = "\n\n".join(extracted_parts)

                st.markdown(final_text)

    with col_tool:
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

        c1, c2 = st.columns(2)
        
        def safe_gen(prompt):
            try: return model.generate_content(prompt).text
            except Exception as e:
                if "429" in str(e): return "⚠️ 하루 사용량을 초과했습니다."
                return f"❌ 오류: {e}"

        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("번역 중..."):
                    st.info(safe_gen(f"스포츠 생체역학 전문가로서 직역하세요:\n\n{raw_input}"))

        if c2.button("🧠 심층 역학 분석"):
            if raw_input.strip():
                with st.spinner("분석 중..."):
                    st.success(safe_gen(f"생체역학 박사로서 상세 분석하세요:\n\n{raw_input}"))

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
