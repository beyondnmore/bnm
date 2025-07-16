import streamlit as st
import hashlib
from datetime import datetime, timedelta
from config import supabase
from session_manager import SessionManager

class AuthManager:
    def __init__(self):
        self.supabase = supabase
        self.session_manager = SessionManager()
        
    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def signup_user(self, name: str, email: str, password: str, departments: list) -> bool:
        """Sign up a new user with departments"""
        try:
            # Check if user already exists
            existing_user = self.supabase.table('users').select('*').eq('email', email).execute()
            if existing_user.data:
                st.error("User with this email already exists!")
                return False
            
            # Hash password
            hashed_password = self.hash_password(password)
            
            # Insert user
            user_data = {
                'name': name,
                'email': email,
                'password_hash': hashed_password,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            user_result = self.supabase.table('users').insert(user_data).execute()
            if not user_result.data:
                st.error("Failed to create user!")
                return False
            
            user_id = user_result.data[0]['id']
            
            # Insert departments
            for dept in departments:
                dept_data = {
                    'user_id': user_id,
                    'department': dept,
                    'created_at': datetime.now().isoformat()
                }
                self.supabase.table('user_departments').insert(dept_data).execute()
            
            st.success("User created successfully! Please login.")
            return True
            
        except Exception as e:
            st.error(f"Error during signup: {str(e)}")
            return False
    
    def login_user(self, email: str, password: str) -> dict:
        """Login user and return user data with departments"""
        try:
            # Hash the provided password
            hashed_password = self.hash_password(password)
            
            # Get user
            user_result = self.supabase.table('users').select('*').eq('email', email).eq('password_hash', hashed_password).execute()
            
            if not user_result.data:
                return {'success': False, 'message': 'Invalid email or password'}
            
            user = user_result.data[0]
            
            # Get user departments
            dept_result = self.supabase.table('user_departments').select('department').eq('user_id', user['id']).execute()
            
            departments = [dept['department'] for dept in dept_result.data]
            
            return {
                'success': True,
                'user': user,
                'departments': departments
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Login error: {str(e)}'}
    
    def set_user_session(self, user_data: dict, selected_department: str):
        """Set user session with 30-day persistence"""
        self.session_manager.set_persistent_session(user_data, selected_department)
    
    def check_session_validity(self) -> bool:
        """Check if current session is still valid"""
        return self.session_manager.is_session_valid()
    
    def load_existing_session(self) -> bool:
        """Load existing session from file storage"""
        return self.session_manager.load_persistent_session()
    
    def logout_user(self):
        """Logout user and clear all session data"""
        self.session_manager.clear_session()
        st.rerun()
    
    def get_welcome_message(self, name: str, department: str) -> str:
        """Generate welcome message based on department"""
        dept_messages = {
            'DST': f"🎯 Welcome {name}! You're logged into DST Dashboard",
            'DST-ADMIN': f"👑 Welcome {name}! You're logged into DST Admin Dashboard", 
            'SALES': f"💰 Welcome {name}! You're logged into Sales Dashboard"
        }
        
        return dept_messages.get(department, f"👋 Welcome {name}! You're logged into {department} Dashboard")
