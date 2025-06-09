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
            
            tab1, tab2, tab3, tab4 = st.tabs(["Timeline", "Heatmap", "By Agent", "By Reason"])
            
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
                label="📥 Download Overlap Report as CSV",
                data=csv,
                file_name=f"agent_overlaps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
        else:
            st.info("No overlapping 'Not Ready' periods found between agents.")
    else:
        st.warning("⚠No 'Not Ready' states found in the uploaded file.")
        
else:
    # Instructions when no file is uploaded
    st.info("""
    ### 📤 How to use this tool:
    
    1. **Upload your CSV file** containing agent state data
    
    ### 📊 Required CSV columns:
    - DATE (format: YYYY/MM/DD)
    - TIME (format: HH:MM:SS)
    - STATE
    - REASON CODE
    - AGENT STATE TIME (format: HH:MM:SS)
    - AGENT ID
    
    ### 🎯 What this tool analyzes:
    - Simultaneous "Not Ready" states between different agents
    - Duration and frequency of overlaps
    - Patterns by agent, time, and reason codes
    """)
