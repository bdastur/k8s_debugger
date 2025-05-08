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

import asyncio
import click
import os
import time
import commonlibs.bedrock_helper as bedrock_helper


@click.group()
def cli():
    pass


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
@click.option("--url", type=str, help="MCP Server URL (http://< addr>:<port>/sse", required=True)
def start(profile, region, url):
    """
    Start the Application that uses the MCP Client library.

    @params:
    profile: Profile name
    region: region name
    url: MCP Server url (example: http://mcp-server-lb-1822128806.us-east-1.elb.amazonaws.com:5001/sse)
    """
    async def executeLoop(profile, region, url):
        systemInstructions = """
        [purposeSummary] You are a skilled kubernetes operation agent. You have the tools necessary to get specific details from a kubernetes cluster. You will use these tools and return the right information to the users.[/purposeSummary] [instructions] Users will ask you to retrive information for the kubernetes cluster. You will use the tools to get the results. The results from the tool will be in json format, so you will need to parse it to get the right information. 1. For pod information, always specify the namespace and status along with the pod name. 1.1 If asked to get a count of pods, specify the namespaces and the pod count in the namespaces, your output should be in the format n pods in xyz namespace, y pods in xyz namespace, total n pods. 2. For information regarding pod to pod communication, networking, you will get the network policy information. You will check if network policies allow access to ingress/egress to the pod to make an assessment if it can communicate with another pod. 3. A user may ask you to fix the issue or provide guidance on how to fix. Before you run any create/update operations, always show the changes to the user and get confirmation before executing[/instructions]
        """
        mcpClient = bedrock_helper.MCPClient(profileName=profile, regionName=region, systemInstructions=systemInstructions, verbose=True)

        inputFile = "/tmp/k8sinput.txt"
        outputFile = "/tmp/k8sresponse.txt"
        try:
            tools = await mcpClient.connectMCPServer(serverUrl=url)
            while True:
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
                    response = await mcpClient.processQuery(query, tools)
                    finalResponse = responseParser(response)
                    print("Response: ", finalResponse)
                    with open(outputFile, "w") as outFile:
                        outFile.write(finalResponse)

                    time.sleep(3)

                except Exception as e:
                    print(f"\nError: {str(e)}")
        finally:
            await mcpClient.cleanup()
    asyncio.run(executeLoop(profile, region, url))



def main():
    cli()


if __name__ == '__main__':
    main()


