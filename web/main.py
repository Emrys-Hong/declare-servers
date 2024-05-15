import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import requests
import streamlit as st

from data_model import MachineStatus
from scheme import header


curr_dir = Path(__file__).resolve().parent.parent
CONFIG_PATH = curr_dir / "config.json"


if not CONFIG_PATH.exists():
    sys.exit(1)

with CONFIG_PATH.open(mode="r") as f:
    configs = json.load(f)

REPORT_INTERVAL = int(configs.get("report_interval", 5))
ADMIN_PASSWORD = configs.get("admin_password", "")
VIEW_KEY = configs.get("view_key", "")


def moving_average(data, window_size=5):
    for _ in range(2):
        data = np.convolve(data, np.ones(window_size) / window_size, mode="same")
    return data


def gpu_usage_history_per_server(ip):
    csvs = {
        ip: pd.read_csv(f"{ip}_gpu_log.csv", on_bad_lines="skip", names=header)
        for ip in ip_list
        if os.path.exists(f"{ip}_gpu_log.csv")
    }
    for k, v in csvs.items():
        v["machine"] = k

    if ip == "Total":
        df = pd.concat(list(csvs.values()))
        if per_user:
            user = st.selectbox("Select User: ", ["All User"] + list(set(df["user"])))
            if user != "All User":
                df = df[df["user"] == user]

    else:
        if os.path.exists(f"{ip}_gpu_log.csv"):
            df = csvs[ip]
        else:
            df = pd.concat(list(csvs.values()))

    if not per_user:
        df["user"] = "All Users"
    if per_machine:
        df["user"] = "All Users"

    df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"], errors="coerce")
    time_limit = datetime.today() - timedelta(days=int(time_span))
    df = df[df["datetime"] >= time_limit]
    # previous full hour
    now = datetime.now()
    truncated_time = now.replace(minute=0, second=0, microsecond=0)
    df = df[df["datetime"] < truncated_time]

    if per_machine:
        grouped_df = (
            df.groupby([pd.Grouper(key="datetime", freq="1H"), "machine"])
            .size()
            .reset_index(name="count")
        )

        table = grouped_df.pivot_table(
            index="datetime", columns="machine", values="count", fill_value=0
        )

    else:
        grouped_df = (
            df.groupby([pd.Grouper(key="datetime", freq="1H"), "user"])
            .size()
            .reset_index(name="count")
        )

        table = grouped_df.pivot_table(
            index="datetime", columns="user", values="count", fill_value=0
        )
    table = table.divide(12)  # one hour have 12 five minutes interval

    for col in table.columns:
        table[col] = moving_average(table[col])

    st.line_chart(table)

    if ip != "Total":
        du_file = f"disk_usage_{ip}.txt"
        if os.path.exists(du_file):
            content = parse_content(du_file)
            st.text_area("Disk Usage:", content, height=800)  # Adjust height as needed


def header():
    st.title("DeCLaRe Server Status")


def gpu_usage_history():

    chart_option = st.selectbox(
        "Select Machine for gpu and disk usage: ", ["Total"] + ip_list
    )
    per_user = st.checkbox("Show individual user usage", value=False)
    per_machine = st.checkbox("Show individual machine usage", value=False)

    if per_user and per_machine:
        st.text(
            "Error: You cannot select individual user and machine at the same time!",
        )
    time_span = st.radio("Usage History in Days", ("1", "3", "7", "30"))

    gpu_usage_history_per_server(chart_option)


def get_server_status() -> List[MachineStatus]:
    params = {"view_key": VIEW_KEY}
    url = f"http://localhost:{configs['server_port']}/server_status/"
    response = requests.get(url, params=params)
    if response.status_code == 200:
        items = response.json()
    server_status = [MachineStatus.parse_obj(item) for item in items]
    return server_status


def percent_color_text(per: float, text: str = None) -> str:
    if not text:
        text = f"{(per * 100):.2f}%"
    if text == "temp":
        text = f"{int(per)}°C"
        per = per / 100

    if per > 0.7:
        text = f"<span style='color: red;'>{text}</span>"
    else:
        text = f"<span style='color: blue;'>{text}</span>"
    return text


def display_servers_html(online_users, offline_users):
    online_users_text, offline_users_text = "", ""
    for user in online_users:
        online_users_text += f"<div style='flex: 0; padding: 8px; margin: 5px; border-radius: 10px; background-color: transparent; border: 2px solid green; color: black; font-size: 10px; display: flex;'>{user}</div>"
    for user in offline_users:
        offline_users_text += f"<div style='flex: 0; padding: 8px; margin: 5px; border-radius: 10px; background-color: transparent; border: 2px solid red; color: black; font-size: 10px; display: flex;'>{user}</div>"

    return f"""
<div style='display: flex; flex-wrap: wrap; justify-content: start;'>
<div id="user-status">Online: </div>
{online_users_text}
<div id="user-status">Offline: </div>
{offline_users_text}
</div>"""


def display_disk_html(disk_detail: List):
    for user, disk_usage in disk_detail:
        st.write(user + ": " + disk_usage)


