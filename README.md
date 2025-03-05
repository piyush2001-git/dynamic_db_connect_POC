# ChatBot POC
A Flask web app that enables users to ask questions about data from URLs using natural language, powered by OpenAI.

## Main Functionality
The ChatBot POC is a Flask-based web application designed to allow users to interact with data sourced from URLs through natural language queries. Users provide URLs, and the app retrieves the relevant data, processes it, and leverages OpenAI’s language models to interpret questions and deliver accurate, context-aware responses. This seamless integration of web data retrieval and AI-driven query processing makes it a powerful proof-of-concept for natural language interaction with online content.

## System diagram:
    You can refer to the system diagram attached in the project folder for better understanding of the user flow of the system.  

## Main Features

- **Flexible URL Support**  
  The app supports querying data from both public URLs (no authentication required) and secure URLs protected by OAuth 2.0 authentication, using single-token authentication for access. This versatility enables interaction with a wide range of web resources.

- **Database Management**  
  - **`mydatabase.db`**: Stores data fetched from URLs, this is for testing purposes. For production, switch to an in-memory database by setting the connection to :memory: in `load_file_from_url.py` AND `ai_agent_response.py` to avoid persistent storage of user data.  
  - **`memory.db`**: A separate SQLite database that maintains memory logs, such as chat histories and schema caches, to preserve context and enhance response quality across sessions.  

- **In-Memory Database Option**  
  The app can switch to an in-memory database by updating the database connection strings in the `load_file_from_url.py` and `ai_agent_response.py` scripts. This eliminates persistent storage 
  of the user's data.

- **OpenAI API Integration**  
  The app interfaces with OpenAI via API calls managed in the `ai_agent_response.py` script. Users can customize the AI model, API KEY, and other parameters to tailor the agent’s behavior to specific needs.
  To tune the model's responses, tweak the prompts provided to the model along with the attributes for the completions api call.

## Setup

Follow these steps to set up and run the ChatBot POC on your local machine:

1. **Clone the Repository**  
   Clone the project repository and navigate to the project folder

2. **Create and Activate a Virtual Environment**
    python -m venv venv
    source venv/Scripts/activate

3. **Install required dependencies**
    pip install -r requirements.txt

4. **Add AzureOpenAI Authentication details**
    In `ai_agent_response.py` replace the placeholder with your API key and endpoint to authenticate before using the app

5. **Initialize Databases**
    Create sqlite databases as:
    sqlite3 mydatabase.db(to create database file for storing data from url while testing)
    sqlite3 memory.db(to create database to store memory logs)

6. **Run the application**
    flask run
    Once running you can access the app at your localhost endpoint in your browser.

## How to Use It

- **Set Up OpenAI API KEY**  
  - Obtain AzureOpenAI API KEY and endpoint for your model deployment.  
  - Update `ai_agent_response.py` with your API KEY, endpoint and desired model (e.g., "gpt-4o-mini").

- **Manage Database and Memory Logs**  
  - Create memory.db and mydatabase.db(if necessary using sqlite3)
  - Use the default `.db` files for persistent storage during development.  
  - For production, switch to an in-memory database as described in "Database Management."  
  - To clear chat histories, delete tables in `memory.db` (they’ll be recreated automatically).

- **Handle URL Authentication**  
  - For public URLs, enter the URL directly in the app’s interface.  
  - For OAuth 2.0-protected URLs, provide a valid token as prompted.

- **Interact with the App**  
  - Once running, access the app at `http://127.0.0.1:5000/`, and chat with our ai agent.