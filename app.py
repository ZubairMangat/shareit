import socket
import streamlit as st
import os
from datetime import datetime
import json
import magic  # for file type detection
import hashlib

# Set page config at the very beginning
st.set_page_config(page_title="File Transfer Dashboard", layout="wide")

# Constants
HISTORY_FILE = "transfer_history.json"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB in bytes
ALLOWED_MIME_TYPES = {
    'application/pdf', 'image/jpeg', 'image/png', 'text/plain',
    'application/zip', 'video/mp4', 'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

# Custom styling remains the same
st.markdown("""
    <style>
    .main-header {
        color: #2e7d32;
        text-align: center;
        padding: 1rem;
    }
    .stat-card {
        background-color: #f5f5f5;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .file-history {
        margin: 1rem 0;
        padding: 1rem;
        border-radius: 10px;
        background-color: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        background-color: #2e7d32;
        color: white;
    }
    .stButton>button:hover {
        background-color: #1b5e20;
    }
    </style>
""", unsafe_allow_html=True)

# Utility functions remain the same
def load_transfer_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_transfer_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def add_transfer_record(operation, filename, status, size=None):
    history = load_transfer_history()
    history.append({
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'operation': operation,
        'filename': filename,
        'status': status,
        'size': size or 'Unknown'
    })
    save_transfer_history(history)

# New security check function
def check_file_security(file_path):
    try:
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            return False, f"File size ({file_size/1024/1024:.2f} MB) exceeds maximum limit of 100 MB"

        # Check file type
        file_type = magic.from_file(file_path, mime=True)
        if file_type not in ALLOWED_MIME_TYPES:
            return False, f"File type {file_type} is not allowed"

        # Calculate file hash for integrity
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        file_hash = sha256_hash.hexdigest()

        return True, file_hash
    except Exception as e:
        return False, f"Security check failed: {str(e)}"

# Modified send_file function
def send_file(file_path, receiver_ip, port):
    try:
        # Security check before sending
        is_safe, result = check_file_security(file_path)
        if not is_safe:
            st.error(f"Security check failed: {result}")
            add_transfer_record("Send", os.path.basename(file_path), f"Failed - Security: {result}")
            return

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((receiver_ip, port))

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        # Send metadata
        metadata = {
            "name": file_name,
            "size": file_size,
            "hash": result  # This is the file hash from security check
        }
        client_socket.send(json.dumps(metadata).encode('utf-8'))
        client_socket.recv(1024)  # Wait for acknowledgment

        with open(file_path, "rb") as f:
            while chunk := f.read(1024):
                client_socket.sendall(chunk)

        st.success("File sent successfully!")
        add_transfer_record("Send", file_name, "Success", f"{file_size/1024:.2f} KB")
        client_socket.close()

    except Exception as e:
        error_msg = str(e)
        st.error(f"Error: {error_msg}")
        add_transfer_record("Send", os.path.basename(file_path), f"Failed - {error_msg}")

# Modified receive_file_server function
def receive_file_server(port):
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("0.0.0.0", port))
        server_socket.listen(1)

        conn, addr = server_socket.accept()
        st.info(f"Connected to {addr}")

        # Receive metadata
        metadata = json.loads(conn.recv(1024).decode('utf-8'))
        conn.send(b"ACK")

        file_name = metadata["name"]
        file_size = metadata["size"]
        expected_hash = metadata["hash"]

        if file_size > MAX_FILE_SIZE:
            raise Exception("File size exceeds maximum limit of 100 MB")

        received_file_path = os.path.join("downloads", file_name)
        os.makedirs(os.path.dirname(received_file_path), exist_ok=True)

        with open(received_file_path, "wb") as file:
            total_size = 0
            while chunk := conn.recv(1024):
                file.write(chunk)
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    raise Exception("File size exceeds maximum limit during transfer")

        # Verify received file
        is_safe, result = check_file_security(received_file_path)
        if not is_safe:
            os.remove(received_file_path)
            raise Exception(f"Security check failed: {result}")

        if result != expected_hash:
            os.remove(received_file_path)
            raise Exception("File integrity check failed")

        st.success(f"File received and verified successfully! Saved as: {received_file_path}")
        
        with open(received_file_path, "rb") as file:
            file_data = file.read()
            st.download_button(
                label="📥 Download Received File",
                data=file_data,
                file_name=file_name,
                mime="application/octet-stream",
                key="download_button"
            )

        add_transfer_record("Receive", file_name, "Success", f"{total_size/1024:.2f} KB")
        conn.close()
        server_socket.close()

    except Exception as e:
        error_msg = str(e)
        st.error(f"Error: {error_msg}")
        add_transfer_record("Receive", "Unknown", f"Failed - {error_msg}")

