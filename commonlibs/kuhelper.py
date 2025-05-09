#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import kubernetes
import os
import re
import yaml
import kubernetes.client as kclient
import kubernetes.utils as kutils
import kubernetes.dynamic as kdynamic
import commonlibs.render as render


#######################################################################
# Setup Logging.
#######################################################################
def get_logger(level=logging.INFO,
               name="Default",
               msg_format:str = '[%(asctime)s %(levelname)s]:  %(message)s',
               date_format: str = '%m-%d %H:%M',
               output_file_name: str = './output.log'):

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



class KuPods():
    def __init__(self, verbose=True):
        logLevel = logging.WARN
        if verbose:
            logLevel = logging.INFO

        self.logger = get_logger(name="KuPods", level=logLevel)
        self.kuHelper = KuHelper(verbose=True)


    def _parsePodDetails(self, podDetail):
        """
        For individual pod within a Pod list or a specific pod, parse and return
        a normalized dict after parsing the podDetails.
        """
        obj = {}
        namespace = podDetail["metadata"]["namespace"]

        obj["kind"] = podDetail["kind"]
        obj["metadata"] = {}
        obj["metadata"]["labels"] = podDetail["metadata"].get("labels", {})
        obj["metadata"]["annotations"] = podDetail["metadata"].get("annotations", {})
        obj["metadata"]["resourceVersion"] = podDetail["metadata"]["resourceVersion"]

        obj["name"] = podDetail["metadata"]["name"]
        obj["namespace"] = namespace

        obj["total_container_count"] = 0

        obj["containers"] = []
        for container in podDetail["spec"]["containers"]:
            obj2 = {}
            obj2["name"] = container["name"]
            obj2["image"] = container["image"]
            obj2["imagePullPolicy"] = container["imagePullPolicy"]
            obj2["resources"] = container["resources"]
            obj2["ports"] = container.get("ports", [])
            obj2["volumeMounts"] = container["volumeMounts"]

            # Get container status.
            if podDetail["status"].get("containerStatuses", None) is not None:
                for contStatus in podDetail["status"]["containerStatuses"]:
                    if contStatus["name"] == container["name"]:
                        obj2["state"] = contStatus["state"]
                        break

            obj["containers"].append(obj2)
            obj["total_container_count"] += 1

        if podDetail["status"].get("conditions", None) is not None:
            obj2["pod_status"] = podDetail["status"]["conditions"]

        obj["nodeName"] = podDetail["spec"].get("nodeName", "Not Set")
        obj["nodeSelector"] = podDetail["spec"].get("nodeSelector", "Not Set")

        return obj


    def getPodsInformation(self, podName=None, namespace=None):
        results = {}
        self.logger.info("getPodsInfo [%s] [%s]", podName, namespace)

        ret = self.kuHelper.getResource(resourceType="pod", resourceName=podName, namespace=namespace)

        results["kind"] = ret["kind"]
        results["items"] = []
        results["summary"] = {
            "total_pod_count": 0,
            "pods_count_by_namespace": {}
        }

        if ret["kind"] == "Pod":
            podDetails = self._parsePodDetails(ret)
            results["items"].append(podDetails)
            results["total_pod_count"] = 1
            namespace = ret["metadata"]["namespace"]
            results["summary"]["pods_count_by_namespace"][namespace] = 1

            return results

        perNamespaceCount = {}
        for item in ret["items"]:
            namespace = item["metadata"]["namespace"]

            obj = {}
            obj = self._parsePodDetails(item)

            try:
                perNamespaceCount[namespace] += 1
            except KeyError:
                perNamespaceCount[namespace] = 1

            results["items"].append(obj)
            results["summary"]["total_pod_count"] += 1

        results["summary"]["pods_count_by_namespace"] = perNamespaceCount

        return results



