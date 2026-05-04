import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import streamlit.components.v1 as components

# 1. 페이지 레이아웃 및 보안 설정
st.set_page_config(layout="wide", page_title="Biomechanics Pro Lab", page_icon="🔬")

# --- 보안 잠금 시스템 ---
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

# --- [해결] 404 에러 방지 모델 연결 로직 ---
api_key = st.secrets.get("GOOGLE_API_KEY")
if api_key:
    try:
        genai.configure(api_key=api_key)
        # 사용 가능한 모델 목록에서 최적의 모델을 자동으로 찾아 매칭합니다.
        model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = "models/gemini-1.5-pro" if "models/gemini-1.5-pro" in model_list else model_list[0]
        model = genai.GenerativeModel(target_model)
        st.sidebar.success(f"✅ 엔진 가동 중: {target_model}")
    except Exception as e:
        st.sidebar.error(f"❌ 연결 오류: {e}")
        st.stop()
else:
    st.error("API Key 설정이 필요합니다.")
    st.stop()

if "chat_history" not in st.session_state: st.session_state.chat_history = []

st.title("🔬 스마트 생체역학 통합 연구실")

# 3. PDF 업로드 및 [고정밀 포맷팅] 뷰어 섹션
uploaded_file = st.file_uploader("분석할 논문(PDF) 업로드", type="pdf")

if uploaded_file:
    col_pdf, col_tool = st.columns([1.1, 1])
    file_bytes = uploaded_file.getvalue()
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    with col_pdf:
        st.subheader("📄 논문 원문 및 정밀 추출")
        
        # [해결] 아이패드 직접 드래그를 위한 최적화 임베딩
        base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
        pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700" type="application/pdf">'
        st.markdown(pdf_display, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # [해결] 제목/소제목 자동 감지 및 포맷팅 텍스트 추출기
        with st.expander("📋 논문 텍스트 정밀 복사 (제목 굵게/줄바꿈 최적화)", expanded=True):
            page_idx = st.number_input("페이지 선택", min_value=1, max_value=len(doc), value=1) - 1
            page = doc.load_page(page_idx)
            
            # 텍스트 구조 분석 (폰트 크기 기반 제목 감지)
            blocks = page.get_text("dict")["blocks"]
            formatted_text = ""
            
            for b in blocks:
                if "lines" in b:
                    block_text = ""
                    is_header = False
                    for l in b["lines"]:
                        for s in l["spans"]:
                            # 폰트 크기가 12 이상이거나 굵은 글씨면 제목으로 간주
                            if s["size"] > 12 or (s["flags"] & 2**4):
                                is_header = True
                            block_text += s["text"] + " "
                    
                    block_text = block_text.strip()
                    if is_header:
                        formatted_text += f"### **{block_text}**\n\n"
                    else:
                        formatted_text += f"{block_text}\n\n"
            
            st.markdown(formatted_text)
            st.text_area("드래그용 텍스트 영역", value=formatted_text, height=300)

    with col_tool:
        # --- 🧪 정밀 분석 도구 ---
        st.subheader("🧪 문단 정밀 분석")
        raw_input = st.text_area("드래그한 내용을 여기에 붙여넣으세요", height=150)
        
        b1, b2 = st.columns(2)
        if b1.button("🌐 전문 용어 직역"):
            if raw_input:
                with st.spinner("전문 번역 중..."):
                    res = model.generate_content(f"생체역학 전문 용어를 적용해 정확히 번역하세요:\n\n{raw_input}").text
                    st.info(res)
        
        if b2.button("🧠 심층 역학 분석"):
            if raw_input:
                with st.spinner("역학적 기전 분석 중..."):
                    res = model.generate_content(f"스포츠 생체역학 박사로서 기전을 심층 분석하세요:\n\n{raw_input}").text
                    st.success(res)

        st.markdown("---")
        
        # [해결] 다시 살려낸 이미지 붙여넣기(Ctrl+V) 기능
        st.subheader("📸 데이터 및 그래프 분석")
        st.caption("그래프 캡처 후 아래 영역을 클릭하고 **Ctrl+V** 하세요.")
        
        paste_html = """
        <div id="p-area" style="border:2px dashed #4CAF50; padding:15px; text-align:center; cursor:pointer; border-radius:10px; background-color:#f9f9f9;">
            여기를 클릭 후 <b>Ctrl+V</b>로 붙여넣기 (미리보기)
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
        components.html(paste_html, height=200)

        # 아이패드 업로드용
        data_img = st.file_uploader("📸 또는 파일 선택", type=["png", "jpg", "jpeg"])
        if data_img: st.image(data_img, width=300)

        chat_query = st.text_area("질문을 입력하세요", height=80)
        if st.button("🚀 분석 전송"):
            if chat_query or data_img:
                st.session_state.chat_history.insert(0, {"role": "user", "content": chat_query})
                with st.spinner("AI 분석 중..."):
                    try:
                        req = [f"생체역학 전문가로서 답변하세요: {chat_query}"]
                        if data_img: req.append(Image.open(data_img))
                        response = model.generate_content(req).text
                        st.session_state.chat_history.insert(0, {"role": "assistant", "content": response})
                    except Exception as e:
                        st.error(f"오류: {e}")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
