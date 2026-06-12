from pydantic import BaseModel


# 定义用户注册提交的数据类型
class RegisterRequest(BaseModel):
    username: str
    password: str


# 定义POST '/login' 请求体数据结构
class LoginRequest(BaseModel):
    username: str
    password: str
