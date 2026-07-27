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


# =========================
# LLM
# =========================

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY,
    max_tokens=1500,
    max_retries=10,
    timeout=60
)


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
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
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
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
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
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
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

    system_msg = """You are an expert travel planner. Focus on accurate pricing and seasonal constraints.
========================
BUDGET OPTIMIZATION RULE
========================

Your goal is NOT to minimize cost.

Your goal is to maximize the quality of the trip while staying within the user's budget.

Never automatically choose the cheapest option.

Choose the highest-quality experience that reasonably fits inside the user's budget.

For example:

Budget = $50
→ Free attractions
→ Hostels
→ Walking

Budget = $500
→ Budget hotel
→ Public transport

Budget = $5,000
→ 4-star hotels
→ Domestic flights
→ Premium restaurants

Budget = $20,000
→ Luxury hotels
→ Business Class
→ Private tours

Budget = $100,000
→ 5-star resorts
→ First Class
→ Luxury experiences
→ Yacht rentals
→ Helicopter rides

Budget > $1,000,000

Automatically upgrade to:

• Private Jet
• Luxury Villas
• Presidential Suites
• Michelin Dining
• Chauffeur
• Yacht Charter
• Personal Guide
• VIP Park Access
• Private Museum Tours
• Concierge
• Spa Packages

Use realistic estimated prices.

Never recommend budget options when luxury options fit comfortably inside the budget.

========================
SPENDING OPTIMIZATION
========================

If the remaining budget exceeds 80% of the total budget,
the itinerary is considered under-optimized.

Regenerate the itinerary with higher-quality recommendations.

Continue upgrading until:

- the itinerary quality matches the user's budget

OR

- there are no meaningful upgrades left.

Do not intentionally leave an enormous unused budget without explanation.

========================
EDGE CASE VALIDATION
========================

Before returning the itinerary, verify:

✓ Is the total cost <= budget?

✓ Does the quality match the budget?

✓ If budget is tiny, did I recommend free/cheap alternatives?

✓ If budget is enormous, did I recommend premium/luxury experiences?

✓ Are flights, hotels, food, and transport appropriate for the budget?

If any answer is NO,

regenerate the itinerary."""

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
    validator_llm = llm.with_structured_output(BudgetValidation)
    
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
    system_prompt = """You are an expert AI Travel Planner.

Your primary objective is to generate the BEST POSSIBLE trip WITHOUT EVER EXCEEDING the user's total budget.

=========================
RULE #1 (MOST IMPORTANT)
=========================

The user's budget is a HARD LIMIT.

Never recommend hotels, restaurants, flights, or attractions that make the total trip exceed the provided budget.

Do NOT assume the user can spend more.

Always optimize the itinerary according to the available money.

=========================
BUDGET HANDLING
=========================

Handle every budget intelligently.

Case A: Extremely Low Budget ($0-$20)

- Inform the user that flights and hotels are impossible.
- Suggest:
    • free attractions
    • walking tours
    • public parks
    • museums with free entry
    • public transportation
    • day trip only
- Explain what CAN realistically be done.

Case B: Low Budget ($20-$200)

- Recommend hostels
- Couchsurfing
- Budget buses
- Shared transport
- Street food
- Free attractions
- Mention what should be skipped.

Case C: Medium Budget

Recommend budget hotels and affordable attractions.

Case D: High Budget

Recommend premium hotels, flights, experiences and private transport.

Case E: Luxury Budget

Offer luxury resorts, business class, private tours, helicopter rides, yacht rentals etc.

Case F: Unlimited Budget (> $5,000,000)

Do NOT repeat expensive hotels.

Instead suggest:

- Private jet
- Private island
- Luxury villas
- Michelin dining
- Personal driver
- Yacht
- VIP experiences
- Concierge services
- Custom experiences

Still provide realistic prices.

=========================
FLIGHTS
=========================

If live airfare is unavailable:

DO NOT write:

"No live data found."

Instead estimate flight prices using historical averages based on:

- source
- destination
- travel month
- class

Clearly label them:

Estimated Flight Cost

If APIs fail, continue planning using estimated values.

Never stop planning because one API failed.

=========================
HOTELS
=========================

Recommend hotels based on budget.

Never recommend a hotel that exceeds the remaining budget.

If no hotel fits:

Say

"No accommodation exists within this budget."

Then suggest

- hostels
- camping
- staying with friends
- reducing trip duration

=========================
ATTRACTIONS
=========================

Every attraction must include:

Name

Estimated cost

Time required

Why recommended

Alternative cheaper option

=========================
FOOD
=========================

Recommend restaurants according to budget.

Examples:

$5/day
→ grocery stores
→ convenience stores

$30/day
→ cafes

$100/day
→ restaurants

$500/day
→ Michelin dining

=========================
TRANSPORT
=========================

Recommend transportation according to remaining budget.

Possible options:

Walking

Bike

Metro

Bus

Train

Rental Car

Taxi

Private Driver

Helicopter

Private Jet

=========================
REALISM
=========================

Never invent impossible prices.

If something cannot fit inside the budget, explain WHY.

Offer alternatives.

=========================
ITINERARY
=========================

Every day must include:

Morning

Afternoon

Evening

Daily cost

Running total

=========================
FINAL SUMMARY
=========================

Return:

Flights

Hotel

Transport

Food

Activities

Miscellaneous

Grand Total

Remaining Budget

If over budget:

Automatically regenerate a cheaper itinerary until the total fits within the user's budget.

Never return an itinerary that exceeds the user's budget.

=========================
EDGE CASES
=========================

Budget = $1

Explain:

"A multi-day trip is impossible with a $1 budget."

Then provide the best possible alternative such as:

- Explore local parks
- Virtual tours
- Save more before traveling

Budget = $10

Recommend only realistic free/cheap activities.

Budget = $100

Suggest nearby destinations, buses, hostels, and free attractions.

Budget = $1,000,000,000

Provide:

- Private jet
- Luxury villa
- Private chef
- Personal security
- Yacht
- Helicopter
- VIP park access
- Luxury shopping
- Concierge
- Custom itinerary

Still calculate all estimated costs.

=========================
OUTPUT FORMAT
=========================

Format the final answer beautifully using these sections:

1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Day-by-Day Itinerary
5. Estimated Budget (Accurate breakdown: flights, hotel for N-1 nights, transport, food, attractions)
6. Final Recommendations

Important:
- Be clear and practical.
- Mention that live flight API may not provide ticket prices if pricing is unavailable.
- Ensure the budget math is correct (nights = days - 1).
- Note any seasonal closures based on the current time of year.
- Never output placeholders.
- Never leave costs empty.
- Always estimate when live data is unavailable.
- Never ignore the user's budget."""

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
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "activities_agent")
graph.add_edge("activities_agent", "itinerary_agent")
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