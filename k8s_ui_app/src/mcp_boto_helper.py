#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time



def requestResponse(query):
    """
    Invoke the MCP Client helper 
    """
    pipeStage = "/tmp/mcp"
    inputFile = os.path.join(pipeStage, "k8sinput.txt")
    outputFile = os.path.join(pipeStage, "k8sresponse.txt")

    if not os.path.exists(pipeStage):
        os.makedirs(pipeStage)
        print("Create pipe staging directory")


    with open(inputFile, "w") as outFile:
        print("Writing query to file [%s]" % inputFile)
        outFile.write(query)
        outFile.flush()

    if not os.path.exists(inputFile):
        print("File %s does not exist" % inputFile)

    print("File exists %s" % inputFile)
     
    count = 10
    while count > 0:
        print("Waiting for response", count)
        time.sleep(2)
        count -= 1

        if not os.path.exists(outputFile):
            continue

        if os.path.getsize(outputFile) == 0:
            continue

        with open(outputFile, "r") as inFile:
            response = inFile.read()

        print("Removed outputfile")
        os.remove(outputFile)

        print("Response returned: ", response)
        return response

    # Return standard response.
    return "MCP Client did not respond within the time limit"
        
