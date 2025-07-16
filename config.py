import os
from supabase import create_client, Client
import streamlit as st

# Supabase configuration
SUPABASE_URL = "https://wnwentpoiswbgduyjmwb.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indud2VudHBvaXN3YmdkdXlqbXdiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTE0Mjc2ODUsImV4cCI6MjA2NzAwMzY4NX0.xKwT3FA8R4yH_6_H90QlnBnwL1A71UI_V_ERIuJvQqU"



def get_supabase_client() -> Client:
    """Initialize and return Supabase client"""
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return supabase
    except Exception as e:
        st.error(f"Error connecting to Supabase: {str(e)}")
        return None

# Initialize Supabase client
supabase = get_supabase_client()
