import os
import uuid

from fastapi import FastAPI
from pydantic import BaseModel
from langchain_community.utilities.sql_database import SQLDatabase
import google.generativeai as genai
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
import redis
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy import text
from starlette.responses import JSONResponse



#importing customs models classes
from Model.DbInformation import DbConnectionInfo

app  = FastAPI()
# redis_client = redis.StrictRedis(host='127.0.0.1', port=6379, db=0)
# redis_client.set("user-session-name-or-id", "Hello World")
# value = redis_client.get('user-session-name-or-id')
# print(str(value))

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)


class Question(BaseModel):
    question: str

# class DbConnectionInfo(BaseModel):
#     host:str
#     port: str
#     user: str
#     password: str
#     database: str

db_instance =  DbConnectionInfo()

DB_schema = {}
session_id = ""


@app.get("/")
def sayhello():
    response = "Hello This is Test"
    user = {"Name":"Praddep","car":"me pagal hu"}
    redis_client = redis.StrictRedis(host='127.0.0.1',port=6379,db=0)
    redis_client.hmset("testing" ,user)
    data = redis_client.hgetall("testing")
    session_id  = str(uuid.uuid4()) # Generate unique session ID for each user
    print(session_id)
    return data

@app.post("/getConnection")
def getconnection(info: DbConnectionInfo):
    print(info)
    global  db_instance
    db_instance.host = info.host
    db_instance.port = info.port
    db_instance.user = info.user
    db_instance.password = info.password
    db_instance.database = info.database
    database=info.database

    connection_flag = False

    try:
        database_props = SQLDatabase.from_uri(f"mysql+pymysql://{info.user}:{info.password}@{info.host}/{info.database}")
        print(database_props.dialect)
        print(database_props.table_info)
        print("OK ok")
        print("OK ok")
        engine = create_engine(f"mysql+pymysql://{info.user}:{info.password}@{info.host}/{info.database}")
        print("reached")
        metadata = MetaData()
        metadata.reflect(bind=engine)
        try:
            with engine.connect() as connection:
                print(database)
                result = connection.execute(text("SHOW TABLES"))
                print("Connected Successfully. Tables in the Database:")

                for row in result:
                    print(row)
                connection_flag = True
        except OperationalError as e:
            print("Operational Error has Occured",str(e))
        except IntegrityError as e:
            print("Integrity error Occured", str(e))
        except Exception as e:
            print("An unexpected error occured", str(e))

        finally:
            if connection_flag:
                print("Connection Established")
            else:
                print("Failed to Connect")

        if(connection_flag):
            print("\nLooking For Changes...")

            for table_name in metadata.tables:
                table = metadata.tables[table_name]

                table_info = {
                    "columns": [],
                    "primary_key": [],
                    "foreign_key": [],
                    "indexes": [],
                    "unique_constraints": [],
                    "check_constraints": []
                }

                print(f"\nTable: {table_name}")

                for column in table.columns:
                    print(f"Column: {column.name}, Type: {column.type}")
                    table_info["columns"].append({"name": column.name, "type": str(column.type)})
                    # tColumn = f"\nColumn: {column.name}, Type: {column.type}"

                table_info["primary_key"] = [pk.name for pk in table.primary_key.columns]
                print("Primary Key:", [pk.name for pk in table.primary_key.columns])

                for fk in table.foreign_keys:
                    print(f"Foreign Key:{fk.column},References {fk.target_fullname}")
                    table_info["foreign_key"].append([{f"Foreign Key:{fk.column},References {fk.target_fullname}"}])

                DB_schema[table_name] = table_info
                DB_schema_string = {key: str(value) for key ,value in DB_schema.items() }
            redis_client = redis.StrictRedis(host='127.0.0.1', port=6379, db=0)
            redis_client.hset(session_id, mapping=DB_schema_string)
            data  = redis_client.hgetall(session_id)
            if len(data)>0:
                print(f"redis cached data: {data}")
            else:
                print(f"nothing found from cache")
            return JSONResponse(content={
                "schema":DB_schema_string,
                "connection_flag": connection_flag
            })
        else:
            connection_flag=False
            return JSONResponse(content={"error:" "Connection failed"}, status_code=400)
    except Exception as e:
        print(f"Something wrong..{str(e)}")


@app.post("/generateQuery")
def generateQuery(info: Question):
    global sql_query
    redis_conn = redis.StrictRedis(host='127.0.0.1',port=6379,db=0)
    db_schema = redis_conn.hgetall(session_id)
    prompt=f"You are an expert SQL master. Convert the following natural language question: {info.question} to an SQL query, considering the following database schema: {db_schema}. Make sure to provide a unique query based on the provided question."

    model = genai.GenerativeModel('gemini-1.5-pro-exp-0827',
                                  generation_config={"response_mime_type": "application/json"})
    response = model.generate_content(prompt)

    import json
    response_text = response._result.candidates[0].content.parts[0].text
    parsed_json = json.loads(response_text)
    print(response_text)

    try:
        if "query" in parsed_json:
            sql_query = parsed_json["query"]
            sql_query = sql_query.replace("\\", "")
        elif "SQL" in parsed_json:
            sql_query = parsed_json["SQL"]
            sql_query = sql_query.replace("\\", "")

        if sql_query:
            #send the query to frontend
            return JSONResponse(content={"query":sql_query, "status":"success"})
        else:
            # Handle case when neither "query" nor "SQL" exists
            return JSONResponse(content={"error": "No query found", "status": "failed"})
    except Exception as e:
        print(e)
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/executeQuery")
def executeQuery(query:str):
    print("in executeQuery")
    try:
        database_uri = f"mysql+pymysql://{db_instance.user}:{db_instance.password}@{db_instance.host}/{db_instance.database}"
        engine = create_engine(f"{database_uri}")
        print("OK")
        metadata = MetaData()
        metadata.reflect(bind=engine)
        print("OK")
        if not query:
            print("No query was sent")
            return JSONResponse(content={"error":"No query was Sent"}, status_code=400)
        with engine.connect() as connection:
            result = connection.execute(text(query))
            rows = [dict(row) for row in result]
            return JSONResponse(content={"result":rows},status_code=200)
    except Exception as e:
        print(e)