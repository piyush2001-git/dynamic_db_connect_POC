import sqlite3
import re
import hashlib
from datetime import datetime
from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate

# --- Helper Function ---
def extract_text(result):
    """
    Extracts and returns the text content from a chain output.
    """
    if isinstance(result, str):
        return result.strip()
    elif hasattr(result, "content"):
        return result.content.strip()
    elif isinstance(result, dict) and "text" in result:
        return result["text"].strip()
    else:
        return str(result).strip()

# --- Configuration ---
# Replace these placeholders with your actual Azure OpenAI credentials.
endpoint = "ENDPOINT PLACEHOLDER"
deployment = "gpt-4o-mini"  
subscription_key = "API KEY PLACEHOLDER"  

# Create two LLM instances:
# One for schema summary generation (with higher max_tokens)
llm_summary = AzureChatOpenAI(
    azure_endpoint=endpoint,
    deployment_name=deployment,
    api_key=subscription_key,
    api_version="2024-05-01-preview",
    temperature=0,
    max_tokens=400,  # Enough for a ~200-word summary
)

# One for all other tasks (SQL generation and final answer)
llm_general = AzureChatOpenAI(
    azure_endpoint=endpoint,
    deployment_name=deployment,
    api_key=subscription_key,
    api_version="2024-05-01-preview",
    temperature=0,
    max_tokens=300,
)

# Database paths
DB_PATH = "mydatabase.db"         # Main database with user data(Change here to shift to in memory database)
MEMORY_DB_PATH = "memory.db"       # Used for caching schema summary and logging interactions

# --- Schema Functions ---
def get_schema(db_path=DB_PATH):
    """
    Retrieves the current database schema from the SQLite database.
    To ensure consistency, sort the schema lines.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
    schema_lines = [row[0] for row in cursor.fetchall() if row[0] is not None]
    conn.close()
    # Sort the lines to reduce false mismatches due to order variations.
    return "\n".join(sorted(schema_lines))

def compute_schema_hash(schema: str) -> str:
    """
    Computes a SHA256 hash of the schema string.
    """
    return hashlib.sha256(schema.encode('utf-8')).hexdigest()

# --- Schema Cache Handling ---
def get_cached_schema_summary(current_schema: str) -> str:
    """
    Checks if a cached schema summary exists for the current schema.
    If the database schema is empty, returns "no_sql".
    Otherwise, if the hash matches, returns the cached summary.
    If not, generates a new summary, updates the cache, and returns it.
    """
    # If there is no schema (i.e., no tables exist), return "no_sql" immediately.
    if not current_schema.strip():
        return "no_sql"
    
    schema_hash = compute_schema_hash(current_schema)
    conn = sqlite3.connect(MEMORY_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_cache (
            id INTEGER PRIMARY KEY,
            schema_hash TEXT,
            schema_summary TEXT,
            last_updated TEXT
        )
    """)
    conn.commit()
    cursor.execute("SELECT schema_hash, schema_summary FROM schema_cache WHERE id = 1")
    row = cursor.fetchone()
    if row and row[0] == schema_hash:
        cached_summary = row[1]
        conn.close()
        return cached_summary
    else:
        new_summary = generate_schema_summary(current_schema)
        now = datetime.now().isoformat()
        if row:
            cursor.execute("""
                UPDATE schema_cache
                SET schema_hash = ?, schema_summary = ?, last_updated = ?
                WHERE id = 1
            """, (schema_hash, new_summary, now))
        else:
            cursor.execute("""
                INSERT INTO schema_cache (id, schema_hash, schema_summary, last_updated)
                VALUES (1, ?, ?, ?)
            """, (schema_hash, new_summary, now))
        conn.commit()
        conn.close()
        return new_summary

# --- Prompt Templates and Chains ---

