import datetime
from google.adk.agents.llm_agent import Agent


def get_current_time(timezone: str = "UTC") -> dict:
    """Returns the current date and time.
    
    Args:
        timezone: The timezone name (defaults to UTC).
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    return {
        "status": "success",
        "timezone": timezone,
        "utc_time": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def calculate(expression: str) -> dict:
    """Evaluates a safe mathematical expression.
    
    Args:
        expression: A mathematical expression string, e.g. "42 * 12 / (5 + 3)".
    """
    try:
        # Evaluate simple math expressions safely
        allowed_chars = set("0123456789+-*/(). %^")
        if not all(c in allowed_chars for c in expression):
            return {"status": "error", "message": "Invalid characters in expression"}
        result = eval(expression, {"__builtins__": None}, {})
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_agent(model: str = "gemini-3.7-flash") -> Agent:
    """Creates and configures the Google ADK Agent instance."""
    return Agent(
        model=model,
        name="telegram_assistant",
        instruction=(
            "You are a friendly and intelligent Telegram assistant powered by Google ADK. "
            "Help users with their questions clearly and concisely. "
            "Use available tools whenever needed for calculations or time queries."
        ),
        tools=[get_current_time, calculate],
    )


# Default root agent instance
assistant = create_agent()
