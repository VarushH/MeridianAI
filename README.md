# MeridianAI

set GOOGLE_APPLICATION_CREDENTIALS=./credentials/service-account.json

Backend:

python -m venv .meridian
.meridian\Scripts\activate
pip install -r requirements.txt

uvicorn main:app --app-dir backend --reload --port 8000

Frontend:
cd frontend
npm install
npm run dev