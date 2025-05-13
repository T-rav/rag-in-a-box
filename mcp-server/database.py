from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Boolean, Table, MetaData
from sqlalchemy.sql import func, select
from typing import Optional, List
import os
from datetime import datetime

# Create base class for models
Base = declarative_base()

# Database connection
DB_URL = os.getenv("DB_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/openwebui")
engine = create_async_engine(DB_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# OpenWebUI User model (matches the OpenWebUI database schema)
class OpenWebUIUser(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    hashed_password = Column(String)
    oauth_accounts = Column(JSON, default=list)
    settings = Column(JSON, default=dict)

# Our internal models
class User(Base):
    __tablename__ = "mcp_users"
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    metadata = Column(JSON, default=dict)
    openwebui_id = Column(String, ForeignKey("users.id"))  # Reference to OpenWebUI user

class Context(Base):
    __tablename__ = "contexts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    content = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    metadata = Column(JSON, default=dict)

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    metadata = Column(JSON, default=dict)

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String)  # user, assistant, system
    content = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata = Column(JSON, default=dict)

# Database operations
async def get_openwebui_user_by_email(email: str) -> Optional[OpenWebUIUser]:
    """Get OpenWebUI user by email"""
    async with async_session() as session:
        result = await session.execute(
            select(OpenWebUIUser).where(OpenWebUIUser.email == email)
        )
        return result.scalar_one_or_none()

async def get_user_by_id(user_id: str) -> Optional[User]:
    """Get our user by ID"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

async def get_user_by_email(email: str) -> Optional[User]:
    """Get our user by email"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

async def create_user(user_id: str, email: str, name: Optional[str] = None, openwebui_id: Optional[str] = None) -> User:
    """Create a new user in our database"""
    async with async_session() as session:
        user = User(
            id=user_id,
            email=email,
            name=name,
            openwebui_id=openwebui_id
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

async def get_user_contexts(
    user_id: str,
    limit: int = 10,
    active_only: bool = True
) -> List[Context]:
    """Get recent contexts for a user"""
    async with async_session() as session:
        query = select(Context).where(Context.user_id == user_id)
        if active_only:
            query = query.where(Context.is_active == True)
        query = query.order_by(Context.created_at.desc()).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

async def create_context(
    user_id: str,
    content: dict,
    expires_at: Optional[datetime] = None,
    metadata: Optional[dict] = None
) -> Context:
    """Create a new context entry"""
    async with async_session() as session:
        context = Context(
            user_id=user_id,
            content=content,
            expires_at=expires_at,
            metadata=metadata or {}
        )
        session.add(context)
        await session.commit()
        await session.refresh(context)
        return context

async def get_conversation_history(
    user_id: str,
    limit: int = 5,
    active_only: bool = True
) -> List[Conversation]:
    """Get recent conversations for a user"""
    async with async_session() as session:
        query = select(Conversation).where(Conversation.user_id == user_id)
        if active_only:
            query = query.where(Conversation.is_active == True)
        query = query.order_by(Conversation.updated_at.desc()).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

async def create_conversation(
    user_id: str,
    title: Optional[str] = None,
    metadata: Optional[dict] = None
) -> Conversation:
    """Create a new conversation"""
    async with async_session() as session:
        conversation = Conversation(
            user_id=user_id,
            title=title,
            metadata=metadata or {}
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation

async def add_message(
    conversation_id: int,
    role: str,
    content: str,
    metadata: Optional[dict] = None
) -> Message:
    """Add a message to a conversation"""
    async with async_session() as session:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata or {}
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message

# Initialize database
async def init_db():
    """Initialize the database with tables"""
    async with engine.begin() as conn:
        # Only create our tables, not the OpenWebUI tables
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(
            sync_conn,
            tables=[User.__table__, Context.__table__, Conversation.__table__, Message.__table__]
        )) 