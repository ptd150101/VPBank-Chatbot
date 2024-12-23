import streamlit as st
import requests
import os
import json

# API Configuration
API_URL = "http://localhost:8500"
def split_content_and_references(content):
    # Split by newlines
    lines = content.split('\n')
    main_content = []
    references = []
    
    # Flag to track if we're in references section
    in_references = False
    
    for line in lines:
        if line.strip().lower() == 'xem thêm:' or line.strip().lower() == 'tham khảo thêm:':
            in_references = True
            continue
        
        if 'http' in line:
            references.append(line.strip())
        elif not in_references:
            main_content.append(line)
            
    return '\n'.join(main_content).strip(), references
# Page Configuration 
st.set_page_config(
    page_title="VPBank Assistant",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state for chat history if not exists
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Xin chào! Tôi là trợ lý của VPBank. Tôi có thể giúp gì cho bạn?"}
    ]

# Display chat title
st.title("💬 VPBank Assistant")

# Display chat history with proper styling for each message
for message in st.session_state.messages:
    with st.container():
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            # Split content and references for assistant messages
            main_content, references = split_content_and_references(message["content"])
            
            # Create container for response
            response_container = st.container()
            
            with response_container:
                # Create two columns with borders
                col1, col2 = st.columns([2, 1])
                
                # Main content in left column
                with col1:
                    with st.chat_message("assistant"):
                        st.write(main_content)
                
                # References in right column with border
                with col2:
                    with st.container():
                        st.markdown("""
                        <div style="border-left: 2px solid #ccc; padding-left: 20px; height: 100%;">
                            <h5 style="color: #666;">📚 Tài liệu tham khảo</h5>
                        </div>
                        """, unsafe_allow_html=True)
                        if references:
                            for link in references:
                                st.markdown(f"- {link}")
                        else:
                            st.markdown("*Không có link tham khảo*")

st.markdown("""
<style>
.chat-message {
    padding: 1.5rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
    line-height: 1.6;
}

.chat-message.assistant {
    border-left: 6px solid #2e7af7;
    height: 100%;
}

.chat-message.user {
    border-left: 6px solid #dedede;
}

.references {
    background: #fafafa;
    padding: 1rem;
    border-radius: 0.5rem;
    border-left: 6px solid #28a745;
    height: 100%;
}

.references h4 {
    color: #28a745;
    margin-bottom: 1rem;
}

.references ul {
    list-style-type: none;
    padding-left: 0;
}

.references li {
    margin-bottom: 0.5rem;
}

.references a {
    color: #1a6d32;
    text-decoration: none;
}
</style>
""", unsafe_allow_html=True)



# Modified message display code
if prompt := st.chat_input("Nhập câu hỏi của bạn..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.write(prompt)

    try:
        response = requests.post(
            f"{API_URL}/chat",
            json={
                "content": prompt,
                "histories": st.session_state.messages,
                "summary": "",
            },
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            assistant_response = response.json()
            if assistant_response.get("data", {}).get("content"):
                content = assistant_response["data"]["content"]
                
                # Split content and references
                main_content, references = split_content_and_references(content)
                
                # Create container for response
                response_container = st.container()
                
                with response_container:
                    # Create two columns with borders
                    col1, col2 = st.columns([2, 1])
                    
                    # Main content in left column
                    with col1:
                        with st.chat_message("assistant"):
                            st.write(main_content)
                    
                    # References in right column with border
                    with col2:
                        with st.container():
                            st.markdown("""
                            <div style="border-left: 2px solid #ccc; padding-left: 20px; height: 100%;">
                                <h5 style="color: #666;">📚 Tài liệu tham khảo</h5>
                            </div>
                            """, unsafe_allow_html=True)
                            if references:
                                for link in references:
                                    st.markdown(f"- {link}")
                            else:
                                st.markdown("*Không có link tham khảo*")

                # Save cleaned message to session state
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": content
                })

    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
# Add instructions in sidebar
with st.sidebar:
    st.title("Hướng dẫn sử dụng")
    st.markdown("""
    1. Nhập câu hỏi về VPBank vào ô chat
    2. Nhấn Enter để gửi câu hỏi
    3. Đợi phản hồi từ trợ lý
    
    **Lưu ý:** Trợ lý có thể trả lời các câu hỏi về:
    - Khách hàng cá nhân
    """)