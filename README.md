# k8s Debugger
Kubernetes Troubleshooting with Bedrock and AI Agents using MCP

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=flat&logo=kubernetes&logoColor=white)](https://kubernetes.io/)

A powerful Kubernetes debugging tool that leverages Bedrock AI Foundation Models and MCP (Model Context Protocol) to help diagnose and troubleshoot Kubernetes cluster issues through natural language interaction.

## 📋 Table of Contents
- [Introduction](#introduction)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Features](#features)
- [Usage Examples](#usage-examples)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Introduction

The K8s Debugger combines the power of Large Language Models with Kubernetes expertise to provide an intuitive debugging experience. Users can interact with their Kubernetes clusters using natural language queries, getting intelligent responses and suggestions based on their cluster's state.

## 🏗️ Architecture

![Architecture diagram](https://raw.githubusercontent.com/bdastur/k8s_debugger/refs/heads/main/docs/architecture.drawio.png "K8s Debugger Architecture Diagram")

### MCP Server
MCP Server interfaces with Kubernetes clusters to gather cluster information, and provide various tools to gather  information about:
- Pod status and health
- Node information
- Network policies
- Resource utilization
- Cluster events
- Configuration details

### MCP Client
The MCP Client:
- Interfaces with Amazon Bedrock AI Foundation Models
- Processes natural language queries
- Communicates with the MCP Server
- Formats responses for the UI

### Streamlit UI
User interface that provides:
- Interactive chat interface
- Cluster status visualization
- Debug session history
- Resource metrics display

## 📝 Prerequisites

- AWS account with Bedrock Model Access enabled.
- AWS credentials configured (~/.aws/credentials)
- Gnu Automake (simplifies docker build and run operations)
- Docker installed (if running containerized version)
- Python 3.11+ (if running locally)
- Kubernetes cluster access
- Valid kubeconfig file (~/.kube/config)

## 🚀 Installation

### Docker Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/k8s-debugger.git
cd k8s-debugger

# Build and run mcp server, client and debugger ap.

cd k8s_mcp_server
make build
make run

cd k8s_mcp_client
make build
make run

cd k8s_ui_app
make build
make run
 
```

### Local Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/k8s-debugger.git
cd k8s-debugger

# Install dependencies
pip install -r requirements.txt

# Start the components (in separate terminals)
./k8s_mcp_server.py start
./k8s_mcp_client.py start --profile <profile> --region <region> --url <mcp server url:5001/sse>
streamlit run src/app.py
```

## ⚙️ Configuration

1. Configure AWS credentials:
```bash
aws configure
```

2. Ensure your kubeconfig is properly set up:
```bash
kubectl config view
```

```

## 🎨 Features

- ✨ **Natural Language Debugging**: Ask questions about your cluster in plain English
- 🤖 **Intelligent Analysis**: Get AI-powered insights about cluster issues
- 📊 **Resource Monitoring**: Real-time monitoring of cluster resources
- 🌐 **Network Diagnostics**: Analyze network policies and connectivity issues
- ⚡ **Configuration Validation**: Identify misconfigurations and potential issues
- 🔍 **Interactive Troubleshooting**: Step-by-step guidance for complex problems
- 📖 **Historical Analysis**: Review past issues and their resolutions

## 💡 Usage Examples

```plaintext
Q: "Why is my nginx pod in CrashLoopBackOff?"
Q: "Show me all pods that are not healthy"
Q: "Check network connectivity between pod A and pod B"
Q: "Explain the current network policies in namespace 'production'"
```

## 🔒 Security

- The tool requires cluster access permissions
- Uses existing kubeconfig authentication
- AWS credentials should have minimum required permissions
- Container runs with limited privileges
- Network policies should be configured appropriately

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection Issues | Verify kubectl access and AWS credentials |
| Permission Errors | Check RBAC settings in your cluster |
| Model Errors | Ensure Bedrock API access is configured correctly |
| UI Issues | Check browser console and application logs |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

Distributed under the Apache 2.0 License. See `LICENSE` for more information.

⚠️ **Important Note:**  
The code samples are provided as is, and should not be directly used in production
environment.


---

## 🌟 Support

- Create an issue in the GitHub repository
- Check the [Wiki](link-to-wiki) for detailed documentation


## 🛣️ Roadmap

- [ ] Support for Caching cluster state
- [ ] Support for additional AI models
- [ ] Enhanced visualization capabilities
- [ ] Integration with monitoring tools
- [ ] Custom plugin support
- [ ] Multi-cluster support

## 📝 Version History

| Version | Features |
|---------|----------|
| v0.1.0 | Initial release |


---

For detailed documentation, visit our [Wiki](tba).

