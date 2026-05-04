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
            
            with st.expander("📋 논문 텍스트 전체 추출 (정밀 문장 결합 모드)", expanded=True):
                
                if st.button("🚀 AI 정밀 판독 실행 (텍스트가 엉망일 때 클릭)"):
                    with st.spinner("AI가 논문의 읽기 순서를 분석 중입니다..."):
                        try:
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                            img_ocr = Image.open(io.BytesIO(pix_ocr.tobytes()))
                            prompt = "이 학술 논문 페이지를 읽고, 왼쪽 단부터 오른쪽 단 순서로 텍스트를 추출해. 문단이 끊기지 않게 자연스럽게 이어주고, 진짜 제목만 굵게(### **제목**) 처리해줘."
                            response = model.generate_content([prompt, img_ocr])
                            st.session_state[f"ocr_{page_num}"] = response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"분석 오류: {e}")

                if f"ocr_{page_num}" in st.session_state:
                    final_text = st.session_state[f"ocr_{page_num}"]
                else:
                    # 🚀 [핵심] 블록 안에서 '진짜 문단'을 찾아내어 문장들을 하나로 결합하는 로직
                    blocks = page.get_text("dict")["blocks"]
                    text_blocks = [b for b in blocks if b.get("type") == 0]
                    
                    def smart_column_sort(block):
                        x0, y0, x1, y1 = block["bbox"]
                        col_group = int(x0 // 120) 
                        return (col_group, y0)

                    text_blocks.sort(key=smart_column_sort)
                    
                    extracted_parts = []
                    for b in text_blocks:
                        block_x0, block_y0, block_x1, block_y1 = b["bbox"]
                        
                        current_para_text = ""
                        max_size = 0
                        bold_char_count = 0
                        prev_line_bbox = None
                        
                        for line in b.get("lines", []):
                            l_x0, l_y0, l_x1, l_y1 = line["bbox"]
                            line_height = l_y1 - l_y0
                            
                            is_new_para = False
                            
                            if prev_line_bbox is not None:
                                p_x0, p_y0, p_x1, p_y1 = prev_line_bbox
                                
                                # 1. 머리-머리 간격이 줄 높이의 1.4배 이상 벌어지면 새 문단
                                if (l_y0 - p_y0) > (line_height * 1.4):
                                    is_new_para = True
                                # 2. 현재 줄이 블록 왼쪽 끝보다 15픽셀 이상 들여쓰기 되었으면 새 문단
                                elif (l_x0 - block_x0) > 15:
                                    is_new_para = True
                                # 3. 윗줄이 블록 오른쪽 끝에 도달하지 못하고 일찍 끝났으면(마침표 등) 새 문단
                                elif (block_x1 - p_x1) > 40:
                                    is_new_para = True

                            # 새 문단이 시작될 때, 지금까지 모은 텍스트를 저장하고 초기화
                            if is_new_para and current_para_text.strip():
                                current_para_text = re.sub(r'([a-zA-Z])-\s+([a-zA-Z])', r'\1\2', current_para_text).strip()
                                
                                is_heading = False
                                text_len = len(current_para_text)
                                if text_len < 150:
                                    if max_size >= 12.5: is_heading = True
                                    elif text_len > 0 and (bold_char_count / text_len) > 0.4: is_heading = True
                                    elif current_para_text.isupper() and text_len < 100: is_heading = True
                                
                                if is_heading: extracted_parts.append(f"### **{current_para_text}**")
                                else: extracted_parts.append(current_para_text)
                                
                                current_para_text = ""
                                max_size = 0
                                bold_char_count = 0
                                
                            # 글자들을 current_para_text라는 하나의 바구니(문단)에 스페이스바 한 칸으로 계속 이어붙임
                            line_text = ""
                            for span in line.get("spans", []):
                                text = span.get("text", "")
                                size = span.get("size", 0)
                                flags = span.get("flags", 0)
                                
                                line_text += text
                                max_size = max(max_size, size)
                                if flags & 2**4: bold_char_count += len(text)
                                
                            if current_para_text and not current_para_text.endswith(" "):
                                current_para_text += " "
                            current_para_text += line_text.strip()
                            
                            prev_line_bbox = (l_x0, l_y0, l_x1, l_y1)
                            
                        # 블록의 마지막에 남은 텍스트 처리
                        if current_para_text.strip():
                            current_para_text = re.sub(r'([a-zA-Z])-\s+([a-zA-Z])', r'\1\2', current_para_text).strip()
                            is_heading = False
                            text_len = len(current_para_text)
                            if text_len < 150:
                                if max_size >= 12.5: is_heading = True
                                elif text_len > 0 and (bold_char_count / text_len) > 0.4: is_heading = True
                                elif current_para_text.isupper() and text_len < 100: is_heading = True
                            
                            if is_heading: extracted_parts.append(f"### **{current_para_text}**")
                            else: extracted_parts.append(current_para_text)

                    # 문단과 문단 사이만 두 줄 바꿈(\n\n)으로 깔끔하게 결합
                    final_text = "\n\n".join(extracted_parts)

                st.markdown(final_text)

    with col_tool:
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 여기에 붙여넣으세요", height=200)

        c1, c2 = st.columns(2)
        
        def safe_gen(prompt):
            try: return model.generate_content(prompt).text
            except Exception as e:
                if "429" in str(e): return "⚠️ 하루 사용량을 초과했습니다. 잠시 후 시도하세요."
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
