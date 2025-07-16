import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta,date
from config import supabase
from supabase import create_client
import json
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import altair as alt
import numpy as np
MANHOURS = 7.5

class DstDashboard:

    def __init__(self,user_id):
        self.supabase = supabase
        self.user_id = user_id
        self.actions = ["Selection", "Presentation","Quotation","Selection Rep",
        "Presentation Rep","Quotation Rep","Others"]
        self.action_to_assigned_count_field = {
        "Selection": "selection_assigned_count",
        "Presentation": "presentation_assigned_count",
        "Quotation": "quotation_assigned_count",
        "Selection Rep": "selection_repetition_assigned_count",
        "Presentation Rep": "presentation_repetition_assigned_count",
        "Quotation Rep": "quotation_repetition_assigned_count",
        "Others": None}


        if "active_action" not in st.session_state:
            st.session_state.active_action = None
        if "start_time" not in st.session_state:
            st.session_state.start_time = None
        if "selected_project" not in st.session_state:
            st.session_state.selected_project = None
        if "duration_tracker" not in st.session_state:
            st.session_state.duration_tracker = {action: 0 for action in self.actions}


    def show(self):
        if st.session_state.get('show_assignment',False):
            self.show_assignment_dashboard()
        if st.session_state.get('show_summary',False):
            self.show_summary_dashboard()
        if st.session_state.get('show_timetracker',False):
            self.show_timetracker_dashboard()

    def show_assignment_dashboard(self):
        st.subheader("Assignment Dashboard")

        # Step 1: Fetch data with JOIN
        response = self.supabase.table("assigned_masters").select(
            "*, users(name), project_masters(project_code)"
        ).eq("user_id", self.user_id).execute()

        data = response.data

        if not data:
            st.warning("No assignment data found.")
            return

        df = pd.DataFrame(data)

        # Step 2: Flatten nested fields
        df['name'] = df['users'].apply(lambda x: x['name'] if isinstance(x, dict) else None)
        df['project_code'] = df['project_masters'].apply(lambda x: x['project_code'] if isinstance(x, dict) else None)

        # Step 3: Convert date to datetime format for filtering
        df['date'] = pd.to_datetime(df['date'])

        # Step 4: Create UI filters
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

        with col1:
            start_date = st.date_input("Start Date", df["date"].min().date())
        with col2:
            end_date = st.date_input("End Date", date.today())
        with col3:
            project_code_filter = st.selectbox("Project Code", options=["All"] + sorted(df["project_code"].dropna().unique().tolist()))
        with col4:
            show_details = st.toggle("Show Details", value=False)

        # Step 5: Apply filters
        mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
        if project_code_filter != "All":
            mask &= df['project_code'] == project_code_filter
        df = df.loc[mask]
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%d-%m-%Y')


        # Step 6: Select columns to display
        base_cols = [
            "date", "name", "project_code",
            "working_time", "total_assigned_estimated_time", "other_time"
        ]
        detail_cols = [
            "selection_assigned_count", "selection_assigned_estimated_time",
            "presentation_assigned_count", "presentation_assigned_estimated_time",
            "quotation_assigned_count", "quotation_assigned_estimated_time",
            "selection_repetition_assigned_count", "selection_repetition_assigned_estimated_time",
            "presentation_repetition_assigned_count", "presentation_repetition_assigned_estimated_time",
            "quotation_repetition_assigned_count", "quotation_repetition_assigned_estimated_time"
        ]

        display_cols = base_cols + detail_cols if show_details else base_cols

        # Step 7: Add total row
        numeric_cols = df[display_cols].select_dtypes(include='number').columns
        total_row = df[display_cols].copy()
        total = pd.DataFrame(total_row[numeric_cols].sum()).T
        for col in total_row.columns:
            if col not in total.columns:
                total[col] = ""
        total["name"] = ""
        total["date"] = ""
        total["project_code"] = "Total"
        df_display = pd.concat([total_row[display_cols], total[display_cols]], ignore_index=True)



        # step 9: convert the time columns in hh:mm:ss
        time_cols = [col for col in df_display.columns if 'time' in col]
        for col in time_cols:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(
                    lambda x: str(timedelta(seconds=int(x))) if pd.notnull(x) and str(x).isdigit() else x
                )


        # Step 10: Display final dataframe
        st.dataframe(df_display.reset_index(drop=True), use_container_width=True)

        # step 11: Project selection for time tracking

        st.subheader("Select Project for Time Tracking")

        project_options = []
        for _, row in df.iterrows():
            option = f"{row['project_code']} - {row['date']}"
            project_options.append((option, row))

        if project_options:
            selected_option = st.selectbox(
                "Choose a project to start time tracking:",
                options=[opt[0] for opt in project_options],
                key="project_selector"
            )

            if st.button("🚀 Start Time Tracking for Selected Project", type="primary"):
                selected_row = next(row for opt, row in project_options if opt == selected_option)
                print(f'selected_row: \n{selected_row}')
                st.session_state.selected_project = selected_row
                st.session_state.show_assignment = False
                st.session_state.show_timetracker = True
                st.success(f"Time tracking started for: {selected_row['project_code']} at {selected_row['date']}")
                st.rerun()

    def show_summary_dashboard(self):
        
        attendence_response = self.supabase.table("attendance").select(
            "login_time", "logout_time", "working_time", "comments"
        ).eq("user_id", self.user_id).eq("is_present", True).execute()

        attendence_data = pd.DataFrame(attendence_response.data)

        if not attendence_data.empty:
            # Convert login_time to datetime
            attendence_data["login_time"] = pd.to_datetime(attendence_data["login_time"])

            # Date range picker
            min_date = attendence_data["login_time"].min().date()
            max_date = attendence_data["login_time"].max().date()

            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date", min_value=min_date, max_value=max_date, value=min_date)
            with col2:
                end_date = st.date_input("End Date", min_value=min_date, max_value=max_date, value=max_date)


            # Filter the DataFrame
            filtered_df = attendence_data[
                (attendence_data["login_time"].dt.date >= start_date) &
                (attendence_data["login_time"].dt.date <= end_date)
            ]

            # Summary calculations from filtered data
            attendance_day_count = len(filtered_df)
            actual_work_hours = attendance_day_count * (MANHOURS * 3600)
            work_hours = filtered_df['working_time'].sum()
            difference = actual_work_hours - work_hours

            summary_data = [{
                "Present Count":attendance_day_count,
                "Actual Work Hours": actual_work_hours,
                "Work Hours": work_hours,
                "Difference": difference
            }]
            df = pd.DataFrame(summary_data)

            # Convert seconds to hh:mm:ss for display
            def seconds_to_hms(seconds):
                if pd.isna(seconds): return "00:00:00"
                total_seconds = int(seconds)
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                secs = total_seconds % 60
                return f"{hours:02}:{minutes:02}:{secs:02}"


            df_display = df.copy()
            for col in ["Actual Work Hours", "Work Hours", "Difference"]:
                df_display[col] = df_display[col].apply(seconds_to_hms)

            st.dataframe(df_display)

        else:
            st.warning("No attendance records found.")


           


     # ------------------------------------------------------
        

        assigned_masters_response = self.supabase.table("assigned_masters").select(
            "*,project_masters(project_code)"
        ).eq("user_id", self.user_id).execute()

        assigned_masters_data = assigned_masters_response.data
        #st.write(f"assigned_masters_data:\n{assigned_masters_data}")

        worklog_masters_response = self.supabase.table("worklog_masters").select(
            "*,project_masters(project_code)"
        ).eq("user_id", self.user_id).execute()

        worklog_masters_data = worklog_masters_response.data
        #st.write(f"worklog_masters_data: {worklog_masters_data}")


        # Step 1: Convert to DataFrame
        assigned_df = pd.DataFrame(assigned_masters_data)
        worklog_df = pd.DataFrame(worklog_masters_data)

        # Step 2: Extract project_code
        assigned_df['project_code'] = assigned_df['project_masters'].apply(lambda x: x['project_code'])
        worklog_df['project_code'] = worklog_df['project_masters'].apply(lambda x: x['project_code'])


        # Step 3 & 4: Group and Aggregate
        assigned_summary = assigned_df.groupby('project_code')[[
            'selection_assigned_count', 'presentation_assigned_count', 'quotation_assigned_count',
            'selection_repetition_assigned_count', 'presentation_repetition_assigned_count', 'quotation_repetition_assigned_count',
            'selection_assigned_estimated_time', 'presentation_assigned_estimated_time', 'quotation_assigned_estimated_time',
            'selection_repetition_assigned_estimated_time', 'presentation_repetition_assigned_estimated_time', 'quotation_repetition_assigned_estimated_time',
            'working_time', 'total_assigned_estimated_time', 'other_time'
        ]].sum().reset_index()
        #st.dataframe(assigned_summary)

        worklog_summary = worklog_df.groupby('project_code')[[
            'selection_submit_count', 'presentation_submit_count', 'quotation_submit_count',
            'selection_repetition_submit_count', 'presentation_repetition_submit_count', 'quotation_repetition_submit_count',
            'selection_actual_time', 'presentation_actual_time', 'quotation_actual_time',
            'selection_repetition_actual_time', 'presentation_repetition_actual_time', 'quotation_repetition_actual_time',
            'others_time'
        ]].sum().reset_index()
        #st.dataframe(worklog_summary)

        # Get list of unique project codes from both summaries
        assigned_codes = assigned_summary['project_code'].unique().tolist()
        worklog_codes = worklog_summary['project_code'].unique().tolist()
        all_project_codes = sorted(set(assigned_codes + worklog_codes))

        # Dropdown to select project
        selected_project_code = st.selectbox("Select Project Code", all_project_codes)

        # Filter assigned and worklog summaries separately
        assigned_row = assigned_summary[assigned_summary['project_code'] == selected_project_code]
        worklog_row = worklog_summary[worklog_summary['project_code'] == selected_project_code]

        # Fill with 0 if not found
        assigned_data = assigned_row.iloc[0] if not assigned_row.empty else pd.Series(dtype='float64')
        worklog_data = worklog_row.iloc[0] if not worklog_row.empty else pd.Series(dtype='float64')


        # Helper to get value safely
        def val(d, key):
            return d.get(key, 0)

        
        data = {
            "Selection": {
                "Assiged": val(assigned_data, 'selection_assigned_count'),
                "Submit": val(worklog_data, 'selection_submit_count'),
                "Pending": val(assigned_data, 'selection_assigned_count') - val(worklog_data, 'selection_submit_count'),
                "Estimated Time": val(assigned_data, 'selection_assigned_estimated_time'),
                "Actual Time": val(worklog_data, 'selection_actual_time'),
                "Difference": val(assigned_data, 'selection_assigned_estimated_time') - val(worklog_data, 'selection_actual_time')
            },
            "Presentation": {
                "Assiged": val(assigned_data, 'presentation_assigned_count'),
                "Submit": val(worklog_data, 'presentation_submit_count'),
                "Pending": val(assigned_data, 'presentation_assigned_count') - val(worklog_data, 'presentation_submit_count'),
                "Estimated Time": val(assigned_data, 'presentation_assigned_estimated_time'),
                "Actual Time": val(worklog_data, 'presentation_actual_time'),
                "Difference": val(assigned_data, 'presentation_assigned_estimated_time') - val(worklog_data, 'presentation_actual_time')
            },
            "Quotation": {
                "Assiged": val(assigned_data, 'quotation_assigned_count'),
                "Submit": val(worklog_data, 'quotation_submit_count'),
                "Pending": val(assigned_data, 'quotation_assigned_count') - val(worklog_data, 'quotation_submit_count'),
                "Estimated Time": val(assigned_data, 'quotation_assigned_estimated_time'),
                "Actual Time": val(worklog_data, 'quotation_actual_time'),
                "Difference": val(assigned_data, 'quotation_assigned_estimated_time') - val(worklog_data, 'quotation_actual_time')
            },
            "Selection Repetition": {
                "Assiged": val(assigned_data, 'selection_repetition_assigned_count'),
                "Submit": val(worklog_data, 'selection_repetition_submit_count'),
                "Pending": val(assigned_data, 'selection_repetition_assigned_count') - val(worklog_data, 'selection_repetition_submit_count'),
                "Estimated Time": val(assigned_data, 'selection_repetition_assigned_estimated_time'),
                "Actual Time": val(worklog_data, 'selection_repetition_actual_time'),
                "Difference": val(assigned_data, 'selection_repetition_assigned_estimated_time') - val(worklog_data, 'selection_repetition_actual_time')
            },
            "Presentation Repetition": {
                "Assiged": val(assigned_data, 'presentation_repetition_assigned_count'),
                "Submit": val(worklog_data, 'presentation_repetition_submit_count'),
                "Pending": val(assigned_data, 'presentation_repetition_assigned_count') - val(worklog_data, 'presentation_repetition_submit_count'),
                "Estimated Time": val(assigned_data, 'presentation_repetition_assigned_estimated_time'),
                "Actual Time": val(worklog_data, 'presentation_repetition_actual_time'),
                "Difference": val(assigned_data, 'presentation_repetition_assigned_estimated_time') - val(worklog_data, 'presentation_repetition_actual_time')
            },
            "Quotation Repetition": {
                "Assiged": val(assigned_data, 'quotation_repetition_assigned_count'),
                "Submit": val(worklog_data, 'quotation_repetition_submit_count'),
                "Pending": val(assigned_data, 'quotation_repetition_assigned_count') - val(worklog_data, 'quotation_repetition_submit_count'),
                "Estimated Time": val(assigned_data, 'quotation_repetition_assigned_estimated_time'),
                "Actual Time": val(worklog_data, 'quotation_repetition_actual_time'),
                "Difference": val(assigned_data, 'quotation_repetition_assigned_estimated_time') - val(worklog_data, 'quotation_repetition_actual_time')
            },

            "Others":{
                "Assiged":"",
                "Submit": "",
                "Pending":"",
                "Estimated Time":val(assigned_data, 'other_time'),
                "Actual Time":val(worklog_data, 'others_time'),
                "Difference": val(assigned_data, 'other_time') - val(worklog_data, 'others_time')

            }
        }
 
        df = pd.DataFrame.from_dict(data, orient='index')

        def seconds_to_hms(seconds):
            if pd.isna(seconds): return "00:00:00"
            seconds = int(seconds)
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h:02}:{m:02}:{s:02}"

        for col in ["Estimated Time", "Actual Time", "Difference"]:
            df[col] = df[col].apply(seconds_to_hms)
            
        st.dataframe(df)



    # def show_timetracker_dashboard(self):
    #     st.write("Time Tracker Buttons will appear here.")

    #     if st.session_state.selected_project is None:
    #         st.warning("Please select a project from Assignment Details first.")
    #         if st.button("📋 Go to Assignment Details"):
    #             st.session_state.show_timetracker = False
    #             st.session_state.show_assignment = True
    #             st.rerun()
    #         return
                
    #     project_data = st.session_state.selected_project
    #     st.write(f"project data: {project_data}")

    #     st.info(f"**Assigned Date:** {project_data['date']}  |  "
    #             f"**Project Code:** {project_data['project_code']}\n"
    #             f"**Total Workdays Hours:** {str(timedelta(seconds=int(project_data.get('working_time', 0))))}  |  "
    #             f"**Live Working Time:** {str(timedelta(seconds=int(project_data.get('total_assigned_estimated_time', 0))))}  |  "
    #             f"**Other Working Time:** {str(timedelta(seconds=int(project_data.get('other_time', 0))))}")

    #     st.subheader("🎯 Activity Tracking")

    #     if st.session_state.active_action:
    #         elapsed_time = datetime.now() - st.session_state.start_time
    #         st.success(f"⏰ Currently tracking: **{st.session_state.active_action}** | Elapsed: {str(elapsed_time).split('.')[0]}")

    #     cols = st.columns(len(self.actions))
    #     for i, action in enumerate(self.actions):
    #         with cols[i]:
    #             button_type = "secondary"
    #             button_text = action
    #             disabled = False
                
    #             if st.session_state.active_action == action:
    #                 button_type = "primary"
    #                 button_text = f"{action}"
    #             elif st.session_state.active_action and st.session_state.active_action != action:
    #                 disabled = True
    #             else:
    #                 button_text = f"{action}"
                
    #             if st.button(
    #                 button_text,
    #                 key=f"btn_{action}",
    #                 type=button_type,
    #                 disabled=disabled,
    #                 use_container_width=True
    #             ):
    #                 self.handle_button_click(action, project_data)


    #     if getattr(st.session_state, 'show_submit_form', False):
    #         action = st.session_state.temp_action
    #         duration_seconds = st.session_state.temp_duration
    #         project_data = st.session_state.temp_project_data
            
    #         with st.form(key=f"submit_form_{action}"):
    #             st.write(f"**{action} completed!**")
    #             st.write(f"Duration: {str(timedelta(seconds=duration_seconds))}")
                
    #             submit_count = st.number_input(
    #                 f"How many {action.lower()} did you submit?",
    #                 min_value=0,
    #                 value=0,
    #                 step=1,
    #                 key=f"submit_{action}"
    #             )
                
    #             col1, col2 = st.columns(2)
    #             with col1:
    #                 submitted = st.form_submit_button("Submit & Save")
    #             with col2:
    #                 cancelled = st.form_submit_button("Cancel")
                
    #             if submitted:
    #                 # Save to Excel with submission count
    #                 self.save_time_log(action, project_data, duration_seconds, submit_count)
                    
    #                 # Clear form state
    #                 st.session_state.show_submit_form = False
    #                 st.session_state.duration_tracker[action] += duration_seconds
                    
    #                 duration_str = str(timedelta(seconds=duration_seconds))
    #                 st.success(f"Saved: {action} | Duration: {duration_str} | Submissions: {submit_count}")
    #                 st.rerun()
                    
    #             if cancelled:
    #                 # Just clear the form without saving
    #                 st.session_state.show_submit_form = False
    #                 st.rerun()

    #     st.subheader("📊 Today's Time Summary")
    #     self.display_time_summary(project_data)
        
    #     # Refresh button
    #     if st.button("🔄 Refresh Summary", type="secondary"):
    #         st.rerun()

    def show_timetracker_dashboard(self):        
        if st.session_state.selected_project is None:
            st.warning("Please select a project from Assignment Details first.")
            if st.button("📋 Go to Assignment Details"):
                st.session_state.show_timetracker = False
                st.session_state.show_assignment = True
                st.rerun()
            return

        project_data = st.session_state.selected_project
        
        st.info(f"**Assigned Date:** {project_data['date']}  |  "
                f"**Project Code:** {project_data['project_code']}\n"
                f"**Total Workdays Hours:** {str(timedelta(seconds=int(project_data.get('working_time', 0))))}  |  "
                f"**Live Working Time:** {str(timedelta(seconds=int(project_data.get('total_assigned_estimated_time', 0))))}  |  "
                f"**Other Working Time:** {str(timedelta(seconds=int(project_data.get('other_time', 0))))}")

        st.subheader("🎯 Activity Tracking")

        if st.session_state.active_action:
            elapsed_time = datetime.now() - st.session_state.start_time
            st.success(f"⏰ Currently tracking: **{st.session_state.active_action}** | Elapsed: {str(elapsed_time).split('.')[0]}")

        # Filter actions based on assigned counts
        visible_actions = []
        for action in self.actions:
            assigned_field = self.action_to_assigned_count_field.get(action)
            if assigned_field is None or int(project_data.get(assigned_field, 0)) > 0:
                visible_actions.append(action)

        cols = st.columns(len(visible_actions))
        for i, action in enumerate(visible_actions):
            with cols[i]:
                button_type = "secondary"
                button_text = action
                disabled = False

                if st.session_state.active_action == action:
                    button_type = "primary"
                elif st.session_state.active_action:
                    disabled = True

                if st.button(
                    button_text,
                    key=f"btn_{action}",
                    type=button_type,
                    disabled=disabled,
                    use_container_width=True
                ):
                    self.handle_button_click(action, project_data)

        if getattr(st.session_state, 'show_submit_form', False):
            action = st.session_state.temp_action
            duration_seconds = st.session_state.temp_duration
            project_data = st.session_state.temp_project_data

            with st.form(key=f"submit_form_{action}"):
                st.write(f"**{action} completed!**")
                st.write(f"Duration: {str(timedelta(seconds=duration_seconds))}")

                submit_count = st.number_input(
                    f"How many {action.lower()} did you submit?",
                    min_value=0,
                    value=0,
                    step=1,
                    key=f"submit_{action}"
                )

                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("Submit & Save")
                with col2:
                    cancelled = st.form_submit_button("Cancel")

                if submitted:
                    self.save_time_log(action, project_data, duration_seconds, submit_count)
                    st.session_state.show_submit_form = False
                    st.session_state.duration_tracker[action] += duration_seconds
                    st.success(f"Saved: {action} | Duration: {str(timedelta(seconds=duration_seconds))} | Submissions: {submit_count}")
                    st.rerun()

                if cancelled:
                    st.session_state.show_submit_form = False
                    st.rerun()

        st.subheader("📊 Today's Time Summary")
        self.display_time_summary(project_data)

        if st.button("🔄 Refresh Summary", type="secondary"):
            st.rerun()

    def handle_button_click(self, action, project_data):
        current_time = datetime.now()
        
        if st.session_state.active_action is None:
            # Start tracking
            st.session_state.active_action = action
            st.session_state.start_time = current_time
            st.success(f"Started tracking: {action}")
            
        elif st.session_state.active_action == action:
            # Stop tracking - store data temporarily and show form
            duration_seconds = int((current_time - st.session_state.start_time).total_seconds())
            
            # Store the data temporarily in session state
            st.session_state.temp_action = action
            st.session_state.temp_duration = duration_seconds
            st.session_state.temp_project_data = project_data
            st.session_state.show_submit_form = True
            
            # Reset active tracking immediately
            st.session_state.active_action = None
            st.session_state.start_time = None
            
        st.rerun()
    
    # def save_time_log(self, action, project_data, duration_seconds, submit_count):
    #     today = datetime.now().date()

    #     # Mapping action → column names
    #     submit_column_map = {
    #         "Quotation": "quotation_submit_count",
    #         "Presentation": "presentation_submit_count",
    #         "Selection": "selection_submit_count",
    #         "Quotation Rep": "quotation_repetition_submit_count",
    #         "Presentation Rep": "presentation_repetition_submit_count",
    #         "Selection Rep": "selection_repetition_submit_count",
    #     }

    #     time_column_map = {
    #         "Quotation": "quotation_actual_time",
    #         "Presentation": "presentation_actual_time",
    #         "Selection": "selection_actual_time",
    #         "Quotation Rep": "quotation_repetition_actual_time",
    #         "Presentation Rep": "presentation_repetition_actual_time",
    #         "Selection Rep": "selection_repetition_actual_time",
    #         "Others": "others_time"
    #     }

    #     submit_col = submit_column_map.get(action)
    #     time_col = time_column_map.get(action)

    #     try:
    #         # Step 1: Check if row exists
    #         response = supabase.table("worklog_masters").select("*").eq("user_id", self.user_id)\
    #             .eq("project_id", project_data["project_id"]).eq("working_date", today).execute()

    #         if response.data:
    #             existing = response.data[0]
    #             update_payload = {
    #                 time_col: existing.get(time_col, 0) + duration_seconds,
    #                 "updated_at": datetime.now().isoformat()
    #             }
    #             if submit_col:
    #                 update_payload[submit_col] = existing.get(submit_col, 0) + submit_count

    #             supabase.table("worklog_masters")\
    #                 .update(update_payload)\
    #                 .eq("user_id", self.user_id)\
    #                 .eq("project_id", project_data["project_id"])\
    #                 .eq("working_date", today)\
    #                 .execute()

    #         else:
    #             insert_payload = {
    #                 "assigned_date": datetime.strptime(project_data["date"], "%d-%m-%Y").date().isoformat(),
    #                 "user_id": self.user_id,
    #                 "project_id": project_data["project_id"],
    #                 "working_date": today.isoformat(),
    #                 time_col: duration_seconds,
    #                 "updated_at": datetime.now().isoformat()
    #             }
    #             if submit_col:
    #                 insert_payload[submit_col] = submit_count

                    

    #             supabase.table("worklog_masters").insert(insert_payload).execute()

    #     except Exception as e:
    #         st.error(f"Error saving time log: {str(e)}")

    def save_time_log(self, action, project_data, duration_seconds, submit_count):
        today = datetime.now().date()
        assigned_date = datetime.strptime(project_data["date"], "%d-%m-%Y").date()

        # Mapping action → column names
        submit_column_map = {
            "Quotation": "quotation_submit_count",
            "Presentation": "presentation_submit_count",
            "Selection": "selection_submit_count",
            "Quotation Rep": "quotation_repetition_submit_count",
            "Presentation Rep": "presentation_repetition_submit_count",
            "Selection Rep": "selection_repetition_submit_count",
        }

        time_column_map = {
            "Quotation": "quotation_actual_time",
            "Presentation": "presentation_actual_time",
            "Selection": "selection_actual_time",
            "Quotation Rep": "quotation_repetition_actual_time",
            "Presentation Rep": "presentation_repetition_actual_time",
            "Selection Rep": "selection_repetition_actual_time",
            "Others": "others_time"
        }

        submit_col = submit_column_map.get(action)
        time_col = time_column_map.get(action)

        try:
            # Step 1: Check if row exists (now including assigned_date in filter)
            response = supabase.table("worklog_masters").select("*")\
                .eq("user_id", self.user_id)\
                .eq("project_id", project_data["project_id"])\
                .eq("working_date", today)\
                .eq("assigned_date", assigned_date)\
                .execute()

            if response.data:
                existing = response.data[0]
                update_payload = {
                    time_col: existing.get(time_col, 0) + duration_seconds,
                    "updated_at": datetime.now().isoformat()
                }
                if submit_col:
                    update_payload[submit_col] = existing.get(submit_col, 0) + submit_count

                supabase.table("worklog_masters")\
                    .update(update_payload)\
                    .eq("user_id", self.user_id)\
                    .eq("project_id", project_data["project_id"])\
                    .eq("working_date", today)\
                    .eq("assigned_date", assigned_date)\
                    .execute()

            else:
                insert_payload = {
                    "assigned_date": assigned_date.isoformat(),
                    "user_id": self.user_id,
                    "project_id": project_data["project_id"],
                    "working_date": today.isoformat(),
                    time_col: duration_seconds,
                    "updated_at": datetime.now().isoformat()
                }
                if submit_col:
                    insert_payload[submit_col] = submit_count

                supabase.table("worklog_masters").insert(insert_payload).execute()

        except Exception as e:
            st.error(f"Error saving time log: {str(e)}")

    # def display_time_summary(self, project_data):
    #     today = datetime.now().date().isoformat()

    #     try:
    #         # Fetch today's worklog for current user and selected project
    #         response = supabase.table("worklog_masters")\
    #             .select("*")\
    #             .eq("user_id", self.user_id)\
    #             .eq("project_id", project_data["project_id"])\
    #             .eq("working_date", today)\
    #             .execute()

    #         if not response.data:
    #             st.info("No time logs found for this project today.")
    #             # Optional: show debug info
    #             with st.expander("🔍 Debug Info"):
    #                 st.write("No data returned for:")
    #                 st.json({
    #                     "user_id": self.user_id,
    #                     "project_id": project_data.get("project_id"),
    #                     "working_date": today
    #                 })
    #             return

    #         row = response.data[0]

    #         import pandas as pd
    #         from datetime import timedelta

    #         def seconds_to_hms(seconds):
    #             return str(timedelta(seconds=seconds)) if seconds else "00:00:00"

    #         def build_summary_df(project_data, row):
    #             def get_row(task_prefix, has_count=True):
    #                 assigned = project_data.get(f'{task_prefix}_assigned_count', 0) if has_count else ''
    #                 submit = row.get(f'{task_prefix}_submit_count', 0) if has_count else ''
    #                 pending = (assigned - submit) if has_count else ''
                    
    #                 # Handle 'others' separately
    #                 if task_prefix == "others":
    #                     estimated = project_data.get("other_time", 0)
    #                 else:
    #                     estimated = project_data.get(f'{task_prefix}_assigned_estimated_time', 0)

    #                 actual = row.get(f'{task_prefix}_actual_time', 0)
    #                 pending_time = estimated - actual

    #                 return {
    #                     "Assigned": assigned if has_count else '',
    #                     "Submit": submit if has_count else '',
    #                     "Pending": pending if has_count else '',
    #                     "Estimated Time": seconds_to_hms(estimated),
    #                     "Actual Time": seconds_to_hms(actual),
    #                     "Pending Time": seconds_to_hms(pending_time),
    #                 }

    #             task_mapping = {
    #                 "Selection": "selection",
    #                 "Presentation": "presentation",
    #                 "Quatation": "quotation",  # Change to "Quotation" if needed
    #                 "Selection Rep": "selection_repetition",
    #                 "Presentation Rep": "presentation_repetition",
    #                 "Quatation Rep": "quotation_repetition",
    #                 "Others": "others"
    #             }

    #             data = {}
    #             for label, prefix in task_mapping.items():
    #                 if label == "Others":
    #                     data[label] = get_row(prefix, has_count=False)
    #                 else:
    #                     assigned_count = project_data.get(f"{prefix}_assigned_count", 0)
    #                     if assigned_count > 0:
    #                         data[label] = get_row(prefix)

    #             df = pd.DataFrame.from_dict(data, orient="index")
    #             return df

    #         summary_df = build_summary_df(project_data, row)
    #         st.dataframe(summary_df)  

    #     except Exception as e:
    #         st.error(f"Error loading time summary: {str(e)}")

    def display_time_summary(self, project_data):
        today = datetime.now().date()
        assigned_date = datetime.strptime(project_data["date"], "%d-%m-%Y").date()

        try:
            # Fetch today's worklog for current user and selected project and assigned date
            response = supabase.table("worklog_masters")\
                .select("*")\
                .eq("user_id", self.user_id)\
                .eq("project_id", project_data["project_id"])\
                .eq("working_date", today)\
                .eq("assigned_date", assigned_date)\
                .execute()

            if not response.data:
                st.info("No time logs found for this project today.")
                with st.expander("🔍 Debug Info"):
                    st.json({
                        "user_id": self.user_id,
                        "project_id": project_data.get("project_id"),
                        "working_date": today.isoformat(),
                        "assigned_date": assigned_date.isoformat()
                    })
                return

            row = response.data[0]

            def seconds_to_hms(seconds):
                return str(timedelta(seconds=seconds)) if seconds else "00:00:00"

            def build_summary_df(project_data, row):
                def get_row(task_prefix, has_count=True):
                    assigned = project_data.get(f'{task_prefix}_assigned_count', 0) if has_count else ''
                    submit = row.get(f'{task_prefix}_submit_count', 0) if has_count else ''
                    pending = (assigned - submit) if has_count else ''
                    
                    estimated = (
                        project_data.get("other_time", 0) if task_prefix == "others"
                        else project_data.get(f'{task_prefix}_assigned_estimated_time', 0)
                    )

                    actual = row.get(f'{task_prefix}_actual_time', 0)
                    pending_time = estimated - actual

                    return {
                        "Assigned": assigned if has_count else '',
                        "Submit": submit if has_count else '',
                        "Pending": pending if has_count else '',
                        "Estimated Time": seconds_to_hms(estimated),
                        "Actual Time": seconds_to_hms(actual),
                        "Pending Time": seconds_to_hms(pending_time),
                    }

                task_mapping = {
                    "Selection": "selection",
                    "Presentation": "presentation",
                    "Quatation": "quotation",
                    "Selection Rep": "selection_repetition",
                    "Presentation Rep": "presentation_repetition",
                    "Quatation Rep": "quotation_repetition",
                    "Others": "others"
                }

                data = {}
                for label, prefix in task_mapping.items():
                    if label == "Others":
                        data[label] = get_row(prefix, has_count=False)
                    else:
                        assigned_count = project_data.get(f"{prefix}_assigned_count", 0)
                        if assigned_count > 0:
                            data[label] = get_row(prefix)

                return pd.DataFrame.from_dict(data, orient="index")

            summary_df = build_summary_df(project_data, row)
            st.dataframe(summary_df)

        except Exception as e:
            st.error(f"Error loading time summary: {str(e)}")









    






























































