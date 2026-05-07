import os
import json
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, JSON, DateTime, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Fetch database URL from environment or use default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@postgres:5432/mediadb")

try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.error(f"Failed to initialize database engine: {e}")
    engine = None
    SessionLocal = None

Base = declarative_base()

class GeneratedPost(Base):
    __tablename__ = "generated_posts"

    thread_id = Column(String, primary_key=True, index=True)
    topic = Column(String, nullable=True)
    niche = Column(String, nullable=True)
    research_brief = Column(Text, nullable=True)
    post_contents = Column(JSON, nullable=True)
    status = Column(String, default="PENDING_REVIEW")
    image_url = Column(String, nullable=True)
    image_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

def init_db():
    if engine:
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully.")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")

def save_post_to_db(thread_id: str, topic: str, niche: str, research_brief: str, post_contents: dict, image_url: str = None, image_prompt: str = None):
    if not SessionLocal:
        logger.warning("Database not initialized, skipping save_post_to_db")
        return
        
    db = SessionLocal()
    try:
        # Check if exists
        post = db.query(GeneratedPost).filter(GeneratedPost.thread_id == thread_id).first()
        if not post:
            post = GeneratedPost(
                thread_id=thread_id,
                topic=topic,
                niche=niche,
                research_brief=research_brief,
                post_contents=post_contents,
                image_url=image_url,
                image_prompt=image_prompt,
                status="PENDING_REVIEW"
            )
            db.add(post)
        else:
            post.topic = topic
            post.niche = niche
            post.research_brief = research_brief
            post.post_contents = post_contents
            post.image_url = image_url
            post.image_prompt = image_prompt
            post.status = "PENDING_REVIEW"
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(post, "post_contents")
            
        db.commit()
        logger.info(f"Successfully saved post data to DB for thread {thread_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving to db: {e}")
    finally:
        db.close()

def update_post_status(thread_id: str, new_status: str):
    if not SessionLocal:
        logger.warning("Database not initialized, skipping update_post_status")
        return
        
    db = SessionLocal()
    try:
        post = db.query(GeneratedPost).filter(GeneratedPost.thread_id == thread_id).first()
        if post:
            post.status = new_status
            db.commit()
            logger.info(f"Successfully updated post status to {new_status} for thread {thread_id}")
        else:
            logger.warning(f"Thread {thread_id} not found in DB to update status.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating status in db: {e}")
    finally:
        db.close()

def get_all_posts():
    if not SessionLocal:
        logger.warning("Database not initialized, skipping get_all_posts")
        return []
        
    db = SessionLocal()
    try:
        posts = db.query(GeneratedPost).order_by(GeneratedPost.created_at.desc()).all()
        return posts
    except Exception as e:
        logger.error(f"Error fetching all posts: {e}")
        return []
    finally:
        db.close()

def get_post_by_id(thread_id: str):
    if not SessionLocal:
        logger.warning("Database not initialized, skipping get_post_by_id")
        return None
        
    db = SessionLocal()
    try:
        post = db.query(GeneratedPost).filter(GeneratedPost.thread_id == thread_id).first()
        return post
    except Exception as e:
        logger.error(f"Error fetching post by id {thread_id}: {e}")
        return None
    finally:
        db.close()

