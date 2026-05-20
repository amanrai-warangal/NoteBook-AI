import streamlit as st
import requests

# FastAPI backend base URL
BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Smart Notes App", page_icon="📝", layout="wide")

st.title("📝 Smart Notes App")
st.caption("A gorgeous frontend for your FastAPI notes backend")

# Setup a clean two-column layout: Left for creating notes, Right for viewing them
col1, col2 = st.columns([1, 2], gap="large")

# ==========================================
# LEFT COLUMN: CREATE A NEW NOTE
# ==========================================
with col1:
    st.header("✨ New Note")
    
    with st.form("create_note_form", clear_on_submit=True):
        title = st.text_input("Note Title", placeholder="e.g., Grocery List")
        content = st.text_area("Note Content", placeholder="Type your note details here...")
        tags_input = st.text_input("Tags (comma separated)", placeholder="e.g., shopping, personal")
        
        submit_btn = st.form_submit_button("Save Note", use_container_width=True)
        
        if submit_btn:
            if not title or not content:
                st.error("Title and Content cannot be empty!")
            else:
                # Process comma-separated tags into a clean list
                tags_list = [t.strip().lower() for t in tags_input.split(",") if t.strip()]
                
                # Payload matching your FastAPI 'NoteCreate' model
                payload = {
                    "title": title,
                    "content": content,
                    "tags": tags_list
                }
                
                try:
                    response = requests.post(f"{BASE_URL}/notes", json=payload)
                    if response.status_code == 201:
                        st.success("🎉 Note saved successfully!")
                        # Force a rerun to refresh the list instantly
                        st.rerun()
                    else:
                        st.error(f"Failed to save note: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Could not connect to backend. Is your FastAPI server running?")

# ==========================================
# RIGHT COLUMN: DISPLAY NOTES AS CARDS
# ==========================================
with col2:
    st.header("📋 Your Notes")
    
    try:
        # Fetch notes from FastAPI
        response = requests.get(f"{BASE_URL}/notes")
        
        if response.status_code == 200:
            notes = response.json()
            
            if not notes:
                st.info("No notes found. Create your first note on the left side!")
            else:
                # Render cards dynamically
                for note in notes:
                    # Using st.container creates a clean visual border/box per note
                    with st.container(border=True):
                        st.subheader(note["title"])
                        st.write(note["content"])
                        
                        # Render tags beautifully as text badges
                        if note.get("tags"):
                            badges = " ".join([f"`🏷️ {tag}`" for tag in note["tags"]])
                            st.markdown(badges)
                            
                        # Muted ID footer
                        st.caption(f"ID: {note['id']}")
        else:
            st.error("Error retrieving notes from backend.")
            
    except requests.exceptions.ConnectionError:
        st.warning("🔄 Waiting for FastAPI backend to connect... Make sure it's running on port 8000!")