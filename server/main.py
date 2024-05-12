import os
import sys
from datetime import datetime
from logging import DEBUG, INFO
from typing import List, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from puts import get_logger

from database import DB as db
from data_model import MachineStatus

logger = get_logger()
logger.setLevel(INFO)

###############################################################################
# Constants

app = FastAPI()
origins = [
    "http://localhost",
    "http://localhost:8501",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# print timezone and current time
print()
logger.info(f"Environ 'TZ'    : {os.environ.get('TZ', 'N.A.')}")
logger.info(f"Current Time    : {datetime.now()}")
logger.info(f"Current UTC Time: {datetime.utcnow()}")
logger.info(f"Python Version  : {sys.version}")
print()


###############################################################################
## ENDPOINTS for DEBUGGING


@app.get("/")
async def hello():
    return {"msg": "Hello, this is Emrys."}


@app.get("/get", response_model=List[MachineStatus])
async def get_status():
    """Temporary endpoint for testing, will deprecated soon"""
    return list(db.DB.STATUS_DATA.values())


###############################################################################
## ENDPOINTS


@app.post("/report", status_code=201)
async def report_status(status: MachineStatus):
    """
    POST Endpoint for receiving status report from client (machines under monitoring).
    Incoming status report needs to have a valid report_key.
    Invalid report_key will be rejected.
    """
    try:
        db.add(status)
        logger.debug(
            f"Received status report from: {status.name} (report_key: {status.report_key})"
        )
        return {"msg": "OK"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


###############################################################################
## Web ENDPOINTS


@app.get("/server_status", status_code=200, response_model=List[MachineStatus])
def view_status(view_key):
    """
    GET Endpoint for receiving view request from web (users).
    Incoming view request needs to have a valid view_key.
    """
    try:
        if view_key == "PxHWZArEKqMEnb9N6c9M":
            return db.get_status()
    except ValueError as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