def show_gpu_status_html(gpu_cards):
    table_form = """
    **GPU Cards**
    <table style="margin: 20px auto; border-collapse: collapse;">
        <tr>
            <th style="border: 2px solid #ddd; padding: 20px; text-align: left; background-color: #f2f2f2; color: #333;">GPU</th>
            <th style="border: 2px solid #ddd; padding: 20px; text-align: left; background-color: #f2f2f2; color: #333;">Model</th>
            <th style="border: 2px solid #ddd; padding: 20px; text-align: left; background-color: #f2f2f2; color: #333;">Util</th>
            <th style="border: 2px solid #ddd; padding: 20px; text-align: left; background-color: #f2f2f2; color: #333;">Temp</th>
            <th style="border: 2px solid #ddd; padding: 20px; text-align: left; background-color: #f2f2f2; color: #333;">Memory</th>
        </tr>
        {table_content}
    """

    table_content = ""
    for card in gpu_cards:
        table_content += """<tr style="background-color: #fff; hover:background-color: #f5f5f5;">\n"""
        with st.container():
            card_index = card.index
            gpu_model = card.gpu_name
            core_util = percent_color_text(card.gpu_usage)
            core_temp = percent_color_text(card.temperature, "temp")
            mem_util = percent_color_text(card.memory_usage)
            mem_free = card.memory_free
            mem_total = card.memory_total
            td = """<td style="border: 2px solid #ddd; padding: 20px; text-align: center;">"""
            table_content += (
                f"{td}{card_index}</td>\n"
                f"{td}{gpu_model}</td>\n"
                f"{td}{core_util}</td>\n"
                f"{td}{core_temp}</td>\n"
                f"{td}{mem_util} \t (free: {mem_free} total: {mem_total})</td>\n"
            )
        table_content += "</tr>\n"
    return table_form.format(table_content=table_content)


def show_gpu_program(programs):

    tables = []
    for program in programs:
        program = dict(
            GPU=program["gpu_index"],
            PID=program["pid"],
            User=program["user"],
            Uptime=program["proc_uptime_str"],
            CMD=program["command"],
            Memory=program["gpu_mem_used"],
        )
        tables.append(program)
    if tables:
        df = pd.DataFrame(tables)
        st.dataframe(df)


def show_disk_detail(disk_status):
    st.markdown(
        f"Directory: {disk_status.directory}, Usage {percent_color_text(disk_status.usage)}",
        unsafe_allow_html=True,
    )
    st.write(f"Free: {disk_status.free}, Total: {disk_status.total}")
    display_disk_html(disk_status.detail)


def show_details(status: MachineStatus):
    local_ip = dict(status.ipv4s)["enp69s0"]
    with st.expander("Details"):
        st.markdown(
            f"**Last Seen**: {status.created_at.strftime('%Y-%m-%d %H:%M:%S')}, **Uptime**: {status.uptime_str}"
        )
        st.markdown(f"**Arch**: {status.architecture}")
        st.markdown(f"**System: {status.linux_distro}")
        st.markdown(f"**Nvidia SMI**: {status.nvidia_smi_version}")
        st.markdown(f"**CUDA Version**: {status.cuda_version}")
        st.markdown(f"CPU Model: {status.cpu_model}, Cores: {status.cpu_cores}")
        # System disk information
        st.markdown(f"**Disk Info**: {status.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        for disk_i, disk_col in enumerate(st.columns(len(status.disk_external) + 1)):
            with disk_col:
                if disk_i == 0:
                    show_disk_detail(status.disk_system)
                else:
                    show_disk_detail(status.disk_external[disk_i - 1])

        # local ip
        st.markdown(
            f"""
<div style='display: flex; flex-wrap: wrap; justify-content: start;'>
<div><b>IP Address</b> (inet)</div>
<span style="margin-left: 40px;"></span>
<div style='background-color: transparent; border: 2px solid #00ff00; padding: 8px; border-radius: 10px; width: max-content; margin-bottom: 8px;'>{local_ip}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        # online offline user
        st.markdown(
            display_servers_html(
                status.users_info["online_users"], status.users_info["offline_users"]
            ),
            unsafe_allow_html=True,
        )


def show_gpu_history():
    return


def show_status(status: MachineStatus):

    with st.container():
        # IP
        local_ip = dict(status.ipv4s)["enp69s0"]
        # Online
        is_online = (
            status.created_at + timedelta(seconds=REPORT_INTERVAL*3)
        ) > datetime.now()
        status_line = "🟢[Online]" if is_online else "🔴[Offline]"

        st.header(
            local_ip,
            divider="rainbow",
        )
        st.markdown(f"### {status_line} {status.machine_id[-4:]}: ({local_ip})")

        # Details
        show_details(status)

        # Usage
        cpu_util = status.cpu_usage
        st.markdown(
            f"**CPU Util:** {percent_color_text(status.cpu_usage)}"
            "\n\n"
            f"**CPU Temp**: {percent_color_text(status.cpu_temp, 'temp')}"
            "\n\n"
            f"**RAM Util:** {percent_color_text(status.ram_usage)} (*free: {status.ram_free}, total:{status.ram_total}*)"
            "\n\n"
            f"**System Disk Util**: {percent_color_text(status.disk_system.usage)} (*free: {status.disk_system.free}, total:{status.disk_system.total}*)",
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # GPU card Usage
        gpu_table = show_gpu_status_html(status.gpu_status)
        st.markdown(gpu_table, unsafe_allow_html=True)

        st.markdown("---")
        # GPU program
        show_gpu_program(status.gpu_compute_processes)

        # GPU History
        show_gpu_history()


def show_machine_status(server_status: List[MachineStatus]):
    for status in server_status:
        show_status(status)


def main():
    header()
    machine_status = get_server_status()

    show_machine_status(machine_status)

    return


if __name__ == "__main__":
    main()