class KuNetworkPolicy():
    """
    Kubernetes Network Policy Handler.
    ---------------------------------

    Network Policies allow you to control traffic flow at IP address or port
    level for TCP, UDP and SCTP protocols.

    Pod Isolation:
    * Two types of isolation for pods. for ingress and for egress.
   
    Egress:
    * By default pod is non-isolated for egress. All outbound connections are allowed.
    * A pod is isolated for egress if there is a NetworkPolicy that bot selects
      the pod and has "Egress" in the PolicyTypes.
    * When a pod is isolated for egress; the only allowed connections from the pod
      are those allowed by the egress list. Reply traffic for those allowed connections
      will also be implicitly allowed.
    * The effects of those egress lists combine additively.

    Ingress:
    * By default a pod is not isolated for ingress. All inbound connections are allowed.
    * A pod is isolated for ingress, if there is any NetworkPolicy that both selects
      the pod and has "Ingress" in its policyTypes. 
    * When a pod is isolated for ingress, the only allowed connections into the pod
      are those from the pod's node and those allowed by ingress list of the Network
      Policy. Reply traffic will be allowed implicitly.

    * Network policies are additive in nature.

    NetworkPolicy Anatomy.
    ---------------------
    apiVersion: networking.k8s.io/v1
    kind: NetworkPolicy
    metadata:
      name: <policy name>
      namespace: <optional> - If unspecified will be created in current namespace.
    spec:
      podSelector:     <Specifies which pod the policy applies to. 
                        If not specified will apply to all pods>
      namespaceSelector:  <Specifies which namespace policy applies to. 
                           If empty but specified will apply to all namespace>
                           If namespaceSelector is omitted, the policy's scope is 
                           limited to the namespace where the policy is defined

      policyTypes:
        - Ingress
        - Egress
    ingress:
    - from:
        - namespaceSelector: Specify which namespace will be allowed.
          podSelector: Specify the pods that will be allowed.
    egress:
    - to:
        - ipBlock: Which ip addr/range to allow eg: (cidr: 10.0.1.0/26)



    """
    def __init__(self, verbose=True):
        logLevel = logging.WARN
        if verbose:
            logLevel = logging.INFO

        self.logger = get_logger(name="KuNetworkPolicy", level=logLevel)
        self.kuHelper = KuHelper(verbose=True)

    def getNetworkPolicyDetails(self):
        """
        Get Netwokr policy details. This API will simply cleanup the network policies
        removing unwanted metadata etc.
        """
        results = {}

        self.logger.info("getNetworkPolicyDetails ")

        ret = self.kuHelper.getResource(resourceType="networkpolicy", resourceName=None, namespace=None)

        results["kind"] = ret["kind"]
        results["items"] = []

        for item in ret["items"]:
            obj = {}
            obj["name"] = item["metadata"]["name"]
            obj["namespace"] = item["metadata"]["namespace"]
            obj["resourceVersion"] = item["metadata"]["resourceVersion"]
            obj["spec"] = item["spec"]

            results["items"].append(obj)

        return results


    def getNetworkPolicyDetailsVerbose(self):
        """
        Get Network policy details. Here we will get network policy from all namespaces
        in the cluster.
        """

        results = {}
        self.logger.info("getNetworkPolicyDetails ")

        ret = self.kuHelper.getResource(resourceType="networkpolicy", resourceName=None, namespace=None)


        results["kind"] = ret["kind"]
        results["items"] = []

        for item in ret["items"]:
            obj = {}
            obj["name"] = item["metadata"]["name"]
            obj["namespace"] = item["metadata"]["namespace"]
            obj["resourceVersion"] = item["metadata"]["resourceVersion"]

            results["items"].append(obj)
            keys = item["spec"]

            # Check if podSelector is configured.
            if "podSelector" in item["spec"]:
                podSelector = item["spec"]["podSelector"]
                if not podSelector:
                    obj["applied_to_pods"] = "Applied to All pods"
                else:
                    matchLabels = item["spec"]["podSelector"]["matchLabels"]
                    obj["applied_to_pods"] = "That match the labels: %s" % matchLabels


            # Check if namespaceSelector is configured.
            if "namespaceSelector" in item["spec"]:
                namespaceSelector = item["spec"]["namespaceSelector"]
                if not namespaceSelector:
                    obj["applied_to_entities_in_namespace"] = "Applies to all namespaces"
                else:
                    matchLabels = item["spec"]["namespaceSelector"]["matchLabels"]
                    obj["applied_to_entities_in_namespace"] = "That match with labels: %s" % matchLabels
            else:
                obj["applied_to_entities_in_namespace"] = item["metadata"]["namespace"]

            # Check for ingress rules.
            if "ingress" in item["spec"]:
                obj["connection_allowed_from_pods"] = []
                obj["connection_allowed_from_namespaces"] = []
                obj["connection_allowed_to_specific_ports"] = []
                if not item["spec"]["ingress"]:
                    # If Ingress rule is empty, no connections are allowed.
                    obj["connection_allowed_from_pods"] = ["No connections from outside the namespace are allowed"]
                    obj["connection_allowed_from_namespaces"] = ["No connections from outside the namespace are allowed"]
                else: 
                    ingressRules = item["spec"]["ingress"]
                    for rule in ingressRules:
                        print("BRD: Rule in ingress Rules: ", rule)
                        fromRules = rule["from"]
                        for fromRule in fromRules:
                            if "podSelector" in fromRule:
                                podSelector = fromRule["podSelector"]
                                if not podSelector:
                                    obj["connection_allowed_from_pods"].append("Connections allowed from all pods within a namespace")
                                else:
                                    matchLabels = podSelector["matchLabels"]
                                    obj["connection_allowed_from_pods"].append("That match the labels %s" % matchLabels)

                            if "namespaceSelector" in fromRule:
                                namespaceSelector = fromRule["namespaceSelector"]
                                matchLabels = namespaceSelector["matchLabels"]
                                obj["connection_allowed_from_namespaces"].append("that match the labels %s" % matchLabels)

                        portsRule  = rule.get("ports", None)
                        if portsRule:
                            #{'ports': [{'protocol': 'TCP', 'port': 80}, {'protocol': 'TCP', 'port': 443}], 'from': [{'podSelector': {}}]}
                            for rule in portsRule:
                                obj["connection_allowed_to_specific_ports"].append("Protocol : %s, port: %d" % (rule["protocol"], rule["port"]))
                        else:
                            obj["connection_allowed_to_specific_ports"].append("Connection not restricted to any port")
            else:
                obj["connection_allowed_from_pods"] = ["No connections are allowed into the pod"]
                obj["connection_allowed_from_namespaces"] = ["No connections are allowed into the pod"]
                obj["connection_allowed_to_specific_ports"] = ["No connections are allowed into the pod"]

            # Check for egress rules.
            if "egress" in item["spec"]:
                obj["egress_to_external_entity"] = []
                if not item["spec"]["egress"]:
                    # If egress rule is empty, no connections egress are allowed.
                    obj["egress_to_external_entity"].append("No egress connections are allowed")
                else:
                    egressRules = item["spec"]["egress"]
                    for rule in egressRules:
                        print("BRD: Rule in egress Rules: ", rule) 
                        toRules = rule["to"]
                        for toRule in toRules:
                            if "podSelector" in toRule:
                                podSelector = toRule["podSelector"]
                                if not podSelector:
                                    obj["egress_to_external_entity"].append("Egress connect allowed to all pods within a namespace")
                                else:
                                    matchLabels = podSelector["matchLabels"]
                                    obj["egress_to_external_entity"].append("Egress connect allowed to pods with label %s" % matchLabels)

                            if "namespaceSelector" in toRule:
                                namespaceSelector = toRule["namespaceSelector"]
                                matchLabels = namespaceSelector["matchLabels"]
                                obj["egress_to_external_entity"].append("Egress connect allowed to namespaces with label %s" % matchLabels)

            else:
                obj["egress_to_external_entity"] = ["Egress connections are not blocked"]


            """
            for key in item["spec"]:
                # Check if podspec is configured.
                print("policy: ", item["spec"][key])
                if key == "ingress":
                    # Parse the list of ingress policies.
                    for ingressPolicy  in item["spec"]["ingress"]:
                        print("Val: ", ingressPolicy)
                        # {'from': [{'podSelector': {'matchLabels': {'app': 'far-1'}}, 'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': 'test-namespace'}}}]}
                        for policy in ingressPolicy["from"]:
                            print("policy from: ", policy)
                            if policy.get("podSelector", None) is not None:
                                obj["allow_traffic_from_pods"] = policy["podSelector"] 

                            if policy.get("namespaceSelector", None) is not None:
                                obj["allow_traffic_from_namespace"] = policy["namespaceSelector"]

            """




        return results



