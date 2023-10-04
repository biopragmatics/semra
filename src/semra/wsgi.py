"""Run the app."""

import fastapi
from curies import Reference


from semra.neo4j_client import Client


client = Client()

app = fastapi.FastAPI()


@app.get("/")
def home():
    return "SeMRA"


@app.get("/equivalent/<c1>/<c2>")
def are_equivalent(c1: Reference, c2: Reference):
    res= client.are_equivalent(c1, c2)
    return {"source": c1, "target": c2, "equivalent": res}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=8773, host="0.0.0.0")  # noqa:S104
