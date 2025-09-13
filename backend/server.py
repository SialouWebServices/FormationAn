from fastapi import FastAPI, APIRouter, HTTPException, Cookie, Response, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import aiohttp
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="RIAN Learning Platform", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer(auto_error=False)

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str
    picture: Optional[str] = None
    role: str = "learner"  # learner, admin, instructor
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    profile_completed: bool = False

class UserProfile(BaseModel):
    user_id: str
    location: Optional[str] = None
    phone: Optional[str] = None
    experience_level: Optional[str] = None  # beginner, intermediate, advanced
    motivation: Optional[str] = None
    goals: List[str] = []

class Competence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    number: int
    title: str
    description: str
    duration_hours: int
    units: int
    learning_objectives: List[str]
    evaluation_method: str
    evaluation_description: str
    evaluation_criteria: List[str]
    success_threshold: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserProgress(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    competence_id: str
    status: str = "not_started"  # not_started, in_progress, completed
    current_score: float = 0.0
    quiz_attempts: int = 0
    assignment_submitted: bool = False
    assignment_score: Optional[float] = None
    exam_taken: bool = False
    exam_score: Optional[float] = None
    certified: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class QuizQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    competence_id: str
    question: str
    options: List[str]
    correct_answer: int
    explanation: Optional[str] = None

class QuizAttempt(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    competence_id: str
    answers: List[int]
    score: float
    passed: bool
    attempt_number: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AIWorkshopSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    competence_id: str
    session_type: str  # individual, group
    status: str = "active"  # active, completed
    messages: List[Dict[str, Any]] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Certificate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    competence_id: str
    certificate_number: str
    issued_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    score: float
    valid: bool = True

# Authentication helpers
async def get_session_data(session_id: str):
    """Get user data from Emergent Auth service"""
    url = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
    headers = {"X-Session-ID": session_id}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            return None

async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    session_token = None
    
    # Check for session_token in cookies first
    if "session_token" in request.cookies:
        session_token = request.cookies["session_token"]
    elif credentials:
        session_token = credentials.credentials
    
    if not session_token:
        return None
    
    # Verify session in database
    session_data = await db.user_sessions.find_one({"session_token": session_token})
    if not session_data:
        return None
    
    # Handle timezone comparison
    expires_at = session_data["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        return None
    
    # Get user data
    user = await db.users.find_one({"id": session_data["user_id"]})
    return User(**user) if user else None

# Auth endpoints
@api_router.post("/auth/process-session")
async def process_session(request: Request, response: Response):
    """Process session ID from frontend after Google OAuth"""
    body = await request.json()
    session_id = body.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID required")
    
    # Get user data from Emergent Auth
    user_data = await get_session_data(session_id)
    if not user_data:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data["email"]})
    
    if existing_user:
        user = User(**existing_user)
    else:
        # Create new user
        user = User(
            email=user_data["email"],
            name=user_data["name"],
            picture=user_data.get("picture")
        )
        await db.users.insert_one(user.dict())
    
    # Create session
    session_token = user_data["session_token"]
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    await db.user_sessions.insert_one({
        "user_id": user.id,
        "session_token": session_token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc)
    })
    
    # Set cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        max_age=7 * 24 * 60 * 60,  # 7 days
        httponly=True,
        secure=True,
        samesite="none",
        path="/"
    )
    
    return {"user": user, "session_token": session_token}

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout user"""
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}

@api_router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    """Get current user info"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# Competences endpoints
@api_router.get("/competences", response_model=List[Competence])
async def get_competences():
    """Get all competences"""
    competences = await db.competences.find().sort("number", 1).to_list(length=None)
    return [Competence(**comp) for comp in competences]

@api_router.get("/competences/{competence_id}", response_model=Competence)
async def get_competence(competence_id: str):
    """Get specific competence"""
    competence = await db.competences.find_one({"id": competence_id})
    if not competence:
        raise HTTPException(status_code=404, detail="Competence not found")
    return Competence(**competence)

