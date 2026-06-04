from asyncio import threads
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from pymongo.mongo_client import MongoClient
from datetime import datetime, timedelta
from typing import Optional
try:
    from database import Posts, Users
except ModuleNotFoundError:
    from app.database import Posts, Users

CONNECTION_STRING = "mongodb+srv://Mayank1234:mayank1234@mydata.ezd5wcv.mongodb.net/"
SECRET_KEY = "supersecret_blog_key_change_in_prod"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 1 # 1hour

mongo_db = MongoClient(CONNECTION_STRING)
database = mongo_db["Blogpost"]

posts_col = database["posts"]
users_col = database["users"]

#search index
try:
    posts_col.create_index([("title", "text"), ("author_username", "text")])
except Exception:
    pass

posts_obj = Posts(posts_col)
users_obj = Users(users_col)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = users_obj.get_by_id(user_id)
    if not user:
        raise credentials_exception
    return user

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class PostCreate(BaseModel):
    title: str
    content: str


class PostUpdate(BaseModel):
    title: str
    content: str

app = FastAPI(title="Blog Post API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/register", status_code=201, tags=["User"])
async def register(body: RegisterRequest):
    "Register a new user account."
    hashed = hash_password(body.password)
    ok, result = users_obj.create_user(body.username, body.email, hashed)
    if not ok:
        raise HTTPException(status_code=400, detail=result)
    # strip password before returning
    result.pop("password", None)
    return {"message": "User registered successfully", "user": result}


@app.post("/login", tags=["User"])
async def login(form: OAuth2PasswordRequestForm = Depends()):
    "Login with username + password → returns a JWT access token."
    user = users_obj.get_by_username(form.username)
    if not user or not verify_password(form.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        data={"sub": user["user_id"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
        "user_id": user["user_id"],
    }


@app.get("/posts/", tags=["Posts"])
async def get_all_posts():
    "Return every post in the database (sorted newest-first)."
    posts = posts_obj.get_all_posts()
    posts.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return {"count": len(posts), "posts": posts}


@app.get("/posts/search", tags=["Posts"])
async def search_posts(q: str = Query(..., min_length=1, description="Search by post title or author username")):
    """
    Search posts by **title** or **author username**.
    Example: GET /posts/search?q=python
    """
    results = posts_obj.search_posts(q)
    return {"count": len(results), "query": q, "posts": results}


@app.post("/posts/", status_code=201, tags=["Posts"])
async def create_post(body: PostCreate, current_user=Depends(get_current_user)):
    "Create a new post (login required). Returns the created post with its `post_id`."
    post = posts_obj.create_post(
        title=body.title,
        content=body.content,
        author_username=current_user["username"],
        author_id=current_user["user_id"],
    )
    return {"message": "Post created successfully", "post": post}


@app.put("/posts/{post_id}", tags=["Posts"])
async def update_post(post_id: str, body: PostUpdate, current_user=Depends(get_current_user)):
    "Update a post (login required, owner only)."
    post, err = posts_obj.update_post(post_id, body.title, body.content, current_user["user_id"])
    if err:
        code = 404 if err == "Post not found" else 403
        raise HTTPException(status_code=code, detail=err)
    return {"message": "Post updated successfully", "post": post}


@app.delete("/posts/{post_id}", tags=["Posts"])
async def delete_post(post_id: str, current_user=Depends(get_current_user)):
    "Delete a post (login required, owner only)."
    ok, err = posts_obj.delete_post(post_id, current_user["user_id"])
    if not ok:
        code = 404 if err == "Post not found" else 403
        raise HTTPException(status_code=code, detail=err)
    return {"message": f"Post '{post_id}' deleted successfully"}
