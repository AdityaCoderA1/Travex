import os 
import certifi
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from typing import TypedDict, Annotated
import operator
import uuid
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. Please add your Render PostgreSQL External Database URL to .env"
        )

    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"

    return database_url


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing. Please add it to your .env file.")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# =========================
# LLM
# =========================

models = [
    "llama-3.1-8b-instant",   # 500k TPD
    "llama3-8b-8192",         # 500k TPD
    "mixtral-8x7b-32768",     # 500k TPD
    "gemma2-9b-it",           # 500k TPD
    "llama-3.3-70b-versatile" # 100k TPD — best quality
]

llms = [
    ChatGroq(
        model=m,
        api_key=GROQ_API_KEY,
        max_tokens=1500,
        max_retries=0, # Fail fast and fallback
        timeout=30
    ) for m in models
]

# OpenRouter as last-resort fallback when all Groq daily limits are exhausted
if OPENROUTER_API_KEY:
    llms.append(
        ChatOpenAI(
            model="meta-llama/llama-3.3-70b-instruct",
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            max_tokens=1500,
            max_retries=1,
            timeout=60
        )
    )

# Primary: first Groq model. Falls through all Groq models, then OpenRouter
llm = llms[0].with_fallbacks(llms[1:])


# =========================
# State
# =========================

class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    activities_results: str
    itinerary: str
    llm_calls: int
    budget_feedback: str
    replan_count: int


# =========================
# Flight Agent
# =========================

def flight_agent(state: TravelState):
    query = state["user_query"]
    flight_data = search_flights(query)

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(content="Flight results fetched.")
        ]
    }



# =========================
# Hotel Agent
# =========================

def hotel_agent(state: TravelState):
    query = f"Best hotels for {state['user_query']}"
    hotel_results = tavily_search(query)

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel information fetched.")
        ]
    }



# =========================
# Activities Agent
# =========================

def activities_agent(state: TravelState):
    query = f"Top attractions, current ticket prices, and seasonal availability for {state['user_query']}"
    activities_results = tavily_search(query)

    return {
        "activities_results": activities_results,
        "messages": [
            AIMessage(content="Attractions and activities information fetched.")
        ]
    }




# =========================
# Itinerary Agent
# =========================

