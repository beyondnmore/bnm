import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta,date
from config import supabase
from supabase import create_client
import json
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import altair as alt


ONE_SELECTION_TIME = 0.2
ONE_PRESENTATION_TIME = 0.09
ONE_QUOTATION_TIME = 0.2
ONE_SELECTION_REPETITION_TIME = 0.2
ONE_PRESENTATION_REPETITION_TIME = 0.05
ONE_QUOTATION_REPETITION_TIME = 0.09

class DSTAdminDashboard:

    def __init__(self,user_id):
        self.supabase = supabase
        self.user_id=user_id

    def show(self):
        if st.session_state.get('show_attendance', False):
            self.attendance_masters_dashboard()
        elif st.session_state.get('project_master', False):
            self.project_masters_dashboard()
        elif st.session_state.get('assign_master', False):
            self.assignment_masters_dashboard()

    def get_dst_users(self):
        try:
            if not self.supabase:
                st.error("Supabase connection not available")
                return []
            dept_response = self.supabase.table('user_departments').select('user_id').eq('department', 'DST').execute()
            if not dept_response.data:
                st.info("No users found in DST department")
                return []
            user_ids = [str(record['user_id']) for record in dept_response.data]
            if not user_ids:
                return []
            users_response = self.supabase.table('users').select('id, name').in_('id', user_ids).order('name').execute()
            if users_response.data:
                return [(user['id'], user['name']) for user in users_response.data]
            return []
        except Exception as e:
            st.error(f"Error fetching DST users: {str(e)}")
            return []

    def get_attendance_for_date_range(self, start_date, end_date):
        try:
            if not self.supabase:
                st.error("Supabase connection not available")
                return []
            start_datetime = datetime.combine(start_date, time.min)
            end_datetime = datetime.combine(end_date, time.max)
            response = self.supabase.table('attendance').select(
                'user_id, is_present, login_time, logout_time, working_time, comments, users(name)'
            ).gte('login_time', start_datetime.isoformat()).lte('login_time', end_datetime.isoformat()).execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching attendance data: {str(e)}")
            return []

    def save_attendance(self, user_id, is_present, login_time, logout_time, working_time, comments, date):
        try:
            if not self.supabase:
                st.error("Supabase connection not available")
                return False
            date_str = date.strftime('%Y-%m-%d')
            existing = self.supabase.table('attendance').select('id').eq('user_id', user_id).gte(
                'login_time', f"{date_str}T00:00:00"
            ).lt('login_time', f"{date_str}T23:59:59").execute()

            attendance_data = {
                'user_id': user_id,
                'is_present': is_present,
                'login_time': login_time.isoformat(),
                'logout_time': logout_time.isoformat(),
                'working_time': working_time,
                'comments': comments,
                'updated_at': datetime.now().isoformat()
            }

            if existing.data:
                self.supabase.table('attendance').update(attendance_data).eq('id', existing.data[0]['id']).execute()
            else:
                attendance_data['created_at'] = datetime.now().isoformat()
                self.supabase.table('attendance').insert(attendance_data).execute()

            return True
        except Exception as e:
            st.error(f"Error saving attendance: {str(e)}")
            return False

    def calculate_working_time_seconds(self, login_time, logout_time):
        if login_time and logout_time and login_time <= logout_time:
            duration = logout_time - login_time
            return int(duration.total_seconds())
        return 0

    def format_seconds_to_hms(self, seconds):
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def attendance_masters_dashboard(self):
        st.subheader("📝 Attendance Masters Dashboard")
        dst_users = self.get_dst_users()
        if not dst_users:
            st.error("No DST users found in the database.")
            return

        today = datetime.now().date()
        existing_attendance = self.get_attendance_for_date_range(today, today)
        existing_dict = {att['user_id']: att for att in existing_attendance}

        time_options = [(f"{h:02}:{m:02}", time(h, m)) for h in range(9, 17) for m in [0, 30]]
        comment_options = ["Late", "Early Leaving", "WFM"]

        if not time_options:
            st.error("⚠️ No time options available.")
            return



        with st.expander("📝 Mark Attendance", expanded=True):
            with st.form("attendance_form"):
                updated_data = []

                # 👉 Add column headers for user clarity
                col1, col2, col3, col4, col5 = st.columns([2, 1, 1.5, 1.5, 1.5])
                with col1: st.markdown("**👤 Name**")
                with col2: st.markdown("**✅ Present**")
                with col3: st.markdown("**⏰ Login Time**")
                with col4: st.markdown("**⏱ Logout Time**")
                with col5: st.markdown("**💬 Comments**")

                for user_id, name in dst_users:
                    existing = existing_dict.get(user_id, {})

                    col1, col2, col3, col4, col5 = st.columns([2, 1, 1.5, 1.5, 1.5])
                    with col1:
                        st.write(f"**{name}**")
                    with col2:
                        is_present = st.checkbox(
                            "Mark",
                            value=existing.get('is_present', False),
                            key=f"present_{user_id}",
                            label_visibility="collapsed"
                        )
                    with col3:
                        current_login = datetime.fromisoformat(existing['login_time']).time() if existing.get('login_time') else time(9, 0)
                        available_times = [s for s, _ in time_options]
                        try:
                            current_login_index = available_times.index(current_login.strftime("%H:%M"))
                        except:
                            current_login_index = 0
                        login_time_str = st.selectbox(
                            "Login Time",
                            options=available_times,
                            index=current_login_index,
                            key=f"login_{user_id}",
                            label_visibility="collapsed"
                        )
                        login_time = next(t for s, t in time_options if s == login_time_str)
                    with col4:
                        available_times = [s for s, _ in time_options]
                        if existing.get('logout_time'):
                            current_logout = datetime.fromisoformat(existing['logout_time']).time()
                            try:
                                current_logout_index = available_times.index(current_logout.strftime("%H:%M"))
                            except:
                                current_logout_index = len(available_times) - 1  # fallback to last
                        else:
                            current_logout_index = len(available_times) - 1  # default to last option

                        logout_time_str = st.selectbox(
                            "Logout Time",
                            options=available_times,
                            index=current_logout_index,
                            key=f"logout_{user_id}",
                            label_visibility="collapsed"
                        )
                        logout_time = next(t for s, t in time_options if s == logout_time_str)
                    with col5:
                        comment = st.selectbox(
                            "Comments",
                            options=comment_options,
                            index=comment_options.index(existing.get('comments', 'Late')) if existing.get('comments') in comment_options else 0,
                            key=f"comment_{user_id}",
                            label_visibility="collapsed"
                        )

                    if not is_present:
                        login_time = time(0, 0)
                        logout_time = time(0, 0)

                    login_datetime = datetime.combine(today, login_time)
                    logout_datetime = datetime.combine(today, logout_time)
                    working_time_seconds = self.calculate_working_time_seconds(login_datetime, logout_datetime) if is_present else 0

                    updated_data.append({
                        'user_id': user_id,
                        'name': name,
                        'is_present': is_present,
                        'login_time': login_datetime,
                        'logout_time': logout_datetime,
                        'working_time': working_time_seconds,
                        'comments': comment
                    })

                st.divider()
                if st.form_submit_button("✅ Submit Attendance"):
                    success_count = 0
                    for data in updated_data:
                        if self.save_attendance(
                            data['user_id'],
                            data['is_present'],
                            data['login_time'],
                            data['logout_time'],
                            data['working_time'],
                            data['comments'],
                            today
                        ):
                            success_count += 1
                    if success_count == len(updated_data):
                        st.success("✅ Attendance saved successfully.")
                        st.rerun()
                    else:
                        st.error(f"❌ Only {success_count} out of {len(updated_data)} records saved.")

        st.subheader("📊 Attendance Summary")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("📅 Start Date", value=today, key="start_date")
        with col2:
            end_date = st.date_input("📅 End Date", value=today, key="end_date")

        if start_date > end_date:
            st.error("Start date cannot be after end date.")
            return

        attendance_data = self.get_attendance_for_date_range(start_date, end_date)
        if not attendance_data:
            st.info("No attendance data found for the selected date range.")
            return

        display_data = []
        for record in attendance_data:
            login_dt = datetime.fromisoformat(record['login_time'])
            logout_dt = datetime.fromisoformat(record['logout_time'])
            display_data.append({
                'Name': record['users']['name'],
                'Present': '✅ Yes' if record['is_present'] else '❌ No',
                'Login Time': login_dt.strftime('%H:%M') if record['is_present'] else '00:00',
                'Logout Time': logout_dt.strftime('%H:%M') if record['is_present'] else '00:00',
                'Working Time': self.format_seconds_to_hms(record['working_time']),
                'Comments': record['comments'] or '',
                'Date': login_dt.strftime('%d-%m-%Y')
            })

        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        total_count = len(df)
        present_count = (df['Present'] == '✅ Yes').sum()
        absent_count = (df['Present'] == '❌ No').sum()
        total_seconds = sum(record['working_time'] for record in attendance_data)
        total_working_time = self.format_seconds_to_hms(total_seconds)

        st.markdown("---")
        st.markdown(f"""
        ### 📈 Summary for {start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}
        - 👥 **Total Employees**: {total_count}
        - ✅ **Present**: {present_count}
        - ❌ **Absent**: {absent_count}
        - ⏱️ **Total Working Hours**: {total_working_time}
        """)

    def project_masters_dashboard(self):

        user_id = self.user_id

        st.subheader("📝 Enter the Project Details")
        col1, col2 = st.columns(2)

        with col1:
            status_filter = st.selectbox("📌 Filter by Status", ["Pending", "Completed"])

        # Fetch data from Supabase
        response = supabase.table("project_masters").select("*").eq("status", status_filter).order("created_at", desc=True).execute()
        df = pd.DataFrame(response.data)

        with col2:
            project_codes = sorted(df["project_code"].unique()) if not df.empty else []
            project_code_filter = st.selectbox("🔎 Filter by Project Code", ["All"] + project_codes)

        if project_code_filter != "All":
            df = df[df["project_code"] == project_code_filter]

        # ---------------- Chart 1: Counts ----------------
        count_columns = {
            "selection_count": "SC",
            "presentation_count": "PC",
            "quotation_count": "QC",
            "selection_repetition_count": "SRC",
            "presentation_repetition_count": "PRC",
            "quotation_repetition_count": "QRC"
        }

        count_legends = {
            "SC": "Selection Count",
            "PC": "Presentation Count",
            "QC": "Quotation Count",
            "SRC": "Selection Repetition Count",
            "PRC": "Presentation Repetition Count",
            "QRC": "Quotation Repetition Count"
        }

        try:
            count_data = {label: df[col].sum() for col, label in count_columns.items()}
        except Exception:
            count_data = {label: 0 for label in count_columns.values()}

        count_fig = go.Figure()
        for label, value in count_data.items():
            count_fig.add_trace(go.Bar(
                name=label,
                x=[label],
                y=[value],
                text=[value],
                textposition="outside",
                hovertext=count_legends.get(label, label)
            ))

        count_fig.update_layout(
            title="Project Activity Counts",
            yaxis_title="Count",
            showlegend=False,
            height=400
        )

        # ---------------- Chart 2: Estimated Time ----------------
        time_columns = {
            "selection_estimated_time": "SET",
            "presentation_estimated_time": "PET",
            "quotation_estimated_time": "QET",
            "selection_repetition_estimated_time": "SRET",
            "presentation_repetition_estimated_time": "PRET",
            "quotation_repetition_estimated_time": "QRET"
        }

        time_legends = {
            "SET": "Selection Estimated Time",
            "PET": "Presentation Estimated Time",
            "QET": "Quotation Estimated Time",
            "SRET": "Selection Repetition Estimated Time",
            "PRET": "Presentation Repetition Estimated Time",
            "QRET": "Quotation Repetition Estimated Time"
        }

        try:
            time_data = {label: df[col].sum() for col, label in time_columns.items()}
        except Exception:
            time_data = {label: 0 for label in time_columns.values()}

        time_fig = go.Figure()
        for label, total_seconds in time_data.items():
            try:
                hms = self.format_seconds_to_hms(total_seconds)
            except Exception:
                hms = "00:00:00"

            full_label = time_legends.get(label, label)

            time_fig.add_trace(go.Bar(
                name=label,
                x=[label],
                y=[total_seconds],
                text=[hms],
                textposition="outside",
                hovertemplate=f"<b>{full_label}</b><br>Seconds: {total_seconds}<br>HH:MM:SS: {hms}<extra></extra>"
            ))

        time_fig.update_layout(
            title="Estimated Times",
            yaxis_title="Seconds",
            showlegend=False,
            height=400
        )

        # ---------------- Display Side by Side ----------------
        col3, col4 = st.columns(2)
        with col3:
            st.plotly_chart(count_fig, use_container_width=True)
        with col4:
            st.plotly_chart(time_fig, use_container_width=True)

        with st.expander("➕ Enter New Project", expanded=False):
            with st.form("project_entry_form", clear_on_submit=True):
                project_code = st.text_input("Project Code")
                got_date = st.date_input("Date Got")
                required_date = st.date_input("Date Required")
                commited_date = st.date_input("Date Commited")

                selection_count = st.number_input("Selection Count", min_value=0, step=1)
                presentation_count = st.number_input("Presentation Count", min_value=0, step=1)
                quotation_count = st.number_input("Quotation Counts", min_value=0, step=1)

                selection_repetition_count = st.number_input("Selection Repetition Count", min_value=0, step=1)
                presentation_repetition_count = st.number_input("Presentation Repetition Count", min_value=0, step=1)
                quotation_repetition_count = st.number_input("Quotation Repetition Count", min_value=0, step=1)

                remarks = st.text_area("📝 Enter Remarks / Notes", height=150)
                status = st.selectbox("📌 Status", ["Pending", "Completed"])

                def h2s(count, base):
                    return int((count * base) *3600) if count else 0

                selection_estimated_time = h2s(selection_count, ONE_SELECTION_TIME)
                presentation_estimated_time = h2s(presentation_count, ONE_PRESENTATION_TIME)
                quotation_estimated_time = h2s(quotation_count, ONE_QUOTATION_TIME)

                selection_repetition_estimated_time = h2s(selection_repetition_count, ONE_SELECTION_REPETITION_TIME)
                presentation_repetition_estimated_time = h2s(presentation_repetition_count, ONE_PRESENTATION_REPETITION_TIME)
                quotation_repetition_estimated_time = h2s(quotation_repetition_count, ONE_QUOTATION_REPETITION_TIME)

                total_estimated_time = sum([
                    selection_estimated_time,
                    presentation_estimated_time,
                    quotation_estimated_time,
                    selection_repetition_estimated_time,
                    presentation_repetition_estimated_time,
                    quotation_repetition_estimated_time
                ])

                submitted = st.form_submit_button("Submit")
                if submitted:
                    if not project_code or not got_date or not required_date or not status:
                        st.warning("Project Code, Dates and Status are required.")
                    else:
                        data = {
                            "project_code": project_code,
                            "got_date": got_date.isoformat(),
                            "required_date": required_date.isoformat(),
                            "commited_date": commited_date.isoformat(),

                            "selection_count": selection_count,
                            "selection_estimated_time": selection_estimated_time,

                            "presentation_count": presentation_count,
                            "presentation_estimated_time": presentation_estimated_time,

                            "quotation_count": quotation_count,
                            "quotation_estimated_time": quotation_estimated_time,

                            "selection_repetition_count": selection_repetition_count,
                            "selection_repetition_estimated_time": selection_repetition_estimated_time,

                            "presentation_repetition_count": presentation_repetition_count,
                            "presentation_repetition_estimated_time": presentation_repetition_estimated_time,

                            "quotation_repetition_count": quotation_repetition_count,
                            "quotation_repetition_estimated_time": quotation_repetition_estimated_time,

                            "total_estimated_time": total_estimated_time,
                            "remarks": remarks,
                            "status": status,
                            "details": {}
                        }
                        supabase.table("project_masters").insert(data).execute()
                        st.success("✅ Project added successfully!")


        if "confirm_update" not in st.session_state:
            st.session_state.confirm_update = False
        if "reset_confirm_update" not in st.session_state:
            st.session_state.reset_confirm_update = False

        if st.session_state.reset_confirm_update:
            st.session_state.confirm_update = False
            st.session_state.reset_confirm_update = False


        with st.expander("✏️ Edit Existing Project", expanded=False):

            if df.empty:
                st.info("ℹ️ No project data available to edit.")
            else:
                selected_code = st.selectbox("Select Project Code to Edit", df["project_code"].unique())
                row = df[df["project_code"] == selected_code].iloc[0]

                with st.form("edit_project_form"):
                    st.write("### ✍️ Edit Project")

                    got_date = st.date_input("Date Got", pd.to_datetime(row["got_date"], dayfirst=True))
                    required_date = st.date_input("Date Required", pd.to_datetime(row["required_date"], dayfirst=True))
                    commited_date = st.date_input("Date Commited", pd.to_datetime(row["commited_date"], dayfirst=True))

                    # Quotation Section
                    quotation_count = st.number_input("Quotation Counts", min_value=0, step=1, value=int(row["quotation_count"]))
                    
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col1:
                        st.write("**Quotation Time Settings**")
                        
                    with col2:
                        default_quotation_estimated_time = max(int(h2s(quotation_count, ONE_QUOTATION_TIME)), 0)  # Ensure minimum 0
                        quotation_estimated_time_int = st.number_input("Quotation Time (Second)", min_value=0, step=300, value=default_quotation_estimated_time)
                        
                    with col3:
                        quotation_estimated_time_str = st.text_input("Quotation Time (HH:MM:SS)", value=self.format_seconds_to_hms(quotation_estimated_time_int), disabled=True)

                    # Presentation Section
                    presentation_count = st.number_input("Presentation Count", min_value=0, step=1, value=int(row["presentation_count"]))
                    
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col1:
                        st.write("**Presentation Time Settings**")
                        
                    with col2:
                        default_presentation_estimated_time = max(int(h2s(presentation_count, ONE_PRESENTATION_TIME)), 0)  # Ensure minimum 0
                        presentation_estimated_time_int = st.number_input("Presentation Time (Second)", min_value=0, step=1800, value=default_presentation_estimated_time)

                    with col3:
                        presentation_estimated_time_str = st.text_input("Presentation Time (HH:MM:SS)", value=self.format_seconds_to_hms(presentation_estimated_time_int), disabled=True)

                    # Selection Section
                    selection_count = st.number_input("Selection Count", min_value=0, step=1, value=int(row["selection_count"]))
                    
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col1:
                        st.write("**Selection Time Settings**")
                        
                    with col2:
                        default_selection_estimated_time = max(int(h2s(selection_count, ONE_SELECTION_TIME)), 0)  # Ensure minimum 0
                        selection_estimated_time_int = st.number_input("Selection Time (Second)", min_value=0, step=480, value=default_selection_estimated_time)
                        
                    with col3:
                        selection_estimated_time_str = st.text_input("Selection Time (HH:MM:SS)", value=self.format_seconds_to_hms(selection_estimated_time_int), disabled=True)

                    # Selection Repetition Section
                    selection_repetition_count = st.number_input("Selection Repetition Count", min_value=0, step=1, value=int(row["selection_repetition_count"]))
                    
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col1:
                        st.write("**Selection Repetition Time Settings**")
                        
                    with col2:
                        default_selection_repetition_estimated_time = max(int(h2s(selection_repetition_count, ONE_SELECTION_REPETITION_TIME)), 0)  # Ensure minimum 0
                        selection_repetition_estimated_time_int = st.number_input("Selection Repetition Time (Second)", min_value=0, step=360, value=default_selection_repetition_estimated_time)
                        
                    with col3:
                        selection_repetition_estimated_time_str = st.text_input("Selection Repetition Time (HH:MM:SS)", value=self.format_seconds_to_hms(selection_repetition_estimated_time_int), disabled=True)

                    # Presentation Repetition Section
                    presentation_repetition_count = st.number_input("Presentation Repetition Count", min_value=0, step=1, value=int(row["presentation_repetition_count"]))
                    
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col1:
                        st.write("**Presentation Repetition Time Settings**")
                        
                    with col2:
                        default_presentation_repetition_estimated_time = max(int(h2s(presentation_repetition_count, ONE_PRESENTATION_REPETITION_TIME)), 0)  # Ensure minimum 0
                        presentation_repetition_estimated_time_int = st.number_input("Presentation Repetition Time (Second)", min_value=0, step=600, value=default_presentation_repetition_estimated_time)
                        
                    with col3:
                        presentation_repetition_estimated_time_str = st.text_input("Presentation Repetition Time (HH:MM:SS)", value=self.format_seconds_to_hms(presentation_repetition_estimated_time_int), disabled=True)

                    # Quotation Repetition Section
                    quotation_repetition_count = st.number_input("Quotation Repetition Count", min_value=0, step=1, value=int(row["quotation_repetition_count"]))
                    
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col1:
                        st.write("**Quotation Repetition Time Settings**")
                        
                    with col2:
                        default_quotation_repetition_estimated_time = max(int(h2s(quotation_repetition_count, ONE_QUOTATION_REPETITION_TIME)), 0)  # Ensure minimum 0
                        quotation_repetition_estimated_time_int = st.number_input("Quotation Repetition Time (Second)", min_value=0, step=240, value=default_quotation_repetition_estimated_time)
                        
                    with col3:
                        quotation_repetition_estimated_time_str = st.text_input("Quotation Repetition Time (HH:MM:SS)", value=self.format_seconds_to_hms(quotation_repetition_estimated_time_int), disabled=True)

                    remarks = st.text_area("📝 Enter Remarks / Notes", height=150, value=row["remarks"])
                    status = st.selectbox("📌 Status", ["Pending", "Completed"], index=["Pending", "Completed"].index(row["status"]))

                    confirm_update = st.checkbox("✅ I confirm the changes are correct.", key="confirm_update")

                    submitted_edit = st.form_submit_button("💾 Save Changes")

                    if submitted_edit and confirm_update:
                        total_estimated_time = (
                            quotation_estimated_time_int + presentation_estimated_time_int +
                            selection_estimated_time_int + selection_repetition_estimated_time_int +
                            presentation_repetition_estimated_time_int + quotation_repetition_estimated_time_int
                        )

                        has_changes = (
                            row["got_date"] != got_date.isoformat() or
                            row["required_date"] != required_date.isoformat() or
                            row["commited_date"] != commited_date.isoformat() or
                            row["quotation_count"] != quotation_count or
                            row["quotation_estimated_time"] != quotation_estimated_time_int or
                            row["presentation_count"] != presentation_count or
                            row["presentation_estimated_time"] != presentation_estimated_time_int or
                            row["selection_count"] != selection_count or
                            row["selection_estimated_time"] != selection_estimated_time_int or
                            row["selection_repetition_count"] != selection_repetition_count or
                            row["selection_repetition_estimated_time"] != selection_repetition_estimated_time_int or
                            row["presentation_repetition_count"] != presentation_repetition_count or
                            row["presentation_repetition_estimated_time"] != presentation_repetition_estimated_time_int or
                            row["quotation_repetition_count"] != quotation_repetition_count or
                            row["quotation_repetition_estimated_time"] != quotation_repetition_estimated_time_int or
                            row["total_estimated_time"] != total_estimated_time or
                            row["remarks"] != remarks or
                            row["status"] != status
                        )

                        existing_details = row.get("details") or {}
                        if isinstance(existing_details, str):
                            try:
                                existing_details = json.loads(existing_details)
                            except:
                                existing_details = {}

                        if has_changes:
                            timestamp = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
                            previous_data = {
                                "project_code": str(row["project_code"]),
                                "got_date": str(row["got_date"]),
                                "required_date": str(row["required_date"]),
                                "commited_date": str(row["commited_date"]),
                                "quotation_count": int(row["quotation_count"]),
                                "quotation_estimated_time": int(row["quotation_estimated_time"]),
                                "presentation_count": int(row["presentation_count"]),
                                "presentation_estimated_time": int(row["presentation_estimated_time"]),
                                "selection_count": int(row["selection_count"]),
                                "selection_estimated_time": int(row["selection_estimated_time"]),
                                "selection_repetition_count": int(row["selection_repetition_count"]),
                                "selection_repetition_estimated_time": int(row["selection_repetition_estimated_time"]),
                                "presentation_repetition_count": int(row["presentation_repetition_count"]),
                                "presentation_repetition_estimated_time": int(row["presentation_repetition_estimated_time"]),
                                "quotation_repetition_count": int(row["quotation_repetition_count"]),
                                "quotation_repetition_estimated_time": int(row["quotation_repetition_estimated_time"]),
                                "total_estimated_time": int(row["total_estimated_time"]),
                                "remarks": str(row["remarks"]),
                                "status": str(row["status"])
                            }

                            log_entry = {
                                "user_id": user_id,
                                "previous_data": previous_data
                            }

                            existing_details[timestamp] = log_entry

                        safe_details = json.loads(json.dumps(existing_details, default=lambda o: int(o) if isinstance(o, (int, float)) else str(o)))

                        updated_data = {
                            "got_date": got_date.isoformat(),
                            "required_date": required_date.isoformat(),
                            "commited_date": commited_date.isoformat(),

                            "quotation_count": quotation_count,
                            "quotation_estimated_time": quotation_estimated_time_int,

                            "presentation_count": presentation_count,
                            "presentation_estimated_time": presentation_estimated_time_int,

                            "selection_count": selection_count,
                            "selection_estimated_time": selection_estimated_time_int,

                            "selection_repetition_count": selection_repetition_count,
                            "selection_repetition_estimated_time": selection_repetition_estimated_time_int,

                            "presentation_repetition_count": presentation_repetition_count,
                            "presentation_repetition_estimated_time": presentation_repetition_estimated_time_int,

                            "quotation_repetition_count": quotation_repetition_count,
                            "quotation_repetition_estimated_time": quotation_repetition_estimated_time_int,

                            "total_estimated_time": total_estimated_time,
                            "remarks": remarks,
                            "status": status,
                            "details": safe_details,
                            "updated_at": datetime.utcnow().isoformat()
                        }

                        supabase.table("project_masters").update(updated_data).eq("project_code", selected_code).execute()
                        st.success("✅ Project updated successfully!")
                        st.session_state.reset_confirm_update = True
                        st.rerun()

                    elif submitted_edit and not confirm_update:
                        st.warning("⚠️ Please confirm your changes before saving.")

    def assignment_masters_dashboard(self):
        st.subheader("📋 Assignment Masters")

        def fetch_project_masters():
            return pd.DataFrame(supabase.table("project_masters")
            .select("id","project_code",
            "selection_count","selection_estimated_time",
            "presentation_count","presentation_estimated_time",
            "quotation_count","quotation_estimated_time",
            "selection_repetition_count","selection_repetition_estimated_time",
            "presentation_repetition_count","presentation_repetition_estimated_time",
            "quotation_repetition_count","quotation_repetition_estimated_time",
            "total_estimated_time"
            )
            .eq("status", "Pending")
            .execute()
            .data)

        def fetch_assigned_masters():
            data = supabase.table("assigned_masters") \
                .select(
                    "id","date","user_id","project_id",
                    "selection_assigned_count","selection_assigned_estimated_time",
                    "presentation_assigned_count","presentation_assigned_estimated_time",
                    "quotation_assigned_count","quotation_assigned_estimated_time",
                    "selection_repetition_assigned_count","selection_repetition_assigned_estimated_time",
                    "presentation_repetition_assigned_count","presentation_repetition_assigned_estimated_time",
                    "quotation_repetition_assigned_count","quotation_repetition_assigned_estimated_time",
                    "total_assigned_estimated_time","other_time","working_time",
                    "users(id, name)", "project_masters(id, project_code)"
                ) \
                .execute().data

            if not data:
                # Return empty DataFrame with expected columns
                return pd.DataFrame(columns=[
                    "id", "date", "user_id", "project_id",
                    "selection_assigned_count", "selection_assigned_estimated_time",
                    "presentation_assigned_count", "presentation_assigned_estimated_time",
                    "quotation_assigned_count", "quotation_assigned_estimated_time",
                    "selection_repetition_assigned_count", "selection_repetition_assigned_estimated_time",
                    "presentation_repetition_assigned_count", "presentation_repetition_assigned_estimated_time",
                    "quotation_repetition_assigned_count", "quotation_repetition_assigned_estimated_time",
                    "total_assigned_estimated_time", "other_time", "working_time",
                    "users", "project_masters"
                ])
            
            return pd.DataFrame(data)

        def fetch_attendance():
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)

            response = supabase.table("attendance") \
                .select("user_id, working_time, users(id, name, user_departments(department))") \
                .eq("is_present", True) \
                .gte("login_time", today.isoformat()) \
                .lt("login_time", tomorrow.isoformat()) \
                .execute()

            return pd.DataFrame(response.data)

        def sum_column_as_int(df, column_name):
            return int(df[column_name].sum()) if not df.empty and column_name in df and not df[column_name].isnull().all() else 0

        project_masters_df = fetch_project_masters()
        #st.dataframe(project_masters_df)
        
        assigned_masters_df = fetch_assigned_masters()
        assigned_masters_df["project_code"] = assigned_masters_df["project_masters"].apply(lambda x: x["project_code"])
        assigned_masters_df["name"] = assigned_masters_df["users"].apply(lambda x: x["name"])
        assigned_masters_df.drop(columns=["users"], inplace=True)
        assigned_masters_df.drop(columns=["project_masters"], inplace=True)

        attendance_df = fetch_attendance()
        if attendance_df.empty:
            st.info("Plz Mark the attendance from the Attendance tab.")
        else:    
            attendance_df["name"] = attendance_df["users"].apply(lambda x: x.get("name", ""))
            attendance_df["department"] = attendance_df["users"].apply(
                lambda x: [d["department"] for d in x.get("user_departments", [])]
            )
            attendance_df = attendance_df.drop(columns=["users"]).explode("department")
            attendance_df = attendance_df[attendance_df["department"] == "DST"]


        def seconds_to_hms(seconds):
            """Convert seconds to HH:MM:SS format"""
            if pd.isna(seconds) or seconds == 0:
                return "00:00:00"
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            seconds = int(seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        tab1, tab2 = st.tabs(["🧑‍💻Assigned Details", "📝Unassigned Details"])

        with tab1:
            if assigned_masters_df.empty:
                st.warning("No Assigned Data to Display")
            else:
                print(f'assigned_masters_df: {assigned_masters_df.columns}')
                assigned_masters_df = assigned_masters_df[['date','project_code','name','working_time','total_assigned_estimated_time', 'other_time',
                'selection_assigned_count','selection_assigned_estimated_time',
                'presentation_assigned_count','presentation_assigned_estimated_time', 
                'quotation_assigned_count','quotation_assigned_estimated_time',
                'selection_repetition_assigned_count','selection_repetition_assigned_estimated_time',
                'presentation_repetition_assigned_count','presentation_repetition_assigned_estimated_time',
                'quotation_repetition_assigned_count','quotation_repetition_assigned_estimated_time'
                ]]
                # time_columns = [col for col in assigned_masters_df.columns if 'time' in col and col.endswith(('working_time', 'estimated_time'))]
                # assigned_masters_df[time_columns] = assigned_masters_df[time_columns].apply(
                # lambda col: [self.format_seconds_to_hms(x) for x in col])

                display_df = assigned_masters_df.copy()
                time_columns = [col for col in display_df.columns if 'time' in col ]
                for col in time_columns:
                    if col in display_df.columns:
                        display_df[col] = display_df[col].apply(seconds_to_hms)
                
                st.dataframe(display_df)

        with tab2:
            if project_masters_df.empty:
                st.warning("No data to display.")
            else:
                unique_project_codes = project_masters_df['project_code'].unique()
                unassigned_summary_list = []

                for project_code in unique_project_codes:
                    filter_assigned_masters_df = assigned_masters_df[assigned_masters_df['project_code'] == project_code] if not assigned_masters_df.empty else pd.DataFrame()
                    filter_project_masters_df= project_masters_df[project_masters_df['project_code'] == project_code]

                    # Assignment Task Count and estimated time by project_code
                    selection_assigned_count = sum_column_as_int(filter_assigned_masters_df, "selection_assigned_count")
                    selection_assigned_estimated_time = sum_column_as_int(filter_assigned_masters_df, "selection_assigned_estimated_time")

                    presentation_assigned_count = sum_column_as_int(filter_assigned_masters_df, "presentation_assigned_count")
                    presentation_assigned_estimated_time = sum_column_as_int(filter_assigned_masters_df, "presentation_assigned_estimated_time")

                    quotation_assigned_count = sum_column_as_int(filter_assigned_masters_df, "quotation_assigned_count")
                    quotation_assigned_estimated_time = sum_column_as_int(filter_assigned_masters_df, "quotation_assigned_estimated_time")
                    
                    selection_repetition_assigned_count = sum_column_as_int(filter_assigned_masters_df, "selection_repetition_assigned_count")
                    selection_repetition_assigned_estimated_time = sum_column_as_int(filter_assigned_masters_df, "selection_repetition_assigned_estimated_time")

                    presentation_repetition_assigned_count = sum_column_as_int(filter_assigned_masters_df, "presentation_repetition_assigned_count")
                    presentation_repetition_assigned_estimated_time = sum_column_as_int(filter_assigned_masters_df, "presentation_repetition_assigned_estimated_time")

                    quotation_repetition_assigned_count = sum_column_as_int(filter_assigned_masters_df, "quotation_repetition_assigned_count")
                    quotation_repetition_assigned_estimated_time = sum_column_as_int(filter_assigned_masters_df, "quotation_repetition_assigned_estimated_time")

                    total_assigned_count = selection_assigned_count+presentation_assigned_count+quotation_assigned_count+selection_repetition_assigned_count+presentation_repetition_assigned_count+quotation_repetition_assigned_count
                    total_assigned_estimated_time = sum_column_as_int(filter_assigned_masters_df, "total_assigned_estimated_time")


                    # Task count and Estimated Time by Project code and we are fetching the data from the project_masters table.

                    selection_count = sum_column_as_int(filter_project_masters_df, "selection_count")
                    selection_estimated_time = sum_column_as_int(filter_project_masters_df, "selection_estimated_time")

                    presentation_count = sum_column_as_int(filter_project_masters_df, "presentation_count")
                    presentation_estimated_time = sum_column_as_int(filter_project_masters_df, "presentation_estimated_time")

                    quotation_count = sum_column_as_int(filter_project_masters_df, "quotation_count")
                    quotation_estimated_time = sum_column_as_int(filter_project_masters_df, "quotation_estimated_time")

                    selection_repetition_count = sum_column_as_int(filter_project_masters_df, "selection_repetition_count")
                    selection_repetition_estimated_time = sum_column_as_int(filter_project_masters_df, "selection_repetition_estimated_time")

                    presentation_repetition_count = sum_column_as_int(filter_project_masters_df, "presentation_repetition_count")
                    presentation_repetition_estimated_time = sum_column_as_int(filter_project_masters_df, "presentation_repetition_estimated_time")

                    quotation_repetition_count = sum_column_as_int(filter_project_masters_df, "quotation_repetition_count")
                    quotation_repetition_estimated_time = sum_column_as_int(filter_project_masters_df, "quotation_repetition_estimated_time")

                    total_count = selection_count+presentation_count+quotation_count+selection_repetition_count+presentation_repetition_count+quotation_repetition_count
                    total_estimated_time = sum_column_as_int(filter_project_masters_df, "total_estimated_time")

                    unassigned_summary = {
                        'project_code':project_code,

                        'selection_unassigned_count' : selection_count - selection_assigned_count,
                        'selection_unassigned_estimated_time' : selection_estimated_time- selection_assigned_estimated_time,

                        'presentation_unassigned_count' : presentation_count - presentation_assigned_count,
                        'presentation_unassigned_estimated_time' : presentation_estimated_time - presentation_assigned_estimated_time,

                        'quotation_unassigned_count' : quotation_count - quotation_assigned_count,
                        'quotation_unassigned_estimated_time' : quotation_estimated_time - quotation_assigned_estimated_time,

                        'selection_repetition_unassigned_count' : selection_repetition_count - selection_repetition_assigned_count,
                        'selection_repetition_unassigned_estimated_time' : selection_repetition_estimated_time - selection_repetition_assigned_estimated_time,

                        'presentation_repetition_unassigned_count' : presentation_repetition_count - presentation_repetition_assigned_count,
                        'presentation_repetition_unassigned_estimated_time' : presentation_repetition_estimated_time - presentation_repetition_assigned_estimated_time,

                        'quotation_repetition_unassigned_count' : quotation_repetition_count - quotation_repetition_assigned_count,
                        'quotation_repetition_unassigned_estimated_time' : quotation_repetition_assigned_estimated_time - quotation_repetition_assigned_estimated_time,

                        'total_unassigned_count' : total_count - total_assigned_count,
                        'total_unassigned_estimated_time' :total_estimated_time - total_assigned_estimated_time                    
                    }
                    unassigned_summary_list.append(unassigned_summary)

                unassigned_df = pd.DataFrame(unassigned_summary_list)
                unassigned_df = pd.DataFrame(unassigned_summary_list)
                col1, col2 = st.columns([1.5, 1.5])
                with col1:
                    project_code_filter = st.selectbox(
                        "Filter by Project Code",
                        options=["All"] + sorted(unassigned_df['project_code'].unique())
                    )

                with col2:
                    show_details = st.selectbox(
                        "Show All Details",
                        options=["No", "Yes"],
                        index=0  # default to "No"
                    )

                if project_code_filter != "All":
                    filtered_df = unassigned_df[unassigned_df['project_code'] == project_code_filter]
                else:
                    filtered_df = unassigned_df

                filtered_df['total_unassigned_estimated_time'] = filtered_df['total_unassigned_estimated_time'].apply(self.format_seconds_to_hms)

                if show_details == "Yes":
                    display_cols = [
                        'project_code','selection_unassigned_count','presentation_unassigned_count',
                        'quotation_unassigned_count','selection_repetition_unassigned_count',
                        'presentation_repetition_unassigned_count','quotation_repetition_unassigned_count',
                        'total_unassigned_count','total_unassigned_estimated_time'
                    ]
                else:
                    display_cols = ['project_code','total_unassigned_count','total_unassigned_estimated_time']

                # Show result
                st.dataframe(filtered_df[display_cols])
            attendance_df = fetch_attendance()


        tab3, tab4 = st.tabs(["➕ New Assignment", "✏️ Edit Assignment"])

        with tab3:            
            st.write("New Assignment Tab is responsible for Assigning Task to Designer.")
            if project_masters_df.empty:
                st.warning("No pending projects found.")
                return

            if attendance_df.empty:
                st.warning("No Designer Present to assign.")
                return

            # Helper function to convert seconds to HH:MM:SS
            def seconds_to_hms(seconds):
                """Convert seconds to HH:MM:SS format"""
                if pd.isna(seconds) or seconds == 0:
                    return "00:00:00"
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                seconds = int(seconds % 60)
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            # Helper function to convert HH:MM:SS to seconds
            def hms_to_seconds(time_str):
                """Convert HH:MM:SS format to seconds"""
                if pd.isna(time_str) or time_str == "00:00:00":
                    return 0
                h, m, s = map(int, time_str.split(':'))
                return h * 3600 + m * 60 + s

            project_code_list = list(project_masters_df['project_code'].unique())    
            project_code = st.selectbox("🏷️ Project Code", project_code_list)
            selected_project = project_masters_df[project_masters_df['project_code'] == project_code].iloc[0]

            # Get today's date for filtering existing assignments
            today_date = datetime.now().date()
            
            # Get existing assignments for today and this project
            try:
                today_str = date.today().strftime('%Y-%m-%d')
                existing_assignments = (
                    supabase
                    .table("assigned_masters")
                    .select("user_id")
                    .eq("project_id", selected_project['id'])
                    .eq("date", today_str)
                    .execute()
                )
                assigned_user_ids = [assignment['user_id'] for assignment in existing_assignments.data] if existing_assignments.data else []
            except Exception as e:
                st.error(f"Error fetching existing assignments: {str(e)}")
                assigned_user_ids = []            

            # Filter present designers to exclude already assigned ones
            present_designers = []
            designer_working_hours = {}

            for record in attendance_df.itertuples():
                user_info = record.users
                departments = [d['department'] for d in user_info.get("user_departments", [])]
                
                if "DST" in departments:
                    user_id = user_info["id"]
                    
                    # Skip if user is already assigned to this project today
                    if user_id not in assigned_user_ids:
                        user_name = user_info["name"]
                        working_time = record.working_time

                        present_designers.append({
                            "user_id": user_id,
                            "name": user_name,
                            "working_time": working_time
                        })
                        designer_working_hours[user_id] = working_time

            # Check if any designers are available after filtering
            if not present_designers:
                st.warning("No designers available for assignment (all present designers have already been assigned to this project today).")
                #return

            else:
                num_designers = len(present_designers)
                
                # Initialize assignment data with filtered designers
                if 'assignment_data' not in st.session_state or st.session_state.get('current_project_code') != project_code:
                    assignment_data = []
                    for item in present_designers:
                        assignment_data.append({
                            'user_id': item['user_id'],
                            'Name': item['name'],
                            'Total Workday Hours': int(item['working_time']),
                            'Selection Count': 0,
                            'Presentation Count': 0,
                            'Quotation Count': 0,
                            'Selection Repetition Count': 0,
                            'Presentation Repetition Count': 0,
                            'Quotation Repetition Count': 0,
                            'Live Time Assigned': 0,
                            'Other Time Assigned': int(item['working_time'])
                        })
                
                    st.session_state.assignment_data = pd.DataFrame(assignment_data)
                    st.session_state.current_project_code = project_code
                
                # Function to calculate times (optimized)
                def calculate_times(df):
                    """Calculate live time and other time based on assignment counts"""
                    df_copy = df.copy()
                    
                    # Get per-unit times from project master (convert seconds to hours)
                    unit_times = {
                        'selection': (ONE_SELECTION_TIME*3600),
                        'presentation':(ONE_PRESENTATION_TIME*3600) ,
                        'quotation': (ONE_QUOTATION_TIME*3600),
                        'selection_rep': (ONE_SELECTION_REPETITION_TIME*3600),
                        'presentation_rep': (ONE_PRESENTATION_REPETITION_TIME*3600),
                        'quotation_rep': (ONE_QUOTATION_REPETITION_TIME*3600),
                    }
                    
                    for i in range(len(df_copy)):
                        # Calculate time for each task type
                        live_time = (
                            df_copy.loc[i, 'Selection Count'] * unit_times['selection'] +
                            df_copy.loc[i, 'Presentation Count'] * unit_times['presentation'] +
                            df_copy.loc[i, 'Quotation Count'] * unit_times['quotation'] +
                            df_copy.loc[i, 'Selection Repetition Count'] * unit_times['selection_rep'] +
                            df_copy.loc[i, 'Presentation Repetition Count'] * unit_times['presentation_rep'] +
                            df_copy.loc[i, 'Quotation Repetition Count'] * unit_times['quotation_rep']
                        )
                        
                        live_time = int(live_time)
                        total_workday_hours = df_copy.loc[i, 'Total Workday Hours']
                        
                        # Calculate other time
                        other_time = int(max(0, (total_workday_hours - live_time)))
                        
                        df_copy.loc[i, 'Live Time Assigned'] = live_time
                        df_copy.loc[i, 'Other Time Assigned'] = other_time
                    
                    return df_copy

                # Function to remove assigned users from the dataframe
                def remove_assigned_users(df, assigned_user_ids):
                    """Remove users who have been assigned from the dataframe"""
                    return df[~df['user_id'].isin(assigned_user_ids)]

                # Conditional formatting for overassigned time
                def highlight_live_time_editor(row):
                    # Convert HH:MM:SS back to seconds for comparison
                    live_time_str = row['Live Time Assigned']
                    total_workday_str = row['Total Workday Hours']
                    
                    live_time_seconds = hms_to_seconds(live_time_str)
                    total_workday_seconds = hms_to_seconds(total_workday_str)
                    
                    if live_time_seconds > total_workday_seconds:
                        return ['background-color: #ffcccc; color: #cc0000; font-weight: bold' if col == 'Live Time Assigned' else '' for col in row.index]
                    return ['' for _ in row.index]

                # Create display copy of assignment data
                display_assignment_df = st.session_state.assignment_data.copy()

                # Convert time columns from seconds to HH:MM:SS for display
                display_assignment_df['Total Workday Hours'] = display_assignment_df['Total Workday Hours'].apply(seconds_to_hms)
                display_assignment_df['Live Time Assigned'] = display_assignment_df['Live Time Assigned'].apply(seconds_to_hms)
                display_assignment_df['Other Time Assigned'] = display_assignment_df['Other Time Assigned'].apply(seconds_to_hms)

                # Apply styling to the display dataframe
                styled_df = display_assignment_df.style.apply(highlight_live_time_editor, axis=1)

                # Display data editor
                edited_df = st.data_editor(
                    styled_df,
                    column_config={
                        "user_id": st.column_config.TextColumn("User ID", disabled=True),
                        "Name": st.column_config.TextColumn("Name", disabled=True),
                        "Total Workday Hours": st.column_config.TextColumn("Total Workday Hours", disabled=True, help="Format: HH:MM:SS"),
                        "Selection Count": st.column_config.NumberColumn("Selection Count", min_value=0, step=1),
                        "Presentation Count": st.column_config.NumberColumn("Presentation Count", min_value=0, step=1),
                        "Quotation Count": st.column_config.NumberColumn("Quotation Count", min_value=0, step=1),
                        "Selection Repetition Count": st.column_config.NumberColumn("Selection Rep Count", min_value=0, step=1),
                        "Presentation Repetition Count": st.column_config.NumberColumn("Presentation Rep Count", min_value=0, step=1),
                        "Quotation Repetition Count": st.column_config.NumberColumn("Quotation Rep Count", min_value=0, step=1),
                        "Live Time Assigned": st.column_config.TextColumn("Live Time Assigned", disabled=True, help="Format: HH:MM:SS"),
                        "Other Time Assigned": st.column_config.TextColumn("Other Time Assigned", disabled=True, help="Format: HH:MM:SS")
                    },
                    disabled=["user_id", "Name", "Total Workday Hours", "Live Time Assigned", "Other Time Assigned"],
                    use_container_width=True,
                    key="assignment_editor_persistent",
                    on_change=None
                )

                # Update assignment data when changes occur
                if not edited_df.equals(display_assignment_df):
                    # Convert the edited display data back to seconds for internal calculations
                    edited_df_seconds = edited_df.copy()
                    
                    # Convert time columns back to seconds (only the ones that might have changed)
                    edited_df_seconds['Total Workday Hours'] = edited_df_seconds['Total Workday Hours'].apply(hms_to_seconds)
                    edited_df_seconds['Live Time Assigned'] = edited_df_seconds['Live Time Assigned'].apply(hms_to_seconds)
                    edited_df_seconds['Other Time Assigned'] = edited_df_seconds['Other Time Assigned'].apply(hms_to_seconds)
                    
                    # Now use the seconds version for calculations
                    updated_df = calculate_times(edited_df_seconds)
                    st.session_state.assignment_data = updated_df
                    st.rerun()

                        
                # Validation logic
                def validate_assignments(df):
                    """Validate assignments and return errors if any"""
                    validation_errors = []
                    for i, row in df.iterrows():
                        if row['Live Time Assigned'] > row['Total Workday Hours']:
                            validation_errors.append(f"{row['Name']}: Live Time ({seconds_to_hms(row['Live Time Assigned'])}) exceeds Workday Hours ({seconds_to_hms(row['Total Workday Hours'])})")
                    return validation_errors

                validation_errors = validate_assignments(st.session_state.assignment_data)
                can_submit = len(validation_errors) == 0

                if validation_errors:
                    st.error("❌ Assignment errors found:")
                    for error in validation_errors:
                        st.error(f"   • {error}")

                # Submit Assignment
                if st.button("Submit Assignment", disabled=not can_submit):
                    if not project_code:
                        st.warning("Please fill in all required fields.")
                    else:
                        assignments_to_insert = []
                        submitted_user_ids = []
                        
                        for i, row in st.session_state.assignment_data.iterrows():
                            # Only add rows where there's actual assignment
                            if (row['Selection Count'] > 0 or row['Presentation Count'] > 0 or 
                                row['Quotation Count'] > 0 or row['Selection Repetition Count'] > 0 or
                                row['Presentation Repetition Count'] > 0 or row['Quotation Repetition Count'] > 0):
                                
                                # Calculate individual estimated times in seconds
                                time_calculations = {
                                    'selection': row['Selection Count'] * (ONE_SELECTION_TIME*3600),
                                    'presentation': row['Presentation Count'] * (ONE_PRESENTATION_TIME*3600),
                                    'quotation': row['Quotation Count'] * (ONE_QUOTATION_TIME*3600) ,
                                    'selection_rep': row['Selection Repetition Count'] * (ONE_SELECTION_REPETITION_TIME*3600),
                                    'presentation_rep': row['Presentation Repetition Count'] * (ONE_PRESENTATION_REPETITION_TIME*3600),
                                    'quotation_rep': row['Quotation Repetition Count'] * (ONE_QUOTATION_REPETITION_TIME*3600),
                                }
                                
                                total_assigned_time = sum(time_calculations.values())
                                
                                assignment_record = {
                                    'user_id': row['user_id'],
                                    'project_id': selected_project['id'],
                                    'selection_assigned_count': int(row['Selection Count']),
                                    'selection_assigned_estimated_time': int(time_calculations['selection']),
                                    'presentation_assigned_count': int(row['Presentation Count']),
                                    'presentation_assigned_estimated_time': int(time_calculations['presentation']),
                                    'quotation_assigned_count': int(row['Quotation Count']),
                                    'quotation_assigned_estimated_time': int(time_calculations['quotation']),
                                    'selection_repetition_assigned_count': int(row['Selection Repetition Count']),
                                    'selection_repetition_assigned_estimated_time': int(time_calculations['selection_rep']),
                                    'presentation_repetition_assigned_count': int(row['Presentation Repetition Count']),
                                    'presentation_repetition_assigned_estimated_time': int(time_calculations['presentation_rep']),
                                    'quotation_repetition_assigned_count': int(row['Quotation Repetition Count']),
                                    'quotation_repetition_assigned_estimated_time': int(time_calculations['quotation_rep']),
                                    'total_assigned_estimated_time': int(total_assigned_time),
                                    'other_time': int(row['Other Time Assigned']),  
                                    'working_time': int(row['Total Workday Hours'])
                                }
                                assignments_to_insert.append(assignment_record)
                                submitted_user_ids.append(row['user_id'])
                        
                        if assignments_to_insert:
                            print('assignments_to_insert: ',assignments_to_insert)
                            try:
                                # Insert assignments to database
                                result = supabase.table("assigned_masters").insert(assignments_to_insert).execute()
                                
                                st.success(f"✅ Assignment saved successfully for {len(assignments_to_insert)} designers.")
                                
                                # *** NEW FEATURE: Remove submitted users from the assignment data ***
                                st.session_state.assignment_data = remove_assigned_users(
                                    st.session_state.assignment_data, 
                                    submitted_user_ids
                                )
                                
                                # Show remaining designers message
                                remaining_designers = len(st.session_state.assignment_data)
                                if remaining_designers > 0:
                                    st.info(f"📋 {remaining_designers} designer(s) remaining for assignment.")
                                else:
                                    st.info("🎉 All present designers have been assigned!")
                                    
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ Error saving assignment: {str(e)}")
                        else:
                            st.warning("No assignments to save. Please enter counts for at least one designer.")

        with tab4:
            st.write("Edit Assignment Tab is responsible for editing the Previous assigned Task.")                
            # Load existing assignments for selection
            try:
                existing_assignments = supabase.table("assigned_masters").select("*").execute()
                if existing_assignments.data:
                    # Create selection filters
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Get unique project IDs for selection
                        available_project_ids = sorted(list(set([assignment['project_id'] for assignment in existing_assignments.data])))
                        
                        # Get project details for display
                        project_options = {}
                        for project_id in available_project_ids:
                            try:
                                project_detail = supabase.table("project_masters").select("project_code").eq("id", project_id).execute()
                                if project_detail.data:
                                    project_code = project_detail.data[0]['project_code']
                                    project_options[project_id] = project_code
                            except:
                                project_options[project_id] = f"Project {project_id}"
                        
                        selected_project_display = st.selectbox("Select Project", list(project_options.values()))
                        selected_project_id = [k for k, v in project_options.items() if v == selected_project_display][0] if selected_project_display else None
                    
                    with col2:
                        # Get unique dates for selected project
                        # if selected_project_id:
                        #     project_assignments = [a for a in existing_assignments.data if a['project_id'] == selected_project_id]
                        #     available_dates = sorted(list(set([assignment['created_at'][:10] for assignment in project_assignments])))
                        #     selected_date = st.selectbox("Select Date (YYYY-MM-DD)", available_dates)
                        selected_date = date.today().strftime("%Y-%m-%d")
                    
                    if selected_project_id and selected_date:
                        # Filter data for selected project and date
                        filtered_assignments = [
                            a for a in existing_assignments.data 
                            if a['project_id'] == selected_project_id and a['created_at'][:10] == selected_date
                        ]
                        
                        if filtered_assignments:
                            st.write(f"**Editing Assignment for Project: {selected_project_display}, Date: {selected_date}(YYYY-MM-DD)**")
                            
                            # Get project details for calculations
                            try:
                                project_detail = supabase.table("project_masters").select("*").eq("id", selected_project_id).execute()
                                selected_project = project_detail.data[0] if project_detail.data else None
                            except:
                                selected_project = None
                            
                            if not selected_project:
                                st.error("Could not load project details for editing.")
                                return
                            
                            # Initialize edit session state
                            edit_key = f"edit_data_{selected_project_id}_{selected_date}"
                            
                            if edit_key not in st.session_state:
                                # Convert existing data to editable format
                                edit_data = []
                                for assignment in filtered_assignments:
                                    # Get user name
                                    try:
                                        user_detail = supabase.table("users").select("name").eq("id", assignment['user_id']).execute()
                                        user_name = user_detail.data[0]['name'] if user_detail.data else f"User {assignment['user_id']}"
                                    except:
                                        user_name = f"User {assignment['user_id']}"
                                    
                                    edit_row = {
                                        'user_id': assignment['user_id'],
                                        'assignment_id': assignment['id'],
                                        'Name': user_name,
                                        'Total Workday Hours': assignment['working_time'],
                                        'Selection Count': assignment['selection_assigned_count'] or 0,
                                        'Presentation Count': assignment['presentation_assigned_count'] or 0,
                                        'Quotation Count': assignment['quotation_assigned_count'] or 0,
                                        'Selection Repetition Count': assignment['selection_repetition_assigned_count'] or 0,
                                        'Presentation Repetition Count': assignment['presentation_repetition_assigned_count'] or 0,
                                        'Quotation Repetition Count': assignment['quotation_repetition_assigned_count'] or 0,
                                        'Live Time Assigned': assignment['total_assigned_estimated_time'],
                                        'Other Time Assigned': assignment['other_time']
                                    }
                                    edit_data.append(edit_row)
                                
                                st.session_state[edit_key] = pd.DataFrame(edit_data)
                            
                            # Function to auto-calculate Live Time and Other Time for editing
                            def calculate_times_edit(df):
                                """Calculate live time and other time based on assignment counts for editing"""
                                df_copy = df.copy()
                                
                                # Get per-unit times from project master (convert seconds to hours)
                                unit_times = {
                                    'selection': (ONE_SELECTION_TIME*3600),
                                    'presentation': (ONE_PRESENTATION_TIME*3600),
                                    'quotation': (ONE_QUOTATION_TIME*3600),
                                    'selection_rep': (ONE_SELECTION_REPETITION_TIME*3600),
                                    'presentation_rep': (ONE_PRESENTATION_REPETITION_TIME*3600),
                                    'quotation_rep': (ONE_QUOTATION_REPETITION_TIME*3600),
                                }
                                
                                for i in range(len(df_copy)):
                                    # Calculate time for each task type
                                    live_time = (
                                        df_copy.loc[i, 'Selection Count'] * unit_times['selection'] +
                                        df_copy.loc[i, 'Presentation Count'] * unit_times['presentation'] +
                                        df_copy.loc[i, 'Quotation Count'] * unit_times['quotation'] +
                                        df_copy.loc[i, 'Selection Repetition Count'] * unit_times['selection_rep'] +
                                        df_copy.loc[i, 'Presentation Repetition Count'] * unit_times['presentation_rep'] +
                                        df_copy.loc[i, 'Quotation Repetition Count'] * unit_times['quotation_rep']
                                    )
                                    
                                    live_time = int(live_time)
                                    total_workday_hours = df_copy.loc[i, 'Total Workday Hours']
                                    
                                    # Calculate other time
                                    other_time = int(max(0, total_workday_hours - live_time))
                                    
                                    df_copy.loc[i, 'Live Time Assigned'] = live_time
                                    df_copy.loc[i, 'Other Time Assigned'] = other_time
                                
                                return df_copy

                            # Helper function to convert seconds to HH:MM:SS
                            def seconds_to_hms(seconds):
                                """Convert seconds to HH:MM:SS format"""
                                if pd.isna(seconds) or seconds == 0:
                                    return "00:00:00"
                                hours = int(seconds // 3600)
                                minutes = int((seconds % 3600) // 60)
                                seconds = int(seconds % 60)
                                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                            # Helper function to convert HH:MM:SS to seconds
                            def hms_to_seconds(time_str):
                                """Convert HH:MM:SS format to seconds"""
                                if pd.isna(time_str) or time_str == "00:00:00":
                                    return 0
                                h, m, s = map(int, time_str.split(':'))
                                return h * 3600 + m * 60 + s
                            
                            # Function to highlight over-limit times in edit mode
                            def highlight_live_time_editor_edit(row):
                                # Convert HH:MM:SS back to seconds for comparison
                                live_time_str = row['Live Time Assigned']
                                total_workday_str = row['Total Workday Hours']
                                
                                live_time_seconds = hms_to_seconds(live_time_str)
                                total_workday_seconds = hms_to_seconds(total_workday_str)
                                
                                if live_time_seconds > total_workday_seconds:
                                    return ['background-color: #ffcccc; color: #cc0000; font-weight: bold' if col == 'Live Time Assigned' else '' for col in row.index]
                                return ['' for _ in row.index]
                            
                            # Convert time columns for editing display
                            display_edit_df = st.session_state[edit_key].copy()
                            display_edit_df['Total Workday Hours'] = display_edit_df['Total Workday Hours'].apply(seconds_to_hms)
                            display_edit_df['Live Time Assigned'] = display_edit_df['Live Time Assigned'].apply(seconds_to_hms)
                            display_edit_df['Other Time Assigned'] = display_edit_df['Other Time Assigned'].apply(seconds_to_hms)

                            # Apply styling to the display dataframe (not the original)
                            styled_edit_df = display_edit_df.style.apply(highlight_live_time_editor_edit, axis=1)
                            
                            # Editable dataframe for existing assignment
                            edited_assignment_df = st.data_editor(
                                styled_edit_df,
                                column_config={
                                    "user_id": st.column_config.TextColumn("User ID", disabled=True),
                                    "assignment_id": st.column_config.TextColumn("Assignment ID", disabled=True),
                                    "Name": st.column_config.TextColumn("Name", disabled=True),
                                    "Total Workday Hours": st.column_config.TextColumn("Total Workday Hours", disabled=True, help="Format: HH:MM:SS"),
                                    "Selection Count": st.column_config.NumberColumn("Selection Count", min_value=0, step=1),
                                    "Presentation Count": st.column_config.NumberColumn("Presentation Count", min_value=0, step=1),
                                    "Quotation Count": st.column_config.NumberColumn("Quotation Count", min_value=0, step=1),
                                    "Selection Repetition Count": st.column_config.NumberColumn("Selection Rep Count", min_value=0, step=1),
                                    "Presentation Repetition Count": st.column_config.NumberColumn("Presentation Rep Count", min_value=0, step=1),
                                    "Quotation Repetition Count": st.column_config.NumberColumn("Quotation Rep Count", min_value=0, step=1),
                                    "Live Time Assigned": st.column_config.TextColumn("Live Time Assigned", disabled=True, help="Format: HH:MM:SS"),
                                    "Other Time Assigned": st.column_config.TextColumn("Other Time Assigned", disabled=True, help="Format: HH:MM:SS")
                                },
                                disabled=["user_id", "assignment_id", "Name", "Total Workday Hours", "Live Time Assigned", "Other Time Assigned"],
                                use_container_width=True,
                                key=f"edit_assignment_editor_{selected_project_id}_{selected_date}"
                            )
                            
                            # Check if edit data has changed and update session state
                            if not edited_assignment_df.equals(display_edit_df):
                                # Convert the edited display data back to seconds for internal calculations
                                edited_df_seconds = edited_assignment_df.copy()
                                
                                # Convert time columns back to seconds (only the ones that might have changed)
                                edited_df_seconds['Total Workday Hours'] = edited_df_seconds['Total Workday Hours'].apply(hms_to_seconds)
                                edited_df_seconds['Live Time Assigned'] = edited_df_seconds['Live Time Assigned'].apply(hms_to_seconds)
                                edited_df_seconds['Other Time Assigned'] = edited_df_seconds['Other Time Assigned'].apply(hms_to_seconds)
                                
                                # Now use the seconds version for calculations
                                updated_edit_df = calculate_times_edit(edited_df_seconds)
                                st.session_state[edit_key] = updated_edit_df
                                st.rerun()
                            
                            # Calculate summary statistics for editing
                            def calculate_edit_summary_stats(df):
                                """Calculate summary statistics for the edit assignment data"""
                                return {
                                    'total_designer': len(df),
                                    'total_workday_time': df['Total Workday Hours'].sum(),
                                    'total_live_time': df['Live Time Assigned'].sum(),
                                    'total_other_time': df['Other Time Assigned'].sum(),
                                    'total_selection': int(df['Selection Count'].sum()),
                                    'total_presentation': int(df['Presentation Count'].sum()),
                                    'total_quotation': int(df['Quotation Count'].sum()),
                                    'total_selection_rep': int(df['Selection Repetition Count'].sum()),
                                    'total_presentation_rep': int(df['Presentation Repetition Count'].sum()),
                                    'total_quotation_rep': int(df['Quotation Repetition Count'].sum()),
                                }
                            
                            edit_stats = calculate_edit_summary_stats(st.session_state[edit_key])
                            edit_utilization = round((edit_stats['total_live_time']/edit_stats['total_workday_time'])*100, 1) if edit_stats['total_workday_time'] > 0 else 0
                            
                            # Display totals for editing
                            st.write("### **Edit Totals**")
                            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)
                            
                            with col1:
                                st.metric("**Total Designers**", edit_stats['total_designer'])
                            with col2:
                                st.metric("**Total Workday Hours**", f"{seconds_to_hms(edit_stats['total_workday_time'])}")
                            with col3:
                                st.metric("**Total Quotation**", edit_stats['total_quotation'])
                            with col4:
                                st.metric("**Total Selection**", edit_stats['total_selection'])
                            with col5:
                                st.metric("**Total Presentation**", edit_stats['total_presentation'])
                            with col6:
                                st.metric("**Total Live Time**", f"{seconds_to_hms(edit_stats['total_live_time'])}")
                            with col7:
                                st.metric("**Total Other Time**", f"{seconds_to_hms(edit_stats['total_other_time'])}")
                            with col8:
                                st.metric("**Utilization %**", f"{edit_utilization}%")
                            
                            # Check validation for editing
                            def validate_edit_assignments(df):
                                """Validate edit assignments and return errors if any"""
                                validation_errors = []
                                for i, row in df.iterrows():
                                    if row['Live Time Assigned'] > row['Total Workday Hours']:
                                        validation_errors.append(f"{row['Name']}: Live Time ({seconds_to_hms(row['Live Time Assigned'])}) exceeds Workday Hours ({seconds_to_hms(row['Total Workday Hours'])})")
                                return validation_errors
                            
                            edit_validation_errors = validate_edit_assignments(st.session_state[edit_key])
                            edit_can_submit = len(edit_validation_errors) == 0
                            
                            if edit_validation_errors:
                                st.error("❌ Assignment errors found:")
                                for error in edit_validation_errors:
                                    st.error(f"   • {error}")
                            else:
                                st.success("✅ All assignments are within valid limits!")
                            
                            # Update Assignment button
                            if st.button("Update Assignment", disabled=not edit_can_submit, key="update_assignment_btn"):
                                try:
                                    # Prepare updated assignments
                                    updates_to_execute = []
                                    
                                    for i, row in st.session_state[edit_key].iterrows():
                                        # Calculate individual estimated times in seconds
                                        time_calculations = {
                                            'selection': row['Selection Count'] * (ONE_SELECTION_TIME*3600),
                                            'presentation': row['Presentation Count'] * (ONE_PRESENTATION_TIME*3600),
                                            'quotation': row['Quotation Count'] * (ONE_QUOTATION_TIME*3600) ,
                                            'selection_rep': row['Selection Repetition Count'] * (ONE_SELECTION_REPETITION_TIME*3600),
                                            'presentation_rep': row['Presentation Repetition Count'] * (ONE_PRESENTATION_REPETITION_TIME*3600),
                                            'quotation_rep': row['Quotation Repetition Count'] * (ONE_QUOTATION_REPETITION_TIME*3600),
                                        }
                                        
                                        total_assigned_time = sum(time_calculations.values())
                                        
                                        update_data = {
                                            'selection_assigned_count': int(row['Selection Count']),
                                            'selection_assigned_estimated_time': int(time_calculations['selection']),
                                            'presentation_assigned_count': int(row['Presentation Count']),
                                            'presentation_assigned_estimated_time': int(time_calculations['presentation']),
                                            'quotation_assigned_count': int(row['Quotation Count']),
                                            'quotation_assigned_estimated_time': int(time_calculations['quotation']),
                                            'selection_repetition_assigned_count': int(row['Selection Repetition Count']),
                                            'selection_repetition_assigned_estimated_time': int(time_calculations['selection_rep']),
                                            'presentation_repetition_assigned_count': int(row['Presentation Repetition Count']),
                                            'presentation_repetition_assigned_estimated_time': int(time_calculations['presentation_rep']),
                                            'quotation_repetition_assigned_count': int(row['Quotation Repetition Count']),
                                            'quotation_repetition_assigned_estimated_time': int(time_calculations['quotation_rep']),
                                            'total_assigned_estimated_time': int(total_assigned_time),
                                            'other_time': int(row['Other Time Assigned']),  
                                            'working_time': int(row['Total Workday Hours'])
                                        }
                                        
                                        updates_to_execute.append((row['assignment_id'], update_data))
                                    
                                    # Execute updates
                                    for assignment_id, update_data in updates_to_execute:
                                        supabase.table("assigned_masters").update(update_data).eq("id", assignment_id).execute()
                                    
                                    st.success(f"✅ Assignment updated successfully for {len(updates_to_execute)} designers.")
                                    
                                    # Clear the edit session state
                                    del st.session_state[edit_key]
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Error updating assignment: {str(e)}")
                        else:
                            st.info("No assignments found for the selected project and date.")
                    else:
                        st.info("Please select both project and date to edit assignment.")
                else:
                    st.info("No existing assignments found to edit.")
            except Exception as e:
                st.error(f"Error loading existing assignments: {str(e)}")
                st.info("No existing assignments found to edit.")



























assigned_masters_df = assigned_masters_df[['date','project_code','name','working_time','total_assigned_estimated_time', 'other_time',
'selection_assigned_count','selection_assigned_estimated_time',
'presentation_assigned_count','presentation_assigned_estimated_time', 
'quotation_assigned_count','quotation_assigned_estimated_time',
'selection_repetition_assigned_count','selection_repetition_assigned_estimated_time',
'presentation_repetition_assigned_count','presentation_repetition_assigned_estimated_time',
'quotation_repetition_assigned_count','quotation_repetition_assigned_estimated_time'
]]




'selection_assigned_count', 
'presentation_assigned_count', 
'quotation_assigned_count',
'selection_repetition_assigned_count',
'presentation_repetition_assigned_count',
'quotation_repetition_assigned_count',
'total_assigned_count' and this value will be sum of all assigned count 
display the above in bar chart name chart 2


'selection_assigned_estimated_time',
'presentation_assigned_estimated_time', 
'quotation_assigned_estimated_time',
'selection_repetition_assigned_estimated_time',
'presentation_repetition_assigned_estimated_time',
'quotation_repetition_assigned_estimated_time'
'total_assigned_estimated_time' and this value will be sum of all estimated time 
display the above in bar chart name chart 3