class KuHelper():
    def __init__(self, verbose=True):

        logLevel = logging.WARN
        if verbose:
            logLevel = logging.INFO

        self.logger = get_logger(name="Kuhelper", level=logLevel)
        self._authenticate()
        self.client = kclient.ApiClient()

    def _authenticate(self):
        kubernetes.config.load_config()

    def _getResourceKind(self, resourceType: str) -> str:
        """Get resource kind from type"""
        kinds = {
            'pod': 'Pod',
            'node': "Node",
            'deployment': 'Deployment',
            'service': 'Service',
            'ingress': 'Ingress',
            'configmap': 'ConfigMap',
            # amazonq-ignore-next-line
            # amazonq-ignore-next-line
            'secret': 'Secret',
            'namespace': 'Namespace',
            'persistentvolumeclaim': 'PersistentVolumeClaim',
            'persistentvolume': 'PersistentVolume',
            'statefulset': 'StatefulSet',
            'daemonset': 'DaemonSet',
            'job': 'Job',
            'cronjob': 'CronJob',
            'networkpolicy': 'NetworkPolicy',
            'resourcequota': 'ResourceQuota'
        }
        return kinds.get(resourceType.lower(), resourceType.capitalize())

    def _getApiVersion(self, resourceType: str) -> str:
        """Get API version for resource type"""
        apiVersions = {
            'pod': 'v1',
            'node': 'v1',
            'deployment': 'apps/v1',
            'service': 'v1',
            'ingress': 'networking.k8s.io/v1',
            'configmap': 'v1',
            # amazonq-ignore-next-line
            'secret': 'v1',
            'namespace': 'v1',
            'persistentvolumeclaim': 'v1',
            'persistentvolume': 'v1',
            'statefulset': 'apps/v1',
            'daemonset': 'apps/v1',
            'job': 'batch/v1',
            'cronjob': 'batch/v1',
            'networkpolicy': 'networking.k8s.io/v1',
            'resourcequota': 'v1'
        }
        return apiVersions.get(resourceType.lower(), 'v1')

    def createResourceFromResourceSpec(self, resourceSpec):
        self.logger.info("CreateResourceFromSpec: ", resourceSpec)

        try:
            ret = kutils.create_from_dict(self.client, resourceSpec)
        except kutils.FailToCreateError as err:
            self.logger.error("Failed to create resource [%s]", err)
            return None

        return ret

    def createResourceFromTemplate(self, template, **spec):
        data = json.loads((render.renderJ2TemplateFile(template, "..", **spec)))
        self.logger.info(data)

        try:
            ret = kutils.create_from_dict(self.client, data)
        except kutils.FailToCreateError as err:
            self.logger.error("Failed to create namespace [%s]", err)
            return None

        return ret

    def getResource(self,
                    resourceType:str = None,
                    resourceName:str = None,
                    namespace:str =None):
        """
        Get the Kubernetes resource.
        """
        assert resourceType is not None

        dynamicClient = kdynamic.DynamicClient(self.client)

        resourceKind = self._getResourceKind(resourceType)
        apiVersion = self._getApiVersion(resourceType)

        resource = dynamicClient.resources.get(
            api_version=apiVersion,
            kind=resourceKind
        )

        try:
            if namespace:
                if resourceName:
                    ret = resource.get(name=resourceName, namespace=namespace)
                else:
                    ret = resource.get(namespace=namespace)
            else:
                if resourceName:
                    ret = resource.get(name=resourceName)
                else:
                    ret = resource.get()
        except kclient.rest.ApiException as e:
            if e.status == 404:
                self.logger.warning(
                    f"Resource '{resourceName}' of type '{resourceType}' "
                    f"{'in namespace ' + namespace if namespace else ''} does not exist."
                )
                return None
            else:
                raise

        # Return a dict.
        return ret.to_dict()

    def deleteResource(self,
                       resourceType:str,
                       resourceName:str,
                       namespace=None,
                       force:bool=False):
        #client = kclient.ApiClient()

        dynamicClient = kdynamic.DynamicClient(self.client)

        resourceKind = self._getResourceKind(resourceType)
        apiVersion = self._getApiVersion(resourceType)

        resource = dynamicClient.resources.get(
            api_version=apiVersion,
            kind=resourceKind
        )

        ret = self.getResource(resourceType, resourceName, namespace)
        if ret is None:
            return

        # Delete options
        deleteOptions = kclient.V1DeleteOptions(
            propagation_policy="Foreground",
            grace_period_seconds=5)


        # Delete the resource
        if namespace:
            resource.delete(
                name=resourceName,
                namespace=namespace,
                body=deleteOptions
            )
        else:
            resource.delete(
                name=resourceName,
                body=deleteOptions
            )

        self.logger.info(
            f"Resource '{resourceName}' of type '{resourceType}' "
            f"{'in namespace ' + namespace if namespace else ''} deletion initiated."
        )


    def listKubeConfigClusters(self):
        # Get the path to kubeconfig file
        kubeconfig_path = os.path.expanduser('~/.kube/config')
        clusters = []
        currentContext = ""
        try:
            # Load the kubeconfig file
            with open(kubeconfig_path, 'r') as file:
                kubeconfig = yaml.safe_load(file)

            # Extract and display cluster information
            print("\nClusters in kubeconfig:")
            print("-" * 50)

            # Display current context
            if 'current-context' in kubeconfig:
                print(f"\nCurrent Context: {kubeconfig['current-context']}")
                mobj = re.match(r".*:cluster/(.*)", kubeconfig["current-context"])
                if mobj:
                    currentContext = mobj.group(1)

            for cluster in kubeconfig['clusters']:
                cluster_name = cluster['name']
                mobj = re.match(r"arn:aws:eks:(.*):(.*):cluster/(.*)", cluster_name)
                if mobj:
                    clusterInfo = {}
                    clusterInfo["region"] = mobj.group(1)
                    clusterInfo["account"] = mobj.group(2)
                    clusterInfo["clusterName"] = mobj.group(3)
                    clusterInfo["currentContext"] = False
                    if currentContext == clusterInfo["clusterName"]:
                        clusterInfo["clusterName"] += " (current)"
                        clusterInfo["currentContext"] = True

                    clusters.append(clusterInfo)

                cluster_server = cluster['cluster']['server']
                print(f"Cluster Name: {cluster_name}")
                print(f"Server: {cluster_server}")
                print("-" * 50)
        except FileNotFoundError:
            print(f"Error: Kubeconfig file not found at {kubeconfig_path}")
        except yaml.YAMLError as e:
            print(f"Error parsing kubeconfig file: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

        return clusters

    def createNamespace(self, **spec):
        """
        Create a Namespace.

        @params:
        spec: dict - Specification for the namespace creation.

        Example Spec:
          {
              "name": <name>,
              "labels": {
                "foo": "value",
                "bar": "value"
              },
              "annotations": {
                "afoo": "value",
                "abar": "value"
              }
          }
        """
        namespaceTemplate = "kutemplates/namespace.json.j2"

        ret = self.createResourceFromTemplate(namespaceTemplate, **spec)
        return ret


    def createResourceQuota(self, **spec):
        """
        Create Resource Quotas

        @params:
        spec:
        {
          "name": <resource quota name>,
          "namespace": <namespace to be applied to>
          "requests": {
             "cpu": 2,
             "memory": 2Gi
          },
          "limits": {
             "cpu": 4,
             "memory": 4Gi
          },
          "pods": 10
        }

        """
        resourceQuotaTemplate = "kutemplates/resourceQuota.json.j2"

        ret = createResourceFromTemplate(resourceQuotaTemplate, **spec)
        return ret

    def _addMetadataLabels(self, resourceSpecObject, **spec):
        """
        Add the metadata section to the resource.
        """
        metadata = {
            "labels": {
                "createdBy": "KuBot"
            },
            "annotations": {
                "createdBy": "KuBot"
            }
        }


"----------------------------------------------------------"


