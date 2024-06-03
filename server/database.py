import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pandas as pd

from data_model import MachineStatus

curr_dir = Path(__file__).resolve().parent.parent
CONFIG_PATH = curr_dir / "config.json"


with CONFIG_PATH.open(mode="r") as f:
    configs = json.load(f)


###############################################################################
### Databse Definition and Initialization


class Database:
    def __init__(self, record_filename, gpu_record_filename):
        self.last_updated = datetime.now()
        self.record_filename = record_filename
        self.gpu_record_filename = gpu_record_filename
        self.STATUS_DATA: Dict[str, List[MachineStatus]] = self.load_status_data()
        self.max_records = 10
        self.max_gpu_records = 1e5
        self.gpu_record: List[Dict] = self.load_gpu_record()

    def add(self, status: MachineStatus):
        machine_id = status.machine_id
        status_list = self.STATUS_DATA[machine_id]
        status_list.append(status)
        current_time = datetime.now()

        for process in status.gpu_compute_processes:
            self.gpu_record.append(
                dict(user=process.user, time=status.created_at, machine_id=machine_id)
            )

        # Each status list of certain length
        while len(status_list) >= self.max_records:
            status_list.pop(0)

        # only keep the gpu record history for two weeks
        days_later = status_list[0].created_at + timedelta(days=configs["history_days"])
        if current_time >= days_later:
            self.gpu_record.pop(0)
        while len(self.gpu_record) >= self.max_gpu_records:
            self.gpu_record.pop(0)

        # only update machine_status.json file every hour
        one_hour_later = self.last_updated + timedelta(
            seconds=configs["write_interval"]
        )
        if current_time >= one_hour_later:
            self.last_updated = current_time
            self.save()

    def load_status_data(self):
        try:
            if os.path.exists(self.record_filename):
                with open(self.record_filename, "r") as f:
                    data = json.load(f)
                    status_data = {
                        key: [MachineStatus.parse_obj(json.loads(o)) for o in values]
                        for key, values in data.items()
                    }
                    return defaultdict(list, status_data)
            return defaultdict(list)
        except Exception as e:
            print(e)
            return defaultdict(list)

    def load_gpu_record(self):
        if os.path.exists(self.gpu_record_filename):
            df = pd.read_csv(self.gpu_record_filename)
            records = df.to_dict(orient="records")
            return records
        else:
            return []

    def save(self):
        with open(self.record_filename, "w") as f:
            json.dump(self.to_dict(), f)

        df = pd.DataFrame(self.gpu_record)
        df.to_csv(self.gpu_record_filename, index=False)

    def get_status(self) -> List[MachineStatus]:
        machine_ids = sorted(list(self.STATUS_DATA.keys()), reverse=True)
        machine_status = [
            self.STATUS_DATA[machine_id][-1] for machine_id in machine_ids
        ]
        return machine_status

    def get_gpu_record(self) -> list[dict]:
        return self.gpu_record

    def to_dict(self) -> dict:
        return {
            key: [status.json() for status in status_list]
            for key, status_list in self.STATUS_DATA.items()
        }


DB = Database(
    record_filename="./machine_status.json", gpu_record_filename="./gpu_status.json"
)
