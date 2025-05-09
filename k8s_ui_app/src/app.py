#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""

"""

import streamlit as st
import sidebar
import webbrowser

def definePages():
    """
    Initialize the streamlit pages.
    """
    #loginPage = st.Page("login.py", title="Login", icon=":material/login:")
    chatPage = st.Page("chat.py", title="Query interface", icon=":material/chat:")
    #ordersArchPage = st.Page("ordersArch.py", title="Orders information Architecture",
    #                         icon=":material/transition_slide:")
    #dashboardPage = st.Page("dashboard.py", title="CustomerRep - Dashboard",
    #                        icon=":material/bar_chart_4_bars:")
    #notificationsPage = st.Page("notifications.py", title="Notifications",
    #                            icon=":material/notifications:")

    # Setup page navigation.
    pg = st.navigation([chatPage])
    pg.run()


def main():
    if not st.session_state.get("userLogin", False):
        st.session_state.userLogin = {'Authenticated': False, 'Username': "Guest"}

    # Initialize pages
    # definePages()

    if st.sidebar.button("Cloudwatch Dashboard"):
        webbrowser.open_new_tab("https://cloudwatch.amazonaws.com/dashboard.html?dashboard=AnyCompany-CustomerService-Monitoring-Dashboard&context=eyJSIjoidXMtZWFzdC0xIiwiRCI6ImN3LWRiLTIwMzkxODg2MjY1MyIsIlUiOiJ1cy1lYXN0LTFfank4UFpiVTRwIiwiQyI6IjNhaDRrM29ncmhlNmZxcmdzaTBqcmU2c3FtIiwiSSI6InVzLWVhc3QtMToyOTQ0ZDVhNy1hMTMyLTRkN2MtOTY1Zi05ODE5YzM1ZTM5YTQiLCJNIjoiUHVibGljIn0%3D")


    print("Set sidebar info from app.py")
    sidebar.setSideBarInformation()

    # Initialize pages
    definePages()

if __name__ == '__main__':
    main()

