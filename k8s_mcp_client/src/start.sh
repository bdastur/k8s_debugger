#!/bin/bash 

echo "Bash Template"

echo "profile: $profile"
echo "region: $region"


./k8s_mcp_client.py start --profile $profile --region $region --url http://k8s_mcp_server:5001/sse 


