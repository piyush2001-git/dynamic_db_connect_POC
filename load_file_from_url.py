import requests
import pandas as pd
import sqlite3
import io
from datetime import datetime

# Define the SQLite database path (change to shift to using in memory database, also change in ai_agent_response.py file to connect)
DB_PATH = "mydatabase.db"

### Helper Functions

#### Fetch Data from URL
def fetch_data(url, token=None):
    """
    Fetches data from a given URL, optionally with OAuth token.

    Args:
        url (str): The URL to fetch data from.
        token (str, optional): OAuth token for authentication.

    Returns:
        requests.Response: The response object containing the data.

    Raises:
        Exception: If the request fails (e.g., network error, invalid URL).
    """
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch data: {e}")

#### Process JSON Data
def process_json(response):
    """
    Parses JSON data into a pandas DataFrame, handling various structures.

    Args:
        response (requests.Response): The response object with JSON content.

    Returns:
        pd.DataFrame: The parsed DataFrame.

    Raises:
        Exception: If JSON parsing fails.
    """
    try:
        json_data = response.json()  # Parse JSON content
        if isinstance(json_data, list):
            # Directly handle a list of dictionaries or records
            df = pd.json_normalize(json_data)
        elif isinstance(json_data, dict):
            # Look for a key containing a list or dict to flatten
            data_key = next((key for key in json_data if isinstance(json_data[key], (list, dict))), None)
            if data_key and isinstance(json_data[data_key], list):
                df = pd.json_normalize(json_data[data_key])  # Flatten the list
            elif data_key and isinstance(json_data[data_key], dict):
                sub_key = next((k for k in json_data[data_key] if isinstance(json_data[data_key][k], list)), None)
                if sub_key:
                    df = pd.json_normalize(json_data[data_key][sub_key])
                else:
                    df = pd.json_normalize(json_data[data_key])
            else:
                # Handle a single dictionary with no nested list
                df = pd.json_normalize(json_data)
        else:
            raise Exception("JSON data must be a list or dictionary")
        
        if df.empty:
            raise Exception("No tabular data found in JSON")
        return df
    except Exception as e:
        raise Exception(f"Failed to parse JSON: {e}")

#### Process CSV Data
def process_csv(response):
    """
    Parses CSV data into a pandas DataFrame.

    Args:
        response (requests.Response): The response object with CSV content.

    Returns:
        pd.DataFrame: The parsed DataFrame.

    Raises:
        Exception: If CSV parsing fails.
    """
    try:
        df = pd.read_csv(io.StringIO(response.text), sep=None, engine='python')  # Auto-detect separator
        if df.empty:
            raise Exception("No data found in CSV")
        return df
    except Exception as e:
        raise Exception(f"Failed to parse CSV: {e}")

#### Preprocess DataFrame
def preprocess_dataframe(df):
    """
    Preprocesses the DataFrame to ensure SQLite compatibility.

    Args:
        df (pd.DataFrame): The DataFrame to process.

    Returns:
        pd.DataFrame: The preprocessed DataFrame.
    """
    for col in df.columns:
        # Convert lists or dictionaries to strings
        if df[col].apply(lambda x: isinstance(x, (list, dict))).any():
            df[col] = df[col].apply(str)
        
        # Format datetime columns as strings
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
        
        # Replace NaN with None for SQLite NULL
        df[col] = df[col].where(pd.notnull(df[col]), None)
    
    return df

#### Map Data Types to SQLite
def get_sqlite_dtype(series):
    """
    Maps pandas data types to SQLite data types.

    Args:
        series (pd.Series): The pandas Series to evaluate.

    Returns:
        str: The corresponding SQLite data type.
    """
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"
    elif pd.api.types.is_float_dtype(series):
        return "REAL"
    elif pd.api.types.is_bool_dtype(series):
        return "INTEGER"  # SQLite stores booleans as 0/1
    else:
        return "TEXT"  # Default for strings and other types

#### Generate Unique Table Name
def generate_table_name(df):
    """
    Generates a unique table name based on a timestamp and generic prefix.

    Args:
        df (pd.DataFrame): The DataFrame to base the name on.

    Returns:
        str: A unique table name.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Use a generic prefix unless specific hints exist in columns
    prefix = "data"
    if any(col.lower() in df.columns for col in ["name", "title"]):
        prefix = "records"
    return f"{prefix}_{timestamp}"

#### Main Function to Load Data
def load_file_from_url(url, token=None):
    """
    Loads data from a URL and stores it in a SQLite database.

    Args:
        url (str): The URL to fetch data from.
        token (str, optional): OAuth token for authentication.

    Returns:
        str: A success message with the table name or an error message.
    """
    # Step 1: Fetch data
    try:
        response = fetch_data(url, token)
    except Exception as e:
        return f"Error: {e}"

    # Step 2: Determine data format and parse
    content_type = response.headers.get('Content-Type', '').lower()
    if 'application/json' in content_type:
        try:
            df = process_json(response)
        except Exception as e:
            return f"Error: Failed to parse JSON: {e}"
    elif 'text/csv' in content_type:
        try:
            df = process_csv(response)
        except Exception as e:
            return f"Error: Failed to parse CSV: {e}"
    else:
        # Fallback for mislabeled content types
        try:
            df = process_json(response)
        except Exception:
            try:
                df = process_csv(response)
            except Exception as e:
                return f"Error: Failed to parse data (tried JSON and CSV): {e}"

    # Step 3: Preprocess the DataFrame
    df = preprocess_dataframe(df)

    # Step 4: Generate table name
    table_name = generate_table_name(df)

    # Step 5: Map data types
    dtype_mapping = {col: get_sqlite_dtype(df[col]) for col in df.columns}

    # Step 6: Store in SQLite
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df.to_sql(table_name, conn, index=False, if_exists='fail', dtype=dtype_mapping)
        return f"Success: Data stored in table '{table_name}'."
    except sqlite3.Error as e:
        return f"Error: Failed to store data in SQLite: {e}"

### Execution
if __name__ == "__main__":
    url = input("Enter the URL: ").strip()
    result = load_file_from_url(url)
    print(result)