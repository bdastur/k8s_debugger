#!/usr/bin/env python
# -*- coding: utf-8 -*-

import streamlit as st
import commonlibs.kuhelper as kuhelper


if not st.session_state.get("currentContext", False):
    st.session_state.currentContext = ""


def setSideBarInformation():
    loginText = "### User: %s" % st.session_state.userLogin["Username"]
    st.sidebar.markdown(loginText)

    kobj = kuhelper.KuHelper()
    clusters = kobj.listKubeConfigClusters()
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Clusters:")
    for cluster in clusters:
        if cluster["currentContext"]:
            print("Set current context")
            st.session_state.currentContext = cluster["clusterName"]
            clusterText = "- **%s** [region: %s] [Account: %s]" % (cluster["clusterName"], cluster["region"], cluster["account"])
        else:
            clusterText = "- %s [region: %s] [Account: %s]" % (cluster["clusterName"], cluster["region"], cluster["account"])
        st.sidebar.markdown(clusterText)


