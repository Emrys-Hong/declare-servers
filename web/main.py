import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st

from scheme import header
from pathlib import Path
import json

curr_dir = Path(__file__).resolve().parent.parent
CONFIG_PATH = curr_dir / "config.json"

if not CONFIG_PATH.exists():
    logger.error(f"Config file not found: {CONFIG_PATH}")
    sys.exit(1)

with CONFIG_PATH.open(mode="r") as f:
    configs = json.load(f)


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


def get_server_status():
    try:
        params = {'view_key': configs['view_key']}
        response = requests.get(f"http://localhost:{configs['server_port']}/server_status/", params=params)
        if response.status_code == 200:
            items = response.json()
    except Exception as e:
        print("server status unaccessible")



def main():
    correctpassword = "password"
    password = st.text_input("Admin code here:", type="password")
    if st.button("login"):
        if password == correctpassword:
            st.markdown('else')
            gpu_usage_history()
        else:
            st.error("The password is incorrect")

    get_server_status()
    # Admin part (optional)

    return


if __name__ == "__main__":
    main()