def get_device_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "Could not determine IP"

def main():
    if "page" not in st.session_state:
        st.session_state.page = "home"

    # Sidebar
    with st.sidebar:
        st.title("Navigation")
        st.markdown("---")
        
        if st.button("🏠 Dashboard", key="nav_dashboard", use_container_width=True):
            st.session_state.page = "home"
        
        if st.button("📤 Send File", key="nav_send", use_container_width=True):
            st.session_state.page = "send"
            
        if st.button("📥 Receive File", key="nav_receive", use_container_width=True):
            st.session_state.page = "receive"

        st.markdown("---")
        device_ip = get_device_ip()
        st.info(f"💻 Your IP Address: {device_ip}")

    # Main content area
    if st.session_state.page == "home":
        st.markdown("<h1 class='main-header'>File Transfer Dashboard</h1>", unsafe_allow_html=True)
        
        # Statistics
        history = load_transfer_history()
        successful = sum(1 for item in history if "Success" in item['status'])
        failed = len(history) - successful
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
                <div class='stat-card'>
                    <h3>Total Transfers</h3>
                    <h2>{}</h2>
                </div>
            """.format(len(history)), unsafe_allow_html=True)
            
        with col2:
            st.markdown("""
                <div class='stat-card'>
                    <h3>Successful</h3>
                    <h2>{}</h2>
                </div>
            """.format(successful), unsafe_allow_html=True)
            
        with col3:
            st.markdown("""
                <div class='stat-card'>
                    <h3>Failed</h3>
                    <h2>{}</h2>
                </div>
            """.format(failed), unsafe_allow_html=True)

        # Recent transfers
        st.markdown("### Recent Transfers")
        if history:
            for item in list(reversed(history))[:5]:  # Show last 5 transfers
                status_color = "#4CAF50" if "Success" in item['status'] else "#f44336"
                st.markdown(f"""
                    <div class='file-history'>
                        <p><strong>Time:</strong> {item['timestamp']}</p>
                        <p><strong>Operation:</strong> {item['operation']}</p>
                        <p><strong>File:</strong> {item['filename']}</p>
                        <p><strong>Size:</strong> {item['size']}</p>
                        <p style="color: {status_color}"><strong>Status:</strong> {item['status']}</p>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No transfer history available")

    elif st.session_state.page == "send":
        st.markdown("<h1 class='main-header'>Send File</h1>", unsafe_allow_html=True)
        
        file = st.file_uploader("Choose a file to send", 
                               type=["jpg", "png", "txt", "pdf", "zip", "mp4", "docx"],
                               key="file_uploader")
        
        receiver_ip = st.text_input("🌐 Enter Receiver's IP Address", key="receiver_ip")
        port = st.number_input("🔌 Port Number", value=12345, step=1, key="send_port")
        
        col1, col2 = st.columns(2)
        
        if col1.button("📤 Send File", key="send_button", use_container_width=True):
            if file and receiver_ip:
                if file.size > MAX_FILE_SIZE:
                    st.error(f"File size ({file.size/1024/1024:.2f} MB) exceeds maximum limit of 100 MB")
                else:
                    temp_file_path = f"temp_{file.name}"
                    with open(temp_file_path, "wb") as f:
                        f.write(file.getbuffer())
                    send_file(temp_file_path, receiver_ip, port)
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
            else:
                st.error("Please select a file and enter a valid IP address.")
                
        if col2.button("🏠 Back to Home", key="send_back", use_container_width=True):
            st.session_state.page = "home"

    elif st.session_state.page == "receive":
        st.markdown("<h1 class='main-header'>Receive File</h1>", unsafe_allow_html=True)
        
        port = st.number_input("🔌 Port Number", value=12345, step=1, key="receive_port")
        
        col1, col2 = st.columns(2)
        
        if col1.button("📥 Start Receiving", key="receive_button", use_container_width=True):
            st.info("Waiting for incoming file...")
            receive_file_server(port)
            
        if col2.button("🏠 Back to Home", key="receive_back", use_container_width=True):
            st.session_state.page = "home"

if __name__ == "__main__":
    main()
