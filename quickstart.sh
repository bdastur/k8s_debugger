##!/bin/bash 

echo "Build and Start the MCP Server, CLient and UI app"

rootDir=$(pwd)
serverDir="k8s_mcp_server"
clientDir="k8s_mcp_client"
appDir="k8s_ui_app"


# Stop any containers already running.
docker rm -f k8s_mcp_server k8s_mcp_client k8s_debugger_app

cd ${serverDir}
make build
make run

cd ${rootDir}
cd ${clientDir}
make build
make run

cd ${rootDir}
cd ${appDir}
make build
make run


docker ps
