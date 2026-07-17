import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { 
  Plane, Map, Hotel, ArrowRight, Sparkles, 
  MapPin, RefreshCcw, Send, AlertTriangle, Loader2, Compass, BrainCircuit, Zap, CheckCircle2
} from 'lucide-react';

const LOADING_MESSAGES = [
  "Searching flights...",
  "Comparing fares and layovers...",
  "Analyzing hotels...",
  "Mapping the best routes...",
  "Crafting your perfect itinerary..."
];

export default function App() {
  const [query, setQuery] = useState("");
  const [threadId, setThreadId] = useState(null);
  
  const [status, setStatus] = useState("idle"); // idle, loading, success, error
  const [loadingMsgIdx, setLoadingMsgIdx] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");
  const [result, setResult] = useState(null);
  
  const resultsRef = useRef(null);

  // Cycle loading messages
  useEffect(() => {
    let interval;
    if (status === 'loading') {
      interval = setInterval(() => {
        setLoadingMsgIdx(i => (i + 1) % LOADING_MESSAGES.length);
      }, 2500);
    }
    return () => clearInterval(interval);
  }, [status]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setStatus("loading");
    setLoadingMsgIdx(0);

    try {
      const apiUrl = import.meta.env.VITE_API_URL || '';
      const res = await fetch(`${apiUrl}/api/travel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: query,
          thread_id: threadId
        })
      });

      const data = await res.json();
      
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Something went wrong.");
      }

      setThreadId(data.thread_id);
      setResult(data.answer);
      setStatus("success");
      
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);

    } catch (err) {
      setErrorMsg(err.message);
      setStatus("error");
    }
  };

  const resetPlan = () => {
    setStatus("idle");
    setQuery("");
    setThreadId(null);
    setResult(null);
  };

  return (
    <>
      <div className="ambient-bg" />
      
      <div className="min-h-screen relative z-10 flex flex-col px-4 py-8 md:py-12 max-w-5xl mx-auto">
        
        {/* Header */}
        <header className="flex items-center justify-between mb-16">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg">
              <Compass className="text-white w-5 h-5" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">Travex AI</h1>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
            <a href="#how-it-works" className="hover:text-white transition-colors">How it Works</a>
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#about" className="hover:text-white transition-colors">About</a>
          </nav>
          <div className="hidden sm:block px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-sm text-slate-300 backdrop-blur-md">
            Multi-Agent Travel Planner
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col w-full">
          
          {status === 'idle' && (
            <div className="flex flex-col items-center text-center animate-in fade-in slide-in-from-bottom-8 duration-700 w-full max-w-3xl mx-auto mt-8 md:mt-12">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-indigo-300 text-sm font-medium mb-8">
                <Sparkles className="w-4 h-4" />
                <span>Flights, Hotels, & Itineraries in one prompt</span>
              </div>
              
              <h2 className="text-4xl md:text-6xl font-bold mb-6 leading-tight">
                Plan Your Perfect Trip <br/>
                <span className="text-gradient">With AI Agents</span>
              </h2>
              
              <p className="text-slate-300 text-xl mb-12 max-w-2xl">
                Describe your dream destination, budget, and vibe. Our multi-agent LangGraph system handles the rest.
              </p>

              <form onSubmit={handleSubmit} className="w-full glass-panel p-2 pl-6 flex items-center gap-4 transition-all focus-within:ring-2 focus-within:ring-indigo-500/50">
                <input 
                  type="text"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="e.g. A 7-day romantic trip to Paris under $3000..."
                  className="flex-1 bg-transparent border-none outline-none text-white text-lg placeholder:text-slate-400"
                />
                <button 
                  type="submit"
                  disabled={!query.trim()}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-4 rounded-xl font-semibold transition-all flex items-center gap-2 disabled:opacity-50 disabled:hover:bg-indigo-600"
                >
                  Generate Plan <ArrowRight className="w-5 h-5" />
                </button>
              </form>
              
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                {["7 days in Japan budget trip", "Luxury weekend in Dubai", "Backpacking across Thailand"].map(hint => (
                  <button 
                    key={hint}
                    type="button"
                    onClick={() => setQuery(hint)}
                    className="px-4 py-2 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-sm text-slate-300 transition-colors"
                  >
                    {hint}
                  </button>
                ))}
              </div>
              
              {/* Feature Cards Below the Fold */}
              <div id="features" className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-24 text-left w-full border-t border-white/10 pt-16">
                <div className="glass-panel p-6 hover:-translate-y-1 transition-transform duration-300">
                  <div className="w-12 h-12 rounded-lg bg-indigo-500/20 flex items-center justify-center mb-4 text-indigo-400">
                    <Plane className="w-6 h-6" />
                  </div>
                  <h3 className="text-lg font-bold text-white mb-2">Smart Flight Matching</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">Our AI scans real-time flight data to find the best routes and fares based on your specific dates and budget constraints.</p>
                </div>
                <div className="glass-panel p-6 hover:-translate-y-1 transition-transform duration-300">
                  <div className="w-12 h-12 rounded-lg bg-purple-500/20 flex items-center justify-center mb-4 text-purple-400">
                    <Hotel className="w-6 h-6" />
                  </div>
                  <h3 className="text-lg font-bold text-white mb-2">Personalized Stays</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">Get hotel recommendations tailored exactly to your vibe, whether you want a luxury resort or a budget backpacker hostel.</p>
                </div>
                <div className="glass-panel p-6 hover:-translate-y-1 transition-transform duration-300">
                  <div className="w-12 h-12 rounded-lg bg-pink-500/20 flex items-center justify-center mb-4 text-pink-400">
                    <Map className="w-6 h-6" />
                  </div>
                  <h3 className="text-lg font-bold text-white mb-2">Day-by-Day Itinerary</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">Receive a complete, logical daily schedule including sightseeing, meals, and transit that actually makes geographic sense.</p>
                </div>
              </div>

              {/* How it Works Section */}
              <div id="how-it-works" className="mt-24 text-left w-full border-t border-white/10 pt-16">
                <h2 className="text-3xl font-bold text-white mb-8 text-center">How It Works</h2>
                <div className="flex flex-col md:flex-row gap-8 items-center justify-center">
                  <div className="glass-panel p-6 flex-1 flex flex-col items-center text-center">
                    <div className="w-16 h-16 rounded-full bg-indigo-500/20 flex items-center justify-center mb-4 text-indigo-400">
                      <BrainCircuit className="w-8 h-8" />
                    </div>
                    <h3 className="text-lg font-bold text-white mb-2">1. You Describe</h3>
                    <p className="text-slate-300 text-sm">Tell us where you want to go, your budget, and what kind of trip you want.</p>
                  </div>
                  <ArrowRight className="hidden md:block text-slate-500 w-8 h-8" />
                  <div className="glass-panel p-6 flex-1 flex flex-col items-center text-center">
                    <div className="w-16 h-16 rounded-full bg-purple-500/20 flex items-center justify-center mb-4 text-purple-400">
                      <Zap className="w-8 h-8" />
                    </div>
                    <h3 className="text-lg font-bold text-white mb-2">2. AI Agents Work</h3>
                    <p className="text-slate-300 text-sm">Our LangGraph agents search live flights, scan hotels, and build your itinerary.</p>
                  </div>
                  <ArrowRight className="hidden md:block text-slate-500 w-8 h-8" />
                  <div className="glass-panel p-6 flex-1 flex flex-col items-center text-center">
                    <div className="w-16 h-16 rounded-full bg-pink-500/20 flex items-center justify-center mb-4 text-pink-400">
                      <CheckCircle2 className="w-8 h-8" />
                    </div>
                    <h3 className="text-lg font-bold text-white mb-2">3. You Travel</h3>
                    <p className="text-slate-300 text-sm">Review your customized travel plan, ask follow-ups, and get ready for your trip!</p>
                  </div>
                </div>
              </div>

              {/* About Section */}
              <div id="about" className="mt-24 mb-16 text-left w-full border-t border-white/10 pt-16 flex flex-col items-center text-center">
                <h2 className="text-3xl font-bold text-white mb-6">About Travex AI</h2>
                <p className="text-slate-300 max-w-2xl leading-relaxed text-lg">
                  Travex AI is a demonstration of how multi-agent LLM systems can solve complex, multi-step problems like travel planning. 
                  By combining specialized agents for flights, hotels, and itinerary generation under a unified LangGraph workflow, 
                  we deliver complete, actionable travel plans in seconds instead of hours.
                </p>
              </div>
            </div>
          )}

          {status === 'loading' && (
            <div className="flex flex-col items-center justify-center flex-1 animate-in fade-in duration-500">
              <div className="relative w-32 h-32 flex items-center justify-center mb-8">
                <div className="absolute inset-0 rounded-full border-2 border-indigo-500/30 animate-[spin_4s_linear_infinite]" />
                <div className="absolute inset-2 rounded-full border-2 border-purple-500/30 border-t-purple-500 animate-[spin_3s_linear_infinite_reverse]" />
                <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-[0_0_30px_rgba(99,102,241,0.5)]">
                  <Map className="w-8 h-8 text-white" />
                </div>
              </div>
              <h3 className="text-xl font-medium text-white mb-2 transition-opacity duration-300">
                {LOADING_MESSAGES[loadingMsgIdx]}
              </h3>
              <div className="flex gap-1 loading-dots mt-2">
                <span className="w-2 h-2 rounded-full bg-indigo-500" />
                <span className="w-2 h-2 rounded-full bg-purple-500" />
                <span className="w-2 h-2 rounded-full bg-pink-500" />
              </div>
            </div>
          )}

          {status === 'error' && (
            <div className="flex flex-col items-center justify-center flex-1 animate-in fade-in slide-in-from-bottom-4">
              <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
                <AlertTriangle className="w-8 h-8 text-red-500" />
              </div>
              <h3 className="text-xl font-medium text-white mb-2">Oops! Something went wrong</h3>
              <p className="text-slate-400 mb-6">{errorMsg}</p>
              <button 
                onClick={() => setStatus("idle")}
                className="px-6 py-3 rounded-xl bg-white/10 hover:bg-white/20 font-medium transition-colors"
              >
                Try Again
              </button>
            </div>
          )}

          {status === 'success' && (
            <div className="w-full max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-8 duration-500" ref={resultsRef}>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold flex items-center gap-3">
                  <Plane className="text-indigo-400" /> Your Travel Plan
                </h2>
                <button 
                  onClick={resetPlan}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-medium transition-colors"
                >
                  <RefreshCcw className="w-4 h-4" /> New Plan
                </button>
              </div>

              <div className="glass-panel p-6 md:p-10 mb-6">
                <div className="markdown-body">
                  <ReactMarkdown>{result}</ReactMarkdown>
                </div>
              </div>


            </div>
          )}

        </main>
        

      </div>
    </>
  );
}
