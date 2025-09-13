import React, { useState, useEffect, createContext, useContext } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation, useParams } from "react-router-dom";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Auth Context
const AuthContext = createContext();

const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setUser(response.data);
    } catch (error) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = (redirectUrl) => {
    const authUrl = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
    window.location.href = authUrl;
  };

  const logout = async () => {
    try {
      await axios.post(`${API}/auth/logout`, {}, { withCredentials: true });
      setUser(null);
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
};

// Components
const LoadingSpinner = () => (
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
    <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-indigo-600"></div>
  </div>
);

const Header = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-indigo-600 cursor-pointer" onClick={() => navigate('/')}>
              RIAN Learning
            </h1>
            <span className="ml-3 text-sm text-gray-500">Réseau Ivoirien des Alphabétiseurs Numériques</span>
          </div>
          
          {user && (
            <div className="flex items-center space-x-4">
              <nav className="flex space-x-6">
                <button 
                  onClick={() => navigate('/dashboard')}
                  className="text-gray-600 hover:text-indigo-600 px-3 py-2 rounded-md text-sm font-medium"
                >
                  Tableau de bord
                </button>
                <button 
                  onClick={() => navigate('/competences')}
                  className="text-gray-600 hover:text-indigo-600 px-3 py-2 rounded-md text-sm font-medium"
                >
                  Compétences
                </button>
              </nav>
              
              <div className="flex items-center space-x-3">
                {user.picture && (
                  <img 
                    src={user.picture} 
                    alt={user.name}
                    className="h-8 w-8 rounded-full"
                  />
                )}
                <span className="text-sm text-gray-700">{user.name}</span>
                <button
                  onClick={logout}
                  className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded-md text-sm"
                >
                  Déconnexion
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) return <LoadingSpinner />;
  if (!user) return <Navigate to="/login" replace />;
  
  return children;
};

const LoginPage = () => {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Check for session_id in URL fragment
    const fragment = window.location.hash;
    if (fragment.includes('session_id=')) {
      const sessionId = fragment.split('session_id=')[1].split('&')[0];
      handleSessionId(sessionId);
      return;
    }

    // If already authenticated, redirect to dashboard
    if (user) {
      navigate('/dashboard');
    }
  }, [user, navigate]);

  const handleSessionId = async (sessionId) => {
    try {
      const response = await axios.post(`${API}/auth/process-session`, 
        { session_id: sessionId },
        { withCredentials: true }
      );
      
      if (response.data.user) {
        window.location.hash = ''; // Clear the fragment
        navigate('/dashboard');
      }
    } catch (error) {
      console.error('Authentication error:', error);
      alert('Erreur d\'authentification. Veuillez réessayer.');
    }
  };

  const handleLogin = () => {
    const redirectUrl = `${window.location.origin}/login`;
    login(redirectUrl);
  };

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-xl shadow-lg">
        <div className="text-center">
          <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
            Plateforme RIAN Learning
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Réseau Ivoirien des Alphabétiseurs Numériques
          </p>
          <p className="mt-4 text-sm text-gray-500">
            Formez-vous pour devenir un alphabétiseur numérique certifié. 
            Maîtrisez les 10 compétences essentielles en 720 heures de formation.
          </p>
        </div>
        
        <div className="mt-8 space-y-6">
          <button
            onClick={handleLogin}
            className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition duration-200"
          >
            Se connecter avec Google
          </button>
          
          <div className="mt-6 text-center text-xs text-gray-500">
            <p>🎯 10 compétences • 📚 720 heures • 🏆 Certification reconnue</p>
          </div>
        </div>
      </div>
    </div>
  );
};

