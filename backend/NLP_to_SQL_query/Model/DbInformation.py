from pydantic import BaseModel


class DbConnectionInfo(BaseModel):
    host:str = ""
    port: str = ""
    user: str = ""
    password: str = ""
    database: str = ""