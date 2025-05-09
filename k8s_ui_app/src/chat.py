#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Chat Interface
"""

import streamlit as st
import datetime
import mcp_boto_helper
import asyncio

# Custom CSS for shadow container
# banner: https://gitlab.aws.dev/bdastur/incubator/-/raw/main/k8sBedrock/k8sui/src/banner.png
st.markdown("""
<style>
.shadow-container {
    background-image: url("https://gitlab.aws.dev/bdastur/incubator/-/raw/main/k8sBedrock/k8sui/src/banner.png");
    background-size: cover;
    width: 100%;
    height: 150px;
    color: gray;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    margin: 10px 0;
}
</style>
""", unsafe_allow_html=True)

# Create container with shadow
st.markdown("""
<div class="shadow-container">
    <span>   </span>
</div>
""", unsafe_allow_html=True)


if not st.session_state.get("messageCount", False):
    st.session_state.messageCount = 0

if not st.session_state.get("chatHistory", False):
    st.session_state.chatHistory = []


def generateResponse(promptTextInput, userInfo):
    st.session_state.messageCount += 1
    userDisplayText = ":blue[%s]" % promptTextInput
    userObj = {"type": "user", "text": userDisplayText}
    st.session_state.chatHistory.append(userObj)

    if not st.session_state.get("sessionId", False):
        sessionId = "%s_%s" % (userInfo["Username"], datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%s"))
        st.session_state.sessionId = sessionId

    response = mcp_boto_helper.requestResponse(promptTextInput)

    #response = boto_interface.requestResponse(
    #    promptTextInput, userInfo, st.session_state.sessionId,
    #    st.session_state.messageCount)

    respObj = {"type": "agent", "text": response}
    st.session_state.chatHistory.append(respObj)

    for msg in reversed(st.session_state.chatHistory):
        if msg["type"] == "user":
            icon = ":material/question_mark:"
        else:
            icon = ":material/neurology:"
        st.info(msg["text"], icon=icon)


with st.form('my_form'):
    label = "Enter query (%s):" % (st.session_state.currentContext)
    text = st.text_area(label, '')
    submitted = st.form_submit_button('Submit')
    if submitted:
        generateResponse(text, st.session_state.userLogin)

