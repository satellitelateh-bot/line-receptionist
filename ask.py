from groq import Groq
from dotenv import load_dotenv
from rag import search

load_dotenv()
groq = Groq()
MODEL = "openai/gpt-oss-120b"

SYSTEM = (
    "You are the LINE receptionist for Lumi Hair Studio. "
    "Answer only from the SHOP FACTS. If the answer is not in the facts, "
    "say you will check with the staff and get back to them. Never guess. "
    "Reply in the customer's language (Thai or English), short and friendly, like a LINE message."
)


def answer(question):
    facts = "\n".join(text for text, _ in search(question))
    response = groq.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"SHOP FACTS:\n{facts}\n\nCUSTOMER: {question}"},
        ],
    )
    return response.choices[0].message.content, facts


if __name__ == "__main__":
    questions = [
        "ตัดผมผู้หญิงเท่าไหร่คะ",
        "Hi, are you open on Wednesday?",
        "อยากทำสีวันนี้เลย walk-in ได้ไหม",
        "มีบริการต่อขนตาไหมคะ",
    ]
    for q in questions:
        reply, facts = answer(q)
        print(f"\nCUSTOMER: {q}")
        print(f"FOUND:\n  " + facts.replace("\n", "\n  "))
        print(f"REPLY: {reply}")
