import streamlit as st
import requests

# Set the FastAPI backend URL
API_BASE_URL = "http://127.0.0.1:8000"

# Streamlit page configuration
st.set_page_config(page_title="NLP to SQL Converter", layout="wide")

# Initialize session state for connection and schema
if 'connection_success' not in st.session_state:
    st.session_state.connection_success = False

# Page 1: Database Connection
if not st.session_state.connection_success:
    st.title("Database Connection")

    with st.form("db_form"):
        st.subheader("Enter your Database Credentials")
        host = st.text_input("Host", value="localhost")
        port = st.text_input("Port", value="3306")
        user = st.text_input("User")
        password = st.text_input("Password", type="password")
        database = st.text_input("Database Name")

        submitted = st.form_submit_button("Connect")

        if submitted:
            if host and port and user and password and database:
                # Call FastAPI endpoint to connect to DB
                db_info = {
                    "host": host,
                    "port": port,
                    "user": user,
                    "password": password,
                    "database": database
                }

                response = requests.post(f"{API_BASE_URL}/getConnection", json=db_info)

                if response.status_code == 200:
                    data = response.json()
                    if data["connection_flag"]:
                        st.success("Connected to the database successfully!")
                        st.session_state.connection_success = True
                        st.session_state.db_schema = data["schema"]
                    else:
                        st.error("Failed to connect. Please check your credentials.")
                else:
                    st.error(f"Error: {response.json().get('error')}")
            else:
                st.warning("Please fill all the fields.")

# Page 2: NLP Query to SQL
if st.session_state.connection_success:
    st.sidebar.success("Connected to the database!")
    st.title("Ask a Question")

    with st.form("nlp_query_form"):
        st.subheader("Enter your natural language query")
        nlp_input = st.text_area("Natural Language Query")

        submitted_nlp = st.form_submit_button("Generate SQL")

        if submitted_nlp and nlp_input:
            # Call FastAPI endpoint to convert NLP to SQL
            query_data = {"question": nlp_input}
            response = requests.post(f"{API_BASE_URL}/generateQuery", json=query_data)

            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success":
                    st.write(f"**Generated SQL Query**: `{data['query']}`")

                    # Optional: Ask if the user wants to execute the SQL query
                    if st.form_submit_button("Execute SQL"):
                        engine = st.session_state.db_engine
                        result = requests.post(f"{API_BASE_URL}/executeQuery",data["query"])
                        if result.status_code == 200:
                            st.write("**Result**:")
                            st.write(result.json())
                        else:
                            st.error("Failed to execute the query.")
                else:
                    st.error(data.get("error", "Error generating SQL"))
            else:
                st.error(f"Error: {response.json().get('error')}")