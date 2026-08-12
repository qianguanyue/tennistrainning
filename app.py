import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

# ==================================================================
# 1. INITIALIZATION & CONFIGURATION
# ==================================================================
load_dotenv()

st.set_page_config(
    page_title="🎾 Tennis Training Tracker",
    page_icon="🎾",
    layout="wide"
)

# 🌟 Mobile-responsive CSS & UI Tweaks
st.markdown("""
<style>
    /* Sidebar width on mobile */
    section[data-testid="stSidebar"] { width: 260px !important; }
    /* Horizontal scroll for tables on small screens */
    .stDataFrame { overflow-x: auto; }
    /* Responsive font sizes */
    @media (max-width: 768px) {
        h1 { font-size: 1.6rem !important; }
        h2 { font-size: 1.3rem !important; }
        h3 { font-size: 1.1rem !important; }
        p, li, span, .st-emotion-cache-16idsys p { font-size: 14px !important; }
        .stSlider label { font-size: 13px !important; }
    }
    /* Hide default Streamlit footer & menu */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Error: Supabase configuration not found! Please check your .env / Secrets.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BJT = timezone(timedelta(hours=8))

# ==================================================================
# 2. DATA ACCESS LAYER (🌟 Optimized with error handling)
# ==================================================================
@st.cache_data(ttl=60)
def get_records(uid, days=30):
    """Fetch records from the last N days safely."""
    days_ago = (datetime.now(BJT) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        res = (
            supabase.table("training_records")
            .select("*")
            .eq("user_id", uid)
            .gte("record_date", days_ago)
            .order("record_date", desc=False)
            .execute()
        )
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.toast(f"⚠️ Failed to load recent data: {e}", icon="🚨")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_latest_n_records(uid, n=7):
    """Fetch the latest N records regardless of date continuity."""
    try:
        res = (
            supabase.table("training_records")
            .select("*")
            .eq("user_id", uid)
            .order("record_date", desc=True)
            .limit(n)
            .execute()
        )
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
        if not df.empty:
            df = df.sort_values("record_date").reset_index(drop=True)
        return df
    except Exception as e:
        st.toast(f"⚠️ Failed to load comparison data: {e}", icon="🚨")
        return pd.DataFrame()

# ==================================================================
# 3. AUTHENTICATION
# ==================================================================
if "user" not in st.session_state:
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.markdown("## 🎾 Tennis Training Tracker")
        tab1, tab2 = st.tabs(["Log In", "Sign Up"])

        with tab1:
            st.write("Welcome back! Enter your credentials.")
            login_email = st.text_input("Email", key="login_email")
            login_pwd = st.text_input("Password", type="password", key="login_pwd")
            if st.button("Log In", type="primary", use_container_width=True):
                if not login_email or not login_pwd:
                    st.warning("Please enter your email and password.")
                else:
                    try:
                        res = supabase.auth.sign_in_with_password({"email": login_email, "password": login_pwd})
                        st.session_state.user = res.user
                        st.success("Login successful! Redirecting…")
                        st.rerun()
                    except Exception:
                        st.error("Login failed: incorrect email or password.")

        with tab2:
            st.write("Create a new account to start tracking.")
            reg_email = st.text_input("Email", key="reg_email")
            reg_pwd = st.text_input("Password (min 6 characters)", type="password", key="reg_pwd")
            reg_name = st.text_input("Your Name / Nickname", key="reg_name")
            if st.button("Sign Up", type="primary", use_container_width=True):
                if not reg_email or not reg_pwd or not reg_name:
                    st.warning("Please fill in all fields.")
                elif len(reg_pwd) < 6:
                    st.warning("Password must be at least 6 characters.")
                else:
                    try:
                        res = supabase.auth.sign_up({"email": reg_email, "password": reg_pwd})
                        supabase.table("profiles").insert({"id": res.user.id, "username": reg_name}).execute()
                        st.success("🎉 Account created! Switch to the **Log In** tab to sign in.")
                    except Exception as e:
                        st.error(f"Sign-up failed: {e}")
    st.stop()

# ==================================================================
# 4. SIDEBAR & NAVIGATION
# ==================================================================
user = st.session_state.user
with st.sidebar:
    st.markdown("## 🎾 Training Tracker")
    st.caption(f"👤 {user.email.split('@')[0]}")
    if st.button("🚪 Log Out", use_container_width=True):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()
    st.markdown("---")
    page = st.radio(
        "Navigation",
        ["📝 Log Today's Session", "📅 History", "📊 30-Day Trends", "🎯 Goal Comparison"],
    )

# 🌟 Skeleton loading state for better UX
with st.spinner("Loading your training data..."):
    df_30 = get_records(user.id, 30)

# ==================================================================
# 5. PAGE LOGIC
# ==================================================================

# -------------------- 📝 PAGE 1: Log Today's Session --------------------
if page == "📝 Log Today's Session":
    st.header("📝 Log Today's Training")
    st.caption("💡 If you log again for the same date, the previous entry will be updated automatically.")

    today_str = datetime.now(BJT).strftime("%Y-%m-%d")
    
    # 🌟 Safe check for empty DataFrame to prevent KeyError
    if not df_30.empty and "record_date" in df_30.columns:
        existing_today = df_30[df_30["record_date"] == today_str]
    else:
        existing_today = pd.DataFrame()

    col1, col2 = st.columns(2)
    with col1:
        d_serve = int(existing_today["serve_rate"].values[0]) if not existing_today.empty else 60
        serve = st.slider("🎾 Serve Success Rate (%)", 0, 100, d_serve)

        d_return = int(existing_today["return_rate"].values[0]) if not existing_today.empty else 50
        return_s = st.slider("🏃 Return Success Rate (%)", 0, 100, d_return)

    with col2:
        d_fh = int(existing_today["forehand_rate"].values[0]) if not existing_today.empty else 65
        forehand = st.slider("💪 Forehand Success Rate (%)", 0, 100, d_fh)

        d_bh = int(existing_today["backhand_rate"].values[0]) if not existing_today.empty else 55
        backhand = st.slider("🛡️ Backhand Success Rate (%)", 0, 100, d_bh)

    record_date = st.date_input("📅 Training Date", value=datetime.now(BJT).date())

    if st.button("💾 Save Record", type="primary", use_container_width=True):
        data = {
            "user_id": user.id,
            "record_date": str(record_date),
            "serve_rate": serve,
            "return_rate": return_s,
            "forehand_rate": forehand,
            "backhand_rate": backhand,
        }
        try:
            result = supabase.table("training_records").upsert(data, on_conflict="user_id,record_date").execute()
            if result.data:
                st.success("✅ Saved successfully!")
                st.cache_data.clear()
                st.balloons()
            else:
                st.error("Save failed. Please try again.")
        except Exception as e:
            st.error(f"Error saving: {e}")


# -------------------- 📅 PAGE 2: History (Edit & Delete) --------------------
elif page == "📅 History":
    st.header("📅 History — View, Edit & Delete Records")
    
    if df_30.empty:
        st.info("📭 No records yet. Go log your first session!")
    else:
        # === EDIT SECTION ===
        st.subheader("✏️ Edit Records")
        st.write("Edit numbers directly in the table below, then click **Save Changes**.")
        
        edit_df = df_30[["id", "record_date", "serve_rate", "return_rate", "forehand_rate", "backhand_rate"]].copy()
        edit_df.rename(columns={
            "record_date": "Date", "serve_rate": "Serve", "return_rate": "Return",
            "forehand_rate": "Forehand", "backhand_rate": "Backhand"
        }, inplace=True)

        edited_df = st.data_editor(
            edit_df, hide_index=True, use_container_width=True,
            column_config={
                "id": st.column_config.Column("ID", disabled=True, width="small"),
                "Date": st.column_config.DateColumn("Date", disabled=True, width="medium"),
                "Serve": st.column_config.NumberColumn("Serve (%)", min_value=0, max_value=100, width="small"),
                "Return": st.column_config.NumberColumn("Return (%)", min_value=0, max_value=100, width="small"),
                "Forehand": st.column_config.NumberColumn("Forehand (%)", min_value=0, max_value=100, width="small"),
                "Backhand": st.column_config.NumberColumn("Backhand (%)", min_value=0, max_value=100, width="small"),
            },
        )

        if st.button("💾 Save Changes", type="primary", use_container_width=True):
            changes_made = False
            for idx, row in edited_df.iterrows():
                orig = edit_df.iloc[idx]
                if (row["Serve"] != orig["Serve"] or row["Return"] != orig["Return"] or 
                    row["Forehand"] != orig["Forehand"] or row["Backhand"] != orig["Backhand"]):
                    try:
                        supabase.table("training_records").update({
                            "serve_rate": int(row["Serve"]), "return_rate": int(row["Return"]),
                            "forehand_rate": int(row["Forehand"]), "backhand_rate": int(row["Backhand"])
                        }).eq("id", row["id"]).execute()
                        changes_made = True
                    except Exception as e:
                        st.error(f"Error updating ID {row['id']}: {e}")

            if changes_made:
                st.success("✅ Changes synced to the cloud!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.info("No changes detected.")

        st.markdown("---")

        # === 🌟 DELETE SECTION ===
        st.subheader("🗑️ Delete a Record")
        st.warning("⚠️ Warning: Deleted records cannot be recovered.")
        
        delete_options = {
            f"{row['record_date']} (ID: {row['id']})": row['id'] 
            for _, row in df_30.sort_values('record_date', ascending=False).iterrows()
        }
        
        selected_label = st.selectbox(
            "Select a record to delete:", 
            options=list(delete_options.keys()),
            index=None,
            placeholder="Tap to choose a date..."
        )
        
        if selected_label is not None:
            target_id = delete_options[selected_label]
            if st.button("❌ Confirm Deletion", type="secondary", use_container_width=True):
                try:
                    result = supabase.table("training_records").delete().eq("id", target_id).execute()
                    if result.data:
                        st.success(f"✅ Record deleted successfully!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Deletion failed. Please try again.")
                except Exception as e:
                    st.error(f"Error deleting record: {e}")


# -------------------- 📊 PAGE 3: 30-Day Trends --------------------
elif page == "📊 30-Day Trends":
    st.header("📊 30-Day Trend Chart")

    if df_30.empty:
        st.info("📭 No data yet.")
    else:
        df_plot = df_30.copy()
        df_plot["record_date"] = pd.to_datetime(df_plot["record_date"])

        metrics = {"Serve": "serve_rate", "Return": "return_rate", "Forehand": "forehand_rate", "Backhand": "backhand_rate"}
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4"]

        fig = go.Figure()
        for (name, col), color in zip(metrics.items(), colors):
            fig.add_trace(go.Scatter(
                x=df_plot["record_date"], y=df_plot[col], mode="lines+markers", name=name,
                line=dict(color=color, width=3), marker=dict(size=8)
            ))

        fig.update_layout(
            height=450, template="plotly_white", yaxis=dict(range=[0, 105]),
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)


# -------------------- 🎯 PAGE 4: Goal Comparison --------------------
elif page == "🎯 Goal Comparison":
    st.header("🎯 Goal Comparison — Last 7 Records vs. Targets")
    st.write("Average calculated from your **last 7 records** (not necessarily consecutive days).")

    targets = {"Serve": 90, "Return": 80, "Forehand": 80, "Backhand": 80}
    cols_map = {"Serve": "serve_rate", "Return": "return_rate", "Forehand": "forehand_rate", "Backhand": "backhand_rate"}

    df_7 = get_latest_n_records(user.id, 7)

    if df_7.empty:
        st.info("📭 No records yet. Log some sessions first!")
    else:
        count = len(df_7)
        st.info(f"📊 Averaging your last **{count}** record{'s' if count != 1 else ''}.")

        avgs = {name: df_7[col].mean() for name, col in cols_map.items()}

        compare_data = []
        for name in cols_map:
            avg, target = avgs[name], targets[name]
            gap = avg - target
            status = "✅ On Target" if gap >= 0 else f"⚠️ Need +{abs(gap):.1f}%"
            compare_data.append({"Metric": name, "7-Record Avg": f"{avg:.1f}%", "Target": f"{target}%", "Gap": gap, "Status": status})

        comp_df = pd.DataFrame(compare_data)

        def highlight_status(row):
            styles = [""] * len(row)
            idx = row.index.get_loc("Status")
            styles[idx] = "background-color: #d4edda; color: #155724; font-weight: bold" if "On Target" in str(row["Status"]) \
                          else "background-color: #fff3cd; color: #856404; font-weight: bold"
            return styles

        st.dataframe(comp_df.style.apply(highlight_status, axis=1), hide_index=True, use_container_width=True)

        st.markdown("---")
        st.subheader("🕸️ Ability Radar (7-Record Average)")

        r_values = [avgs["Serve"], avgs["Return"], avgs["Forehand"], avgs["Backhand"], avgs["Serve"]]
        t_values = [targets["Serve"], targets["Return"], targets["Forehand"], targets["Backhand"], targets["Serve"]]
        theta_labels = ["Serve", "Return", "Forehand", "Backhand", "Serve"]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(r=r_values, theta=theta_labels, fill="toself", name="My Average", line_color="#FF6B6B"))
        fig_radar.add_trace(go.Scatterpolar(r=t_values, theta=theta_labels, fill="toself", name="Target", line_color="#4ECDC4"))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            height=400, margin=dict(l=30, r=30, t=30, b=30),
        )
        st.plotly_chart(fig_radar, use_container_width=True)