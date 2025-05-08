#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
# Library to simplify Bedrock Invoke and Converse API Inovacations for clients.
------------------------------------------------------------------------------

## class BedrockRuntime
This class is a wrapper around Bedrock Runtime Boto APIs.

 Example Usage:
-----------------

1. Simple Example of converse API Usage:

import botolibs.bedrock_helper as bedrock_helper

brObj = bedrock_helper.BedrockRuntime(profileName="brd3", regionName="us-east-1")

userInput = "What is the most famous Australian band?"
response, contentText = brObj.converse(modelId="amazon.nova-lite-v1:0",  userInput=userInput)
print("response: ", contentText)

2.   A more complex example of converse API usage

import botolibs.bedrock_helper as bedrock_helper

brObj = bedrock_helper.BedrockRuntime(profileName="brd3", regionName="us-east-1")

imagePath = "/Users/bdastur/Desktop/orgchart.png"
modelId = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"

message = bedrock_helper.BedrockRuntime.buildMessage(
    role="user",
    texts=["What is this diagram showing?"],
    imagePath=imagePath,
    imageFormat="png")

(fullResponse, responseText) = brObj.converse(modelId=modelId, userInput=None, message=message)
print("Response text: ", responseText)

userInput = "List all the people in the org structure"
(fullResponse, responseText) = brObj.converse(modelId=modelId, userInput=userInput, message=None)
print("Response text: ", responseText)



## class MCPClient
This class is a helper class to simplify adding MCP clients to any application.

Example Usage:
-----------------

1.


"""

import boto3
import botocore
import json
import logging
import os
import pprint
from mcp import ClientSession
from mcp.client.sse import sse_client
from contextlib import AsyncExitStack


#######################################################################
# Setup Logging.
#######################################################################
def get_logger(level=logging.INFO,
               name="Default",
               msg_format:str = '[%(asctime)s %(levelname)s]:  %(message)s',
               date_format: str = '%m-%d %H:%M', output_file_name: str = './output.log'):

    print("Get Logger: %s" % name)
    logger = logging.getLogger(name)

    logging.basicConfig(level=level,
                        format=msg_format,
                        datefmt=date_format,
                        filename=output_file_name,
                        filemode='w')

    if logger.hasHandlers():
        logger.handlers.clear()

    # Set console message format. Can be the same.
    consoleMsgFormat:str = msg_format

    console = logging.StreamHandler()
    #avoid logs below INFO serity to standard out
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(consoleMsgFormat))
    # add the handler to the root logger
    logger.addHandler(console)

    return logger


class MCPClient():
    def __init__(self, profileName=None, regionName=None, systemInstructions=None, verbose=False):
        """
        Initialize MCP Client Library.
        """
        assert profileName is not None
        assert regionName is not None
        print("BRD: verbose: ", verbose)
        if verbose:
            level = logging.INFO
        else:
            level = logging.WARN

        self.logger = get_logger(name="McpClient", level=level)

        self.serverUrl = None
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.brObj = BedrockRuntime(profileName=profileName, regionName=regionName)
        self.brObj.setSystemInstructions(systemInstructions)

        self.logger.info("MCPClient Initialized (%s/%s)" % (profileName, regionName))


    async def connectMCPServer(self, serverUrl: str):
        """
        Connect to a MCP server and create a Client session. If succesfull, return the
        list of tools provided by the server.

        @params:
        serverUrl: (str) The MCP Server url. (eg: http://272.23.44.3:5001/sse)

        @returns:
        tools:  (list) List of tools

        """
        # Store the context managers so they stay alive
        self.serverUrl = serverUrl
        self._streams_context = sse_client(url=serverUrl)
        streams = await self._streams_context.__aenter__()

        self._session_context = ClientSession(*streams)
        self.session: ClientSession = await self._session_context.__aenter__()

        # Initialize
        await self.session.initialize()

        # List available tools to verify connection
        self.logger.info("Connected to server %s. Listing tools" % serverUrl)
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server: ", self.serverUrl)
        print("    tools available :", [tool.name for tool in tools])
        self.logger.info("Server [%s] tools: [%s]" % (self.serverUrl, [tool.name for tool in tools]))

        return tools

    def buildToolConfig(self, tools):
        """
        Build the ToolConfig in the format that Bedrock API expects.
        """
        toolConfig = {
            "tools": []
        }

        availableTools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in tools]

        for tool in availableTools:
            obj = {"toolSpec": {}}
            obj["toolSpec"]["name"] = tool["name"]
            obj["toolSpec"]["description"] = tool["description"]
            obj["toolSpec"]["inputSchema"] = {
                "json": {
                    "type": "object",
                    "properties": {
                    }
                }
            }
            for property in tool["input_schema"]["properties"]:
                propObj = tool["input_schema"]["properties"][property]
                obj["toolSpec"]["inputSchema"]["json"]["properties"][property] = {
                    "type": propObj["type"],
                    "description": propObj["title"]
                }
            toolConfig["tools"].append(obj)

        return toolConfig

    async def getToolResponse(self, response):
        """
        Invoke the tool and get the response.

        @params:
            response: The response from the bedrock agent that has the tool Request info.

        Note:
        The Tool Response (from MCP Server tools) is expected to be a json string with the format.
        {"result": <result> }

        """
        toolInfo = {}
        toolRequests = response["output"]["message"]["content"]
        for toolRequest in toolRequests:
            if "toolUse" in toolRequest:
                toolInfo = toolRequest["toolUse"]
                break

        toolName = toolInfo["name"]
        toolArgs = toolInfo["input"]

        if toolName == "get_pods_information" and toolArgs == {}:
            toolArgs = {'namespace': 'None', 'podName': 'None'}

        self.logger.info("Invoke Tool (name) %s with Args: %s" % (toolName, toolArgs))

        # Execute tool call
        result = await self.session.call_tool(toolName, toolArgs)
        self.logger.info("Result returned from the tool")
        print("BRD: result: ", result)

        resultValue = json.loads(result.content[0].text)
        toolResult = {
            "toolUseId": toolInfo["toolUseId"],
            "content": [{"text": "Result is %s " % (str(resultValue["result"]))}]
        }
        self.logger.info("ResultValue extracted from tool")

        toolResponseMessage = {
            "role": "user",
            "content": [
                {"toolResult": toolResult}
            ]
        }

        self.logger.info("Tool Response: %s" % toolResponseMessage)
        return toolResponseMessage

    async def processQuery(self, query, availableTools):
        """
        Query.
        """
        toolConfig = self.buildToolConfig(availableTools)
        #pp = pprint.PrettyPrinter()
        #pp.pprint(toolConfig)
        response, contentText = self.brObj.converse(
                modelId="amazon.nova-lite-v1:0",
                userInput=query, toolConfig=toolConfig)

        #print("=== response 1 ===")
        #print(json.dumps(response, indent=4))
        #print(" === end ===")

        stopReason = response['stopReason']

        if stopReason == "tool_use":
            toolResponseMessage = await self.getToolResponse(response)
        elif stopReason == "end_turn":
            return  contentText

        self.logger.info("Send toolResponseMessage to FoundationModel")
        # Send the result to the FM.
        response, contentText = self.brObj.converse(
            modelId="amazon.nova-lite-v1:0",
            message=toolResponseMessage,
            toolConfig=toolConfig)

        #print("=== response 2 ===")
        #print(json.dumps(response, indent=4))
        #print(" === end ===")

        return contentText


    async def cleanup(self):
        """Properly clean up the session and streams"""
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)




class BedrockRuntime():
    def __init__(self, profileName=None, regionName=None):
        assert profileName is not None
        assert regionName is not None

        self.logger = get_logger(name="BedRockHandler")

        self.validated = False
        self.converseMessages = []
        self.botoClient = None
        self.systemPrompt = [] 

        try:
            botoSession = boto3.Session(profile_name=profileName, region_name=regionName)
            self.botoClient = botoSession.client("bedrock-runtime")
        except botocore.exceptions.ProfileNotFound as err:
            print("Failed to get Boto3 client [%s]" % err)
            return

        self.validated = True
        self.logger.info("BedrockRuntime Initialized")

    def setSystemInstructions(self, text):
        """
        Set System prompt for the bedrock runtime agent.
        """
        if text:
            self.systemPrompt = [
                {
                    "text": text
                }
            ]

    def converse(self,
                 modelId="us.amazon.nova-lite-v1:0",
                 userInput="",
                 message=None,
                 toolConfig=None,
                 enableVerbose=False):
        assert self.validated is True

        if message is None:
            assert len(userInput) > 1
            message = {
                "role": "user",
                "content": [{"text": "%s" % userInput}]
            }

        self.converseMessages.append(message)

        try:
            if toolConfig:
                modelResponse = self.botoClient.converse(
                    modelId=modelId,
                    messages=self.converseMessages,
                    toolConfig=toolConfig,
                    system=self.systemPrompt
                )
            else:
                modelResponse = self.botoClient.converse(
                    modelId=modelId,
                    messages=self.converseMessages,
                    system=self.systemPrompt
                )

        except botocore.errorfactory.ClientError as err:
            self.logger.error("Bedrock Invocation Failure [%s]" % err)
            return None, None

        outputMessage = modelResponse["output"]["message"]
        messageContentText = outputMessage["content"][0]["text"]

        self.converseMessages.append(outputMessage)

        if enableVerbose:
            print("\n[Full Response]")
            print(json.dumps(modelResponse, indent=2))

        #print("\n[Response Content Text]")
        #print(messageContentText)

        return modelResponse, messageContentText

    @staticmethod
    def buildMessage(role="user", texts=[], imagePath=None, imageFormat="png"):
        """
        build a message structure
        """
        message = {}
        message["role"] = role
        message["content"] = []
        for text in texts:
            textContent = {}
            textContent["text"] = text
            message["content"].append(textContent)

        if imagePath is not None and  os.path.exists(imagePath):
            # Read image.
            with open(imagePath, "rb") as fh:
                image = fh.read()

            imageContent = {}
            imageContent["image"] = {}
            imageContent["image"]["format"] = imageFormat
            imageContent["image"]["source"] = {
                "bytes": image
            }
            message["content"].append(imageContent)

        return message


    def invoke(self, modelId="amazon.nova-lite-v1:0", userInput="", messages=None, enableVerbose=False):
        """
        Invoke the Bedrock Nova Foundation Model.
        """

        invokeBody = {
            "messages": []
        }
        if "nova" in modelId:
            print("This is a nova model")
            invokeBody["inferenceConfig"] = {
                "max_new_tokens": 200
            }
            if messages is not None:
                invokeBody["messags"] = messages
            else:
                message = {
                    "role": "user",
                    "content": [
                        {"text": userInput}
                    ]
                }
                invokeBody["messages"].append(message)
            body = json.dumps(invokeBody)
        elif "claude" in modelId:
            print("This is an Anthropic Claude Model")
            body = json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 200,
                    "top_k": 250,
                    "stop_sequences": [],
                    "temperature": 1,
                    "top_p": 0.999,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "hello world"
                                }
                            ]
                        }
                    ]
                })

        try:
            response = self.botoClient.invoke_model(
                modelId=modelId,
                body=body,
                contentType="application/json",
                accept="application/json")
        except botocore.errorfactory.ClientError as err:
            print("Bedrock Invocation Failure [%s]" % err)
            return None

        responseBody = json.loads(response.get("body").read())
        return responseBody



class BedrockAgentRuntime():
    def __init__(self, profileName=None, regionName="us-east-1"):
        assert profileName is not None

        self.validated = False
        self.botoClient = None

        try:
            botoSession = boto3.Session(profile_name=profileName, region_name=regionName)
            self.botoClient = botoSession.client("bedrock-agent-runtime")
        except botocore.exceptions.ProfileNotFound as err:
            print("Failed to get Boto3 client [%s]" % err)
            return

        self.validated = True

    def invokeAgent(self, user_query):
        pass








