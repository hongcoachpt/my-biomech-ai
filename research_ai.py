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
            
            with st.expander("📋 논문 텍스트 전체 추출 (단/사이드바 분리 알고리즘 적용)", expanded=True):
                
                # 🚀 [수정] AI에게 논문의 논리적 구조를 파악하도록 프롬프트 고도화
                if st.button("🚀 AI 정밀 판독 실행 (텍스트가 엉망일 때 클릭)"):
                    with st.spinner("AI가 논문의 읽기 순서를 분석하여 추출 중입니다..."):
                        try:
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            prompt = """
                            이 이미지는 학술 논문 페이지입니다. 사이드바(저작권, 날짜, 에디터 정보 등)와 메인 본문(제목, 초록, 서론 등)이 나뉘어 있을 수 있습니다. 
                            사람이 논문을 읽는 논리적인 순서(메인 제목 -> 저자 -> 초록 -> 본문)대로 텍스트를 추출해 주세요. 중요하지 않은 사이드바 정보는 맨 마지막에 빼주세요. 
                            진짜 제목이나 소제목만 마크다운(### **제목**)으로 굵게 처리하고, 초록이나 일반 본문은 내용에 굵은 글씨가 섞여 있어도 절대 제목 처리하지 말고 일반 텍스트로 출력하세요.
                            """
                            response = model.generate_content([prompt, img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"분석 오류: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    final_text = st.session_state[f"ocr_{page_num}"]
                else:
                    # 🚀 [수정] 파이썬 추출 로직: x좌표를 그룹화하여 단(Column)별로 먼저 나누고, 단 안에서 위아래로 정렬
                    blocks = page.get_text("dict")["blocks"]
                    text_blocks = [b for b in blocks if b.get("type") == 0]
                    
                    def smart_column_sort(block):
                        x0, y0, x1, y1 = block["bbox"]
                        # x좌표를 약 150픽셀 단위의 큰 덩어리(단)로 나눕니다.
                        # 이렇게 하면 같은 단에 있는 글자들끼리 먼저 묶이고, 그 안에서 y좌표(높이) 순으로 정렬됩니다.
                        col_group = int(x0 // 150)
                        return (col_group, y0)

                    text_blocks.sort(key=smart_column_sort)
                    
                    extracted_parts = []
                    for b in text_blocks:
                        paragraph_text = ""
                        max_size = 0
                        bold_char_count = 0
                        
                        for line in b.get("lines", []):
                            for span in line.get("spans", []):
                                text = span.get("text", "")
                                size = span.get("size", 0)
                                flags = span.get("flags", 0)
                                
                                paragraph_text += text
                                max_size = max(max_size, size)
                                
                                if flags & 2**4: # 굵은 글씨 감지
                                    bold_char_count += len(text)
                            paragraph_text += " " 
                            
                        paragraph_text = re.sub(r'(\w)-\s+(\w)', r'\1\2', paragraph_text).strip()
                        if not paragraph_text: continue
                        
                        # 🚀 [수정] 초록이 굵어지는 현상 방지 (방어막 강화)
                        is_heading = False
                        text_length = len(paragraph_text)
                        
                        # 길이가 150자를 넘어가면 아무리 굵은 글씨가 많고 폰트가 커도 무조건 본문으로 간주
                        if text_length < 150:
                            if max_size >= 13.0:
                                is_heading = True
                            elif text_length > 0 and (bold_char_count / text_length) > 0.4:
                                is_heading = True
                            elif paragraph_text.isupper() and text_length < 100:
                                is_heading = True
                                
                        if is_heading:
                            extracted_parts.append(f"\n### **{paragraph_text}**\n")
                        else:
                            extracted_parts.append(paragraph_text)
                            
                    final_text = "\n\n".join(extracted_parts)

                st.markdown(final_text)

    with col_tool:
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

        c1, c2 = st.columns(2)
        
        def safe_gen(prompt):
            try: return model.generate_content(prompt).text
            except Exception as e:
                if "429" in str(e): return "⚠️ 하루 사용량을 초과했습니다. 잠시 후 다시 시도하세요."
                return f"❌ 오류: {e}"

        if c1.button("🌐 전문 직역 실행"):
            if raw_input.strip():
                with st.spinner("번역 중..."):
                    st.info(safe_gen(f"스포츠 생체역학 전문가로서 한국어로 자연스럽게 직역하세요:\n\n{raw_input}"))

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
