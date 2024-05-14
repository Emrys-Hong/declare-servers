import os
from datetime import datetime, timedelta
from typing import List

import numpy as np
import pandas as pd
import requests
import streamlit as st

from scheme import header
from pathlib import Path
import json
from data_model import MachineStatus

curr_dir = Path(__file__).resolve().parent.parent
CONFIG_PATH = curr_dir / "config.json"


if not CONFIG_PATH.exists():
    logger.error(f"Config file not found: {CONFIG_PATH}")
    sys.exit(1)

with CONFIG_PATH.open(mode="r") as f:
    configs = json.load(f)

REPORT_INTERVAL = int(configs.get("report_interval", 5))
ADMIN_PASSWORD = configs.get('admin_password', "")
VIEW_KEY = configs.get('view_key', "")

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
    params = {'view_key': VIEW_KEY}
    url = f"http://localhost:{configs['server_port']}/server_status/"
    response = requests.get(url, params=params)
    if response.status_code == 200:
        items = response.json()
    server_status = [MachineStatus.parse_obj(item) for item in items]
    return server_status

def percent_color_text(per: float, text: str = None) -> str:
    if not text:
        text = f"{(per * 100):.2f}%"
    if text == 'temp':
        text = f"{int(per)}°C"

    if per > 0.7:
        text = f"<span style='color: red;'>{text}</span>"
    else:
        text = f"<span style='color: blue;'>{text}</span>"
    return text


def display_servers(users, status):
    server_cards = ""
    for user in users:
        color = "#0f0" if status == "Online" else "#f00"
        server_cards += f"<div style='flex: 1; padding: 8px; margin: 5px; border-radius: 10px; background-color: #1e1e1e; border: 2px solid {color}; color: white; font-size: 16px; display: flex; align-items: center; justify-content: center;'>{user}</div>"
    
    return f"<div style='display: flex; flex-wrap: wrap; justify-content: start;'>{server_cards}</div>"

def show_gpu_status(gpu_cards):

    for card in gpu_cards:
        with st.container():
            card_index = card.index
            gpu_model = card.gpu_name
            core_util = percent_color_text(card.gpu_usage)
            core_temp = percent_color_text(card.temperature, 'temp')
            mem_util = percent_color_text(card.memory_usage)
            mem_free = card.memory_free
            mem_total = card.memory_total

            st.write(f"GPU: {card_index} {gpu_model}")
            st.markdown(f"Core Util: {core_util} \t Core Temp: {core_temp}", unsafe_allow_html=True)
            st.markdown(f"Memory Util: {mem_util} \t (free: {mem_free} total: {mem_total})", unsafe_allow_html=True)


def show_gpu_program(programs):

    tables = []
    for program in programs:
        program = dict(GPU=program['gpu_index'],
                       PID=program['pid'],
                       User=program['user'],
                       Uptime=program['proc_uptime_str'],
                       CMD=program['command'],
                       Memory=program['gpu_mem_used']
                       )
        tables.append(program)
    if tables:
        df = pd.DataFrame(tables)
        st.dataframe(df)



def show_details(status: MachineStatus):
    local_ip = dict(status.ipv4s)["enp69s0"]
    with st.expander("Details"):
        st.write(f"Last Seen: {status.created_at.strftime('%Y-%m-%d %H:%M:%S')}, Uptime: {status.uptime_str}")
        st.write(f"Arch: {status.architecture}, System: {status.linux_distro}")
        st.write(f"CPU Model: {status.cpu_model}, Cores: {status.cpu_cores}")
        st.write(f"System Disk: {status.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        st.write(status.disk_system.detail_string)
        st.write(f"External Disk")
        for ext in status.disk_external:
            st.write(ext.detail_string)
        st.markdown(f"<div style='background-color: #1e1e1e; border: 2px solid #00ff00; padding: 8px; border-radius: 10px; width: max-content; margin-bottom: 20px;'>**Local IP Address**: {local_ip}</div>", unsafe_allow_html=True)
        # online user
        st.markdown("Online: " + display_servers(status.users_info['online_users'], "Online") + "|" + "Offline: " + display_servers(status.users_info['offline_users'], "Offline"), unsafe_allow_html=True)



def show_gpu_history():
    return 

def show_status(status: MachineStatus):


    with st.container():
        # IP
        local_ip = dict(status.ipv4s)["enp69s0"]
        st.write(f"### Machine: {status.machine_id[-4:]} {local_ip}")

        # Online
        is_online = (status.created_at + timedelta(seconds=REPORT_INTERVAL)) > datetime.now()
        status_line = "**Server Status**: 🟢 Online" if is_online else "**Server Status**: 🔴 Offline"
        st.markdown(status_line)

        # Details
        show_details(status)


        # Usage
        cpu_util = status.cpu_usage
        st.markdown(f"CPU Util: {percent_color_text(status.cpu_usage)}, CPU Temp: {percent_color_text(status.cpu_temp, 'temp')}", unsafe_allow_html=True)
        st.markdown(f"RAM Util: {percent_color_text(status.ram_usage)} (free: {status.ram_free}, total:{status.ram_total})", unsafe_allow_html=True)
        st.markdown(f"System Disk Util: {percent_color_text(status.disk_system.usage)} (free: {status.disk_system.free}, total:{status.disk_system.total})", unsafe_allow_html=True)

        # GPU card Usage
        show_gpu_status(status.gpu_status)

        # GPU program
        show_gpu_program(status.gpu_compute_processes)

        # TODO: GPU History
        show_gpu_history()

def show_machine_status(server_status: List[MachineStatus]):
    for status in server_status:
        show_status(status)



def main():
    header()
    correctpassword = ADMIN_PASSWORD
    password = st.text_input("Admin password here:", type="password")

    if st.button("login"):
        if password == correctpassword:
            gpu_usage_history()
        else:
            st.error("The password is incorrect")

    machine_status = get_server_status()

    show_machine_status(machine_status)
    # Admin part (optional)

    return


if __name__ == "__main__":
    main()
