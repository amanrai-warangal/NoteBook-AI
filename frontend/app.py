import streamlit as st
import requests

# FastAPI backend base URL
BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Smart Notes App", page_icon="📝", layout="wide")

# ==========================================
# 🎨 INJECT UNIFORM CARD HEIGHT STYLES (CSS)
# ==========================================
st.markdown("""
    <style>
        /* Forces all border containers inside our card loops to anchor to a fixed layout height */
        div[data-testid="stVComponentBlock"] > div.stElementContainer div[data-testid="stVerticalBlockBorderWrapper"] {
            min-height: 220px !important;
            max-height: 220px !important;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 💾 APPLICATION STATE MANAGEMENT (AUTH CORE)
# ==========================================
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None
if "auth_page" not in st.session_state:
    st.session_state.auth_page = "login"  # Options: "login" or "register"


# ==========================================
# 📋 NATIVE MODAL DIALOG
# ==========================================
@st.dialog("📖 Full Document View", width="large")
def show_note_modal(note_item):
    """
    Renders an interactive native overlay modal popup. Allows reading full text,
    updating title/content/tags, or executing a safe cascade delete operation.
    """
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    note_id = note_item["id"]

    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False

    # -------------------------------------------------------------
    # 👁️ MODE A: READ-ONLY VIEWS (WITH PREVIEW & REMOVAL SWITCHES)
    # -------------------------------------------------------------
    if not st.session_state.edit_mode:
        st.header(note_item["title"])
        
        if note_item.get("tags"):
            st.write(" ".join([f"🏷️ `{tag}`" for tag in note_item["tags"]]))
            
        st.divider()
        st.write(note_item["content"])
        st.divider()

        st.caption(f"System ID: `{note_id}`")
        st.divider()

        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("📝 Edit Note", use_container_width=True):
                st.session_state.edit_mode = True
                st.rerun()
                
        with col2:
            if st.button("🗑️ Delete", type="primary", use_container_width=True):
                with st.spinner("Dropping Note Asset..."):
                    response = requests.delete(f"{BASE_URL}/notes/{note_id}", headers=headers)
                    
                if response.status_code == 204:
                    st.success("Note dropped successfully!")
                    st.session_state.edit_mode = False
                    st.rerun()
                else:
                    st.error(f"Deletion failed: {response.json().get('detail')}")

    # -------------------------------------------------------------
    # ✏️ MODE B: LIVE IN-PLACE EDITING DASHBOARD
    # -------------------------------------------------------------
    else:
        st.subheader("✏️ Edit Note Asset Workspace")
        
        updated_title = st.text_input("Title", value=note_item["title"])
        existing_tags_str = ", ".join(note_item.get("tags", []))
        updated_tags_raw = st.text_input("Tags (comma-separated)", value=existing_tags_str)
        updated_content = st.text_area("Content Space", value=note_item["content"], height=250)
        
        st.divider()
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            if st.button("💾 Save Changes", type="primary", use_container_width=True):
                processed_tags = [t.strip().lower() for t in updated_tags_raw.split(",") if t.strip()]
                
                payload = {
                    "title": updated_title,
                    "content": updated_content,
                    "tags": processed_tags
                }
                
                with st.spinner("Updating database indexes..."):
                    response = requests.put(f"{BASE_URL}/notes/{note_id}", json=payload, headers=headers)
                    
                if response.status_code == 200:
                    st.toast("✅ Changes saved perfectly!")
                    st.session_state.edit_mode = False
                    st.rerun()
                else:
                    st.error(f"Update Failure: {response.json().get('detail')}")
                    
        with col_cancel:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.edit_mode = False
                st.rerun()


# ==========================================
# 🌐 DYNAMIC HEADER NAVBAR COMPONENT
# ==========================================
def render_navbar():
    """Renders a responsive user context top utility bar natively."""
    nav_col1, nav_col2 = st.columns([3, 1], gap="large")
    
    with nav_col1:
        st.title("📝 Smart Notes")
        if st.session_state.token:
            st.markdown(f"#### 👋 Welcome back, **{st.session_state.username}**!")
        else:
            st.caption("A sleek, non-blocking asynchronous note system powered by FastAPI & MongoDB")
            
    with nav_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.session_state.token:
            if st.button("🚪 Log Out", use_container_width=True, type="secondary"):
                st.session_state.token = None
                st.session_state.username = None
                st.toast("Logged out successfully. See you soon!", icon="ℹ️")
                st.rerun()
                
    st.divider()


# ==========================================
# 🔐 VIEW: AUTHENTICATION (LOGIN / REGISTER)
# ==========================================
def render_auth_view():
    """Renders standard card layouts for user sign-in and account creation."""
    _, center_col, _ = st.columns([1, 1.5, 1])
    
    with center_col:
        if st.session_state.auth_page == "login":
            st.subheader("🔑 Account Sign In")
            
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                submit_btn = st.form_submit_button("Log In", use_container_width=True, type="primary")
                
                if submit_btn:
                    if not username or not password:
                        st.error("Please fill in all verification credentials.")
                    else:
                        try:
                            payload = {"username": username, "password": password}
                            response = requests.post(f"{BASE_URL}/auth/login", json=payload)
                            
                            if response.status_code == 200:
                                res_data = response.json()
                                st.session_state.token = res_data["access_token"]
                                st.session_state.username = username
                                st.toast(f"Welcome back, {username}! Access granted.", icon="🚀")
                                st.rerun()
                            else:
                                try:
                                    error_detail = response.json().get("detail", "Authentication failed.")
                                except Exception:
                                    error_detail = response.text if response.text else "Unknown backend error."
                                st.error(f"❌ {error_detail}")
                        except requests.exceptions.ConnectionError:
                            st.error("Unable to link to local backend validation server.")
            
            st.markdown("Don't have an account yet?")
            if st.button("Create an account ↗", type="secondary"):
                st.session_state.auth_page = "register"
                st.rerun()
                
        else:
            st.subheader("✨ Register New Profile")
            
            with st.form("register_form", clear_on_submit=True):
                new_username = st.text_input("Choose Username", placeholder="Minimum 3 characters")
                new_password = st.text_input("Choose Password", type="password", placeholder="Minimum 6 characters")
                submit_btn = st.form_submit_button("Sign Up Account", use_container_width=True, type="primary")
                
                if submit_btn:
                    if len(new_username) < 3 or len(new_password) < 6:
                        st.error("Validation Error: Review length specifications.")
                    else:
                        try:
                            payload = {"username": new_username, "password": new_password}
                            response = requests.post(f"{BASE_URL}/auth/register", json=payload)
                            
                            if response.status_code == 201:
                                st.success("🎉 Registration complete! Please log in below.")
                                st.session_state.auth_page = "login"
                                st.toast("Profile built successfully!", icon="❇️")
                                st.rerun()
                            else:
                                try:
                                    error_detail = response.json().get("detail", "Registration blocked.")
                                except Exception:
                                    error_detail = response.text if response.text else "Unknown backend error."
                                st.error(f"❌ {error_detail}")
                        except requests.exceptions.ConnectionError:
                            st.error("Unable to link to local backend validation server.")
                            
            if st.button("← Back to Sign In Login", type="secondary"):
                st.session_state.auth_page = "login"
                st.rerun()


# ==========================================
# 📋 VIEW: THE NOTES WORKSPACE
# ==========================================
def render_workspace_view():
    """Renders the core two-column notes workflow interface."""
    col1, col2 = st.columns([1, 2], gap="large")

    # LEFT COLUMN: CREATE A NEW NOTE
    with col1:
        st.subheader("✨ Create Note")
        
        with st.form("create_note_form", clear_on_submit=True):
            title = st.text_input("Note Title", placeholder="e.g., Kafka Architecture Insights")
            content = st.text_area("Note Content", placeholder="Type deep technical details here...", height=150)
            tags_input = st.text_input("Tags (comma separated)", placeholder="e.g., microservices, infra")
            
            submit_btn = st.form_submit_button("Save Note", use_container_width=True, type="primary")
            
            if submit_btn:
                if not title or not content:
                    st.error("Title and Content specifications cannot be left blank!")
                else:
                    tags_list = [t.strip().lower() for t in tags_input.split(",") if t.strip()]
                    payload = {"title": title, "content": content, "tags": tags_list}
                    
                    try:
                        headers = {"Authorization": f"Bearer {st.session_state.token}"}
                        response = requests.post(f"{BASE_URL}/notes", json=payload, headers=headers)
                        
                        if response.status_code == 201:
                            st.toast("Document committed to database storage cluster!", icon="💾")
                            st.rerun()
                        else:
                            st.error(f"Write operation failure: {response.text}")
                    except requests.exceptions.ConnectionError:
                        st.error("Could not connect to backend server infrastructure.")

    # RIGHT COLUMN: SEARCH & LIVE FRAGMENT GRID VIEW
    with col2:
        st.subheader("📋 Your Collection")
        
        @st.fragment
        def live_search_container():
            # Dedicated Layout columns for the search panel layout
            search_col, toggle_col = st.columns([2, 1])
            
            with search_col:
                search_query = st.text_input(
                    "Search Input Box",
                    label_visibility="collapsed",
                    placeholder="Search notes instantly...",
                    key="realtime_search"
                )
                
            with toggle_col:
                # 🌟 SWAPPED SELECTBOX FOR ST.TOGGLE: Sleek switch engine design pattern
                ai_mode_active = st.toggle(
                    "🧠 AI Semantic Search",
                    value=False,
                    key="search_mode_toggle_switch"
                )

            try:
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                params = {"q": search_query} if search_query else {}
                
                # Branching endpoint route logic tied directly to the boolean toggle switch state
                if search_query and ai_mode_active:
                    endpoint_route = f"{BASE_URL}/notes/semantic-search"
                    params["limit"] = 3  # 🌟 LOCKED LIMIT: Restricts semantic returns to 3 matches
                else:
                    endpoint_route = f"{BASE_URL}/notes"

                response = requests.get(endpoint_route, params=params, headers=headers)
                
                if response.status_code == 200:
                    notes = response.json()
                    
                    if not notes:
                        if search_query:
                            st.info(f"No results match your search: '{search_query}'")
                        else:
                            st.info("Your collection is empty. Create your first note on the left side!")
                    else:
                        for i in range(0, len(notes), 2):
                            grid_cols = st.columns(2)
                            
                            for step in range(2):
                                index = i + step
                                if index < len(notes):
                                    note = notes[index]
                                    with grid_cols[step]:
                                        with st.container(border=True):
                                            # Title formatting with uniform bounding
                                            title_text = note['title']
                                            if len(title_text) > 35:
                                                title_text = title_text[:35] + "..."
                                            st.markdown(f"### {title_text}")
                                            
                                            # Truncate content text uniformly to keep cards completely crisp
                                            display_text = note["content"]
                                            if len(display_text) > 100:
                                                display_text = display_text[:100] + "..."
                                            st.write(display_text)
                                            
                                            action_col, btn_col = st.columns([1.8, 1])
                                            
                                            with action_col:
                                                if note.get("tags"):
                                                    # Show first 2 tags only on dashboard card preview for spatial grid safety
                                                    st.write(" ".join([f"`{tag}`" for tag in note["tags"][:2]]))
                                            
                                            with btn_col:
                                                if st.button("Expand ↗", key=f"expand_{note['id']}", use_container_width=True):
                                                    show_note_modal(note)
                else:
                    st.error("Error retrieving records data logs out of collection stack.")
                    
            except requests.exceptions.ConnectionError:
                st.warning("🔄 Waiting for FastAPI backend connection interface...")

        live_search_container()


# ==========================================
# 🚦 CORE EXECUTION ROUTER ENTRYPOINT
# ==========================================
render_navbar()

if st.session_state.token is None:
    render_auth_view()
else:
    render_workspace_view()