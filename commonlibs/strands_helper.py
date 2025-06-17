#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
# Library to simplify interfacing with Strands SDK.
------------------------------------------------------------------------------


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
import re
from mcp.client.sse import sse_client
import strands
import mcp.client.streamable_http as streamable_http
import strands.tools.mcp.mcp_client as mcp_client
import strands.models as models
from strands.telemetry.tracer import get_tracer
import commonlibs.ddb_helper as dynamodb
import commonlibs.s3_helper as s3_helper



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


class StrandsAgent():
    def __init__(self, **kwargs):
        """
        Initialize the StrandsAgent Wrapper Class.
        agentInfo = {
            "name": "simple-metrics-agent",
            "systemInstructions": "<system instructions>"
            "modelInfo": {
                "bedrock": {
                    "profile": "brd3"
                    "region": "us-east-1",
                    "modelId": "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
                }
            },
            "tracerConfig": {
                "otlpEndpoint": "http://localhost:4318",
                "otlpHeaders": {"Authorization": "Bearer TOKEN"},
                "enableConsoleExport": true
            },
            "mcpServers": {
                "calculator": {
                    "transport": "streamable-http",
                    "url": "http://localhost:5001"
                }
            },
            "metricsConfig": {
                "metricsSchemaBucket": "xyz",
                "metricSchemaKey": "/path/to/key",
                "metricsSummaryTable": "ddb table",
                "region": "us-east-1",
                "profile": "brd3"
            }
        }
        """

        self.logger = get_logger(name="StransClient", level="INFO")
        self.name = kwargs.get("name", "default")
        self.systemPrompt = kwargs.get("systemInstructions", None)

        self.metricSummaryItemSchema = None
        self.metricSchemaKey = "/agentMetricSchema/%s_ddb_schema.json" % self.name


        # Storage.
        metricsConfig =  kwargs.get("metricsConfig", None)
        if metricsConfig:
            self.metricsConfig = metricsConfig


        if kwargs.get("modelInfo", None) is None:
            print("Model configuration required")
            return

        self.llmModel = self.__setupModelInformation(kwargs["modelInfo"])

        # setup MCP Server clients.
        self.mcpServers = {}
        self.tools = []
        self.mcpClients = []
        if kwargs.get("mcpServers", None) is not None:
            self.mcpServers = kwargs["mcpServers"]
            print("Setup MCP Servers")
            for server in kwargs["mcpServers"]:
                url = kwargs["mcpServers"][server]["url"]
                transport = kwargs["mcpServers"][server]["transport"]

                #Setup MCPClient for the server.
                mcpClient, tools = self.__createMcpClient(server, url, transport)
                self.mcpServers[server]["mcpClient"] = mcpClient
                self.mcpServers[server]["tools"] = tools
                self.tools.extend(tools)
                self.mcpClients.append(mcpClient)

        print("Tools available: ", self.tools)

        #Setup the Strands Agent.
        self.strandsAgent = strands.Agent(model=self.llmModel,
                                          system_prompt=self.systemPrompt,
                                          tools=self.tools)

        # Setup tracer.
        # Configure the tracer
        if kwargs.get("tracerConfig", None) is not None:
            print("Setup tracer config")
            self.__setupTracing(kwargs["tracerConfig"])

        self.validated = True
        print("Strands Agent Initialized")

    def __setupModelInformation(self, modelInfo):
        """
        Setup Model configuration.
        Only bedrock supported .
        """
        if "bedrock" in modelInfo:
            print("Bedrock model config")
            try:
                profile = modelInfo["bedrock"]["profile"]
                region = modelInfo["bedrock"]["region"]
                modelId = modelInfo["bedrock"]["modelId"]
            except KeyError as err:
                self.logger.error("Failed to parse input %s" % err)
                return None

            # Boto session.
            botoSession = boto3.Session(region_name=region, profile_name=profile)
            bedrockModel = models.BedrockModel(
                model_id=modelId,
                boto_session=botoSession,
                temperature=0.3)

            return bedrockModel

    def __setupTracing(self, tracerConfig):
        """
        Setup Tracing
        """
        self.tracer = get_tracer(
            service_name=self.name,
            otlp_endpoint=tracerConfig["otlpEndpoint"],
            otlp_headers=tracerConfig["otlpHeaders"],
            enable_console_export=tracerConfig["enableConsoleExport"])

    def __createMcpClient(self, server, url, transport):
        # TODO: Make the url creation more robust.
        # expected input http://<ip.dns>:<port>
        if transport == "sse":
            url = url + "/sse"
        else:
            url = url + "/mcp"

        def createTransport():
            if transport == "sse":
                return sse.sse_client(url=url)
            elif transport == "streamable-http":
                return streamable_http.streamablehttp_client(url=url)

        mcpClient = mcp_client.MCPClient(createTransport)

        # Get tools.
        try:
            with mcpClient:
                tools = mcpClient.list_tools_sync()
        except strands.types.exceptions.MCPClientInitializationError as err:
            self.logger.error("Failed to connect to server (%s, %s, %s) " % (server, url, transport))
            return None, None

        return mcpClient, tools

    def _getMetricSummaryItemSchema(self, metricSummary, setSchema=True):

        s3BucketName = self.metricsConfig["metricsSchemaBucket"]
        region = self.metricsConfig["region"]
        profile = self.metricsConfig["profile"]

        if not setSchema:
            itemSchema = s3_helper.readFromS3(s3BucketName, self.metricSchemaKey, 
                                              region=region, profile=profile)
            return itemSchema


        # set schema.
        itemSchema = [
            {
                "itemName": "latencyMs",
                "itemType": "N"
            },
            {
                "itemName": "inputTokens",
                "itemType": "N"
            },
            {
                "itemName": "outputTokens",
                "itemType": "N"
            },
            {
                "itemName": "totalTokens",
                "itemType": "N"
            },
            {
                "itemName": "average_cycle_time",
                "itemType": "N"
            },
        ]

        if "tool_usage" in  metricSummary:
            for tool in metricSummary["tool_usage"]:
                print("Tool: ", tool)
                ddbKey = "tool_%s_execution_average_time" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)

                ddbKey = "tool_%s_call_count" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)

                ddbKey = "tool_%s_error_count" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)


                ddbKey = "tool_%s_success_count" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)

                ddbKey = "tool_%s_success_rate" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)

                ddbKey = "tool_%s_total_time" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)

            s3_helper.writeToS3(s3BucketName, self.metricSchemaKey, 
                                itemSchema, region=region, profile=profile)
            self.metricSummaryItemSchema = itemSchema
            return itemSchema

    def storeMetrics(self, result):
        """
        Save Agent metrics.
        """
        print("Store Metrics")

        #print("Result type: ", type(result))
        #pp = pprint.PrettyPrinter()
        #pp.pprint(result.metrics)

        metricSummary = result.metrics.get_summary()

        #print("------------")
        #print("")
        #pp.pprint(metricSummary)

        itemSchema = self._getMetricSummaryItemSchema(metricSummary)

        tableName = self.metricsConfig["metricsSummaryTable"]
        region = self.metricsConfig["region"]
        profile = self.metricsConfig["profile"] 


        ddbTable = dynamodb.Table(region=region, profile=profile, tableName=tableName)
        itemSchema = itemSchema
        ddbTable.setItemSchema(itemSchema)

        record = {}
        record["agent_service_name"] = self.name
        record["latencyMs"] = metricSummary["accumulated_metrics"]["latencyMs"]
        record["inputTokens"] = metricSummary["accumulated_usage"]["inputTokens"]
        record["outputTokens"] = metricSummary["accumulated_usage"]["outputTokens"]
        record["totalTokens"] = metricSummary["accumulated_usage"]["totalTokens"]
        record["average_cycle_time"] = metricSummary["average_cycle_time"]


        for tool in metricSummary["tool_usage"]:
            ddbKey = "tool_%s_execution_average_time" % tool
            record[ddbKey] = metricSummary["tool_usage"][tool]["execution_stats"]["average_time"]

            ddbKey = "tool_%s_call_count" % tool
            record[ddbKey] = metricSummary["tool_usage"][tool]["execution_stats"]["call_count"]

            ddbKey = "tool_%s_error_count" % tool
            record[ddbKey] = metricSummary["tool_usage"][tool]["execution_stats"]["error_count"]

            ddbKey = "tool_%s_success_count" % tool
            record[ddbKey] = metricSummary["tool_usage"][tool]["execution_stats"]["success_count"]

            ddbKey = "tool_%s_success_rate" % tool
            record[ddbKey] = metricSummary["tool_usage"][tool]["execution_stats"]["success_rate"]

            ddbKey = "tool_%s_total_time" % tool
            record[ddbKey] = metricSummary["tool_usage"][tool]["execution_stats"]["total_time"]


        ddbTable.putItem(record, update=True)


    def scanMetricSummary(self):

        tableName = self.metricsConfig["metricsSummaryTable"]
        region = self.metricsConfig["region"]
        profile = self.metricsConfig["profile"]

        ddbTable = dynamodb.Table(region=region, profile=profile, tableName=tableName)

        itemSchema = self._getMetricSummaryItemSchema(None, setSchema=False)
        print("Item schema: ", itemSchema)
        
        #itemSchema = self.metricSummaryItemSchema
        ddbTable.setItemSchema(itemSchema)


        # Scan the whole table.
        scanOptions = {}
        ret = ddbTable.scanItems(**scanOptions)

        returnVal = []
        # Change the data before returning.

        toolMetrics = ["call_count", "error_count", 
                       "execution_average_time", "success_count",
                       "success_rate", "total_time"]

        for item in ret["Items"]:
            obj = {}
            obj["agent_service_name"] = item["agent_service_name"] 
            obj["average_cycle_time"] = item["average_cycle_time"]
            obj["inputTokens"] = item["inputTokens"]
            obj["outputTokens"] = item["outputTokens"]
            obj["latencyMs"] = item["latencyMs"]
            obj["totalTokens"] = item["totalTokens"]
            obj["tool_usage"] = {}

            tool_keys = [key for key in item.keys() if key.startswith('tool_')]
            tools = []
            for key in tool_keys:
                mobj = re.match(r"tool_(.*)_call_count", key)
                if mobj:
                    tools.append(mobj.group(1))
            print("Tools found: ", tools)

            for tool in tools:
                obj["tool_usage"][tool] = {}
                for metric in toolMetrics:
                    toolMetricKey = "tool_%s_%s" % (tool, metric)
                    obj["tool_usage"][tool][metric] = item[toolMetricKey] 


            returnVal.append(obj)

        return returnVal


