import json
from groq import Groq
from dotenv import load_dotenv
from rag import search
from booking import check_availability, book_appointment, cancel_appointment, SERVICES, now, upcoming_days

load_dotenv()
groq = Groq()
MODEL = "openai/gpt-oss-120b"
MAX_STEPS = 6


def search_shop_info(query):
    return {"facts": [text for text, _ in search(query)]}


TOOL_FUNCTIONS = {
    "search_shop_info": search_shop_info,
    "check_availability": check_availability,
    "book_appointment": book_appointment,
    "cancel_appointment": cancel_appointment,
}


def tool(name, description, properties, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }}


SERVICE = {"type": "string", "enum": list(SERVICES)}
DATE = {"type": "string", "description": "YYYY-MM-DD"}
TOOLS = [
    tool("search_shop_info", "Look up shop facts: prices, hours, location, parking, policies, staff, payment.",
         {"query": {"type": "string"}}, ["query"]),
    tool("check_availability", "List free start times for one service on one date.",
         {"date_str": DATE, "service": SERVICE}, ["date_str", "service"]),
    tool("book_appointment", "Book a time. Call only after the customer picked a free time and gave their name.",
         {"customer": {"type": "string"}, "date_str": DATE, "time_str": {"type": "string", "description": "HH:MM"},
          "service": SERVICE}, ["customer", "date_str", "time_str", "service"]),
    tool("cancel_appointment", "Cancel a booking by its id and the customer's name.",
         {"booking_id": {"type": "integer"}, "customer": {"type": "string"}}, ["booking_id", "customer"]),
]


def system_prompt():
    return (
        "You are the LINE receptionist for Lumi Hair Studio (a demo shop). "
        f"Now is {now().strftime('%A %Y-%m-%d %H:%M')} in Thailand. "
        f"Calendar: {upcoming_days()}. Always pick dates from this calendar, never calculate dates yourself. Only the date marked today is today; call other dates by their day name and date, never today. " "Use tools for every fact, free time and booking. Never guess prices, hours or times. Write plain text only, no markdown, because LINE does not show it. "
        "If a tool returns an error, explain it simply and offer another option. "
        "Before booking, make sure you know the service, date, time and the customer's name. "
        "After booking, give the booking id. "
        "If the shop facts do not answer a question, say you will check with staff. "
        "Reply in the customer's language, short and friendly, like a LINE message."
    )


def reply(history):
    for _ in range(MAX_STEPS):
        response = groq.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system_prompt()}] + history,
            tools=TOOLS,
        )
        msg = response.choices[0].message
        if not msg.tool_calls:
            history.append({"role": "assistant", "content": msg.content or ""})
            return msg.content

        history.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in msg.tool_calls
        ]})
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
                result = TOOL_FUNCTIONS[call.function.name](**args)
            except Exception as error:
                result = {"error": str(error)}
            print(f"   [tool] {call.function.name}({args if 'args' in dir() else ''}) -> {result}")
            history.append({"role": "tool", "tool_call_id": call.id,
                            "content": json.dumps(result, ensure_ascii=False)})

    fallback = "ขออภัยค่ะ ระบบขัดข้องชั่วคราว เดี๋ยวพนักงานจะติดต่อกลับนะคะ 🙏"
    history.append({"role": "assistant", "content": fallback})
    return fallback


if __name__ == "__main__":
    history = []
    print("Lumi Hair Studio receptionist. Type 'quit' to stop.")
    while True:
        text = input("\nYou: ").strip()
        if text.lower() in ("quit", "exit"):
            break
        if text:
            history.append({"role": "user", "content": text})
            print("Bot:", reply(history))
