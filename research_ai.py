import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
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

# 3. 모델 연결 시스템 (쿼터 에러 방어)
@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return None, "API Key 없음"
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
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
            
            # 아이패드 네이티브 뷰어 호출
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
            
            # [핵심] 파트 분리 및 문단 띄어쓰기 추출 섹션
            with st.expander("📋 논문 텍스트 전체 추출 (파트 및 문단 최적화)", expanded=True):
                
                if st.button("🚀 AI 정밀 판독 실행 (텍스트 구조가 복잡할 때 클릭)"):
                    with st.spinner("AI가 논문 파트를 나누는 중입니다..."):
                        try:
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            prompt = "이 논문 페이지를 읽어줘. 제목이나 소제목(굵은 글씨)을 기점으로 파트를 명확히 나누고, 본문은 문단끼리 띄어쓰기를 잘 지켜서 추출해줘."
                            response = model.generate_content([prompt, img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"분석 오류: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    final_text = st.session_state[f"ocr_{page_num}"]
                else:
                    # 🚀 [수정] 굵은 글씨 기반 파트 분리 및 문단 띄어쓰기 로직
                    # sort=True를 통해 좌상단부터 순서대로 읽어옵니다.
                    blocks = page.get_text("dict", sort=True)["blocks"]
                    
                    extracted_parts = []
                    for b in blocks:
                        if b.get("type") != 0: continue # 텍스트 블록만
                        
                        block_text = ""
                        has_bold_heading = False
                        
                        for line in b.get("lines", []):
                            line_text = ""
                            for span in line.get("spans", []):
                                text = span.get("text", "").strip()
                                if not text: continue
                                
                                # 폰트 속성에서 굵은 글씨(Bold) 감지
                                # 문단이 짧으면서 굵은 글씨면 제목(파트 구분선)으로 간주
                                if (span.get("flags", 0) & 2**4) and len(text) < 100:
                                    has_bold_heading = True
                                    line_text += f"### **{text}**"
                                else:
                                    line_text += text + " "
                            
                            block_text += line_text.strip() + " "
                            
                        # 단어 쪼개짐(하이픈) 복구
                        block_text = re.sub(r"([a-zA-Z])-\s+([a-zA-Z])", r"\1\2", block_text).strip()
                        
                        if not block_text: continue

                        # 굵은 글씨 제목이 있으면 새로운 파트로 시작, 없으면 문단 띄어쓰기 적용
                        if has_bold_heading:
                            extracted_parts.append(block_text)
                        else:
                            extracted_parts.append(block_text)

                    # 각 덩어리(블록) 사이를 두 줄 바꿈으로 연결하여 문단 구분 명확화
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
