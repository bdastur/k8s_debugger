#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
K8s Debugger MCP Server.
-------------------------

The server provides basic constructs to get pod, node, network policy and other
kubernetes resources as tools, which can be used by the MCP Client and LLM to perform
K8s diagnostic and troubleshooting operations.

This server will use Kubernetes module to interface with a provided kubernetes
server.


Example Usage:
--------------
./kagent_server.py start --port 5001

"""

import click
import json
import mcp.server
import mcp.server.fastmcp as fastmcp
from typing import List, Dict, Any
import commonlibs.kuhelper as kuhelper


mcp = fastmcp.FastMCP()

@mcp.tool()
def get_namespace_information(namespace:str):
    """
    Return information regarding Namespaces in a kubernetes cluster.

    @parms:
        namespace: (Optional) Name of the namespace to return.

    @returns:
        namespaceInfo: A json object with namespace information
    """
    print("BRD: here called 4")

    result = {
        "result": {}
    }

    if not namespace.strip():
        namespace = None

    print("Get Namespace Information: [namespace: %s]" %(namespace))
    kObj = kuhelper.KuHelper(verbose=False)

    ret = kObj.getResource(resourceType="namespace", resourceName=namespace)

    result["result"] = ret
    jData = json.dumps(result)

    return jData


@mcp.tool()
def get_pods_information(podName:str , namespace:str):
    """
    Return information regarding pods in a Kubernetes cluster.

    @parms:
        podName: (optional) Name of the pod. If not specified it return all pods.
        namespace: (Optional) Namespace to get the pods. If not specific, get pods from all namespaces.

    @returns:
        podInfo : A json object with pod information.
    """
    result = {
        "result": {}
    }
    print("Get Pod Information: [podname: %s], [namespace: %s]" %(podName, namespace))

    if podName and podName == "None":
        print("Pod name is not None")
        podName = None

    if namespace and namespace == "None":
        print("Namespace is not none")
        namespace = None

    kPod = kuhelper.KuPods(verbose=True)

    ret = kPod.getPodsInformation(podName=podName, namespace=namespace)

    result["result"] = ret
    jData = json.dumps(result)
    return jData


@mcp.tool()
def get_nodes_information(nodeName:str = None):
    """
    Return information regarding Nodes/Hosts in a Kubernetes cluster.

    @parms:
        nodeName: (optional) Name of the host or node If not specified return all nodes

    @returns:
        nodeInfo: A json object with node information.
    """
    result = {
        "result": {}
    }
    print("Get Node Information: [nodeName: %s]" %(nodeName))
    kObj = kuhelper.KuHelper(verbose=False)
    ret = kObj.getResource(resourceType="node", resourceName=nodeName)

    result["result"] = ret
    jData = json.dumps(result)

    return jData


@mcp.tool()
def get_network_policy_information():
    """
    Return information regarding configured network policies in the Kubernetes cluster.
    Network policies will tell you which pods can communicate to which pods through 
    ingress policy rules and which pods can send traffic to other pods through egress policy 

    @parms:
        There are no parameters. 

    @returns:
        Network policy Information : A json object with network policy information.
    """
    result = {
        "result": {}
    }
    print("Get Network Policy Information: " )

    kNw = kuhelper.KuNetworkPolicy()
    ret = kNw.getNetworkPolicyDetails()

    result["result"] = ret
    jData = json.dumps(result)
    return jData


@mcp.tool()
def create_or_update_k8s_resource(resourceSpec:str):
    """
    The Tool is used to create or update a Kubernetes resource like pod, network policy,
    deployment specs etc.

    @params:
        resourceSpec: (Required) A resource specification (JSON format) for the resource that should be created.

    @returns:
        returns sttus.

    NOTE: This is still WIP.
    """
    result = {
        "result": {}
    }
    print("Create/Update Resource. ")

    kuObj = kuhelper.KuHelper()
    ret = kuObj.createResourceFromResourceSpec(resourceSpec)
    result["result"] = ret
    jData = json.dumps(result)
    return jData


@click.group()
def cli():
    pass

@cli.command()
@click.option("--port", type=int, help="Server Listener Port", required=True, default=5001)
def start(port):
    print("MCP Server starting on port %d" % port)
    mcp.settings.port = port
    mcp.run(transport="sse")

def main():
    cli()

if __name__ == '__main__':
    main()
