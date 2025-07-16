import streamlit as st
import json
import os
import uuid
from datetime import datetime, timedelta
import hashlib

class SessionManager:
    def __init__(self):
        self.sessions_dir = "sessions"
        self.ensure_sessions_dir()
        # Force load session on every initialization
        self.auto_load_session()
    
    def ensure_sessions_dir(self):
        """Create sessions directory if it doesn't exist"""
        if not os.path.exists(self.sessions_dir):
            os.makedirs(self.sessions_dir)
    
    def get_browser_session_id(self):
        """Get or create a unique browser session ID"""
        # Use a more persistent approach
        if 'browser_session_id' not in st.session_state:
            # Try to find existing session files first
            existing_files = []
            if os.path.exists(self.sessions_dir):
                for filename in os.listdir(self.sessions_dir):
                    if filename.endswith('.json'):
                        existing_files.append(filename.replace('.json', ''))
            
            # If no existing files, create new session ID
            if not existing_files:
                st.session_state['browser_session_id'] = str(uuid.uuid4())
            else:
                # Use the first existing file (for development purposes)
                # In production, you might want a different strategy
                st.session_state['browser_session_id'] = existing_files[0]
        
        return st.session_state['browser_session_id']
    
    def set_persistent_session(self, user_data: dict, department: str):
        """Set session that persists across page refreshes"""
        browser_session_id = self.get_browser_session_id()
        expiry_date = datetime.now() + timedelta(days=30)
        
        session_data = {
            'user_id': user_data['id'],
            'user_name': user_data['name'],
            'user_email': user_data['email'],
            'department': department,
            'expiry': expiry_date.isoformat(),
            'login_time': datetime.now().isoformat(),
            'browser_session_id': browser_session_id
        }
        
        # Save to file
        session_file = os.path.join(self.sessions_dir, f"{browser_session_id}.json")
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        # Set in Streamlit session state
        st.session_state['authenticated'] = True
        st.session_state['user_id'] = user_data['id']
        st.session_state['user_name'] = user_data['name']
        st.session_state['user_email'] = user_data['email']
        st.session_state['department'] = department
        st.session_state['login_timestamp'] = datetime.now().isoformat()
        st.session_state['session_file'] = session_file
        
        print(f"Session saved to: {session_file}")  # Debug
    
    def auto_load_session(self):
        """Automatically load session on initialization"""
        if not st.session_state.get('authenticated'):
            self.load_persistent_session()
    
    def load_persistent_session(self) -> bool:
        """Load session from file on page load"""
        try:
            # Get browser session ID
            browser_session_id = self.get_browser_session_id()
            session_file = os.path.join(self.sessions_dir, f"{browser_session_id}.json")
            
            print(f"Looking for session file: {session_file}")  # Debug
            
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                
                print(f"Found session data: {session_data}")  # Debug
                
                # Check if session is expired
                expiry_date = datetime.fromisoformat(session_data['expiry'])
                if datetime.now() > expiry_date:
                    print("Session expired, clearing...")  # Debug
                    self.clear_session()
                    return False
                
                # Restore session state
                st.session_state['authenticated'] = True
                st.session_state['user_id'] = session_data['user_id']
                st.session_state['user_name'] = session_data['user_name']
                st.session_state['user_email'] = session_data['user_email']
                st.session_state['department'] = session_data['department']
                st.session_state['login_timestamp'] = session_data['login_time']
                st.session_state['session_file'] = session_file
                
                print(f"Session loaded successfully for user: {session_data['user_name']}")  # Debug
                return True
            else:
                print("No session file found")  # Debug
                return False
                
        except Exception as e:
            print(f"Error loading session: {e}")  # Debug
            self.clear_session()
            return False
    
    def validate_current_session(self) -> bool:
        """Validate the current session"""
        session_file = st.session_state.get('session_file')
        if not session_file or not os.path.exists(session_file):
            return False
        
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            # Check expiry
            expiry_date = datetime.fromisoformat(session_data['expiry'])
            if datetime.now() > expiry_date:
                return False
            
            return True
            
        except Exception:
            return False
    
    def clear_session(self):
        """Clear session from both memory and file"""
        # Remove session file
        session_file = st.session_state.get('session_file')
        if session_file and os.path.exists(session_file):
            try:
                os.remove(session_file)
                print(f"Removed session file: {session_file}")  # Debug
            except Exception as e:
                print(f"Error removing session file: {e}")  # Debug
        
        # Clear browser session file if exists
        if 'browser_session_id' in st.session_state:
            browser_session_id = st.session_state['browser_session_id']
            session_file = os.path.join(self.sessions_dir, f"{browser_session_id}.json")
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                    print(f"Removed browser session file: {session_file}")  # Debug
                except Exception as e:
                    print(f"Error removing browser session file: {e}")  # Debug
        
        # Clear Streamlit session state
        keys_to_clear = [
            'authenticated', 'user_id', 'user_name', 'user_email',
            'department', 'login_timestamp', 'session_file', 'pending_login'
        ]
        
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        
        print("Session cleared")  # Debug
    
    def is_session_valid(self) -> bool:
        """Check if current session is valid"""
        if not st.session_state.get('authenticated'):
            return False
        
        return self.validate_current_session()
    
    def cleanup_expired_sessions(self):
        """Clean up expired session files (call this periodically)"""
        if not os.path.exists(self.sessions_dir):
            return
        
        current_time = datetime.now()
        for filename in os.listdir(self.sessions_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(self.sessions_dir, filename)
                try:
                    with open(file_path, 'r') as f:
                        session_data = json.load(f)
                    
                    expiry_date = datetime.fromisoformat(session_data['expiry'])
                    if current_time > expiry_date:
                        os.remove(file_path)
                        print(f"Cleaned up expired session: {filename}")  # Debug
                        
                except Exception as e:
                    # If we can't read the file, delete it
                    try:
                        os.remove(file_path)
                        print(f"Removed corrupted session file: {filename}")  # Debug
                    except:
                        passs

