import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO

st.set_page_config(
    page_title="Agent Lunch Overlap ",
    page_icon="🍽️",
    layout="wide"
)

st.title("Agent Lunch Overlap ")
st.markdown("Upload your agent state CSV file to analyze overlapping periods when at least one agent is on lunch.")

# Lunch-related reason codes (customizable)
st.sidebar.header("Lunch Configuration")
default_lunch_codes = ["Lunch"]
lunch_codes = st.sidebar.text_area(
    "Lunch Reason Codes (one per line)",
    value="\n".join(default_lunch_codes),
    help="Enter the reason codes that indicate lunch/meal breaks"
).strip().split('\n')
lunch_codes = [code.strip() for code in lunch_codes if code.strip()]

st.sidebar.markdown(f"**Current lunch codes:** {', '.join(lunch_codes)}")

# File upload
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    # Read the CSV
    df = pd.read_csv(uploaded_file)
    
    # Show basic info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Records", len(df))
    with col2:
        st.metric("Unique Agents", df['AGENT'].nunique())
    with col3:
        st.metric("Not Ready Records", len(df[df['STATE'] == 'Not Ready']))
    with col4:
        lunch_records = len(df[df['REASON CODE'].isin(lunch_codes)])
        st.metric("Lunch Records", lunch_records)
    
    # Process Not Ready states
    not_ready_df = df[df['STATE'] == 'Not Ready'].copy()
    
    if len(not_ready_df) > 0:
        # Convert date and time to datetime
        not_ready_df['start_datetime'] = pd.to_datetime(
            not_ready_df['DATE'] + ' ' + not_ready_df['TIME'],
            format='%Y/%m/%d %H:%M:%S'
        )
        
        # Parse duration to seconds
        def parse_duration(duration_str):
            if pd.isna(duration_str):
                return 0
            parts = duration_str.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        
        not_ready_df['duration_seconds'] = not_ready_df['AGENT STATE TIME'].apply(parse_duration)
        not_ready_df['end_datetime'] = not_ready_df['start_datetime'] + pd.to_timedelta(not_ready_df['duration_seconds'], unit='s')
        
        # Mark lunch records
        not_ready_df['is_lunch'] = not_ready_df['REASON CODE'].isin(lunch_codes)
        
        # Find overlaps where at least one agent is on lunch
        overlaps = []
        records = not_ready_df.to_dict('records')
        
        with st.spinner('Finding lunch-related overlaps...'):
            for i in range(len(records)):
                for j in range(i + 1, len(records)):
                    rec1 = records[i]
                    rec2 = records[j]
                    
                    # Skip if same agent
                    if rec1['AGENT'] == rec2['AGENT']:
                        continue
                    
                    # Check if at least one agent is on lunch
                    if not (rec1['is_lunch'] or rec2['is_lunch']):
                        continue
                    
                    # Check overlap
                    overlap_start = max(rec1['start_datetime'], rec2['start_datetime'])
                    overlap_end = min(rec1['end_datetime'], rec2['end_datetime'])
                    
                    if overlap_start < overlap_end:
                        overlap_duration = (overlap_end - overlap_start).total_seconds()
                        
                        # Determine overlap type
                        if rec1['is_lunch'] and rec2['is_lunch']:
                            overlap_type = "Both on Lunch"
                        elif rec1['is_lunch']:
                            overlap_type = f"{rec1['AGENT']} on Lunch"
                        else:
                            overlap_type = f"{rec2['AGENT']} on Lunch"
                        
                        overlaps.append({
                            'Agent 1': rec1['AGENT'],
                            'Agent 2': rec2['AGENT'],
                            'Overlap Start': overlap_start,
                            'Overlap End': overlap_end,
                            'Duration (seconds)': overlap_duration,
                            'Duration (formatted)': f"{int(overlap_duration//3600)}h {int((overlap_duration%3600)//60)}m {int(overlap_duration%60)}s",
                            'Agent 1 Reason': rec1['REASON CODE'],
                            'Agent 2 Reason': rec2['REASON CODE'],
                            'Agent 1 On Lunch': rec1['is_lunch'],
                            'Agent 2 On Lunch': rec2['is_lunch'],
                            'Overlap Type': overlap_type,
                            'Date': overlap_start.date(),
                            'Hour': overlap_start.hour
                        })
        
        if overlaps:
            overlap_df = pd.DataFrame(overlaps)
            
            # Summary metrics
            st.header("Lunch Overlap Summary")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Lunch Overlaps", len(overlap_df))
            with col2:
                st.metric("Total Overlap Time", 
                         f"{int(overlap_df['Duration (seconds)'].sum()//3600)}h {int((overlap_df['Duration (seconds)'].sum()%3600)//60)}m")
            with col3:
                st.metric("Average Overlap", 
                         f"{int(overlap_df['Duration (seconds)'].mean()//60)}m {int(overlap_df['Duration (seconds)'].mean()%60)}s")
            with col4:
                both_lunch = len(overlap_df[overlap_df['Overlap Type'] == 'Both on Lunch'])
                st.metric("Both on Lunch", both_lunch)
            
            # Overlap type breakdown
            st.subheader("Overlap Type Distribution")
            overlap_type_counts = overlap_df['Overlap Type'].value_counts()
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig_pie = px.pie(
                    values=overlap_type_counts.values,
                    names=overlap_type_counts.index,
                    title="Distribution of Lunch Overlap Types"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                st.markdown("**Breakdown:**")
                for overlap_type, count in overlap_type_counts.items():
                    percentage = (count / len(overlap_df)) * 100
                    st.markdown(f"• {overlap_type}: {count} ({percentage:.1f}%)")
            
            # Filters
            st.header("Filter Options")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                selected_agents = st.multiselect(
                    "Filter by Agents",
                    options=sorted(set(overlap_df['Agent 1'].unique()) | set(overlap_df['Agent 2'].unique())),
                    default=None
                )
            
            with col2:
                overlap_types = st.multiselect(
                    "Filter by Overlap Type",
                    options=overlap_df['Overlap Type'].unique(),
                    default=overlap_df['Overlap Type'].unique()
                )
            
            with col3:
                min_duration = st.number_input(
                    "Minimum Duration (seconds)",
                    min_value=0,
                    value=0,
                    step=30
                )
            
            with col4:
                date_range = st.date_input(
                    "Date Range",
                    value=(overlap_df['Date'].min(), overlap_df['Date'].max()),
                    min_value=overlap_df['Date'].min(),
                    max_value=overlap_df['Date'].max()
                )
            
            # Apply filters
            filtered_df = overlap_df.copy()
            
            if selected_agents:
                filtered_df = filtered_df[
                    (filtered_df['Agent 1'].isin(selected_agents)) | 
                    (filtered_df['Agent 2'].isin(selected_agents))
                ]
            
            if overlap_types:
                filtered_df = filtered_df[filtered_df['Overlap Type'].isin(overlap_types)]
            
            if min_duration > 0:
                filtered_df = filtered_df[filtered_df['Duration (seconds)'] >= min_duration]
            
            if len(date_range) == 2:
                filtered_df = filtered_df[
                    (filtered_df['Date'] >= date_range[0]) & 
                    (filtered_df['Date'] <= date_range[1])
                ]
            
            # Visualizations
            st.header("Lunch Overlap")
            
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["Timeline", "Lunch Schedule", "Agent Impact", "Lunch Patterns", "Coverage Analysis"])
            
            with tab1:
                # Timeline visualization with lunch focus
                fig = px.scatter(filtered_df, 
                               x='Overlap Start', 
                               y='Duration (seconds)',
                               color='Overlap Type',
                               size='Duration (seconds)',
                               hover_data=['Agent 1', 'Agent 2', 'Agent 1 Reason', 'Agent 2 Reason', 'Duration (formatted)'],
                               title="Lunch Overlap Timeline")
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                # Lunch schedule heatmap
                st.subheader("Lunch Time Patterns")
                
                # Create lunch schedule data
                lunch_schedule = filtered_df.groupby(['Hour', 'Overlap Type'])['Duration (seconds)'].count().reset_index()
                lunch_schedule['Duration (minutes)'] = lunch_schedule['Duration (seconds)'] / 60
                
                fig_schedule = px.bar(lunch_schedule,
                                    x='Hour',
                                    y='Duration (seconds)',
                                    color='Overlap Type',
                                    title="Lunch Overlaps by Hour of Day",
                                    labels={'Duration (seconds)': 'Number of Overlaps'})
                fig_schedule.update_xaxes(dtick=1, title="Hour of Day")
                fig_schedule.update_layout(height=400)
                st.plotly_chart(fig_schedule, use_container_width=True)
                
                # Peak lunch times
                peak_hours = filtered_df.groupby('Hour')['Duration (seconds)'].count().sort_values(ascending=False).head(5)
                st.subheader("Peak Lunch Overlap Hours")
                for hour, count in peak_hours.items():
                    st.markdown(f"• **{hour:02d}:00 - {hour:02d}:59**: {count} overlaps")
            
            with tab3:
                # Agent impact analysis
                st.subheader("Agent Lunch Impact")
                
                agent_stats = []
                all_agents = set(filtered_df['Agent 1'].unique()) | set(filtered_df['Agent 2'].unique())
                
                for agent in all_agents:
                    agent_overlaps = filtered_df[
                        (filtered_df['Agent 1'] == agent) | 
                        (filtered_df['Agent 2'] == agent)
                    ]
                    
                    # Count overlaps where this agent is on lunch
                    agent_on_lunch = len(agent_overlaps[
                        ((filtered_df['Agent 1'] == agent) & (filtered_df['Agent 1 On Lunch'])) |
                        ((filtered_df['Agent 2'] == agent) & (filtered_df['Agent 2 On Lunch']))
                    ])
                    
                    # Count overlaps where this agent is NOT on lunch (but someone else is)
                    agent_not_on_lunch = len(agent_overlaps) - agent_on_lunch
                    
                    agent_stats.append({
                        'Agent': agent,
                        'Total Overlaps': len(agent_overlaps),
                        'Agent on Lunch': agent_on_lunch,
                        'Agent Working (Other on Lunch)': agent_not_on_lunch,
                        'Total Overlap Time (minutes)': agent_overlaps['Duration (seconds)'].sum() / 60,
                        'Avg Overlap Duration (minutes)': agent_overlaps['Duration (seconds)'].mean() / 60 if len(agent_overlaps) > 0 else 0
                    })
                
                agent_stats_df = pd.DataFrame(agent_stats).sort_values('Total Overlap Time (minutes)', ascending=False)
                
                # Stacked bar chart
                fig_agent = go.Figure()
                fig_agent.add_trace(go.Bar(
                    name='Agent on Lunch',
                    x=agent_stats_df['Agent'],
                    y=agent_stats_df['Agent on Lunch'],
                    marker_color='lightcoral'
                ))
                fig_agent.add_trace(go.Bar(
                    name='Agent Working (Other on Lunch)',
                    x=agent_stats_df['Agent'],
                    y=agent_stats_df['Agent Working (Other on Lunch)'],
                    marker_color='lightblue'
                ))
                
                fig_agent.update_layout(
                    title='Agent Involvement in Lunch Overlaps',
                    xaxis_title='Agent',
                    yaxis_title='Number of Overlaps',
                    barmode='stack',
                    height=500
                )
                st.plotly_chart(fig_agent, use_container_width=True)
                
                # Agent stats table
                st.subheader("Agent Statistics")
                display_agent_stats = agent_stats_df.round(1)
                st.dataframe(display_agent_stats, use_container_width=True, hide_index=True)
            
            with tab4:
                # Lunch pattern analysis
                st.subheader("Lunch Pattern")
                
                # Day of week patterns
                filtered_df['Day of Week'] = filtered_df['Overlap Start'].dt.day_name()
                filtered_df['Day Number'] = filtered_df['Overlap Start'].dt.dayofweek
                
                day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                daily_stats = filtered_df.groupby(['Day of Week', 'Day Number']).agg({
                    'Duration (seconds)': ['count', 'sum']
                }).reset_index()
                daily_stats.columns = ['Day of Week', 'Day Number', 'Count', 'Total Seconds']
                daily_stats['Total Minutes'] = daily_stats['Total Seconds'] / 60
                daily_stats = daily_stats.sort_values('Day Number')
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fig_day = px.bar(daily_stats,
                                   x='Day of Week',
                                   y='Count',
                                   title='Lunch Overlaps by Day of Week',
                                   color='Count',
                                   color_continuous_scale='Blues')
                    fig_day.update_xaxes(categoryorder='array', categoryarray=day_order)
                    st.plotly_chart(fig_day, use_container_width=True)
                
                with col2:
                    # Lunch duration analysis
                    duration_stats = filtered_df.groupby('Overlap Type')['Duration (seconds)'].agg(['mean', 'median', 'std']).reset_index()
                    duration_stats.columns = ['Overlap Type', 'Mean (sec)', 'Median (sec)', 'Std Dev (sec)']
                    duration_stats['Mean (min)'] = duration_stats['Mean (sec)'] / 60
                    duration_stats['Median (min)'] = duration_stats['Median (sec)'] / 60
                    
                    fig_duration = px.bar(duration_stats,
                                        x='Overlap Type',
                                        y='Mean (min)',
                                        title='Average Overlap Duration by Type',
                                        color='Mean (min)',
                                        color_continuous_scale='Reds')
                    st.plotly_chart(fig_duration, use_container_width=True)
                
                # Time distribution
                st.subheader("Lunch Time Distribution")
                time_bins = pd.cut(filtered_df['Hour'], bins=range(0, 25, 2), right=False, labels=[f"{i:02d}-{i+1:02d}" for i in range(0, 24, 2)])
                time_dist = time_bins.value_counts().sort_index()
                
                fig_time_dist = px.bar(x=time_dist.index, y=time_dist.values,
                                     title="Lunch Overlap Distribution by Time Period",
                                     labels={'x': 'Time Period', 'y': 'Number of Overlaps'})
                st.plotly_chart(fig_time_dist, use_container_width=True)
            
            with tab5:
                # Coverage analysis
                st.subheader("Coverage Impact")
                
                # Calculate simultaneous lunch periods
                both_lunch_df = filtered_df[filtered_df['Overlap Type'] == 'Both on Lunch']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Simultaneous Lunch Periods", len(both_lunch_df))
                    st.metric("Total Time Both on Lunch", 
                             f"{int(both_lunch_df['Duration (seconds)'].sum()//3600)}h {int((both_lunch_df['Duration (seconds)'].sum()%3600)//60)}m")
                    
                    if len(both_lunch_df) > 0:
                        avg_both_lunch = both_lunch_df['Duration (seconds)'].mean() / 60
                        st.metric("Average Simultaneous Lunch", f"{avg_both_lunch:.1f} min")
                
                with col2:
                    # Coverage risk by hour
                    coverage_risk = both_lunch_df.groupby('Hour')['Duration (seconds)'].count()
                    if len(coverage_risk) > 0:
                        fig_risk = px.bar(x=coverage_risk.index, y=coverage_risk.values,
                                        title="Coverage Risk by Hour (Both Agents on Lunch)",
                                        labels={'x': 'Hour', 'y': 'Number of Incidents'},
                                        color=coverage_risk.values,
                                        color_continuous_scale='Reds')
                        fig_risk.update_xaxes(dtick=1)
                        st.plotly_chart(fig_risk, use_container_width=True)
                    else:
                        st.info("No periods found where both agents were simultaneously on lunch.")
                
                # Recommendations
                st.subheader("Coverage Recommendations")
                if len(both_lunch_df) > 0:
                    peak_risk_hour = both_lunch_df.groupby('Hour')['Duration (seconds)'].count().idxmax()
                    st.warning(f"⚠️ **High Risk Period**: {peak_risk_hour:02d}:00-{peak_risk_hour:02d}:59 has the most simultaneous lunch overlaps")
                    
                    # Most problematic agent pairs
                    problematic_pairs = both_lunch_df.groupby(['Agent 1', 'Agent 2'])['Duration (seconds)'].agg(['count', 'sum']).reset_index()
                    problematic_pairs.columns = ['Agent 1', 'Agent 2', 'Incidents', 'Total Duration']
                    problematic_pairs = problematic_pairs.sort_values('Incidents', ascending=False).head(5)
                    
                    st.markdown("**Most Frequent Simultaneous Lunch Pairs:**")
                    for _, row in problematic_pairs.iterrows():
                        minutes = row['Total Duration'] / 60
                        st.markdown(f"• {row['Agent 1']} & {row['Agent 2']}: {row['Incidents']} incidents ({minutes:.0f} min total)")
                else:
                    st.success("No periods found where multiple agents were simultaneously on lunch")
            
            # Detailed table
            st.header("Lunch Overlap Details")
            
            # Format the display dataframe
            display_columns = [
                'Agent 1', 'Agent 2', 'Overlap Start', 'Overlap End', 
                'Duration (formatted)', 'Agent 1 Reason', 'Agent 2 Reason', 'Overlap Type'
            ]
            display_df = filtered_df[display_columns].sort_values('Overlap Start', ascending=False)
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Download option
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="Download Lunch Overlap Report as CSV",
                data=csv,
                file_name=f"lunch_overlaps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
        else:
            st.info("No overlapping periods found where at least one agent was on lunch.")
            
            # Show available reason codes for debugging
            if len(not_ready_df) > 0:
                st.subheader("Available Reason Codes in Data")
                reason_codes = not_ready_df['REASON CODE'].value_counts()
                st.dataframe(reason_codes.reset_index().rename(columns={'index': 'Reason Code', 'REASON CODE': 'Count'}))
                st.markdown("**Tip**: Check if your lunch reason codes match those in the data. You can modify them in the sidebar.")
    else:
        st.warning("No 'Not Ready' states found in the uploaded file.")
        
else:
    # Instructions when no file is uploaded
    st.info("""
    ### How to use this Lunch Overlap  :
    
    1. **Upload your CSV file** containing agent state data
    
    ### Required CSV columns:
    - DATE (format: YYYY/MM/DD)
    - TIME (format: HH:MM:SS)
    - STATE
    - REASON CODE
    - AGENT STATE TIME (format: HH:MM:SS)
    - AGENT

    """)