# Progress endpoints
@api_router.get("/progress", response_model=List[UserProgress])
async def get_user_progress(user: User = Depends(get_current_user)):
    """Get user's progress across all competences"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    progress_list = await db.user_progress.find({"user_id": user.id}).to_list(length=None)
    return [UserProgress(**progress) for progress in progress_list]

@api_router.post("/progress/start/{competence_id}")
async def start_competence(competence_id: str, user: User = Depends(get_current_user)):
    """Start a competence"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Check if competence exists
    competence = await db.competences.find_one({"id": competence_id})
    if not competence:
        raise HTTPException(status_code=404, detail="Competence not found")
    
    # Check if already started
    existing_progress = await db.user_progress.find_one({
        "user_id": user.id,
        "competence_id": competence_id
    })
    
    if existing_progress:
        return UserProgress(**existing_progress)
    
    # Create new progress
    progress = UserProgress(
        user_id=user.id,
        competence_id=competence_id,
        status="in_progress",
        started_at=datetime.now(timezone.utc)
    )
    
    await db.user_progress.insert_one(progress.dict())
    return progress

# Quiz endpoints
@api_router.get("/quiz/{competence_id}/questions")
async def get_quiz_questions(competence_id: str, user: User = Depends(get_current_user)):
    """Get quiz questions for a competence"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    questions = await db.quiz_questions.find({"competence_id": competence_id}).to_list(length=None)
    # Remove correct answers from response
    return [
        {
            "id": q["id"],
            "question": q["question"],
            "options": q["options"]
        } for q in questions
    ]

@api_router.post("/quiz/{competence_id}/submit")
async def submit_quiz(competence_id: str, answers: List[int], user: User = Depends(get_current_user)):
    """Submit quiz answers"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get questions
    questions = await db.quiz_questions.find({"competence_id": competence_id}).to_list(length=None)
    if not questions:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    # Calculate score
    correct_answers = 0
    for i, question in enumerate(questions):
        if i < len(answers) and answers[i] == question["correct_answer"]:
            correct_answers += 1
    
    score = (correct_answers / len(questions)) * 100
    
    # Get competence for success threshold
    competence = await db.competences.find_one({"id": competence_id})
    passed = score >= competence["success_threshold"]
    
    # Get attempt number
    existing_attempts = await db.quiz_attempts.count_documents({
        "user_id": user.id,
        "competence_id": competence_id
    })
    
    # Save attempt
    attempt = QuizAttempt(
        user_id=user.id,
        competence_id=competence_id,
        answers=answers,
        score=score,
        passed=passed,
        attempt_number=existing_attempts + 1
    )
    
    await db.quiz_attempts.insert_one(attempt.dict())
    
    # Update progress
    await db.user_progress.update_one(
        {"user_id": user.id, "competence_id": competence_id},
        {
            "$set": {
                "current_score": score,
                "quiz_attempts": existing_attempts + 1,
                "last_activity": datetime.now(timezone.utc)
            }
        }
    )
    
    return {
        "score": score,
        "passed": passed,
        "correct_answers": correct_answers,
        "total_questions": len(questions)
    }

# AI Workshop endpoints
@api_router.post("/workshop/start/{competence_id}")
async def start_ai_workshop(competence_id: str, user: User = Depends(get_current_user)):
    """Start an AI workshop session"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Create new workshop session
    session = AIWorkshopSession(
        user_id=user.id,
        competence_id=competence_id,
        session_type="individual"
    )
    
    await db.ai_workshop_sessions.insert_one(session.dict())
    
    return {"session_id": session.id, "message": "Workshop session started"}

@api_router.post("/workshop/{session_id}/chat")
async def chat_with_ai(session_id: str, message: str, user: User = Depends(get_current_user)):
    """Chat with AI in workshop"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get workshop session
    session_data = await db.ai_workshop_sessions.find_one({"id": session_id, "user_id": user.id})
    if not session_data:
        raise HTTPException(status_code=404, detail="Workshop session not found")
    
    # Get competence for context
    competence = await db.competences.find_one({"id": session_data["competence_id"]})
    
    try:
        # Initialize AI chat
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=f"""Vous êtes un mentor pédagogique bienveillant spécialisé dans l'alphabétisation numérique. 
            Vous aidez un apprenant dans le module: {competence['title']}.
            
            Objectifs du module: {', '.join(competence['learning_objectives'])}
            
            Votre rôle:
            - Être encourageant et patient
            - Expliquer les concepts simplement
            - Donner des exemples pratiques
            - Poser des questions pour vérifier la compréhension
            - Adapter votre niveau à celui de l'apprenant
            
            Répondez toujours en français et de manière bienveillante."""
        ).with_model("openai", "gpt-4o-mini")
        
        user_message = UserMessage(text=message)
        response = await chat.send_message(user_message)
        
        # Save messages to session
        messages = session_data.get("messages", [])
        messages.extend([
            {"role": "user", "content": message, "timestamp": datetime.now(timezone.utc).isoformat()},
            {"role": "assistant", "content": response, "timestamp": datetime.now(timezone.utc).isoformat()}
        ])
        
        await db.ai_workshop_sessions.update_one(
            {"id": session_id},
            {"$set": {"messages": messages}}
        )
        
        return {"response": response}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

