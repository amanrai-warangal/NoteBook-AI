import streamlit as st
import requests

BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Smart Notes", page_icon="📝", layout="wide")

# Minimal custom CSS for polish
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    div[data-testid="stSidebar"] > div:first-child { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None
if "auth_page" not in st.session_state:
    st.session_state.auth_page = "login"
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None
if "active_session_messages" not in st.session_state:
    st.session_state.active_session_messages = []
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "notes"


# ==========================================
# MODAL: VIEW / EDIT / DELETE NOTE
# ==========================================
@st.dialog("View Note", width="large")
def show_note_modal(note_item):
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    note_id = note_item["id"]

    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False

    if not st.session_state.edit_mode:
        st.markdown(f"## {note_item['title']}")
        if note_item.get("tags"):
            st.markdown(" ".join([f"`{tag}`" for tag in note_item["tags"]]))
        st.divider()
        st.markdown(note_item["content"])
        st.divider()

        col1, col2, _ = st.columns([1, 1, 2])
        with col1:
            if st.button("✏️ Edit", use_container_width=True):
                st.session_state.edit_mode = True
                st.rerun()
        with col2:
            if st.button("🗑️ Delete", use_container_width=True, type="primary"):
                response = requests.delete(f"{BASE_URL}/notes/{note_id}", headers=headers)
                if response.status_code == 204:
                    st.success("Note deleted.")
                    st.session_state.edit_mode = False
                    st.rerun()
                else:
                    st.error("Deletion failed.")
    else:
        st.subheader("Edit Note")
        updated_title = st.text_input("Title", value=note_item["title"])
        existing_tags_str = ", ".join(note_item.get("tags", []))
        updated_tags_raw = st.text_input("Tags (comma-separated)", value=existing_tags_str)
        updated_content = st.text_area("Content", value=note_item["content"], height=250)

        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.button("💾 Save", type="primary", use_container_width=True):
                processed_tags = [t.strip().lower() for t in updated_tags_raw.split(",") if t.strip()]
                payload = {"title": updated_title, "content": updated_content, "tags": processed_tags}
                response = requests.put(f"{BASE_URL}/notes/{note_id}", json=payload, headers=headers)
                if response.status_code == 200:
                    st.toast("Changes saved!")
                    st.session_state.edit_mode = False
                    st.rerun()
                else:
                    st.error("Update failed.")
        with col_cancel:
            if st.button("Cancel", use_container_width=True):
                st.session_state.edit_mode = False
                st.rerun()


# ==========================================
# SIDEBAR: CHAT HISTORY (always visible when logged in)
# ==========================================
def render_sidebar():
    with st.sidebar:
        st.markdown("## 📝 Smart Notes")
        st.caption(f"Signed in as **{st.session_state.username}**")
        st.divider()

        # Navigation
        if st.button("📂 My Notes", use_container_width=True,
                     type="primary" if st.session_state.active_tab == "notes" else "secondary"):
            st.session_state.active_tab = "notes"
            st.rerun()

        if st.button("💬 AI Chat", use_container_width=True,
                     type="primary" if st.session_state.active_tab == "chat" else "secondary"):
            st.session_state.active_tab = "chat"
            st.rerun()

        st.divider()

        # Chat history section
        st.markdown("#### Chat History")
        if st.button("➕ New Chat", use_container_width=True):
            st.session_state.active_session_id = None
            st.session_state.active_session_messages = []
            st.session_state.active_tab = "chat"
            st.rerun()

        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        try:
            resp = requests.get(f"{BASE_URL}/ai/history", headers=headers)
            if resp.status_code == 200:
                threads = resp.json()
                if not threads:
                    st.caption("No conversations yet.")
                for thread in threads:
                    is_active = (thread["session_id"] == st.session_state.active_session_id)
                    label = thread["title"]
                    col_btn, col_del = st.columns([4, 1])
                    with col_btn:
                        if st.button(
                            f"{'▶ ' if is_active else ''}{label}",
                            key=f"thread_{thread['session_id']}",
                            use_container_width=True,
                        ):
                            st.session_state.active_session_id = thread["session_id"]
                            st.session_state.active_tab = "chat"
                            # Load conversation
                            hist_resp = requests.get(
                                f"{BASE_URL}/ai/history/{thread['session_id']}", headers=headers
                            )
                            if hist_resp.status_code == 200:
                                raw = hist_resp.json()
                                msgs = []
                                for item in raw:
                                    msgs.append({"role": "user", "content": item["question"]})
                                    msgs.append({
                                        "role": "assistant",
                                        "content": item["answer"],
                                        "sources": item.get("sources", [])
                                    })
                                st.session_state.active_session_messages = msgs
                            st.rerun()
                    with col_del:
                        if st.button("🗑️", key=f"del_{thread['session_id']}"):
                            requests.delete(
                                f"{BASE_URL}/ai/history/{thread['session_id']}",
                                headers=headers
                            )
                            # Clear active session if we deleted it
                            if st.session_state.active_session_id == thread["session_id"]:
                                st.session_state.active_session_id = None
                                st.session_state.active_session_messages = []
                            st.rerun()
        except Exception:
            st.caption("Could not load chat history.")

        st.divider()
        if st.button("🚪 Log Out", use_container_width=True):
            st.session_state.token = None
            st.session_state.username = None
            st.session_state.active_session_id = None
            st.session_state.active_session_messages = []
            st.session_state.active_tab = "notes"
            st.rerun()


# ==========================================
# AUTH VIEW: LOGIN / REGISTER
# ==========================================
def render_auth_view():
    _, center_col, _ = st.columns([1, 1.5, 1])

    with center_col:
        st.markdown("## 📝 Smart Notes")
        st.caption("Save notes and ask questions powered by AI")
        st.divider()

        if st.session_state.auth_page == "login":
            st.subheader("Sign In")
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                submit_btn = st.form_submit_button("Log In", use_container_width=True, type="primary")

                if submit_btn:
                    if not username or not password:
                        st.error("Please fill in all fields.")
                    else:
                        try:
                            response = requests.post(
                                f"{BASE_URL}/auth/login",
                                json={"username": username, "password": password}
                            )
                            if response.status_code == 200:
                                st.session_state.token = response.json()["access_token"]
                                st.session_state.username = username
                                st.rerun()
                            else:
                                detail = response.json().get("detail", "Login failed.")
                                st.error(detail)
                        except requests.exceptions.ConnectionError:
                            st.error("Cannot connect to backend server.")

            if st.button("Don't have an account? Register",use_container_width=True, type="secondary"):
                st.session_state.auth_page = "register"
                st.rerun()

        else:
            st.subheader("Create Account")
            with st.form("register_form", clear_on_submit=True):
                new_username = st.text_input("Username", placeholder="Min 3 characters")
                new_password = st.text_input("Password", type="password", placeholder="Min 6 characters")
                submit_btn = st.form_submit_button("Register", use_container_width=True, type="primary")

                if submit_btn:
                    if len(new_username) < 3 or len(new_password) < 6:
                        st.error("Username must be 3+ chars, password 6+ chars.")
                    else:
                        try:
                            response = requests.post(
                                f"{BASE_URL}/auth/register",
                                json={"username": new_username, "password": new_password}
                            )
                            if response.status_code == 201:
                                st.success("Account created! Please sign in.")
                                st.session_state.auth_page = "login"
                                st.rerun()
                            else:
                                detail = response.json().get("detail", "Registration failed.")
                                st.error(detail)
                        except requests.exceptions.ConnectionError:
                            st.error("Cannot connect to backend server.")

            if st.button("← Back to Sign In"):
                st.session_state.auth_page = "login"
                st.rerun()


# ==========================================
# NOTES TAB
# ==========================================
def render_notes_page():
    st.header("My Notes")

    # Create note section
    with st.expander("➕ Create New Note", expanded=False):
        with st.form("create_note_form", clear_on_submit=True):
            title = st.text_input("Title", placeholder="e.g., Meeting Notes")
            content = st.text_area("Content", placeholder="Write your note here...", height=150)
            tags_input = st.text_input("Tags (comma separated)", placeholder="e.g., work, ideas")
            submit_btn = st.form_submit_button("Save Note", use_container_width=True, type="primary")

            if submit_btn:
                if not title or not content:
                    st.error("Title and content are required.")
                else:
                    tags_list = [t.strip().lower() for t in tags_input.split(",") if t.strip()]
                    payload = {"title": title, "content": content, "tags": tags_list}
                    try:
                        headers = {"Authorization": f"Bearer {st.session_state.token}"}
                        response = requests.post(f"{BASE_URL}/notes", json=payload, headers=headers)
                        if response.status_code == 201:
                            st.toast("Note saved!", icon="✅")
                            st.rerun()
                        else:
                            st.error(f"Error: {response.text}")
                    except requests.exceptions.ConnectionError:
                        st.error("Cannot connect to backend.")

    st.divider()

    # Search bar
    search_col, toggle_col = st.columns([3, 1])
    with search_col:
        search_query = st.text_input(
            "Search",
            label_visibility="collapsed",
            placeholder="🔍 Search your notes...",
            key="search_notes"
        )
    with toggle_col:
        ai_search = st.toggle("AI Search", value=False, key="ai_search_toggle")

    # Fetch and display notes
    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        params = {"q": search_query} if search_query else {}

        if search_query and ai_search:
            endpoint = f"{BASE_URL}/notes/semantic-search"
            params["limit"] = 5
        else:
            endpoint = f"{BASE_URL}/notes"

        response = requests.get(endpoint, params=params, headers=headers)

        if response.status_code == 200:
            notes = response.json()
            if not notes:
                if search_query:
                    st.info(f"No results for '{search_query}'")
                else:
                    st.info("No notes yet. Create your first note above!")
            else:
                # Grid display
                for i in range(0, len(notes), 3):
                    cols = st.columns(3)
                    for j in range(3):
                        idx = i + j
                        if idx < len(notes):
                            note = notes[idx]
                            with cols[j]:
                                with st.container(border=True):
                                    title_text = note["title"]
                                    if len(title_text) > 30:
                                        title_text = title_text[:30] + "..."
                                    st.markdown(f"**{title_text}**")

                                    preview = note["content"]
                                    if len(preview) > 80:
                                        preview = preview[:80] + "..."
                                    st.caption(preview)

                                    if note.get("tags"):
                                        st.markdown(" ".join([f"`{t}`" for t in note["tags"][:3]]))

                                    if st.button("Open", key=f"open_{note['id']}", use_container_width=True):
                                        show_note_modal(note)
        else:
            st.error("Failed to load notes.")
    except requests.exceptions.ConnectionError:
        st.warning("Waiting for backend connection...")


# ==========================================
# AI CHAT TAB
# ==========================================
def render_chat_page():
    st.header("AI Chat")
    st.caption("Ask questions about your saved notes")

    # Display chat messages
    for message in st.session_state.active_session_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("sources"):
                sources = message["sources"]
                is_external = (len(sources) == 1 and sources[0].get("id") == "external")
                if is_external:
                    st.caption("🌐 Source: General Knowledge (not from your notes)")
                else:
                    with st.expander("📚 Sources from your notes", expanded=False):
                        for idx, src in enumerate(sources, 1):
                            st.markdown(f"**{idx}. {src['title']}**")
                            if src.get("tags"):
                                st.caption(" ".join([f"`{t}`" for t in src["tags"]]))

    # Chat input
    if user_input := st.chat_input("Ask something about your notes..."):
        st.session_state.active_session_messages.append({"role": "user", "content": user_input})

        # Show user message immediately
        with st.chat_message("user"):
            st.markdown(user_input)

        # Show thinking indicator while waiting for response
        with st.chat_message("assistant"):
            with st.spinner("Thinking... collecting info from your notes"):
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                payload = {
                    "question": user_input,
                    "session_id": st.session_state.active_session_id
                }

                try:
                    response = requests.post(f"{BASE_URL}/ai/chat", json=payload, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.active_session_id = data["session_id"]
                        st.session_state.active_session_messages.append({
                            "role": "assistant",
                            "content": data["answer"],
                            "sources": data.get("sources", [])
                        })
                        st.rerun()
                    else:
                        st.error(f"Error: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to backend.")


# ==========================================
# MAIN APP ROUTER
# ==========================================
if st.session_state.token is None:
    render_auth_view()
else:
    render_sidebar()
    if st.session_state.active_tab == "notes":
        render_notes_page()
    else:
        render_chat_page()