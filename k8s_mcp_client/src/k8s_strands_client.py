#!/usr/bin/env python
# -*- coding: utf-8 -*-



"""
Example Usage:
%~> ./example_client_ecs_server.py start --profile brd3 --region us-east-1 --url http://mcp-server-lb-1822128806.us-east-1.elb.amazonaws.com:5001/sse
Get Logger: McpClient
Get Logger: BedRockHandler

Connected to server:  http://mcp-server-lb-1822128806.us-east-1.elb.amazonaws.com:5001/sse
    tools available : ['calculate']
Query: add 9 and 44
Response is:  <thinking>The 'calculate' tool has returned the result of the addition of 9 and 44, which is 53.0. I can now provide this result to the user.</thinking>

The result of adding 9 and 44 is 53.0.
Query: multiply 43 and 4949
Response is:  <thinking>The 'calculate' tool has returned the result of the multiplication of 43 and 4949, which is 212807.0. I can now provide this result to the user.</thinking>

The result of multiplying 43 and 4949 is 212807.0.
Query: q

"""

import click
import os
import time
import boto3
import mcp.client.sse as sse
import mcp.client.streamable_http as streamable_http
import commonlibs.strands_helper as strands_helper
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from strands.telemetry.tracer import get_tracer
import strands.models as models
import pprint



# Configure the tracer
tracer = get_tracer(
    service_name="k8s_stands_agent",
    otlp_endpoint="http://localhost:4318",
    otlp_headers={"Authorization": "Bearer TOKEN"},
    enable_console_export=True  # Helpful for development
)


@click.group()
def cli():
    pass


def createMcpClient(url, transport):

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

    mcpClient = MCPClient(createTransport)

    return mcpClient


def responseParser(response):
    """
    Take the raw json result and parse it for easier visualization, as well as dong
    post operations.
    """
    print("raw response: ", response)
    finalResult = response
    """
    try:
        finalResult = response.split("</thinking>")[1]
    except IndexError:
        finalResult = response
    """

    return finalResult



@cli.command()
@click.option("--profile", type=str, help="Profile Name", required=True)
@click.option("--region", type=str, help="Region Name", default="us-east-1")
@click.option("--transport", type=click.Choice(["sse", "streamable-http"]), help="MCP Transport",
              required=True, default="sse")
@click.option("--url", type=str, help="MCP Server URL (http://< addr>:<port>/sse", required=True)
def start(profile, region, transport, url):
    """
    Start the Application that uses the MCP Client library.

    @params:
    profile: Profile name
    region: region name
    url: MCP Server url (example: http://mcp-server-lb-xxxxxxxxxx.us-east-1.elb.amazonaws.com:5001/sse)
    """
    systemInstructions = """
    [purposeSummary] You are a skilled kubernetes operation agent. You have the tools necessary to get specific details from a kubernetes cluster. You will use these tools and return the right information to the users.[/purposeSummary] [instructions] Users will ask you to retrive information for the kubernetes cluster. You will use the tools to get the results. The results from the tool will be in json format, so you will need to parse it to get the right information. 1. For pod information, always specify the namespace and status along with the pod name. 1.1 If asked to get a count of pods, specify the namespaces and the pod count in the namespaces, your output should be in the format n pods in xyz namespace, y pods in xyz namespace, total n pods. 2. For information regarding pod to pod communication, networking, you will get the network policy information. You will check if network policies allow access to ingress/egress to the pod to make an assessment if it can communicate with another pod. 3. A user may ask you to fix the issue or provide guidance on how to fix. Before you run any create/update operations, always show the changes to the user and get confirmation before executing[/instructions]
        """


    pipeStage = "/tmp/mcp"
    inputFile = os.path.join(pipeStage, "k8sinput.txt")
    outputFile = os.path.join(pipeStage, "k8sresponse.txt")

    if not os.path.exists(pipeStage):
        os.makedirs(pipeStage)
        print("Create pipe staging directory")

    botoSession = boto3.Session(region_name=region, profile_name=profile)

    bedrockModel = models.BedrockModel(
        model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        boto_session=botoSession,
        temperature=0.3)

    mcpClient = createMcpClient(url, transport)

    with mcpClient:
        # Get the tools from the MCP server
        tools = mcpClient.list_tools_sync()

        simpleAgent = Agent(model=bedrockModel,
            tools=tools,
            system_prompt=systemInstructions)

        while True:
            time.sleep(3)
            try:
                # Read the input file.
                if not os.path.exists(inputFile):
                    continue

                if os.path.getsize(inputFile) == 0:
                    continue

                with open(inputFile, "r") as inFile:
                    query = inFile.read()

                print("Query read: ", query)
                os.remove(inputFile)

                if query.lower() in ["quit", "q"]:
                    break

                response = simpleAgent(query)
                finalResponse = responseParser(response)
                pp = pprint.PrettyPrinter()
                pp.pprint(response.metrics)
                print("Dir: ", dir(response.metrics))
                #print(response.metrics.get_summary())

                with open(outputFile, "w") as outFile:
                    outFile.write(str(finalResponse))
            except Exception as e:
                print(f"\nError: {str(e)}")



def main():
    cli()


if __name__ == '__main__':
    main()


