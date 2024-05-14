import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

from data_model import MachineStatus


###############################################################################
### Databse Definition and Initialization


class Database:
    def __init__(self, filename):
        self.filename = filename
        self.STATUS_DATA: Dict[str, List[MachineStatus]] = self.load()
        self.last_updated = datetime.now()

    def add(self, status: MachineStatus):
        machine_id = status.machine_id
        status_list = self.STATUS_DATA[machine_id]
        status_list.append(status)
        current_time = datetime.now()

        # only keep the history for two weeks
        two_weeks_later = status_list[0].created_at + timedelta(weeks=2)
        if current_time >= two_weeks_later:
            status_list.pop()

        # only update machine_status.json file every hour
        one_hour_later = self.last_updated + timedelta(hours=1)
        if current_time >= one_hour_later:
            self.last_updated = current_time
            self.save()

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r") as f:
                data = json.load(f)
                status_data = {
                    key: [MachineStatus.parse_obj(json.loads(o)) for o in values]
                    for key, values in data.items()
                }
                return defaultdict(list, status_data)
        return defaultdict(list)

    def save(self):
        with open(self.filename, "w") as f:
            json.dump(self.to_dict(), f)

    def get_status(self) -> List[MachineStatus]:
        machine_ids = sorted(list(self.STATUS_DATA.keys()), reverse=True)
        machine_status = [
            self.STATUS_DATA[machine_id][-1] for machine_id in machine_ids
        ]
        return machine_status

    def to_dict(self) -> dict:
        return {
            key: [status.json() for status in status_list]
            for key, status_list in self.STATUS_DATA.items()
        }

DB = Database(filename="./machine_status.json")
