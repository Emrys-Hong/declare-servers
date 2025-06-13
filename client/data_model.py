from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, validator

from helpers import mask_sensitive_string


class GPUStatus(BaseModel):
    index: int = None
    gpu_name: str = None
    gpu_usage: float = None  # range: [0, 1]
    temperature: float = None  # Celsius
    memory_free: float = None  # MB
    memory_total: float = None  # MB
    memory_usage: float = None  # range: [0, 1]


class GPUComputeProcess(BaseModel):
    pid: int = None
    user: str = None
    gpu_uuid: str = None
    gpu_index: int = None
    gpu_mem_used: float = None  # MiB
    gpu_mem_unit: str = "MiB"
    # gpu_mem_usage: float = None  # range: [0, 1]
    cpu_usage: float = None  # range: [0, 1]
    cpu_mem_usage: float = None  # range: [0, 1]
    proc_uptime: float = None  # seconds
    proc_uptime_unit: str = "seconds"
    proc_uptime_str: str = None  # HH:MM:SS
    command: str = None

    @validator("user", pre=True, always=True)
    def process_gpu_compute_info(cls, v):
        if v:
            return mask_sensitive_string(v)
        else:
            return ""


class DiskStatus(BaseModel):
    directory: str = ""
    created_at: datetime = datetime.now()
    usage: float = 0  # range: [0, 1]
    free: str = ""
    total: str = ""
    detail: List[tuple[str, str]] = [("0GB", "user")]  # [(size, path), ...]

    @validator("detail", pre=True, always=True)
    def process_disk_system_info(cls, v):
        if isinstance(v, List):
            for i, (user, usage) in enumerate(v):
                v[i] = [mask_sensitive_string(user), usage]
            return v
        else:
            []


class MachineStatus(BaseModel):
    created_at: datetime = None
    name: str = None
    machine_id: str = None
    report_key: str = None
    # ip
    hostname: str = None
    local_ip: str = None
    public_ip: str = None
    ipv4s: list = None
    ipv6s: list = None
    # sys info
    architecture: str = None
    mac_address: str = None
    platform: str = None
    platform_release: str = None
    platform_version: str = None
    linux_distro: str = None
    processor: str = None
    uptime: float = None  # seconds
    uptime_unit: str = "seconds"
    uptime_str: str = None
    cuda_version: str = "No CUDA Installed"
    nvidia_smi_version: str = "No GPU Driver installed"
    # sys usage
    cpu_model: str = None
    cpu_cores: int = None
    cpu_usage: float = None  # range: [0, 1]
    cpu_temp: float = None
    ram_free: str = None  # MiB
    ram_total: str = None  # MiB
    ram_usage: float = None  # range: [0, 1]
    # gpu usage
    gpu_status: List[GPUStatus] = None
    gpu_compute_processes: List[GPUComputeProcess] = None
    # users info
    users_info: Dict[str, List[str]] = None
    # disk info
    disk_system: DiskStatus = None
    disk_external: List[DiskStatus] = None

    @validator("created_at", pre=True, always=True)
    def default_created_at(cls, v):
        return v or datetime.now()

    @validator("users_info", pre=True, always=True)
    def process_users_info(cls, v):
        if isinstance(v, dict):
            for keys in v.keys():
                v[keys] = [mask_sensitive_string(user) for user in v[keys]]
            return v
        else:
            return {}

    def __repr__(self) -> str:
        return self.model_dump_json()

    def __str__(self) -> str:
        return self.__repr__()
