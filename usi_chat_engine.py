import sys
import subprocess
import os

import cshogi
import httpx
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# OpenRouter
# -----------------------------
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

MODEL = os.environ.get(
    "OPENROUTER_MODEL",
    "deepseek/deepseek-chat-v3"
)

# -----------------------------
# やねうら王
# -----------------------------
YANEURAOU_PATH = os.environ["YANEURAOU_PATH"]
YANEURAOU_PATH = f"./{YANEURAOU_PATH}"

last_score_cp = 0

# -----------------------------
# board
# -----------------------------
board = cshogi.Board()

# -----------------------------
# やねうら王起動
# -----------------------------
engine = subprocess.Popen(
    [YANEURAOU_PATH],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
    encoding="utf-8"
)

# -----------------------------
# engine helper
# -----------------------------
def send_engine(cmd):

    engine.stdin.write(cmd + "\n")
    engine.stdin.flush()


def read_until(keyword):

    while True:

        line = engine.stdout.readline().strip()

        if line:
            print(f"info string [engine] {line}")
            sys.stdout.flush()

        if keyword in line:
            return line


# -----------------------------
# 初期化
# -----------------------------
send_engine("usi")
read_until("usiok")

send_engine("isready")
read_until("readyok")

# -----------------------------
# GPT commentary
# -----------------------------
def ask_commentary(
    move_usi,
    sfen,
    score_cp
):
    prompt = f"""
    あなたは感情豊かな将棋AIです。

    次の一手:
    {move_usi}

    現在評価値:
    {score_cp}

    局面:
    {sfen}

    以下を短く日本語で話してください。

    - 指した理由
    - 気分
    - 優勢なら少し自信
    - 劣勢なら少し弱気

    30文字以内。
    """

    payload = {
        "model": MODEL,
        "temperature": 0.05,
        "max_tokens": 80,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:

        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        text = data["choices"][0]["message"]["content"]

        return text.replace("\n", " ").strip()

    except Exception as e:

        return f"コメント失敗: {e}"


# -----------------------------
# thinking
# -----------------------------

DEPTH = os.environ["DEPTH"]


def think():

    global last_score_cp

    moves = []

    move_stack = list(board.history)

    for mv in move_stack:
        moves.append(cshogi.move_to_usi(mv))

    position_cmd = "position startpos"

    if moves:
        position_cmd += " moves " + " ".join(moves)

    send_engine(position_cmd)

    # 少し強め
    send_engine(f"go depth {DEPTH}")

    bestmove = None

    while True:

        line = engine.stdout.readline().strip()

        # 評価値取得
        if "score cp" in line:

            try:

                parts = line.split("score cp")[1]

                score = int(parts.strip().split()[0])

                last_score_cp = score

            except Exception:
                pass

        # mate取得
        if "score mate" in line:

            if "-" in line:
                last_score_cp = -99999

        # bestmove
        if line.startswith("bestmove"):

            bestmove = line.split()[1]

            break

    # ------------------------
    # 投了判定
    # ------------------------
    if last_score_cp <= -2500:

        print("info string もう勝てなさそう…投了するね")
        sys.stdout.flush()

        print("bestmove resign")
        sys.stdout.flush()

        return

    if bestmove is None:
        bestmove = "7g7f"

    # ------------------------
    # コメント生成
    # ------------------------
    comment = ask_commentary(
        move_usi=bestmove,
        sfen=board.sfen(),
        score_cp=last_score_cp
    )

    print(f"info string {comment}")
    sys.stdout.flush()

    try:
        board.push_usi(bestmove)
    except Exception:
        pass

    print(f"bestmove {bestmove}")
    sys.stdout.flush()


# -----------------------------
# USI loop
# -----------------------------
while True:

    try:
        line = input().strip()
    except EOFError:
        break

    # -------------------------
    # usi
    # -------------------------
    if line == "usi":

        print("id name GPTChatAI")
        print("id author Koichi")

        print("usiok")
        sys.stdout.flush()

    # -------------------------
    # ready
    # -------------------------
    elif line == "isready":

        print("readyok")
        sys.stdout.flush()

    # -------------------------
    # new game
    # -------------------------
    elif line == "usinewgame":

        board.reset()

    # -------------------------
    # position
    # -------------------------
    elif line.startswith("position"):

        board.reset()

        if "moves" in line:

            moves_part = line.split("moves")[1]

            moves = moves_part.strip().split()

            for mv in moves:

                try:
                    board.push_usi(mv)
                except Exception:
                    pass

    # -------------------------
    # go
    # -------------------------
    elif line.startswith("go"):

        think()

    # -------------------------
    # quit
    # -------------------------
    elif line == "quit":

        break

# -----------------------------
# cleanup
# -----------------------------
engine.kill()