import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import streamlit.components.v1 as components
import re

# 1. 페이지 레이아웃 및 보안 설정
st.set_page_config(layout="wide", page_title="Biomechanics Pro Lab", page_icon="🔬")

# --- 연구실 보안 잠금 (박사님 개인 비번) ---
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

# --- [복구] 모델 연결 및 에러 진단 로직 ---
api_key = st.secrets.get("GOOGLE_API_KEY")
if api_key:
    try:
        genai.configure(api_key=api_key)
        # 모델 목록을 가져와서 정확한 전체 경로를 확인합니다.
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 1.5 Pro 모델을 우선 찾되, 없으면 목록의 첫 번째 모델 사용
        target_model_name = next((m for m in available_models if "gemini-1.5-pro" in m), available_models[0])
        model = genai.GenerativeModel(target_model_name)
        st.sidebar.success(f"✅ 엔진 연결됨: {target_model_name}")
    except Exception as e:
        st.sidebar.error(f"❌ 연결 오류: {str(e)}")
        st.stop()
else:
    st.error("API Key가 설정되지 않았습니다. Streamlit Secrets를 확인하세요.")
    st.stop()

if "chat_history" not in st.session_state: st.session_state.chat_history = []

st.title("🔬 스마트 생체역학 통합 연구실")

# 3. PDF 업로드 및 멀티 뷰어
uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_pdf, col_tool = st.columns([1.1, 1])
    file_bytes = uploaded_file.getvalue()
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    with col_pdf:
        st.subheader("📄 논문 뷰어")
        
        # [해결] 아이패드 네이티브 뷰어 (새 창 열기 버튼 유지)
        base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
        pdf_url = f"data:application/pdf;base64,{base64_pdf}"
        
        st.markdown(f'''
            <a href="{pdf_url}" target="_blank" style="text-decoration: none;">
                <div style="background-color: #4CAF50; color: white; padding: 12px; text-align: center; border-radius: 8px; font-weight: bold; margin-bottom: 10px;">
                    🚀 [iPad] 원문 크게 보기 및 직접 드래그 (새 창)
                </div>
            </a>
        ''', unsafe_allow_html=True)

        v_mode = st.radio("보기 모드", ["원본 이미지 모드", "인터랙티브 모드"], horizontal=True)
        page_idx = st.select_slider("페이지 이동", options=range(1, len(doc) + 1)) - 1
        page = doc.load_page(page_idx)

        if v_mode == "원본 이미지 모드":
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
            st.image(Image.open(io.BytesIO(pix.tobytes())), use_container_width=True)
        else:
            st.markdown(f'<iframe src="{pdf_url}" width="100%" height="800"></iframe>', unsafe_allow_html=True)

        # [해결] 텍스트 추출 가독성 극대화 (제목 굵게 + 띄어쓰기 정제)
        st.markdown("---")
        with st.expander("📋 논문 텍스트 정밀 추출 (가독성 최적화)", expanded=True):
            try:
                blocks = page.get_text("dict", flags=11)["blocks"]
                structured_text = ""
                
                for b in blocks:
                    if "lines" in b:
                        block_text = ""
                        max_font_size = 0
                        for l in b["lines"]:
                            for s in l["spans"]:
                                max_font_size = max(max_font_size, s["size"])
                                block_text += s["text"] + " "
                        
                        # 줄바꿈으로 깨진 단어 합치기 및 불필요한 공백 제거
                        clean_block = re.sub(r'(\w)-\s+(\w)', r'\1\2', block_text).strip()
                        
                        # 폰트 크기가 크면 소제목으로 처리
                        if max_font_size > 11.5:
                            structured_text += f"\n### **{clean_block}**\n\n"
                        else:
                            structured_text += f"{clean_block}\n\n"
                
                if not structured_text.strip():
                    structured_text = page.get_text("text") # 백업 추출
                
                st.markdown(structured_text)
                st.text_area("드래그 복사용 영역", value=structured_text, height=300)
            except Exception as e:
                st.error(f"텍스트 추출 중 오류 발생: {e}")

    with col_tool:
        # --- 🧪 정밀 분석 도구 (오류 방지 강화) ---
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("분석할 문단을 아래에 붙여넣으세요", height=200)
        
        c1, c2 = st.columns(2)
        if c1.button("🌐 전문 용어 직역"):
            if raw_input:
                with st.spinner("전문 번역 중..."):
                    try:
                        res = model.generate_content(f"스포츠 생체역학 전문가로서 다음 내용을 한국어로 자연스럽게 번역하세요. 전문 용어는 최대한 유지하세요:\n\n{raw_input}")
                        st.info(res.text)
                    except Exception as e:
                        st.error(f"분석 오류가 발생했습니다: {str(e)}")
        
        if c2.button("🧠 심층 역학 분석"):
            if raw_input:
                with st.spinner("역학적 기전 분석 중..."):
                    try:
                        res = model.generate_content(f"생체역학 박사로서 다음 연구 내용의 Kinetics 및 Kinematics적 의미를 분석하세요:\n\n{raw_input}")
                        st.success(res.text)
                    except Exception as e:
                        st.error(f"분석 오류가 발생했습니다: {str(e)}")

        st.markdown("---")
        
        # [해결] 이미지 붙여넣기 기능 (Ctrl+V) 복구
        st.subheader("📸 데이터 및 이미지 질의응답")
        st.caption("그래프 캡처 후 아래 박스 클릭 후 **Ctrl+V** 하세요.")
        
        paste_html = """
        <div id="p-area" style="border:2px dashed #4CAF50; padding:15px; text-align:center; cursor:pointer; border-radius:10px; background-color:#f9f9f9;">
            여기 클릭 후 <b>Ctrl+V</b>로 그래프 붙여넣기
        </div>
        <div id="p-view" style="margin-top:10px; display:none; text-align:center;">
            <img id="p-img" style="max-width:100%; border-radius:5px; border:1px solid #ccc;"/>
        </div>
        <script>
            document.addEventListener('paste', function(e) {
                var items = e.clipboardData.items;
                for (var i = 0; i < items.length; i++) {
                    if (items[i].type.indexOf('image') !== -1) {
                        var blob = items[i].getAsFile();
                        var reader = new FileReader();
                        reader.onload = function(event) {
                            document.getElementById('p-img').src = event.target.result;
                            document.getElementById('p-view').style.display = 'block';
                        };
                        reader.readAsDataURL(blob);
                    }
                }
            });
        </script>
        """
        components.html(paste_html, height=220)

        data_img = st.file_uploader("📸 또는 사진첩에서 선택", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=100)
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.insert(0, {"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    try:
                        content = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                        if data_img: content.append(Image.open(data_img))
                        response = model.generate_content(content)
                        st.session_state.chat_history.insert(0, {"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"전송 에러: {e}")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
