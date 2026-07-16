# ✈️ Travex AI — Multi-Agent Travel Planner

Travex AI is an open-source AI travel planner that turns a natural-language trip request into a practical travel plan with flight suggestions, hotel ideas, live attraction pricing, and a day-by-day itinerary. The project uses a multi-agent workflow built with LangGraph, LangChain, and FastAPI, paired with a modern React frontend.

## Why this project?
Planning a trip usually means jumping between multiple websites, tools, and spreadsheets. Travex AI brings that flow into one unified experience by combining specialized AI agents:

- **Flight Agent:** Searches live flight data
- **Hotel Agent:** Researches accommodation options
- **Activities Agent:** Fetches live attraction ticket prices and checks seasonal availability
- **Itinerary Agent:** Crafts a budget-aware, mathematically accurate daily plan
- **Final Agent:** Formats the complete response

All of these agents are coordinated through a powerful LangGraph workflow.

## Features
- ✈️ **Flight research** using AviationStack
- 🏨 **Hotel & Activity suggestions** using Tavily search
- 🧠 **Multi-agent orchestration** with LangGraph
- 📝 **Structured travel itinerary generation** with real-time seasonal constraints
- 🌐 **FastAPI backend** serving the multi-agent graph
- 💻 **React + Vite frontend** with a sleek UI and "Agent Live Research Data" insights
- 💾 **Conversation state persistence** using PostgreSQL (LangGraph Checkpointer)
- ⚡ **LLM-powered responses** with Groq (Llama 3.3)

## Tech Stack
- **Backend:** Python 3.10+, FastAPI, LangGraph, LangChain, Groq, PostgreSQL
- **Frontend:** React, Vite, Tailwind CSS, Lucide Icons
- **APIs:** Tavily (Web Search), AviationStack (Flights)

## Project Structure
```
.
├── app.py                # FastAPI backend entry point
├── backend.py            # LangGraph multi-agent workflow & state management
├── frontend/             # React + Vite frontend application
├── requirements.txt      # Python dependencies
├── tools/                # Flight and web search integrations
└── Dockerfile            # Container configuration
```

## Prerequisites
Before running the project locally, make sure you have:
1. Python 3.10 or newer installed
2. Node.js (for the frontend)
3. PostgreSQL running and accessible
4. API keys for:
   - Groq
   - Tavily
   - AviationStack

## Environment Variables
Create a `.env` file in the project root with the following variables:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/travel_db
GROQ_API_KEY=your_groq_api_key
AVIATIONSTACK_API_KEY=your_aviationstack_api_key
TAVILY_API_KEY=your_tavily_api_key
```

## Installation & Running

### 1. Backend Setup
Create and activate a virtual environment, then install the dependencies:
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

Start the FastAPI server:
```bash
python app.py
```
The backend API will run on `http://127.0.0.1:8000/`.

### 2. Frontend Setup
Open a new terminal, navigate to the frontend directory, install dependencies, and start the Vite dev server:
```bash
cd frontend
npm install
npm run dev
```
The frontend UI will be available at `http://localhost:5173/`.

## API Endpoints
- `GET /health` - Health check
- `POST /api/travel` - Submit a travel request

Example request:
```bash
curl -X POST http://127.0.0.1:8000/api/travel \
  -H "Content-Type: application/json" \
  -d '{"message":"Plan a 3-day romantic trip to Tokyo with a budget of $1200"}'
```

## How the Workflow Works
1. The user submits a natural language travel request.
2. The **flight agent** gathers flight routes and estimated costs.
3. The **hotel agent** searches the web for matching accommodations.
4. The **activities agent** researches top attractions, verifies live pricing, and checks if they are open during the current season.
5. The **itinerary agent** creates a practical, math-checked travel plan utilizing the gathered data.
6. The **final agent** formats the result into a polished Markdown response for the frontend to render, along with the raw agent insights.
