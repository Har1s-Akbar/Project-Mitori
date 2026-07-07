from fastapi import FastAPI
import uvicorn

app = FastAPI(
    title ="mitori-engine",
    discription = "fast paced matching engine for project mitori",
    version = "1.0.0"
)

@app.get("/welcome")
async def welcome():
    
    return {
        "status" : "200",
        "message":"Welcome message for everyone trying to access mitori"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)