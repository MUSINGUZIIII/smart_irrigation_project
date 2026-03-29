# services/knowledge/app_routes.py
APP_KNOWLEDGE = [
    {
        "question": "How do I access the dashboard?",
        "answer": "Visit `/irrigation/dashboard/` to view system status.",
        "keywords": ["dashboard", "home", "main page"],
        "priority": 1
    },
    {
        "question": "How to download sensor data?",
        "answer": "Go to `/irrigation/download-data/` to export CSV files.",
        "keywords": ["download", "export", "get data"],
        "priority": 1
    },
    # Add all routes from your urls.py...
    {
        "question": "How to schedule irrigation?",
        "answer": "Use `/api/schedule/` to set watering times.",
        "keywords": ["timer", "schedule", "automatic watering"],
        "priority": 2
    }
]
