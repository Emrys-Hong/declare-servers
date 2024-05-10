import json
import os
from datetime import datetime, timedelta
from typing import Dict, List

from data_model import MachineStatus

###############################################################################
### Databse Definition and Initialization


class Database:
    def __init__(self, filename):
        self.filename = filename
        self.STATUS_DATA: Dict[str, List[MachineStatus]] = self.load()

    def add(self, status: MachineStatus):
        machine_id = status.machine_id
        status_list = self.STATUS_DATA[machine_id]
        status_list.append(status)
        current_time = datetime.now()
        two_weeks_later = status_list[0].created_at + timedelta(weeks=2)
        if current_time >= two_weeks_later:
            status_list.pop()
        self.save()

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r") as f:
                return json.load(f)
        return {}

    def save(self):
        with open(self.filename, "w") as f:
            json.dump(self.STATUS_DATA, f)


DB = Database(filename="./database.json")

###############################################################################
### report_status


def store_new_report(status: MachineStatus) -> None:
    # check report_key is valid
    # report_key has to be pre-existing
    if status.report_key not in DB.ALL_REPORT_KEYS:
        raise ValueError("Invalid report_key")

    # check machine_id is not empty
    if not status.machine_id:
        raise ValueError("Invalid machine_id")

    # check first time reporting
    if status.machine_id not in DB.ALL_REPORT_KEYS[status.report_key]:
        # new machine_id reporting to this report_key
        DB.ALL_REPORT_KEYS[status.report_key].add(status.machine_id)
        print(
            f"New machine_id ({status.machine_id}) reporting using report_key ({status.report_key})"
        )

    # store update
    DB.STATUS_DATA[status.machine_id] = status.model_dump()

    return


###############################################################################
### view_status


def get_view(view_key: str) -> Dict[str, Dict[str, MachineStatus]]:
    # check view_key is valid
    if view_key not in DB.ALL_VIEW_KEYS:
        raise ValueError("Invalid view_key.")
    # TODO: check access permission and stuff...
    ...
    # get view_group object
    view_group = DB.ALL_VIEW_KEYS[view_key]
    # TODO: maybe check timer here?
    ...
    # check if view is enabled
    view_enabled = view_group.get("view_enabled", False)
    if not view_enabled:
        raise ValueError("View is unavailable.")
    # get machine_id set
    machine_ids = view_group.get("view_machines", [])
    # get status data
    status_data = []
    for machine_id in machine_ids:
        if machine_id in DB.STATUS_DATA:
            status_data.append(DB.STATUS_DATA[machine_id])
    return status_data
