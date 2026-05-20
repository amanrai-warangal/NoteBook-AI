import streamlit as st
import requests

# FastAPI backend base URL
BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Smart Notes App", page_icon="📝", layout="wide")

# ==========================================
# 🎨 CUSTOM STYLING (THE X-FACTOR)
# ==========================================
st.markdown("""
    <style>
    /* Styling the Main App Header */
    .main-title {
        font-size: 2.8rem !important;
        font-weight: 800 !important;
        background: linear-gradient(45deg, #FF4B4B, #FF8F8F);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0rem;
    }
    
    /* Styling the Note Form Container */
    [data-testid="stForm"] {
        border: 1px solid #E0E2E6 !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03) !important;
        padding: 2rem !important;
    }
    
    /* Custom Styling for Note Cards */
    .note-card {
        background-color: #ffffff;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .note-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    
    /* Pill Tag Custom Styles */
    .tag-chip {
        display: inline-block;
        background-color: #F1F5F9;
        color: #475569;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.25rem 0.6rem;
        border-radius: 20px;
        margin-right: 0.4rem;
        margin-top: 0.5rem;
        border: 1px solid #E2E8F0;
    }
    </style>
""", unsafe_allow_html=True)

# App branding using our custom CSS classes
st.markdown('<h1 class="main-title">📝 Smart Notes</h1>', unsafe_allow_html=True)
st.caption("A sleek, non-blocking asynchronous note system powered by FastAPI & MongoDB")
st.markdown("---")

# Setup a clean two-column layout
col1, col2 = st.columns([1, 2], gap="large")

# ==========================================
# LEFT COLUMN: CREATE A NEW NOTE (UNCHANGED CORE LOGIC)
# ==========================================
with col1:
    st.markdown("### ✨ Create Note")
    
    with st.form("create_note_form", clear_on_submit=True):
        title = st.text_input("Note Title", placeholder="e.g., System Design Notes")
        content = st.text_area("Note Content", placeholder="Type your note details here...", height=150)
        tags_input = st.text_input("Tags (comma separated)", placeholder="e.g., backend, redis")
        
        submit_btn = st.form_submit_button("Save Note", use_container_width=True)
        
        if submit_btn:
            if not title or not content:
                st.error("Title and Content cannot be empty!")
            else:
                tags_list = [t.strip().lower() for t in tags_input.split(",") if t.strip()]
                payload = {"title": title, "content": content, "tags": tags_list}
                
                try:
                    response = requests.post(f"{BASE_URL}/notes", json=payload)
                    if response.status_code == 201:
                        st.success("🎉 Note saved!")
                        st.rerun()
                    else:
                        st.error(f"Failed to save note: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Could not connect to backend server.")

# ==========================================
# RIGHT COLUMN: GORGEOUS DYNAMIC GRID VIEW
# ==========================================
with col2:
    st.markdown("### 📋 Your Collection")
    
    try:
        response = requests.get(f"{BASE_URL}/notes")
        
        if response.status_code == 200:
            notes = response.json()
            
            if not notes:
                st.info("Your collection is empty. Create your first note on the left side!")
            else:
                # 🚀 THE MAGIC GRID STEP
                # We turn the notes list into rows of 2 cards each
                for i in range(0, len(notes), 2):
                    grid_cols = st.columns(2)
                    
                    # Left card in the grid row
                    if i < len(notes):
                        with grid_cols[0]:
                            note = notes[i]
                            with st.container(border=True):
                                st.subheader(note["title"])
                                st.write(note["content"])
                                
                                # Render custom HTML tag chips
                                if note.get("tags"):
                                    tags_html = "".join([f'<span class="tag-chip">🏷️ {tag}</span>' for tag in note["tags"]])
                                    st.markdown(tags_html, unsafe_allow_html=True)
                                
                                st.markdown("<br>", unsafe_allow_html=True)
                                st.caption(f"ID: {note['id']}")
                    
                    # Right card in the grid row
                    if i + 1 < len(notes):
                        with grid_cols[1]:
                            note = notes[i+1]
                            with st.container(border=True):
                                st.subheader(note["title"])
                                st.write(note["content"])
                                
                                if note.get("tags"):
                                    tags_html = "".join([f'<span class="tag-chip">🏷️ {tag}</span>' for tag in note["tags"]])
                                    st.markdown(tags_html, unsafe_allow_html=True)
                                
                                st.markdown("<br>", unsafe_allow_html=True)
                                st.caption(f"ID: {note['id']}")
                                
        else:
            st.error("Error retrieving notes from backend.")
            
    except requests.exceptions.ConnectionError:
        st.warning("🔄 Waiting for FastAPI backend to connect...")