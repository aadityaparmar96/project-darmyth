# AI Desktop Assistant

AI-powered desktop assistant with:
- gesture control
- voice commands
- automation
- memory system

Darmyth/
├── main.py # event loop orchestrator
├── requirements.txt
├── .gitignore
├── README.md
│
├── config/
│ ├── .env                        # API keys — never commit
│ ├── settings.yaml               # model, voice, wake word
│ └── constants.py                # shared app-wide constants
│
├── backend/
│ ├── vision/
│ │ ├── camera.py                 # 480p webcam capture
│ │ ├── hands.py                  # mediapipe, complexity=0
│ │ └── gestures.py               # 5-gesture classifier
│ ├── voice/
│ │ ├── wake_word.py              # openWakeWord listener
│ │ ├── stt.py                    # faster-whisper tiny
│ │ └── tts.py                    # edge-tts output
│ ├── assistant/
│ │ ├── brain.py                  # API connector (Groq/Gemini)
│ │ ├── prompt.py                 # Darmyth system prompt
│ │ ├── router.py                 # intent router — skip API when possible
│ │ └── context.py                # last 6 turns memory
│ ├── automation/
│ │ ├── volume.py                 # pycaw / osascript
│ │ └── apps.py                   # open/close apps
│ └── rag/
│ ├── embeddings.py               # MiniLM-L6-v2 encoder
│ ├── store.py                    # ChromaDB local persistence
│ └── retriever.py                # top-3 chunk retrieval
│
├── ui/
│ ├── overlay.py                  # Tkinter floating window
│ └── components.py               # reusable UI widgets
│
├── memory_db/                    # ChromaDB files (gitignored)
│
├── data/
│ ├── notes/                      # .txt files Darmyth can read
│ ├── conversations/              # nightly summaries
│ └── gestures/                   # custom gesture training data
│
├── tests/
│ ├── test_vision.py
│ ├── test_voice.py
│ └── test_brain.py
│
└── docs/
├── architecture.md
└── roadmap.md