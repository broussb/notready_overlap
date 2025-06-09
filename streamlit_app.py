import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO

st.set_page_config(
    page_title="Agent Not Ready Overlap Analyzer",
    page_icon="👥",
    layout="wide"
)

st.title("Agent Not Ready Overlap Analyzer")
st.markdown("Upload your agent state CSV file to analyze overlapping 'Not Ready' periods between agents.")

# File upload
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    # Read the CSV
    df = pd.read_csv(uploaded_file)
    
    # Show basic info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Records", len(df))
    with col2:
        st.metric("Unique Agents", df['AGENT ID'].nunique())
    with col3:
        st.metric("Not Ready Records", len(df[df['STATE'] == 'Not Ready']))
    
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
        
        # Find overlaps
        overlaps = []
        records = not_ready_df.to_dict('records')
        
        with st.spinner('Finding overlaps...'):
            for i in range(len(records)):
                for j in range(i + 1, len(records)):
                    rec1 = records[i]
                    rec2 = records[j]
                    
                    # Skip if same agent
                    if rec1['AGENT ID'] == rec2['AGENT ID']:
                        continue
                    
                    # Check overlap
                    overlap_start = max(rec1['start_datetime'], rec2['start_datetime'])
                    overlap_end = min(rec1['end_datetime'], rec2['end_datetime'])
                    
                    if overlap_start < overlap_end:
                        overlap_duration = (overlap_end - overlap_start).total_seconds()
                        
                        overlaps.append({
                            'Agent 1': rec1['AGENT ID'],
                            'Agent 2': rec2['AGENT ID'],
                            'Overlap Start': overlap_start,
                            'Overlap End': overlap_end,
                            'Duration (seconds)': overlap_duration,
                            'Duration (formatted)': f"{int(overlap_duration//3600)}h {int((overlap_duration%3600)//60)}m {int(overlap_duration%60)}s",
                            'Agent 1 Reason': rec1['REASON CODE'],
                            'Agent 2 Reason': rec2['REASON CODE'],
                            'Date': overlap_start.date()
                        })
        
        if overlaps:
            overlap_df = pd.DataFrame(overlaps)
            
            # Summary metrics
            st.header("Overlap Summary")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Overlaps", len(overlap_df))
            with col2:
                st.metric("Total Overlap Time", 
                         f"{int(overlap_df['Duration (seconds)'].sum()//3600)}h {int((overlap_df['Duration (seconds)'].sum()%3600)//60)}m")
            with col3:
                st.metric("Average Overlap", 
                         f"{int(overlap_df['Duration (seconds)'].mean()//60)}m {int(overlap_df['Duration (seconds)'].mean()%60)}s")
            with col4:
                st.metric("Max Overlap", 
                         f"{int(overlap_df['Duration (seconds)'].max()//60)}m {int(overlap_df['Duration (seconds)'].max()%60)}s")
            
            # Filters
            st.header("🔍 Filter Options")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                selected_agents = st.multiselect(
                    "Filter by Agents",
                    options=sorted(set(overlap_df['Agent 1'].unique()) | set(overlap_df['Agent 2'].unique())),
                    default=None
                )
            
            with col2:
                min_duration = st.number_input(
                    "Minimum Duration (seconds)",
                    min_value=0,
                    value=0,
                    step=30
                )
            
            with col3:
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
            
            if min_duration > 0:
                filtered_df = filtered_df[filtered_df['Duration (seconds)'] >= min_duration]
            
            if len(date_range) == 2:
                filtered_df = filtered_df[
                    (filtered_df['Date'] >= date_range[0]) & 
                    (filtered_df['Date'] <= date_range[1])
                ]
            
            # Visualizations
            st.header("Visualizations")
            
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["Timeline", "Heatmap", "By Agent", "By Reason", "Time Patterns"])
            
            with tab1:
                # Timeline visualization
                fig = px.scatter(filtered_df, 
                               x='Overlap Start', 
                               y='Duration (seconds)',
                               color='Agent 1',
                               size='Duration (seconds)',
                               hover_data=['Agent 2', 'Agent 1 Reason', 'Agent 2 Reason', 'Duration (formatted)'],
                               title="Overlap Timeline")
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                # Agent pair heatmap
                agent_pairs = filtered_df.groupby(['Agent 1', 'Agent 2'])['Duration (seconds)'].sum().reset_index()
                pivot_table = agent_pairs.pivot(index='Agent 1', columns='Agent 2', values='Duration (seconds)').fillna(0)
                
                fig = px.imshow(pivot_table/60,  # Convert to minutes
                               labels=dict(color="Total Overlap (minutes)"),
                               title="Agent Pair Overlap Heatmap",
                               color_continuous_scale="Blues")
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
            
            with tab3:
                # By agent analysis
                agent_stats = []
                all_agents = set(filtered_df['Agent 1'].unique()) | set(filtered_df['Agent 2'].unique())
                
                for agent in all_agents:
                    agent_overlaps = filtered_df[
                        (filtered_df['Agent 1'] == agent) | 
                        (filtered_df['Agent 2'] == agent)
                    ]
                    agent_stats.append({
                        'Agent ID': agent,
                        'Number of Overlaps': len(agent_overlaps),
                        'Total Overlap Time (minutes)': agent_overlaps['Duration (seconds)'].sum() / 60
                    })
                
                agent_stats_df = pd.DataFrame(agent_stats).sort_values('Total Overlap Time (minutes)', ascending=False)
                
                fig = px.bar(agent_stats_df, 
                            x='Agent ID', 
                            y='Total Overlap Time (minutes)',
                            title="Total Overlap Time by Agent",
                            text='Number of Overlaps')
                fig.update_traces(texttemplate='%{text}', textposition='outside')
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
            
            with tab4:
                # By reason analysis
                reason_stats = filtered_df.groupby(['Agent 1 Reason', 'Agent 2 Reason'])['Duration (seconds)'].agg(['count', 'sum']).reset_index()
                reason_stats['Total Minutes'] = reason_stats['sum'] / 60
                reason_stats = reason_stats.sort_values('Total Minutes', ascending=False).head(15)
                
                fig = px.bar(reason_stats, 
                            x='Total Minutes', 
                            y=reason_stats['Agent 1 Reason'] + ' / ' + reason_stats['Agent 2 Reason'],
                            orientation='h',
                            title="Top 15 Reason Code Combinations",
                            text='count')
                fig.update_traces(texttemplate='%{text} overlaps', textposition='outside')
                fig.update_layout(height=600, yaxis_title="Reason Code Combinations")
                st.plotly_chart(fig, use_container_width=True)
            
            with tab5:
                # Time pattern analysis
                # Extract hour and day of week
                filtered_df['Hour'] = filtered_df['Overlap Start'].dt.hour
                filtered_df['Day of Week'] = filtered_df['Overlap Start'].dt.day_name()
                filtered_df['Day Number'] = filtered_df['Overlap Start'].dt.dayofweek
                
                # Create two columns for the visualizations
                col1, col2 = st.columns(2)
                
                with col1:
                    # Hourly distribution
                    hourly_stats = filtered_df.groupby('Hour').agg({
                        'Duration (seconds)': ['count', 'sum']
                    }).reset_index()
                    hourly_stats.columns = ['Hour', 'Count', 'Total Seconds']
                    hourly_stats['Total Minutes'] = hourly_stats['Total Seconds'] / 60
                    
                    fig_hour = go.Figure()
                    fig_hour.add_trace(go.Bar(
                        x=hourly_stats['Hour'],
                        y=hourly_stats['Count'],
                        name='Number of Overlaps',
                        yaxis='y',
                        offsetgroup=1
                    ))
                    fig_hour.add_trace(go.Scatter(
                        x=hourly_stats['Hour'],
                        y=hourly_stats['Total Minutes'],
                        name='Total Minutes',
                        yaxis='y2',
                        line=dict(color='red', width=3)
                    ))
                    
                    fig_hour.update_layout(
                        title='Overlaps by Hour of Day',
                        xaxis=dict(title='Hour of Day', dtick=1),
                        yaxis=dict(title='Number of Overlaps', side='left'),
                        yaxis2=dict(title='Total Minutes', overlaying='y', side='right'),
                        hovermode='x unified',
                        height=400
                    )
                    st.plotly_chart(fig_hour, use_container_width=True)
                
                with col2:
                    # Day of week distribution
                    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    daily_stats = filtered_df.groupby(['Day of Week', 'Day Number']).agg({
                        'Duration (seconds)': ['count', 'sum']
                    }).reset_index()
                    daily_stats.columns = ['Day of Week', 'Day Number', 'Count', 'Total Seconds']
                    daily_stats['Total Minutes'] = daily_stats['Total Seconds'] / 60
                    daily_stats = daily_stats.sort_values('Day Number')
                    
                    fig_day = go.Figure()
                    fig_day.add_trace(go.Bar(
                        x=daily_stats['Day of Week'],
                        y=daily_stats['Count'],
                        name='Number of Overlaps',
                        text=daily_stats['Count'],
                        textposition='auto',
                    ))
                    
                    fig_day.update_layout(
                        title='Overlaps by Day of Week',
                        xaxis=dict(title='Day of Week', categoryorder='array', categoryarray=day_order),
                        yaxis=dict(title='Number of Overlaps'),
                        height=400
                    )
                    st.plotly_chart(fig_day, use_container_width=True)
                
                # Heatmap of hour vs day of week
                st.subheader("Overlap Intensity Heatmap")
                
                # Create pivot table for heatmap
                heatmap_data = filtered_df.groupby(['Day Number', 'Day of Week', 'Hour'])['Duration (seconds)'].count().reset_index()
                heatmap_data.columns = ['Day Number', 'Day of Week', 'Hour', 'Count']
                
                # Create complete grid (all hours and days)
                all_hours = list(range(24))
                all_days = [(i, day) for i, day in enumerate(day_order)]
                
                # Create pivot table
                pivot_data = pd.DataFrame(index=[d[1] for d in all_days], columns=all_hours)
                for _, row in heatmap_data.iterrows():
                    pivot_data.loc[row['Day of Week'], row['Hour']] = row['Count']
                pivot_data = pivot_data.fillna(0)
                
                fig_heatmap = px.imshow(
                    pivot_data.values,
                    labels=dict(x="Hour of Day", y="Day of Week", color="Number of Overlaps"),
                    x=all_hours,
                    y=day_order,
                    color_continuous_scale="YlOrRd",
                    aspect="auto",
                    title="Overlap Frequency by Day and Hour"
                )
                
                fig_heatmap.update_xaxis(dtick=1)
                fig_heatmap.update_layout(height=400)
                st.plotly_chart(fig_heatmap, use_container_width=True)
                
                # Peak times summary
                st.subheader("Peak Overlap Times")
                col1, col2 = st.columns(2)
                
                with col1:
                    # Top 5 busiest hours
                    top_hours = hourly_stats.nlargest(5, 'Count')[['Hour', 'Count', 'Total Minutes']]
                    top_hours['Time'] = top_hours['Hour'].apply(lambda h: f"{h:02d}:00 - {h:02d}:59")
                    st.markdown("**Top 5 Busiest Hours:**")
                    for _, row in top_hours.iterrows():
                        st.markdown(f"• {row['Time']}: {row['Count']} overlaps ({row['Total Minutes']:.0f} min)")
                
                with col2:
                    # Average by day type
                    filtered_df['Is Weekend'] = filtered_df['Day Number'].isin([5, 6])
                    weekend_stats = filtered_df.groupby('Is Weekend')['Duration (seconds)'].agg(['count', 'mean'])
                    
                    st.markdown("**Weekday vs Weekend:**")
                    weekday_count = weekend_stats.loc[False, 'count'] if False in weekend_stats.index else 0
                    weekend_count = weekend_stats.loc[True, 'count'] if True in weekend_stats.index else 0
                    weekday_avg = weekend_stats.loc[False, 'mean'] / 60 if False in weekend_stats.index else 0
                    weekend_avg = weekend_stats.loc[True, 'mean'] / 60 if True in weekend_stats.index else 0
                    
                    st.markdown(f"• Weekdays: {weekday_count} overlaps (avg {weekday_avg:.1f} min)")
                    st.markdown(f"• Weekends: {weekend_count} overlaps (avg {weekend_avg:.1f} min)")
            
            # Detailed table
            st.header("Overlap Table")
            
            # Format the display dataframe
            display_df = filtered_df[[
                'Agent 1', 'Agent 2', 'Overlap Start', 'Overlap End', 
                'Duration (formatted)', 'Agent 1 Reason', 'Agent 2 Reason'
            ]].sort_values('Overlap Start', ascending=False)
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Download option
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="Download Overlap Report as CSV",
                data=csv,
                file_name=f"agent_overlaps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
        else:
            st.info("No overlapping 'Not Ready' periods found between agents.")
    else:
        st.warning("No 'Not Ready' states found in the uploaded file.")
        
else:
    # Instructions when no file is uploaded
    st.info("""
    ### How to use this tool:
    
    1. **Upload your CSV file** containing agent state data
    
    ### Required CSV columns:
    - DATE (format: YYYY/MM/DD)
    - TIME (format: HH:MM:SS)
    - STATE
    - REASON CODE
    - AGENT STATE TIME (format: HH:MM:SS)
    - AGENT ID
    
    ### What this tool analyzes:
    - Simultaneous "Not Ready" states between different agents
    - Duration and frequency of overlaps
    - Patterns by agent, time, and reason codes
    - Time-based patterns showing when overlaps occur most frequently
    """)