const Dashboard = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const response = await axios.get(`${API}/dashboard`, { withCredentials: true });
      setDashboardData(response.data);
    } catch (error) {
      console.error('Error fetching dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  const { user, overall_progress, total_competences, completed_competences, in_progress_competences, certificates_earned } = dashboardData;

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Welcome Section */}
          <div className="bg-white overflow-hidden shadow rounded-lg mb-6">
            <div className="px-4 py-5 sm:p-6">
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                Bonjour {user.name} ! 👋
              </h1>
              <p className="text-gray-600">
                Bienvenue sur votre tableau de bord de formation RIAN. Suivez votre progression et continuez votre parcours d'alphabétiseur numérique.
              </p>
            </div>
          </div>

          {/* Progress Overview */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="text-2xl">📊</div>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">
                        Progression globale
                      </dt>
                      <dd className="text-lg font-medium text-gray-900">
                        {Math.round(overall_progress)}%
                      </dd>
                    </dl>
                  </div>
                </div>
                <div className="mt-3">
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-indigo-600 h-2 rounded-full" 
                      style={{ width: `${overall_progress}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="text-2xl">✅</div>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">
                        Compétences terminées
                      </dt>
                      <dd className="text-lg font-medium text-gray-900">
                        {completed_competences}/{total_competences}
                      </dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="text-2xl">⏳</div>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">
                        En cours
                      </dt>
                      <dd className="text-lg font-medium text-gray-900">
                        {in_progress_competences}
                      </dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="text-2xl">🏆</div>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">
                        Certificats obtenus
                      </dt>
                      <dd className="text-lg font-medium text-gray-900">
                        {certificates_earned}
                      </dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white shadow rounded-lg mb-8">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Actions rapides
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <button
                  onClick={() => navigate('/competences')}
                  className="bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg p-4 text-left transition-colors"
                >
                  <div className="text-2xl mb-2">📚</div>
                  <h4 className="font-medium text-indigo-900">Voir les compétences</h4>
                  <p className="text-sm text-indigo-600 mt-1">
                    Explorez le curriculum complet des 10 compétences
                  </p>
                </button>

                <button
                  onClick={() => navigate('/competences')}
                  className="bg-green-50 hover:bg-green-100 border border-green-200 rounded-lg p-4 text-left transition-colors"
                >
                  <div className="text-2xl mb-2">▶️</div>
                  <h4 className="font-medium text-green-900">Continuer ma formation</h4>
                  <p className="text-sm text-green-600 mt-1">
                    Reprenez là où vous vous êtes arrêté
                  </p>
                </button>

                <button
                  onClick={() => navigate('/workshops')}
                  className="bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-lg p-4 text-left transition-colors"
                >
                  <div className="text-2xl mb-2">🤖</div>
                  <h4 className="font-medium text-purple-900">Ateliers IA</h4>
                  <p className="text-sm text-purple-600 mt-1">
                    Pratiquez avec votre mentor IA personnalisé
                  </p>
                </button>
              </div>
            </div>
          </div>

          {/* Recent Activity */}
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Votre parcours RIAN
              </h3>
              <div className="text-sm text-gray-600">
                <p className="mb-2">
                  <strong>Durée totale :</strong> 720 heures réparties sur 10 compétences
                </p>
                <p className="mb-2">
                  <strong>Certification :</strong> Reconnue par le RIAN et les institutions partenaires
                </p>
                <p>
                  <strong>Modalités :</strong> Formation mixte (présentiel + distanciel) avec accompagnement IA
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const CompetencesPage = () => {
  const [competences, setCompetences] = useState([]);
  const [progress, setProgress] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [competencesRes, progressRes] = await Promise.all([
        axios.get(`${API}/competences`, { withCredentials: true }),
        axios.get(`${API}/progress`, { withCredentials: true })
      ]);
      
      setCompetences(competencesRes.data);
      setProgress(progressRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getProgressForCompetence = (competenceId) => {
    return progress.find(p => p.competence_id === competenceId);
  };

  const getStatusBadge = (competenceProgress) => {
    if (!competenceProgress) {
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">Non commencé</span>;
    }
    
    switch (competenceProgress.status) {
      case 'completed':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Terminé</span>;
      case 'in_progress':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">En cours</span>;
      default:
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">Non commencé</span>;
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">Les 10 Compétences RIAN</h1>
            <p className="mt-2 text-gray-600">
              Curriculum complet de formation d'alphabétiseur numérique (720 heures - 48 unités)
            </p>
          </div>

          <div className="space-y-6">
            {competences.map((competence) => {
              const competenceProgress = getProgressForCompetence(competence.id);
              
              return (
                <div key={competence.id} className="bg-white shadow rounded-lg">
                  <div className="px-6 py-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center mb-2">
                          <span className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-indigo-100 text-indigo-800 text-sm font-medium mr-3">
                            {competence.number}
                          </span>
                          <h3 className="text-lg font-medium text-gray-900">
                            {competence.title}
                          </h3>
                          <div className="ml-3">
                            {getStatusBadge(competenceProgress)}
                          </div>
                        </div>
                        
                        <p className="text-gray-600 mb-3">{competence.description}</p>
                        
                        <div className="flex items-center space-x-6 text-sm text-gray-500 mb-4">
                          <span>⏰ {competence.duration_hours}h</span>
                          <span>📊 {competence.units} unités</span>
                          <span>🎯 {competence.success_threshold}% requis</span>
                        </div>

                        <div className="mb-4">
                          <h4 className="text-sm font-medium text-gray-900 mb-2">Objectifs d'apprentissage :</h4>
                          <ul className="text-sm text-gray-600 space-y-1">
                            {competence.learning_objectives.slice(0, 3).map((objective, index) => (
                              <li key={index} className="flex items-start">
                                <span className="mr-2">•</span>
                                <span>{objective}</span>
                              </li>
                            ))}
                            {competence.learning_objectives.length > 3 && (
                              <li className="text-gray-400 italic">
                                ... et {competence.learning_objectives.length - 3} autres objectifs
                              </li>
                            )}
                          </ul>
                        </div>

                        {competenceProgress && (
                          <div className="mb-4">
                            <div className="flex justify-between text-sm text-gray-600 mb-1">
                              <span>Progression</span>
                              <span>{Math.round(competenceProgress.current_score)}%</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div 
                                className="bg-indigo-600 h-2 rounded-full" 
                                style={{ width: `${competenceProgress.current_score}%` }}
                              ></div>
                            </div>
                          </div>
                        )}
                      </div>
                      
                      <div className="ml-6 flex flex-col space-y-2">
                        <button
                          onClick={() => navigate(`/competence/${competence.id}`)}
                          className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-md text-sm font-medium"
                        >
                          {competenceProgress ? 'Continuer' : 'Commencer'}
                        </button>
                        
                        {competenceProgress && competenceProgress.status === 'in_progress' && (
                          <button
                            onClick={() => navigate(`/workshop/${competence.id}`)}
                            className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-md text-sm font-medium"
                          >
                            Atelier IA
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

const CompetenceDetailPage = () => {
  const { competenceId } = useParams();
  const [competence, setCompetence] = useState(null);
  const [progress, setProgress] = useState(null);
  const [quizQuestions, setQuizQuestions] = useState([]);
  const [currentTab, setCurrentTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchCompetenceData();
  }, [competenceId]);

  const fetchCompetenceData = async () => {
    try {
      const competenceRes = await axios.get(`${API}/competences/${competenceId}`, { withCredentials: true });
      setCompetence(competenceRes.data);

      const progressRes = await axios.get(`${API}/progress`, { withCredentials: true });
      const userProgress = progressRes.data.find(p => p.competence_id === competenceId);
      setProgress(userProgress);

      if (userProgress) {
        const quizRes = await axios.get(`${API}/quiz/${competenceId}/questions`, { withCredentials: true });
        setQuizQuestions(quizRes.data);
      }
    } catch (error) {
      console.error('Error fetching competence data:', error);
    } finally {
      setLoading(false);
    }
  };

  const startCompetence = async () => {
    try {
      await axios.post(`${API}/progress/start/${competenceId}`, {}, { withCredentials: true });
      fetchCompetenceData();
    } catch (error) {
      console.error('Error starting competence:', error);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!competence) return <div>Compétence non trouvée</div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <div className="max-w-4xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Back button */}
          <button
            onClick={() => navigate('/competences')}
            className="mb-6 text-indigo-600 hover:text-indigo-500"
          >
            ← Retour aux compétences
          </button>

          {/* Header */}
          <div className="bg-white shadow rounded-lg mb-6">
            <div className="px-6 py-4">
              <div className="flex items-center mb-4">
                <span className="inline-flex items-center justify-center h-12 w-12 rounded-full bg-indigo-100 text-indigo-800 text-lg font-medium mr-4">
                  {competence.number}
                </span>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">{competence.title}</h1>
                  <p className="text-gray-600">{competence.description}</p>
                </div>
              </div>
              
              <div className="flex items-center space-x-6 text-sm text-gray-500">
                <span>⏰ {competence.duration_hours} heures</span>
                <span>📊 {competence.units} unités</span>
                <span>🎯 {competence.success_threshold}% requis pour réussir</span>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="bg-white shadow rounded-lg">
            <div className="border-b border-gray-200">
              <nav className="-mb-px flex">
                <button
                  onClick={() => setCurrentTab('overview')}
                  className={`py-2 px-4 border-b-2 font-medium text-sm ${
                    currentTab === 'overview'
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  Vue d'ensemble
                </button>
                <button
                  onClick={() => setCurrentTab('content')}
                  className={`py-2 px-4 border-b-2 font-medium text-sm ${
                    currentTab === 'content'
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  Contenu
                </button>
                {progress && (
                  <button
                    onClick={() => setCurrentTab('quiz')}
                    className={`py-2 px-4 border-b-2 font-medium text-sm ${
                      currentTab === 'quiz'
                        ? 'border-indigo-500 text-indigo-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    Quiz
                  </button>
                )}
              </nav>
            </div>

            <div className="p-6">
              {currentTab === 'overview' && (
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Objectifs d'apprentissage</h3>
                  <ul className="space-y-2 mb-6">
                    {competence.learning_objectives.map((objective, index) => (
                      <li key={index} className="flex items-start">
                        <span className="mr-3 text-indigo-600">•</span>
                        <span className="text-gray-700">{objective}</span>
                      </li>
                    ))}
                  </ul>

                  <h3 className="text-lg font-medium text-gray-900 mb-4">Évaluation</h3>
                  <div className="bg-gray-50 rounded-lg p-4 mb-6">
                    <p className="text-sm text-gray-600 mb-2">
                      <strong>Méthode :</strong> {competence.evaluation_method}
                    </p>
                    <p className="text-sm text-gray-600 mb-2">
                      <strong>Description :</strong> {competence.evaluation_description}
                    </p>
                    <p className="text-sm text-gray-600">
                      <strong>Critères :</strong> {competence.evaluation_criteria.join(', ')}
                    </p>
                  </div>

                  {!progress ? (
                    <button
                      onClick={startCompetence}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-md font-medium"
                    >
                      Commencer cette compétence
                    </button>
                  ) : (
                    <div>
                      <h3 className="text-lg font-medium text-gray-900 mb-4">Votre progression</h3>
                      <div className="bg-blue-50 rounded-lg p-4">
                        <div className="flex justify-between text-sm text-gray-600 mb-2">
                          <span>Score actuel</span>
                          <span>{Math.round(progress.current_score)}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
                          <div 
                            className="bg-indigo-600 h-2 rounded-full" 
                            style={{ width: `${progress.current_score}%` }}
                          ></div>
                        </div>
                        <p className="text-sm text-gray-600">
                          Statut: <span className="font-medium">{progress.status === 'in_progress' ? 'En cours' : progress.status}</span>
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {currentTab === 'content' && (
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Contenu de formation</h3>
                  <p className="text-gray-600 mb-4">
                    Le contenu détaillé de cette compétence sera disponible prochainement avec :
                  </p>
                  <ul className="space-y-2 text-gray-600">
                    <li>• Supports de cours (texte, vidéo, PDF)</li>
                    <li>• Exercices pratiques</li>
                    <li>• Ressources complémentaires</li>
                    <li>• Études de cas</li>
                  </ul>
                </div>
              )}

              {currentTab === 'quiz' && progress && (
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Quiz d'évaluation</h3>
                  {quizQuestions.length > 0 ? (
                    <div>
                      <p className="text-gray-600 mb-4">
                        Testez vos connaissances avec {quizQuestions.length} questions.
                      </p>
                      <button
                        onClick={() => navigate(`/quiz/${competenceId}`)}
                        className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md"
                      >
                        Passer le quiz
                      </button>
                    </div>
                  ) : (
                    <p className="text-gray-600">Quiz en cours de préparation.</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Initialize data component
const InitializeData = () => {
  const [initialized, setInitialized] = useState(false);
  const [loading, setLoading] = useState(false);

  const initializeData = async () => {
    setLoading(true);
    try {
      await axios.post(`${API}/init-data`, {}, { withCredentials: true });
      setInitialized(true);
    } catch (error) {
      console.error('Error initializing data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    initializeData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Initialisation des données du curriculum RIAN...</p>
        </div>
      </div>
    );
  }

  return null;
};

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <InitializeData />
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            } />
            <Route path="/competences" element={
              <ProtectedRoute>
                <CompetencesPage />
              </ProtectedRoute>
            } />
            <Route path="/competence/:competenceId" element={
              <ProtectedRoute>
                <CompetenceDetailPage />
              </ProtectedRoute>
            } />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;