// src/components/Dashboard.jsx
import React, { useState, useEffect } from 'react';
import { 
  FileText, Upload, MessageSquare, LogOut, Trash2, 
  Download, RefreshCw, Send, Menu, X, User, FileIcon 
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import useAuthStore from '../stores/authStore';
import { documentService, chatService } from '../services/api';
import toast from 'react-hot-toast';
import ReactMarkdown from 'react-markdown';

const Dashboard = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    loadDocuments();
    loadConversations();
  }, []);

  const loadDocuments = async () => {
    try {
      const docs = await documentService.getDocuments();
      setDocuments(docs);
    } catch (error) {
      toast.error('Sənədlər yüklənmədi');
    }
  };

  const loadConversations = async () => {
    try {
      const convs = await chatService.getConversations();
      setConversations(convs);
    } catch (error) {
      toast.error('Söhbətlər yüklənmədi');
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadProgress(true);
    try {
      const result = await documentService.uploadDocument(file);
      toast.success(result.message || 'Fayl yükləndi');
      await loadDocuments();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Yükləmə xətası');
    } finally {
      setUploadProgress(false);
      event.target.value = '';
    }
  };

  const handleDeleteDocument = async (docId) => {
    if (!window.confirm('Sənədi silmək istədiyinizə əminsiniz?')) return;
    
    try {
      await documentService.deleteDocument(docId);
      toast.success('Sənəd silindi');
      await loadDocuments();
      if (selectedDoc?.id === docId) {
        setSelectedDoc(null);
        setMessages([]);
      }
    } catch (error) {
      toast.error('Silmə xətası');
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!question.trim() || !selectedDoc || isLoading) return;

    const userQuestion = question.trim();
    setQuestion('');
    setIsLoading(true);

    // Add user message
    const userMessage = { 
      question: userQuestion, 
      answer: '', 
      isLoading: true,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      const response = await chatService.askQuestion(
        userQuestion, 
        selectedDoc.id, 
        currentConversation?.id
      );

      // Update with answer
      setMessages(prev => 
        prev.map((msg, idx) => 
          idx === prev.length - 1 
            ? { ...msg, answer: response.answer, isLoading: false }
            : msg
        )
      );

      // Update conversation ID if new
      if (!currentConversation && response.conversation_id) {
        setCurrentConversation({ id: response.conversation_id });
        await loadConversations();
      }
    } catch (error) {
      setMessages(prev => 
        prev.map((msg, idx) => 
          idx === prev.length - 1 
            ? { 
                ...msg, 
                answer: error.response?.data?.error || 'Xəta baş verdi', 
                isLoading: false,
                isError: true 
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
    toast.success('Sistemdən çıxış edildi');
  };

  const getFileIcon = (fileName) => {
    const ext = fileName?.split('.').pop()?.toLowerCase();
    const iconMap = {
      'pdf': '📄', 'docx': '📘', 'txt': '📃', 
      'md': '📋', 'json': '🔧', 'xlsx': '📊', 'xls': '📊'
    };
    return iconMap[ext] || '📎';
  };

  return (
    <div className="h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-80' : 'w-0'} transition-all duration-300 bg-white border-r border-gray-200 flex flex-col overflow-hidden`}>
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="bg-blue-600 rounded-full w-10 h-10 flex items-center justify-center text-white font-bold">
                {user?.username?.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="font-semibold text-gray-900">{user?.username}</div>
                <div className="text-sm text-gray-500">{user?.role}</div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="text-gray-400 hover:text-red-500 transition-colors"
              title="Çıxış"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>

          {/* Upload button for admin */}
          {user?.role === 'admin' && (
            <div>
              <label className={`w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg cursor-pointer flex items-center justify-center space-x-2 transition-colors ${uploadProgress ? 'opacity-50 cursor-not-allowed' : ''}`}>
                <Upload className="w-5 h-5" />
                <span>{uploadProgress ? 'Yüklənir...' : 'Fayl Yüklə'}</span>
                <input
                  type="file"
                  accept=".pdf,.docx,.txt,.md,.json,.xlsx,.xls"
                  onChange={handleFileUpload}
                  disabled={uploadProgress}
                  className="hidden"
                />
              </label>
              <p className="text-xs text-gray-500 mt-1 text-center">
                PDF, DOCX, TXT, MD, JSON, Excel
              </p>
            </div>
          )}
        </div>

        {/* Documents List */}
        <div className="flex-1 p-4 overflow-y-auto">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center">
            <FileText className="w-4 h-4 mr-2" />
            Sənədlər ({documents.length})
          </h3>
          
          {documents.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <FileIcon className="w-12 h-12 mx-auto mb-2 text-gray-300" />
              <p className="text-sm">Heç bir sənəd yoxdur</p>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map(doc => (
                <div
                  key={doc.id}
                  onClick={() => {
                    setSelectedDoc(doc);
                    setMessages([]);
                    setCurrentConversation(null);
                  }}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    selectedDoc?.id === doc.id 
                      ? 'bg-blue-50 border-blue-200' 
                      : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2 flex-1 min-w-0">
                      <span className="text-lg">{getFileIcon(doc.name)}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 truncate">{doc.name}</div>
                        <div className="text-xs text-gray-500">
                          {doc.uploaded_by} • {Math.round(doc.size / 1024)}KB
                        </div>
                      </div>
                    </div>
                    {user?.role === 'admin' && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteDocument(doc.id);
                        }}
                        className="text-red-400 hover:text-red-600 ml-2"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Conversations */}
        <div className="p-4 border-t border-gray-200">
          <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
            <MessageSquare className="w-4 h-4 mr-2" />
            Söhbətlər ({conversations.length})
          </h3>
          <div className="max-h-40 overflow-y-auto">
            {conversations.map(conv => (
              <div
                key={conv.id}
                onClick={() => {
                  chatService.getConversation(conv.id).then(data => {
                    setMessages(data.messages);
                    setCurrentConversation(conv);
                    const doc = documents.find(d => d.id === data.document_id);
                    if (doc) setSelectedDoc(doc);
                  });
                }}
                className="text-sm py-1 px-2 hover:bg-gray-100 rounded cursor-pointer truncate"
              >
                {conv.title}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="text-gray-600 hover:text-gray-900"
              >
                {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
              <div>
                <h1 className="text-xl font-bold text-gray-900">RAG Chatbot</h1>
                {selectedDoc && (
                  <p className="text-sm text-gray-500">
                    {getFileIcon(selectedDoc.name)} {selectedDoc.name}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
          {!selectedDoc ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center">
                <FileText className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Sənəd seçin</h3>
                <p className="text-gray-500">Sol tərəfdən sənəd seçib suallarınızı verə bilərsiniz</p>
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center">
                <MessageSquare className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Söhbətə başlayın</h3>
                <p className="text-gray-500 mb-4">{selectedDoc.name} haqqında sualınızı yazın</p>
                <div className="text-sm text-gray-400 bg-white rounded-lg p-4 max-w-md mx-auto">
                  <p className="font-medium text-gray-700 mb-2">Nümunə suallar:</p>
                  <div className="space-y-1 text-left">
                    {[
                      "Bu sənəddə nə haqqında məlumat var?",
                      "Əsas məzmunu xülasə et",
                      "Müəyyən məlumat axtar"
                    ].map((q, idx) => (
                      <p 
                        key={idx}
                        className="cursor-pointer hover:text-blue-600"
                        onClick={() => setQuestion(q)}
                      >
                        • {q}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4 max-w-4xl mx-auto">
              {messages.map((msg, idx) => (
                <div key={idx} className="space-y-4">
                  {/* User Question */}
                  <div className="flex justify-end">
                    <div className="bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-3 max-w-2xl">
                      <p>{msg.question}</p>
                    </div>
                  </div>
                  
                  {/* AI Answer */}
                  <div className="flex justify-start">
                    <div className={`rounded-2xl rounded-bl-sm px-4 py-3 max-w-2xl ${
                      msg.isError ? 'bg-red-50 text-red-900' : 'bg-white text-gray-900'
                    }`}>
                      {msg.isLoading ? (
                        <div className="flex items-center space-x-2">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
                          <span className="text-gray-600">AI düşünür...</span>
                        </div>
                      ) : (
                        <ReactMarkdown className="prose prose-sm max-w-none">
                          {msg.answer}
                        </ReactMarkdown>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Input Form */}
        {selectedDoc && (
          <div className="bg-white border-t border-gray-200 p-4">
            <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto flex space-x-4">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Sualınızı yazın..."
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading || !question.trim()}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-6 py-3 rounded-lg flex items-center space-x-2 transition-colors"
              >
                <Send className="w-5 h-5" />
                <span>Göndər</span>
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;