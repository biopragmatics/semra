"""Run the app."""

import fastapi

app = fastapi.FastAPI()


@app.get("/")
def home():
    return "SeMRA"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=8773, host="0.0.0.0")  # noqa:S104
