"""Run Streamlit frontend."""

import os
import subprocess

if __name__ == "__main__":
    # Set Streamlit configuration
    os.environ['STREAMLIT_SERVER_PORT'] = '8501'
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'
    
    # Run Streamlit with new step-by-step UI
    subprocess.run([
        "streamlit",
        "run",
        "streamlit_app_v2.py",
        "--server.port=8501",
        "--server.address=0.0.0.0"
    ])