def itinerary_agent(state: TravelState):
    current_date = datetime.now().strftime("%B %Y")
    prompt = f"""
Create a complete travel itinerary.
Current Date: {current_date}

User Query:
{state['user_query']}

Flight Results:
{state['flight_results']}

Hotel Results:
{state['hotel_results']}

Attractions & Activities Results:
{state['activities_results']}

Make the itinerary practical, budget-aware, and easy to follow.
Important Rules:
1. Seasonality: Check the Current Date. If it's summer, DO NOT recommend winter-only outdoor attractions. Suggest indoor alternatives instead.
2. Hotel Budget Math: Calculate hotel nights strictly as (Total Days - 1). For a 7-day trip, budget for exactly 6 nights.
3. Pricing: Use the provided Attractions Results for ticket prices. If exact prices are missing, state clearly that your prices are estimates. Do not overinflate local costs.
"""

    if state.get("budget_feedback"):
        prompt += f"\n\nCRITICAL FEEDBACK FROM BUDGET VALIDATOR:\n{state['budget_feedback']}\nPlease thoroughly revise the itinerary to address this feedback."

    system_msg = """You are an expert travel planner. Rules:
1. Maximize trip quality within budget — never pick cheapest by default.
2. Budget tiers: <$50→hostels/free; $50-$500→budget hotel/transit; $500-$5k→mid hotel; $5k-$20k→4-star/business; $20k-$100k→5-star/first; >$100k→luxury villa/private jet/yacht.
3. If remaining budget >80% unused, upgrade experiences.
4. Hotel nights = trip days - 1.
5. Seasonal accuracy: current month is {current_date}. Skip out-of-season attractions.
6. Use provided search data for prices. If missing, estimate and label as 'Estimated'.
7. Total cost must never exceed the user's stated budget.""".format(current_date=current_date)

    response = llm.invoke([
        SystemMessage(content=system_msg),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "replan_count": state.get("replan_count", 0) + 1
    }



# =========================
# Budget Validator Agent
# =========================

class BudgetValidation(BaseModel):
    is_valid: bool = Field(description="True if the itinerary satisfies all budget rules, False otherwise")
    feedback: str = Field(description="If invalid, provide specific feedback on why.")

def budget_validator_agent(state: TravelState):
    validator_prompt = f"""
Evaluate the generated itinerary against the user's budget and optimization rules.

User Query:
{state['user_query']}

Proposed Itinerary:
{state['itinerary']}

Rules:
1. If total_cost > budget: return False and "REPLAN: Over budget."
2. If budget >= 100000 and luxury travel options are not utilized: return False and "REPLAN: Budget supports luxury travel. Upgrade to private jet, 5-star resorts, etc."
3. If budget <= 100 and it doesn't use free/cheap alternatives: return False and "REPLAN: Suggest local/free alternatives."
4. If remaining_budget / budget > 0.8 and budget > 10000: return False and "REPLAN: Underutilized budget. Massively upgrade experiences."

Determine if valid and provide feedback if not.
"""
    validator_llms = [base_llm.with_structured_output(BudgetValidation) for base_llm in llms]
    validator_llm = validator_llms[0].with_fallbacks(validator_llms[1:])
    
    try:
        result = validator_llm.invoke([
            SystemMessage(content="You are a strict Budget Validator Agent for a travel planner. Enforce all rules rigidly."),
            HumanMessage(content=validator_prompt)
        ])
        is_valid = result.is_valid
        feedback = result.feedback
    except Exception as e:
        # Fallback if structured output fails
        is_valid = True
        feedback = ""

    return {
        "budget_feedback": "" if is_valid else feedback,
        "llm_calls": state.get("llm_calls", 0) + 1,
        "messages": [AIMessage(content=f"Budget validation: Valid={is_valid}, Feedback={feedback}")]
    }


def check_budget_validity(state: TravelState):
    if state.get("replan_count", 0) >= 3:
        return "final_agent"
    if state.get("budget_feedback"):
        return "itinerary_agent"
    return "final_agent"


# =========================
# Final Response Agent
# =========================

def final_agent(state: TravelState):
    system_prompt = """You are an expert AI Travel Planner. Rules:
1. Budget is a HARD LIMIT — never exceed it.
2. Scale quality to budget: <$20→free/day-trip only; $20-$200→hostel/street food/free attractions; $200-$1k→budget hotel/transit; $1k-$5k→mid hotel; $5k-$20k→4-star/premium; $20k-$100k→5-star/business; >$100k→luxury villa/private jet/yacht/Michelin.
3. Flights: if live price unavailable, estimate from historical data and label 'Estimated Flight Cost'. Never stop planning due to API failure.
4. Hotels: nights = days - 1. Never recommend a hotel that exceeds remaining budget.
5. Every attraction: name, estimated cost, time needed, why recommended, cheaper alternative.
6. Food scaled to budget: <$10/day→groceries; $30→cafes; $100→restaurants; $500+→Michelin.
7. Transport scaled to budget: walking→bike→metro→bus→train→rental→taxi→private driver→helicopter→private jet.
8. Output format:
   1. Trip Summary
   2. Flight Information
   3. Hotel Suggestions
   4. Day-by-Day Itinerary (Morning/Afternoon/Evening + daily cost + running total)
   5. Budget Breakdown (flights, hotel N-1 nights, transport, food, activities, misc, Grand Total, Remaining)
   6. Final Recommendations
9. Never use placeholders or leave costs empty. Always estimate if live data is unavailable."""

    final_prompt = f"""
User Request:
{state['user_query']}

Flights:
{state['flight_results']}

Hotels:
{state['hotel_results']}

Activities:
{state['activities_results']}

Itinerary:
{state['itinerary']}
"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Build Graph
# =========================

graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("activities_agent", activities_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("budget_validator_agent", budget_validator_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge(START, "hotel_agent")
graph.add_edge(START, "activities_agent")

graph.add_edge(["flight_agent", "hotel_agent", "activities_agent"], "itinerary_agent")
graph.add_edge("itinerary_agent", "budget_validator_agent")

graph.add_conditional_edges("budget_validator_agent", check_budget_validity, {
    "itinerary_agent": "itinerary_agent",
    "final_agent": "final_agent"
})

graph.add_edge("final_agent", END)


# =========================
# PostgreSQL Checkpointer
# =========================
DATABASE_URL = get_database_url()


# =========================
# Function for FastAPI
# =========================

def run_travel_agent(user_input: str, thread_id: str | None = None):
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    with psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row) as conn:
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
        travel_graph = graph.compile(checkpointer=checkpointer)

        result = travel_graph.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],
            "user_query": user_input,
            "flight_results": "",
            "hotel_results": "",
            "activities_results": "",
            "itinerary": "",
            "llm_calls": 0,
            "budget_feedback": "",
            "replan_count": 0
        },
        config=config
    )

    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "activities_results": result.get("activities_results", ""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }