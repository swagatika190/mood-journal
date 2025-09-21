from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Initialize LLM Chat
llm_key = os.environ.get('EMERGENT_LLM_KEY')

def get_llm_chat(session_id: str, system_message: str = "You are a supportive mental wellness AI assistant focused on helping Indian youth. Be empathetic, culturally sensitive, and provide practical guidance."):
    chat = LlmChat(
        api_key=llm_key,
        session_id=session_id,
        system_message=system_message
    ).with_model("gemini", "gemini-2.0-flash")
    return chat

# Define Models
class MoodEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_session: str
    mood_score: int  # 1-10 scale
    emotions: List[str]
    description: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ai_insights: Optional[str] = None

class MoodEntryCreate(BaseModel):
    user_session: str
    mood_score: int
    emotions: List[str]
    description: str

class AnonymousStory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_session: str
    title: str
    story: str
    category: str
    is_approved: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    support_count: int = 0

class AnonymousStoryCreate(BaseModel):
    user_session: str
    title: str
    story: str
    category: str

class WellnessChallenge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    category: str
    points: int
    duration_days: int

class UserProgress(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_session: str
    total_points: int = 0
    completed_challenges: List[str] = []
    current_streak: int = 0
    mood_entries_count: int = 0

class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_session: str
    message: str
    response: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ChatRequest(BaseModel):
    user_session: str
    message: str

# Routes
@api_router.get("/")
async def root():
    return {"message": "MoodSpace API - Supporting Youth Mental Wellness"}

# Mood Tracking
@api_router.post("/mood", response_model=MoodEntry)
async def create_mood_entry(mood_data: MoodEntryCreate):
    try:
        # Generate AI insights based on mood data
        chat = get_llm_chat(mood_data.user_session)
        
        insight_prompt = f"""
        A young person has shared their mood:
        Mood Score: {mood_data.mood_score}/10
        Emotions: {', '.join(mood_data.emotions)}
        Description: {mood_data.description}
        
        Provide a brief, culturally sensitive insight (2-3 sentences) that acknowledges their feelings and offers gentle guidance or encouragement. Consider Indian cultural context.
        """
        
        user_message = UserMessage(text=insight_prompt)
        ai_response = await chat.send_message(user_message)
        
        mood_dict = mood_data.dict()
        mood_dict['ai_insights'] = ai_response
        mood_obj = MoodEntry(**mood_dict)
        
        await db.mood_entries.insert_one(mood_obj.dict())
        
        # Update user progress
        await update_user_progress(mood_data.user_session, "mood_entry")
        
        return mood_obj
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/mood/{user_session}", response_model=List[MoodEntry])
async def get_user_moods(user_session: str, limit: int = 30):
    moods = await db.mood_entries.find({"user_session": user_session}).sort("timestamp", -1).limit(limit).to_list(limit)
    return [MoodEntry(**mood) for mood in moods]

# Anonymous Story Sharing
@api_router.post("/stories", response_model=AnonymousStory)
async def create_story(story_data: AnonymousStoryCreate):
    story_dict = story_data.dict()
    story_obj = AnonymousStory(**story_dict)
    await db.stories.insert_one(story_obj.dict())
    return story_obj

@api_router.get("/stories", response_model=List[AnonymousStory])
async def get_approved_stories(category: Optional[str] = None, limit: int = 20):
    query = {"is_approved": True}
    if category:
        query["category"] = category
    
    stories = await db.stories.find(query).sort("timestamp", -1).limit(limit).to_list(limit)
    return [AnonymousStory(**story) for story in stories]

@api_router.post("/stories/{story_id}/support")
async def support_story(story_id: str):
    await db.stories.update_one(
        {"id": story_id},
        {"$inc": {"support_count": 1}}
    )
    return {"message": "Support added"}

# AI Chat
@api_router.post("/chat", response_model=Dict[str, str])
async def chat_with_ai(chat_request: ChatRequest):
    try:
        chat = get_llm_chat(
            chat_request.user_session,
            """You are MoodSpace AI, a supportive mental wellness companion for Indian youth. 
            Your role is to:
            1. Listen empathetically and validate feelings
            2. Provide culturally sensitive guidance
            3. Suggest practical coping strategies
            4. Encourage professional help when needed
            5. Be warm, non-judgmental, and understanding of Indian family dynamics
            6. Use simple, encouraging language
            7. Never provide medical diagnoses or replace professional therapy
            
            Always prioritize safety - if someone expresses suicidal thoughts, immediately encourage them to seek help from professionals or crisis helplines."""
        )
        
        user_message = UserMessage(text=chat_request.message)
        ai_response = await chat.send_message(user_message)
        
        # Save chat history
        chat_obj = ChatMessage(
            user_session=chat_request.user_session,
            message=chat_request.message,
            response=ai_response
        )
        await db.chat_history.insert_one(chat_obj.dict())
        
        return {"response": ai_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Wellness Challenges
@api_router.get("/challenges", response_model=List[WellnessChallenge])
async def get_wellness_challenges():
    # Pre-defined challenges
    challenges = [
        {
            "id": str(uuid.uuid4()),
            "title": "Daily Gratitude",
            "description": "Write down 3 things you're grateful for each day",
            "category": "mindfulness",
            "points": 10,
            "duration_days": 7
        },
        {
            "id": str(uuid.uuid4()),
            "title": "5-Minute Breathing",
            "description": "Practice deep breathing for 5 minutes daily",
            "category": "relaxation",
            "points": 15,
            "duration_days": 5
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Digital Detox Hour",
            "description": "Stay off social media for 1 hour each day",
            "category": "balance",
            "points": 20,
            "duration_days": 3
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Connect with Nature",
            "description": "Spend 15 minutes outdoors daily",
            "category": "nature",
            "points": 12,
            "duration_days": 7
        }
    ]
    return [WellnessChallenge(**challenge) for challenge in challenges]

# User Progress
@api_router.get("/progress/{user_session}", response_model=UserProgress)
async def get_user_progress(user_session: str):
    progress = await db.user_progress.find_one({"user_session": user_session})
    if not progress:
        # Create new progress record
        progress_obj = UserProgress(user_session=user_session)
        await db.user_progress.insert_one(progress_obj.dict())
        return progress_obj
    return UserProgress(**progress)

async def update_user_progress(user_session: str, activity_type: str, points: int = 5):
    """Helper function to update user progress"""
    progress = await db.user_progress.find_one({"user_session": user_session})
    if not progress:
        progress_obj = UserProgress(user_session=user_session, total_points=points)
        if activity_type == "mood_entry":
            progress_obj.mood_entries_count = 1
        await db.user_progress.insert_one(progress_obj.dict())
    else:
        update_data = {"$inc": {"total_points": points}}
        if activity_type == "mood_entry":
            update_data["$inc"]["mood_entries_count"] = 1
        await db.user_progress.update_one(
            {"user_session": user_session},
            update_data
        )

# Analytics for patterns
@api_router.get("/analytics/{user_session}")
async def get_mood_analytics(user_session: str):
    try:
        # Get recent mood entries
        recent_moods = await db.mood_entries.find(
            {"user_session": user_session}
        ).sort("timestamp", -1).limit(14).to_list(14)
        
        if not recent_moods:
            return {"message": "No mood data available"}
        
        # Generate AI insights on patterns
        chat = get_llm_chat(user_session)
        
        mood_data = []
        for mood in recent_moods:
            mood_data.append(f"Date: {mood['timestamp'].strftime('%Y-%m-%d')}, Score: {mood['mood_score']}, Emotions: {', '.join(mood['emotions'])}")
        
        pattern_prompt = f"""
        Analyze this 2-week mood pattern for a young person:
        {chr(10).join(mood_data)}
        
        Provide a brief, encouraging analysis (3-4 sentences) highlighting:
        1. Any positive trends or patterns
        2. Areas for gentle attention
        3. One specific, actionable suggestion for improvement
        
        Be supportive and focus on growth rather than problems.
        """
        
        user_message = UserMessage(text=pattern_prompt)
        analysis = await chat.send_message(user_message)
        
        # Calculate basic stats
        avg_mood = sum(mood['mood_score'] for mood in recent_moods) / len(recent_moods)
        
        return {
            "analysis": analysis,
            "average_mood": round(avg_mood, 1),
            "total_entries": len(recent_moods),
            "trend": "improving" if recent_moods[0]['mood_score'] > avg_mood else "stable"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()