class StrandsMetrics():
    def __init__(self, **kwargs):
        """
        agentInfo = {
            "name": "name",
            "metricsConfig": {
                "metricsSchemaBucket": "xyz",
                "metricSchemaKey": "/path/to/key",
                "metricsSummaryTable": "ddb table",
                "region": "us-east-1",
                "profile": "brd3"
            }
        }
        """

        self.logger = get_logger(name="StrandsMetrics", level="INFO")
        self.name = kwargs.get("name", "default")
        self.metricsConfig = None

        self.metricSchemaKey = "/agentMetricSchema/%s_ddb_schema.json" % self.name

        metricsConfig =  kwargs.get("metricsConfig", None)
        if metricsConfig:
            self.metricsConfig = metricsConfig


    def _getMetricSummaryItemSchema(self, metricSummary, setSchema=True):

        s3BucketName = self.metricsConfig["metricsSchemaBucket"]
        region = self.metricsConfig["region"]
        profile = self.metricsConfig["profile"]

        if not setSchema:
            itemSchema = s3_helper.readFromS3(s3BucketName, self.metricSchemaKey, 
                                              region=region, profile=profile)
            return itemSchema


        # set schema.
        itemSchema = [
            {
                "itemName": "latencyMs",
                "itemType": "N"
            },
            {
                "itemName": "inputTokens",
                "itemType": "N"
            },
            {
                "itemName": "outputTokens",
                "itemType": "N"
            },
            {
                "itemName": "totalTokens",
                "itemType": "N"
            },
            {
                "itemName": "average_cycle_time",
                "itemType": "N"
            },
        ]

        if "tool_usage" in  metricSummary:
            for tool in metricSummary["tool_usage"]:
                print("Tool: ", tool)
                ddbKey = "tool_%s_execution_average_time" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)

                ddbKey = "tool_%s_call_count" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)

                ddbKey = "tool_%s_error_count" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)


                ddbKey = "tool_%s_success_count" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)

                ddbKey = "tool_%s_success_rate" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)

                ddbKey = "tool_%s_total_time" % tool
                obj = {
                    "itemName": ddbKey,
                    "itemType": "N"
                }
                itemSchema.append(obj)

        s3_helper.writeToS3(s3BucketName, self.metricSchemaKey, 
                            itemSchema, region=region, profile=profile)
        self.metricSummaryItemSchema = itemSchema
        return itemSchema

    def scanMetricSummary(self):

        tableName = self.metricsConfig["metricsSummaryTable"]
        region = self.metricsConfig["region"]
        profile = self.metricsConfig["profile"]

        ddbTable = dynamodb.Table(region=region, profile=profile, tableName=tableName)

        itemSchema = self._getMetricSummaryItemSchema(None, setSchema=False)
        print("Item schema: ", itemSchema)
        
        #itemSchema = self.metricSummaryItemSchema
        ddbTable.setItemSchema(itemSchema)


        # Scan the whole table.
        scanOptions = {}
        ret = ddbTable.scanItems(**scanOptions)

        returnVal = []
        # Change the data before returning.

        toolMetrics = ["call_count", "error_count", 
                       "execution_average_time", "success_count",
                       "success_rate", "total_time"]

        for item in ret["Items"]:
            obj = {}
            obj["agent_service_name"] = item["agent_service_name"] 
            obj["average_cycle_time"] = item["average_cycle_time"]
            obj["inputTokens"] = item["inputTokens"]
            obj["outputTokens"] = item["outputTokens"]
            obj["latencyMs"] = item["latencyMs"]
            obj["totalTokens"] = item["totalTokens"]
            obj["tool_usage"] = {}

            tool_keys = [key for key in item.keys() if key.startswith('tool_')]
            tools = []
            for key in tool_keys:
                mobj = re.match(r"tool_(.*)_call_count", key)
                if mobj:
                    tools.append(mobj.group(1))
            print("Tools found: ", tools)

            for tool in tools:
                obj["tool_usage"][tool] = {}
                for metric in toolMetrics:
                    toolMetricKey = "tool_%s_%s" % (tool, metric)
                    obj["tool_usage"][tool][metric] = item[toolMetricKey] 


            returnVal.append(obj)

        return returnVal    