# Schema Summary Prompt (unchanged)
schema_summary_prompt = PromptTemplate(
    input_variables=["schema"],
    template=(
        "You are an expert database schema analyst. Given the following database schema, create a concise summary (less than 400 tokens) that highlights:"
        "- Table names and their inferred purposes (based on column names if unclear)."
        "- Key columns for queries (e.g., identifiers like 'Id', numerical values like 'Salary', dates like 'Hire Date', text filters like 'Country')."
        "- Potential relationships between tables. Prioritize identifying columns that could act as foreign keys (e.g., 'Id' matching 'EmployeeId', 'Country' across tables) or shared attributes (e.g., 'Name' vs 'Full Name'). If no clear relationships exist, state 'No clear relationships detected.'"
        "- Data types critical for query syntax (e.g., INTEGER, TEXT), especially for columns used in calculations or comparisons."
        "Use exact column names, enclosing those with spaces or special characters in double quotes. Focus on details essential for accurate SQL query generation, especially for JOINs, aggregations, and filters. If token limit nears, prioritize completing relationship descriptions over less critical details."
        "Schema:{schema}"
        "Schema Summary:"
    )
)

def generate_schema_summary(schema: str) -> str:
    generated = schema_summary_prompt | llm_summary
    return extract_text(generated.invoke({"schema": schema}))

# Updated SQL Generation Prompt
sql_generation_prompt = PromptTemplate(
    input_variables=["question", "schema_summary"],
    template=(
        "You are an expert SQL query generator. Given a user’s question and a schema summary, craft an accurate SQL query following these guidelines:"
        "1. Use exact table and column names from the schema summary, enclosing spaces or special characters in double quotes."
        "2. For text searches or filters (e.g., country names), use case-insensitive exact or partial matches (e.g., LOWER(column) = LOWER('term') or LIKE '%term%'), ensuring consistency with schema data (e.g., 'United States' vs 'us')."
        "3. Use JOINs only when the schema summary suggests potential relationships (e.g., matching 'Country', 'Id' to 'EmployeeId'). Validate JOIN columns share similar types or purposes; if unclear, avoid JOINs and note limitations."
        "4. If the question is ambiguous or misspelled, infer intent from column names (e.g., 'avereage' as 'average') or table purposes, prioritizing schema alignment."
        "5. For aggregations (e.g., AVG, SUM) or multi-level groupings (e.g., by country, gender), use GROUP BY with all non-aggregated columns. For complex logic, prefer CTEs or subqueries, ensuring logical steps (e.g., compute averages before comparisons)."
        "6. Handle calculations with data type compatibility (e.g., CAST(INTEGER as REAL) for divisions, datediff-like logic for dates using strftime)."
        "7. For statistical requests (e.g., correlation), note SQLite lacks built-in functions; select raw paired data (e.g., tenure, salary) ordered for external analysis."
        "8. Return 'NO_SQL' only if the schema definitively lacks required tables/columns or intent cannot be reasonably inferred. Otherwise, attempt a query reflecting the question’s core intent."
        "9. Output only the SQL query, no explanations."
        "Schema Summary: {schema_summary}"
        "User Question: {question}"
        "SQL Query:"
    )
)

sql_generation_chain = sql_generation_prompt | llm_general

def generate_sql_query(user_query: str, schema_summary: str) -> str:
    generated = sql_generation_chain.invoke({"question": user_query, "schema_summary": schema_summary})
    sql_query = extract_text(generated)
    # Remove any markdown formatting if present.
    sql_query = re.sub(r"```(sql)?", "", sql_query).strip()
    return sql_query

