import streamlit as st
from auth_manager import AuthManager

class LoginApp:
    def __init__(self):
        self.auth_manager = AuthManager()
    
    def signup_form(self):
        """Display signup form"""
        st.title("📝 Sign Up - BNM App")
        
        with st.form("signup_form"):
            name = st.text_input("Full Name")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            # Multi-select for departments
            departments = st.multiselect(
                "Select Department(s)", 
                ["DST", "DST-ADMIN", "SALES"],
                help="You can select multiple departments"
            )
            
            submitted = st.form_submit_button("Sign Up")
            
            if submitted:
                # Validation
                if not all([name, email, password, confirm_password]):
                    st.error("Please fill all fields!")
                    return
                
                if password != confirm_password:
                    st.error("Passwords don't match!")
                    return
                
                if len(password) < 6:
                    st.error("Password must be at least 6 characters!")
                    return
                
                if not departments:
                    st.error("Please select at least one department!")
                    return
                
                # Attempt signup
                if self.auth_manager.signup_user(name, email, password, departments):
                    st.session_state['show_signup'] = False
                    st.rerun()
    
    def login_form(self):
        """Display login form"""
        st.title("🔐 Login - BNM App")
        
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password!")
                    return
                
                # Attempt login
                login_result = self.auth_manager.login_user(email, password)
                
                if login_result['success']:
                    user_data = login_result['user']
                    departments = login_result['departments']
                    
                    # If user has multiple departments, show selection
                    if len(departments) > 1:
                        st.session_state['pending_login'] = {
                            'user_data': user_data,
                            'departments': departments
                        }
                        st.rerun()
                    else:
                        # Single department - login directly
                        self.auth_manager.set_user_session(user_data, departments[0])
                        st.success(self.auth_manager.get_welcome_message(user_data['name'], departments[0]))
                        st.rerun()
                else:
                    st.error(login_result['message'])
    
    def department_selection_form(self):
        """Show department selection for users with multiple departments"""
        st.title("🏢 Select Department")
        
        pending_login = st.session_state.get('pending_login')
        if not pending_login:
            st.error("Session expired. Please login again.")
            if 'pending_login' in st.session_state:
                del st.session_state['pending_login']
            st.rerun()
            return
        
        user_data = pending_login['user_data']
        departments = pending_login['departments']
        
        st.write(f"Hello {user_data['name']}! You have access to multiple departments.")
        st.write("Please select which department you want to access:")
        
        with st.form("dept_selection_form"):
            selected_dept = st.selectbox("Department", departments)
            submitted = st.form_submit_button("Continue")
            
            if submitted:
                self.auth_manager.set_user_session(user_data, selected_dept)
                del st.session_state['pending_login']
                st.success(self.auth_manager.get_welcome_message(user_data['name'], selected_dept))
                st.rerun()
    
    def show_auth_interface(self):
        """Main authentication interface"""
        # SessionManager automatically loads session in __init__
        
        # Check for valid session
        if st.session_state.get('authenticated') and self.auth_manager.check_session_validity():
            return True
        
        # Handle pending department selection
        if 'pending_login' in st.session_state:
            self.department_selection_form()
            return False
        
        # Show appropriate form based on state
        if st.session_state.get('show_signup', False):
            # Show signup form
            self.signup_form()
            
            st.markdown("---")
            if st.button("Already have an account? Login"):
                st.session_state['show_signup'] = False
                st.rerun()
        else:
            # Show login form (default)
            self.login_form()
            
            st.markdown("---")
            if st.button("Don't have an account? Sign Up"):
                st.session_state['show_signup'] = True
                st.rerun()
        
        return False
        