# Dashboard endpoint
@api_router.get("/dashboard")
async def get_dashboard(user: User = Depends(get_current_user)):
    """Get user dashboard data"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get progress
    progress_list = await db.user_progress.find({"user_id": user.id}).to_list(length=None)
    
    # Get certificates
    certificates = await db.certificates.find({"user_id": user.id}).to_list(length=None)
    
    # Calculate statistics
    total_competences = await db.competences.count_documents({})
    completed_competences = len([p for p in progress_list if p["status"] == "completed"])
    in_progress_competences = len([p for p in progress_list if p["status"] == "in_progress"])
    
    # Calculate overall progress percentage
    overall_progress = (completed_competences / total_competences * 100) if total_competences > 0 else 0
    
    return {
        "user": user,
        "overall_progress": overall_progress,
        "total_competences": total_competences,
        "completed_competences": completed_competences,
        "in_progress_competences": in_progress_competences,
        "certificates_earned": len(certificates),
        "progress_list": progress_list,
        "certificates": certificates
    }

# Initialize data
@api_router.post("/init-data")
async def initialize_data():
    """Initialize competences data from RIAN curriculum"""
    
    # Check if data already exists
    existing_count = await db.competences.count_documents({})
    if existing_count > 0:
        return {"message": "Data already initialized"}
    
    # RIAN Curriculum Data
    competences_data = [
        {
            "number": 1,
            "title": "Se familiariser avec le métier et la formation",
            "description": "Découverte du métier d'alphabétiseur numérique et de son environnement professionnel",
            "duration_hours": 15,
            "units": 1,
            "learning_objectives": [
                "Présentation des objectifs de formation",
                "Connaissance de l'environnement professionnel",
                "Sensibilisation au développement durable",
                "Présentation et adaptation du parcours de formation",
                "Description de l'environnement de travail",
                "Informations sur les réalités du métier et des perspectives professionnelles",
                "Confirmation ou infirmation de son orientation professionnelle"
            ],
            "evaluation_method": "Évaluation par jury",
            "evaluation_description": "L'épreuve comportera les items suivants : Sa perception (le métier, le marché du travail, la formation offerte, les possibilités de poursuite des études) ; Son auto positionnement (Se situer par rapport au métier, au marché du travail par rapport au parcours de formation).",
            "evaluation_criteria": ["Cohérence des réponses", "Pertinence des réponses"],
            "success_threshold": 50.0
        },
        {
            "number": 2,
            "title": "Communiquer en français",
            "description": "Développement des compétences de communication écrite et orale en français",
            "duration_hours": 30,
            "units": 2,
            "learning_objectives": [
                "Maniement de la langue (vocabulaire, grammaire, conjugaison, orthographe)",
                "Communication orale",
                "Communication écrite"
            ],
            "evaluation_method": "Tâche complexe",
            "evaluation_description": "Vu l'importance de cette compétence axée sur les connaissances de base indispensables pour l'exercice du métier, l'épreuve portera sur la mobilisation des connaissances (savoir) traitée individuellement. La capacité de communication de l'apprenant est mesurée à partir de sa production écrite.",
            "evaluation_criteria": ["Cohérence des réponses", "Pertinence des réponses"],
            "success_threshold": 50.0
        },
        {
            "number": 3,
            "title": "Prévenir les atteintes à la santé, à la sécurité au travail et à l'environnement",
            "description": "Application des mesures de prévention et de sécurité au travail",
            "duration_hours": 15,
            "units": 1,
            "learning_objectives": [
                "Identification des situations de travail à risques et leurs effets sur la santé, la sécurité et l'intégrité physique du travailleur",
                "Application des lois et les règlements en matière de santé, de sécurité, d'hygiène, de salubrité et de protection de l'environnement au travail",
                "Application des moyens de prévention et de traitement relatifs de l'environnement",
                "Application des mesures préventives à l'égard de la santé et de la sécurité au travail"
            ],
            "evaluation_method": "Tâche complexe",
            "evaluation_description": "Vu l'importance de cette compétence axée sur l'application des mesures de préservation de la santé, de la sécurité au travail et à l'environnement, l'évaluation portera sur une épreuve de connaissances pratiques",
            "evaluation_criteria": ["Précision de la terminologie", "Clarté", "Concision"],
            "success_threshold": 50.0
        },
        {
            "number": 4,
            "title": "Utiliser l'outil numérique",
            "description": "Maîtrise des outils numériques pour la formation à distance",
            "duration_hours": 30,
            "units": 2,
            "learning_objectives": [
                "Recherche d'informations à partir de l'outil numérique",
                "Création de supports pédagogiques et didactiques numériques",
                "Conduite d'une formation à distance"
            ],
            "evaluation_method": "Évaluation des acquis d'apprentissage à distance",
            "evaluation_description": "Vu l'importance de cette compétence axée sur les soins du corps, l'évaluation portera sur une épreuve de connaissances pratiques administrée individuellement et portant sur une situation de soins à l'eau. Le candidat travaille dans le respect des consignes de sécurité, d'hygiène et d'environnement.",
            "evaluation_criteria": ["Maîtrise technique", "Créativité", "Efficacité pédagogique"],
            "success_threshold": 75.0
        },
        {
            "number": 5,
            "title": "Planifier un cours d'alphabétisation",
            "description": "Conception et planification de séances d'alphabétisation",
            "duration_hours": 60,
            "units": 4,
            "learning_objectives": [
                "Interprétation des documents contractuels d'une formation",
                "Analyse des documents pédagogiques d'une formation",
                "Détermination des objectifs d'apprentissage",
                "Construction d'une stratégie d'apprentissage",
                "Définition des critères et les démarches d'évaluation formative à mettre en œuvre",
                "Identification des ressources nécessaires pour l'atteinte des objectifs d'apprentissage",
                "Établissement d'un plan de déroulement de module de formation"
            ],
            "evaluation_method": "Tâche complexe",
            "evaluation_description": "Vu l'importance de cette compétence axée sur la planification d'un cours d'alphabétisation, l'évaluation portera sur une épreuve de connaissances pratiques",
            "evaluation_criteria": ["Précision de la terminologie", "Clarté", "Concision"],
            "success_threshold": 50.0
        },
        {
            "number": 6,
            "title": "Animer un cours d'alphabétisation",
            "description": "Animation et gestion de groupes d'apprenants en alphabétisation",
            "duration_hours": 60,
            "units": 4,
            "learning_objectives": [
                "Préparation de l'intervention d'animation",
                "Motiver les apprenants",
                "Gérer un groupe d'apprenants",
                "Mettre en œuvre des mesures de remédiation"
            ],
            "evaluation_method": "Tâche complexe",
            "evaluation_description": "Vu l'importance de cette compétence axée sur le massage relaxant, l'évaluation portera sur une épreuve de connaissances pratiques administrée individuellement et portant sur un massage relaxant. Le candidat travaille dans le respect des consignes de sécurité, d'hygiène et d'environnement.",
            "evaluation_criteria": ["Précision de la terminologie", "Clarté", "Concision"],
            "success_threshold": 75.0
        },
        {
            "number": 7,
            "title": "Évaluer les acquis de l'apprentissage",
            "description": "Évaluation des progrès et acquis des apprenants",
            "duration_hours": 60,
            "units": 4,
            "learning_objectives": [
                "Planification de l'évaluation des apprentissages",
                "Élaboration des outils et épreuves d'évaluation",
                "Conduite des séances d'évaluation",
                "Analyse des résultats de l'évaluation",
                "Mise en œuvre des mesures de remédiation"
            ],
            "evaluation_method": "Tâche complexe",
            "evaluation_description": "Vu l'importance de cette compétence axée sur les soins du corps, l'évaluation portera sur une épreuve de connaissances pratiques administrée individuellement et portant sur une situation de soins de corps. Le candidat travaille dans le respect des consignes de sécurité, d'hygiène et d'environnement.",
            "evaluation_criteria": ["Précision de la terminologie", "Clarté", "Concision"],
            "success_threshold": 75.0
        },
        {
            "number": 8,
            "title": "Appliquer une démarche entrepreneuriale",
            "description": "Développement de l'esprit entrepreneurial et des compétences de gestion",
            "duration_hours": 15,
            "units": 1,
            "learning_objectives": [
                "Caractérisation de l'entrepreneuriat"
            ],
            "evaluation_method": "Projet entrepreneurial",
            "evaluation_description": "Développement d'un projet entrepreneurial dans le domaine de l'alphabétisation numérique",
            "evaluation_criteria": ["Innovation", "Faisabilité", "Impact social"],
            "success_threshold": 50.0
        },
        {
            "number": 9,
            "title": "Utiliser des moyens de recherche d'emploi",
            "description": "Techniques de recherche d'emploi et d'insertion professionnelle",
            "duration_hours": 15,
            "units": 1,
            "learning_objectives": [
                "Identification des opportunités d'emploi",
                "Rédaction de CV et lettres de motivation",
                "Préparation aux entretiens d'embauche",
                "Développement du réseau professionnel"
            ],
            "evaluation_method": "Simulation d'entretien",
            "evaluation_description": "Mise en situation d'entretien d'embauche et évaluation des outils de recherche d'emploi",
            "evaluation_criteria": ["Présentation personnelle", "Argumentation", "Motivation"],
            "success_threshold": 50.0
        },
        {
            "number": 10,
            "title": "S'intégrer en milieu de travail",
            "description": "Intégration professionnelle et adaptation au milieu de travail",
            "duration_hours": 360,
            "units": 24,
            "learning_objectives": [
                "Adaptation aux règles et procédures de l'entreprise",
                "Développement des relations professionnelles",
                "Application des compétences acquises en situation réelle",
                "Évaluation de sa performance professionnelle"
            ],
            "evaluation_method": "Stage pratique",
            "evaluation_description": "Stage d'immersion en milieu professionnel avec suivi et évaluation continue",
            "evaluation_criteria": ["Adaptation", "Performance", "Relations interpersonnelles", "Autonomie"],
            "success_threshold": 75.0
        }
    ]
    
    # Insert competences
    competences = []
    for comp_data in competences_data:
        competence = Competence(**comp_data)
        competences.append(competence.dict())
    
    await db.competences.insert_many(competences)
    
    # Create some sample quiz questions for each competence
    for competence in competences:
        sample_questions = []
        comp_id = competence["id"]
        
        if competence["number"] == 1:
            sample_questions = [
                {
                    "competence_id": comp_id,
                    "question": "Quel est l'objectif principal de la formation d'alphabétiseur numérique ?",
                    "options": [
                        "Apprendre uniquement l'informatique",
                        "Former des personnes capables d'enseigner la lecture et l'écriture avec des outils numériques",
                        "Devenir développeur web",
                        "Vendre des ordinateurs"
                    ],
                    "correct_answer": 1,
                    "explanation": "L'alphabétiseur numérique combine l'enseignement traditionnel de la lecture/écriture avec les outils numériques."
                },
                {
                    "competence_id": comp_id,
                    "question": "Quelle est une compétence essentielle de l'alphabétiseur numérique ?",
                    "options": [
                        "Programmer des applications",
                        "Réparer des ordinateurs",
                        "Adapter les outils numériques aux besoins des apprenants",
                        "Vendre des logiciels"
                    ],
                    "correct_answer": 2,
                    "explanation": "L'adaptation pédagogique des outils numériques est fondamentale dans ce métier."
                }
            ]
        elif competence["number"] == 2:
            sample_questions = [
                {
                    "competence_id": comp_id,
                    "question": "Quelle est la règle d'accord du participe passé avec l'auxiliaire être ?",
                    "options": [
                        "Il ne s'accorde jamais",
                        "Il s'accorde toujours avec le sujet",
                        "Il s'accorde avec le complément d'objet direct",
                        "Il s'accorde selon l'humeur"
                    ],
                    "correct_answer": 1,
                    "explanation": "Le participe passé employé avec être s'accorde toujours avec le sujet."
                }
            ]
        elif competence["number"] == 4:
            sample_questions = [
                {
                    "competence_id": comp_id,
                    "question": "Quel outil est le plus approprié pour créer une présentation interactive ?",
                    "options": [
                        "Bloc-notes",
                        "PowerPoint ou Google Slides",
                        "Calculatrice",
                        "Lecteur vidéo"
                    ],
                    "correct_answer": 1,
                    "explanation": "Les outils de présentation permettent d'intégrer texte, images et interactivité."
                }
            ]
        
        for q_data in sample_questions:
            question = QuizQuestion(**q_data)
            await db.quiz_questions.insert_one(question.dict())
    
    return {"message": f"Initialized {len(competences)} competences with sample quizzes"}

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