import streamlit as st
import requests

# FastAPI backend base URL
BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Smart Notes App", page_icon="📝", layout="wide")

# Native branding headers
st.title("📝 Smart Notes")
st.caption("A sleek, non-blocking asynchronous note system powered by FastAPI & MongoDB")
st.divider()

# Setup clean column layouts
col1, col2 = st.columns([1, 2], gap="large")

# ==========================================
# 📋 NATIVE MODAL DIALOG
# ==========================================
@st.dialog("📖 Full Document View", width="large")
def show_note_modal(note_item):
    """Renders a clean native overlay popup to show full content details."""
    st.header(note_item["title"])
    
    # Display native tags using text formatting if they exist
    if note_item.get("tags"):
        st.write(" ".join([f"🏷️ `{tag}`" for tag in note_item["tags"]]))
        
    st.divider()
    st.write(note_item["content"])
    st.divider()
    st.caption(f"Id : {note_item['id']}")


# ==========================================
# LEFT COLUMN: CREATE A NEW NOTE
# ==========================================
with col1:
    st.subheader("✨ Create Note")
    
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
# RIGHT COLUMN: SEARCH & DYNAMIC GRID VIEW
# ==========================================
with col2:
    st.subheader("📋 Your Collection")
    
    # Native query input box to test your unified backend search engine
    search_query = st.text_input("🔍 Search notes instantly...", placeholder="Type to filter titles or content...")

    try:
        # Route parameters dynamically to your unified GET /notes route
        params = {"q": search_query} if search_query else {}
        response = requests.get(f"{BASE_URL}/notes", params=params)
        
        if response.status_code == 200:
            notes = response.json()
            
            if not notes:
                if search_query:
                    st.info(f"No results match your search: '{search_query}'")
                else:
                    st.info("Your collection is empty. Create your first note on the left side!")
            else:
                # Render cards dynamically in a 2-column grid layout loop
                for i in range(0, len(notes), 2):
                    grid_cols = st.columns(2)
                    
                    for step in range(2):
                        index = i + step
                        if index < len(notes):
                            note = notes[index]
                            with grid_cols[step]:
                                # Native container with border=True handles background, shadows, and spacing!
                                with st.container(border=True):
                                    st.markdown(f"### {note['title']}")
                                    
                                    # Truncate text content cleanly
                                    display_text = note["content"]
                                    if len(display_text) > 120:
                                        display_text = display_text[:120] + "..."
                                    st.write(display_text)
                                    
                                    # Native layout columns inside the card for tags and button
                                    action_col, btn_col = st.columns([2, 1])
                                    
                                    with action_col:
                                        if note.get("tags"):
                                            # Native markdown code blocks look like clean uniform badges
                                            st.write(" ".join([f"`{tag}`" for tag in note["tags"]]))
                                    
                                    with btn_col:
                                        if st.button("Expand ↗", key=f"expand_{note['id']}", use_container_width=True):
                                            show_note_modal(note)
                                            
        else:
            st.error("Error retrieving notes from backend.")
            
    except requests.exceptions.ConnectionError:
        st.warning("🔄 Waiting for FastAPI backend to connect...")