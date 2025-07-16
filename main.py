import streamlit as st
from login import LoginApp
from auth_manager import AuthManager
from datetime import datetime
from dstadmin import DSTAdminDashboard
from dst import *

def main():
    st.set_page_config(page_title="BNM App",page_icon="🏢",layout="wide")
    
    # Initialize auth manager
    auth_manager = AuthManager()
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    
    # Show authentication interface
    login_app = LoginApp()
    
    if not login_app.show_auth_interface():
        return
    
    # User is authenticated - show appropriate dashboard
    user_id = st.session_state.get('user_id')
    user_name = st.session_state.get('user_name')
    department = st.session_state.get('department')
    
    print(f'user_id is : {user_id}, user_name is: {user_name} and departments is: {department}')
    # Add logout button in sidebar
    with st.sidebar:
        st.write(f"👤 **Name:** {user_name}")
        st.write(f"🏢 **Department:** {department}")
        st.write(f"📅 **Login time:** {datetime.fromisoformat(st.session_state.get('login_timestamp', '')):%d-%m-%Y %H:%M:%S}" if st.session_state.get('login_timestamp') else "📅 **Login time:** Unknown")
        
        # Add DST Admin navigation buttons for DST-ADMIN users only
        if department == "DST-ADMIN":            
            with st.expander("🕽️ Options", expanded=True):
                if "show_attendance" not in st.session_state:
                    st.session_state.show_attendance = False
                if "project_master" not in st.session_state:
                    st.session_state.project_master = False
                if "assign_master" not in st.session_state:
                    st.session_state.assign_master = False    

                if st.button("Attendance Masters", key="btn_attendance"):
                    st.session_state.show_attendance = True
                    st.session_state.project_master = False
                    st.session_state.assign_master = False

                if st.button("Project Masters", key="btn_projectmasters"):
                    st.session_state.project_master = True
                    st.session_state.show_attendance = False
                    st.session_state.assign_master = False

                if st.button("Assignment Masters", key="btn_assignment"):
                    st.session_state.assign_master = True
                    st.session_state.show_attendance = False
                    st.session_state.project_master = False
        
        elif department == "DST":

            with st.expander("🕽️ Options", expanded=True):

                if "show_assignment" not in st.session_state:
                    st.session_state.show_assignment = False

                if "show_summary" not in st.session_state:
                    st.session_state.show_summary = False

                if "show_timetracker" not in st.session_state:
                    st.session_state.show_timetracker = False

                if st.button("Assignment Details", key="btn_assignment"):
                    st.session_state.show_assignment = True
                    st.session_state.show_summary = False
                    st.session_state.show_timetracker = False

                if st.button("Working Summary", key="btn_summary"):
                    st.session_state.show_assignment = False
                    st.session_state.show_summary = True
                    st.session_state.show_timetracker = False 

                if st.button("Time Tracker", key="btn_timetracker"):
                    st.session_state.show_assignment = False
                    st.session_state.show_summary = False
                    st.session_state.show_timetracker = True

        elif department == "SALES":
            st.title("💰 Sales Dashboard")
            st.write(f"Welcome to Sales Dashboard, {user_name}!")
            st.info("Sales dashboard functionality will be implemented here")
            
        else:
            st.warning("⚠️ You are not authorized to access this dashboard.")

        if st.button("🚪 Logout", type="secondary"):
            auth_manager.logout_user()
    

    
    # Route to appropriate dashboard based on department
    if department == "DST-ADMIN":
        dstadmin_dashboard = DSTAdminDashboard(user_name)
        dstadmin_dashboard.show()

    elif department == "DST":
        dst_dashboard =  DstDashboard(user_id)
        dst_dashboard.show()   

    elif department == "DST":
        pass    
        

        

if __name__ == "__main__":
    main()
