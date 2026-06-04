from pymongo.collection import Collection
from bson import ObjectId
import uuid
from datetime import datetime

def _serialize(doc: dict) -> dict:
    """Convert ObjectId → str so the doc is JSON-serialisable."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

#users
class Users:
    def __init__(self, collection: Collection) -> None:
        self.col = collection

    #register
    def create_user(self, username: str, email: str, hashed_password: str):
        """Returns (True, user_doc) or (False, reason_str)."""
        if self.col.find_one({"$or": [{"username": username}, {"email": email}]}):
            return False, "Username or email already exists"
        doc = {
            "user_id": str(uuid.uuid4()),
            "username": username,
            "email": email,
            "password": hashed_password,
            "created_at": datetime.utcnow().isoformat(),
        }
        self.col.insert_one(doc)
        return True, _serialize(doc)

    #login
    def get_by_username(self, username: str):
        doc = self.col.find_one({"username": username})
        return _serialize(doc) if doc else None

    def get_by_id(self, user_id: str):
        doc = self.col.find_one({"user_id": user_id})
        return _serialize(doc) if doc else None


#posts
class Posts:
    def __init__(self, collection: Collection) -> None:
        self.col = collection

    #create
    def create_post(self, title: str, content: str, author_username: str, author_id: str):
        doc = {
            "post_id": str(uuid.uuid4()),
            "title": title,
            "content": content,
            "author_username": author_username,
            "author_id": author_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.col.insert_one(doc)
        return _serialize(doc)

    #read all
    def get_all_posts(self):
        docs = list(self.col.find({}, {"_id": 0}))
        return docs

    #title or author username
    def search_posts(self, query: str):
        regex = {"$regex": query, "$options": "i"}
        docs = list(
            self.col.find(
                {"$or": [{"title": regex}, {"author_username": regex}]},
                {"_id": 0},
            )
        )
        return docs

    #update
    def update_post(self, post_id: str, title: str, content: str, author_id: str):
        try:
            existing = self.get_post_by_id(post_id)
            if not existing:
                return None, "Post not found"
            if existing["author_id"] != author_id:
                return None, "Not authorised"
            self.col.update_one(
                {"post_id": post_id},
                {"$set": {"title": title, "content": content, "updated_at": datetime.utcnow().isoformat()}},
            )
            return self.get_post_by_id(post_id), None
        except:
            return None, "Invalid post_id"

    #delete
    def delete_post(self, post_id: str, author_id: str):
        existing = self.get_post_by_id(post_id)
        if not existing:
            return False, "Post not found"
        if existing["author_id"] != author_id:
            return False, "Not authorised"
        self.col.delete_one({"post_id": post_id})
        return True, None