# Final Answer Generation Prompt (unchanged)
final_answer_prompt = PromptTemplate(
    input_variables=["question", "result"],
    template=(
        "You are a highly professional, courteous, and reliable AI agent for EY. Your responses must always maintain a uniform tone and a consistent length (approximately 60 to 80 words). "
        "When crafting your answer, follow these rules carefully:\n\n"
        "1. If the user's question pertains to data retrieval and the provided SQL Result contains valid, relevant data, use that data to form a clear and concise summary that directly answers the query.\n\n"
        "2. If the SQL Result indicates 'No relevant data found', then decide based on the nature of the question:\n"
        "   a. For questions about your identity, capabilities, or general conversational topics (e.g., greetings, 'how are you', 'who are you', or 'what is your role'), provide a warm, friendly, and informative response describing your functions as EY's AI agent.\n"
        "   b. For all other off-topic questions, respond exactly with: \"I'm sorry, I cannot answer that question at the moment. Is there any other query I can help with?\"\n\n"
        "3. Do not include any internal technical details or extraneous information.\n\n"
        "User's Question: {question}\n\n"
        "SQL Result: {result}\n\n"
        "Final Answer:"
    )
)
final_answer_chain = final_answer_prompt | llm_general

# --- Memory Logging Function (unchanged) ---
def log_memory(user_query, sql_query, sql_result, final_answer, memory_db_path=MEMORY_DB_PATH):
    """
    Logs the interaction details to the memory database.
    Creates the memory_logs table if it doesn't exist.
    """
    conn = sqlite3.connect(memory_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user_query TEXT,
            sql_query TEXT,
            sql_result TEXT,
            final_answer TEXT
        )
    """)
    timestamp = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO memory_logs (timestamp, user_query, sql_query, sql_result, final_answer)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, user_query, sql_query, sql_result, final_answer))
    conn.commit()
    conn.close()

# --- New SQL Validation Function ---
def validate_sql_query(sql_query: str) -> bool:
    """
    Validates the SQL query to ensure it's a SELECT query and safe to execute.
    Returns True if safe, False otherwise.
    """
    sql_query = sql_query.strip().upper()
    if not sql_query.startswith("SELECT"):
        return False
    # Check for dangerous keywords
    dangerous_keywords = ["DROP ", "DELETE ", "UPDATE ", "INSERT ", "ALTER ", "TRUNCATE "]
    for keyword in dangerous_keywords:
        if keyword in sql_query:
            return False
    return True

# --- Updated SQL Execution Function ---
def execute_sql(query: str) -> str:
    """
    Executes the SQL query on the main database.
    Returns the result or an error message based on specific SQLite exceptions.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return "No relevant data found."
        return str(rows)
    except sqlite3.OperationalError as e:
        if "no such table" in str(e).lower():
            return "Table not found."
        elif "syntax error" in str(e).lower():
            return "SQL syntax error."
        else:
            return "SQL execution error."
    except sqlite3.Error:
        return "Database error."

# --- Updated Main Agent Function ---
def agent_response(user_query: str) -> str:
    """
    Processes the user's query with the updated flow:
    1. Retrieve schema and compute hash.
    2. Get cached schema summary.
    3. Generate SQL query.
    4. Validate and execute SQL if applicable.
    5. Generate final answer.
    6. Log interaction.
    """
    # Step 1: Retrieve current schema.
    full_schema = get_schema()
    # Step 2: Retrieve cached schema summary.
    schema_summary = get_cached_schema_summary(full_schema)
    # Step 3: Generate SQL query.
    sql_query = generate_sql_query(user_query, schema_summary)
    # Step 4: Validate and execute SQL.
    if sql_query.upper() == "NO_SQL":
        sql_result = "No relevant data found."
    else:
        if not validate_sql_query(sql_query):
            sql_result = "Invalid SQL query detected."
        else:
            sql_result = execute_sql(sql_query)
    # Step 5: Generate final answer.
    generated_final = final_answer_chain.invoke({"question": user_query, "result": sql_result})
    final_answer = extract_text(generated_final)
    # Step 6: Log the interaction.
    log_memory(user_query, sql_query, sql_result, final_answer)
    return final_answer

# --- Example Usage ---
if __name__ == "__main__":
    while True:
        query = input("Enter query: ")
        if query.lower() in ["quit", "exit"]:
            print("Successfully quit the program!")
            break
        answer = agent_response(query)
        print("Final Answer:\n", answer)