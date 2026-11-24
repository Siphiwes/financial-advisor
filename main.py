from fastapi import FastAPI

app = FastAPI(
    title="Financial Advisor API",
    description="Backend API for the AI Personal Finance Advisor",
    version="0.1.0",
)

@app.get("/")
def read_root():
    return {
        "application": "Financial Advisor API",
        "status": "running",
        "version": "0.1.0",
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}
