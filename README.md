# MeridianAI

set GOOGLE_APPLICATION_CREDENTIALS=./credentials/service-account.json

Backend:

python -m venv .meridian
.meridian\Scripts\activate
pip install -r requirements.txt
gcloud auth application-default set-quota-project meridian-platform-ai
uvicorn api.main:app --app-dir backend --reload --port 8080

Frontend:
cd frontend
npm install
npm run dev

Docker:
docker build -t meridian-ai .
docker run -p 8080:8080 meridian-ai
Run at http://localhost:8080