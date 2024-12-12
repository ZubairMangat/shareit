import socket
import streamlit as st
import os

# Function to send a file
def send_file(file_path, receiver_ip, port):
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((receiver_ip, port))  # Connect to the receiver

        # Send file name first
        file_name = os.path.basename(file_path)
        client_socket.send(file_name.encode('utf-8'))
        client_socket.recv(1024)  # Wait for acknowledgment

        # Send the file data
        with open(file_path, "rb") as f:
            while chunk := f.read(1024):
                client_socket.sendall(chunk)

        st.success("File sent successfully!")
        client_socket.close()

    except Exception as e:
        st.error(f"Error: {str(e)}")

# Function to receive a file
def receive_file_server(port):
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("0.0.0.0", port))
        server_socket.listen(1)

        conn, addr = server_socket.accept()
        st.info(f"Connected to {addr}")

        # Receive the file name first
        file_name = conn.recv(1024).decode('utf-8')
        conn.send(b"ACK")  # Acknowledge receipt of the file name

        received_file_path = os.path.join("downloads", file_name)

        # Ensure the downloads directory exists
        os.makedirs(os.path.dirname(received_file_path), exist_ok=True)

        # Receive the file data
        with open(received_file_path, "wb") as file:
            while chunk := conn.recv(1024):
                file.write(chunk)

        st.success(f"File received successfully! Saved as: {received_file_path}")

        # Provide download option for the file
        with open(received_file_path, "rb") as file:
            file_data = file.read()
            st.download_button(
                label="Download Received File",
                data=file_data,
                file_name=file_name,
                mime="application/octet-stream"
            )

        conn.close()
        server_socket.close()

    except OSError as e:
        if e.errno == 98:  # Address already in use
            st.error(f"Port {port} is already in use. Please try another port.")
        else:
            st.error(f"Error: {str(e)}")
    except Exception as e:
        st.error(f"Error: {str(e)}")

# Function to get the device's IP address
def get_device_ip():
    try:
        hostname = socket.gethostname()  # Get the host name
        address = socket.gethostbyname(hostname)  # Get the IP address
        return address
    except Exception as e:
        return f"Error: {str(e)}"

# Streamlit UI with navigation
def main():
    # State to manage navigation
    if "page" not in st.session_state:
        st.session_state.page = "home"

    # Home page
    if st.session_state.page == "home":
        st.title("File Transfer App")
        st.write("Choose an option below:")
        col1, col2, col3 = st.columns(3)

        # Navigation buttons
        if col1.button("Send File"):
            st.session_state.page = "send"

        if col2.button("Receive File"):
            st.session_state.page = "receive"

        # Check IP Address
        if col3.button("Check IP Address"):
            device_ip = get_device_ip()
            st.info(f"Device IP Address: {device_ip}")

    # Send File page
    elif st.session_state.page == "send":
        st.title("Send a File")

        # File selection
        file = st.file_uploader("Choose a file to send", type=["jpg", "png", "txt", "pdf", "zip", "mp4", "docx"])

        # Receiver IP and Port
        receiver_ip = st.text_input("Enter Receiver IP Address (e.g., 192.168.0.122)")
        port = st.number_input("Enter Port (default: 12345)", value=12345, step=1, format="%d")

        if st.button("Send"):
            if file and receiver_ip:
                # Save uploaded file temporarily
                temp_file_path = f"temp_{file.name}"
                with open(temp_file_path, "wb") as f:
                    f.write(file.getbuffer())

                # Send the file
                send_file(temp_file_path, receiver_ip, port)

                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            else:
                st.error("Please select a file and enter a valid IP address.")

        if st.button("Back"):
            st.session_state.page = "home"

    # Receive File page
    elif st.session_state.page == "receive":
        st.title("Receive a File")

        # Port for receiving
        port = st.number_input("Enter Port to Listen (default: 12345)", value=12345, step=1, format="%d")

        if st.button("Receive"):
            st.info("Waiting for a file...")
            receive_file_server(port)

        if st.button("Back"):
            st.session_state.page = "home"

# Run the app
if __name__ == "__main__":
    main()
