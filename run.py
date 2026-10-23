import json
from pathlib import Path
import uvicorn

if __name__ == "__main__":
    port = json.loads((Path(__file__).parent / "project.json").read_text())["port"]
    uvicorn.run("app:app", host="127.0.0.1", port=port)
